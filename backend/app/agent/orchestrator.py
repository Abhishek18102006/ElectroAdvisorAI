import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.agent.state import StateManager
from app.agent.extractor import RequirementsExtractor
from app.agent.tools import search_catalog_controlled
from app.agent.filter_rank import FilterAndRankingEngine
from app.agent.explainer import RecommendationExplainer
from app.schemas.agent import AgentDecision, RecommendationItem, TradeOffComparison
from app.schemas.product import ProductResponse

logger = logging.getLogger(__name__)


class SalesAgentOrchestrator:
    """
    Central orchestration engine for the AI Sales Assistant.
    Follows a strict decision graph:
    1. Extract new/updated requirements from customer utterance.
    2. Maintain and track conversation state across turns.
    3. Determine if sufficient information exists for recommendation.
    4. If missing critical info -> Ask focused, non-repetitive follow-up question.
    5. If sufficient info -> Search database using controlled tools, filter by hard constraints,
       rank using soft preferences, and deliver top-2 recommendations with trade-offs.
    """

    @classmethod
    async def process_turn(
        cls,
        db: Session,
        customer_message: str,
        conversation_history: List[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> AgentDecision:
        msg_clean = customer_message.strip()
        lower_msg = msg_clean.lower()

        # Check for simple greeting when no requirements exist yet
        greetings = ["hi", "hello", "hey", "good morning", "good evening", "greetings"]
        is_pure_greeting = lower_msg in greetings or (len(msg_clean.split()) <= 2 and any(lower_msg.startswith(g) for g in greetings))
        if is_pure_greeting and not current_state.get("primary_uses") and not current_state.get("budget_max"):
            state = StateManager.update_state(current_state, {"last_intent": "greeting"})
            return AgentDecision(
                action="greeting",
                message=(
                    "Hello! Welcome to our electronics store. I'm your AI sales assistant. "
                    "Are you looking for a laptop, smartphone, tablet, monitor, or headphones today? "
                    "Tell me what you need it for, and I'll find the best options for you."
                ),
                state=state,
            )

        # 1. Natural Language Extraction (LLM or Rule-based)
        extracted_patch = await RequirementsExtractor.extract_requirements(
            customer_message=msg_clean,
            conversation_history=conversation_history,
            current_state=current_state,
        )

        # 2. State tracking: Update state while preserving previous context
        state = StateManager.update_state(current_state, extracted_patch)

        # 3. Decision Logic: Has Enough Info?
        category = state.get("category", "laptop")
        primary_uses = state.get("primary_uses", [])
        budget_max = state.get("budget_max")
        clarifications = state.get("clarifications_asked", [])
        preferences = state.get("preferences", {})

        # Scenario A: Primary use is completely missing
        if not primary_uses:
            question = (
                "What will you mainly use it for: general coursework, programming, "
                "gaming, creative work, or machine learning?"
            )
            state["clarifications_asked"].append(question)
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["primary_use"],
                state=state,
            )

        # Scenario B: Machine learning is selected, but local vs cloud is ambiguous AND budget is missing
        if "machine_learning" in primary_uses and "ml_environment" not in preferences and budget_max is None:
            question = "What is your approximate budget? And do you need to run models locally, or will you mostly use cloud platforms?"
            state["clarifications_asked"].append(question)
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["budget", "ml_environment"],
                state=state,
            )

        # Scenario C: Budget is missing (customer mentioned uses, but didn't state budget)
        if budget_max is None:
            question = "What is your approximate budget for this purchase?"
            state["clarifications_asked"].append(question)
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["budget"],
                state=state,
            )

        # Scenario D: Machine learning is selected, budget is known, but local vs cloud is ambiguous
        # BUT only if user hasn't explicitly specified dedicated GPU or local, and hasn't answered yet!
        has_gpu_requirement = state.get("hard_constraints", {}).get("requires_gpu") is True
        has_ml_env = "ml_environment" in preferences and preferences["ml_environment"] != "pending"

        if (
            "machine_learning" in primary_uses
            and not has_ml_env
            and not has_gpu_requirement
            and "ml_environment" not in [c.lower() for c in clarifications]
        ):
            question = "Will you be training models locally (requiring a dedicated GPU), or running them primarily on cloud platforms like Google Colab or Kaggle?"
            state["clarifications_asked"].append(question)
            state["preferences"]["ml_environment"] = "pending"
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["ml_environment"],
                state=state,
            )

        # 4. WE HAVE ENOUGH INFORMATION TO MAKE A SOUND RECOMMENDATION!
        # Step A: Retrieve eligible products from database using controlled query tool
        candidate_products = search_catalog_controlled(
            db=db,
            category=category,
            limit=50,
        )

        # Step B: Filter products against mandatory hard constraints
        eligible_products, violations = FilterAndRankingEngine.filter_hard_constraints(
            products=candidate_products,
            state=state,
        )

        # Step C: Handle zero match case
        if not eligible_products:
            explanation = RecommendationExplainer.generate_no_match_explanation(state, violations)
            return AgentDecision(
                action="no_match",
                message=explanation,
                missing_info=[],
                recommendations=[],
                trade_offs=[],
                state=state,
            )

        # Step D: Rank remaining eligible products based on soft preferences & compute needs
        top_ranked = FilterAndRankingEngine.rank_and_select_top2(
            eligible_products=eligible_products,
            state=state,
        )

        # Step E: Generate spec-accurate recommendation items and trade-off comparison
        recommendation_items: List[RecommendationItem] = []
        for prod, score, _ in top_ranked:
            item = RecommendationExplainer.generate_recommendation_item(prod, score, state)
            recommendation_items.append(item)

        trade_offs: List[TradeOffComparison] = []
        if len(top_ranked) >= 2:
            trade_offs = RecommendationExplainer.generate_trade_offs(
                top_ranked[0][0],
                top_ranked[1][0],
                state,
            )

        # Step F: Craft final conversational message
        p1 = top_ranked[0][0]
        p2 = top_ranked[1][0] if len(top_ranked) > 1 else None

        summary_msg = [
            f"Based on your requirements ({', '.join(primary_uses).replace('_', ' ')} within ₹{budget_max:,.0f}"
            + (", prioritizing portability for campus" if preferences.get("portability") else "")
            + "), I searched our database and selected the two most suitable models for you:\n"
        ]

        summary_msg.append(f"1. **{p1.name}** (₹{p1.price:,.0f}) - {recommendation_items[0].why_recommended}")
        if p2:
            summary_msg.append(f"2. **{p2.name}** (₹{p2.price:,.0f}) - {recommendation_items[1].why_recommended}")
            summary_msg.append(
                f"\n⚖️ **Key Trade-off:** {p1.name} gives you {p1.specs.get('gpu', 'solid performance')} at {p1.specs.get('weight_kg', 2.0)}kg, "
                f"while {p2.name} gives you {p2.specs.get('weight_kg', 2.0)}kg portability and {p2.specs.get('battery_life_hours', 6)}h battery life."
            )

        state["recommended_product_ids"] = [p[0].id for p in top_ranked]
        state["is_ready_for_recommendation"] = True

        return AgentDecision(
            action="recommend",
            message="\n\n".join(summary_msg),
            missing_info=[],
            recommendations=recommendation_items,
            trade_offs=trade_offs,
            state=state,
        )
