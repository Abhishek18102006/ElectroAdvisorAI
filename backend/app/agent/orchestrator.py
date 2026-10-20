import logging
import re
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
    3. Detect contradictory constraints early.
    4. Handle post-recommendation intents (thanks, lighter, cheaper).
    5. Determine if sufficient information exists for recommendation.
    6. If missing critical info -> Ask category-specific focused follow-up question.
    7. If sufficient info -> Search database using controlled tools, filter by hard constraints,
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

        # Strict greeting check: Do not misfire on 'high-end laptop', strip punctuation
        clean_text = re.sub(r"[^\w\s]", "", lower_msg).strip()
        words = clean_text.split()
        greeting_words = {"hi", "hello", "hey", "greetings", "howdy", "good morning", "good evening"}
        category_keywords = {"laptop", "laptops", "phone", "phones", "monitor", "monitors", "tablet", "tablets", "headphones", "headphone", "budget", "price", "end"}
        is_pure_greeting = (
            clean_text in greeting_words
            or (len(words) <= 2 and len(words) > 0 and words[0] in greeting_words and not any(w in category_keywords for w in words))
        )

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

        # 3. Check for Contradictory Constraints early
        if state.get("contradiction"):
            question = f"{state['contradiction']} Could you please clarify your preference?"
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["contradiction_resolution"],
                state=state,
            )

        # 4. Handle Post-Recommendation Follow-up Intents
        last_intent = extracted_patch.get("last_intent")
        if state.get("is_ready_for_recommendation") and last_intent in ["appreciation", "refinement"]:
            if last_intent == "appreciation":
                return AgentDecision(
                    action="informational",
                    message="You're very welcome! If you have any questions about specific ports, warranty, or need to tweak any requirements, feel free to ask. Happy shopping!",
                    state=state,
                )
            elif last_intent == "refinement" and any(w in lower_msg for w in ["lighter", "lightest", "weight"]):
                state["preferences"]["portability"] = True
                state["preferences"]["max_weight_kg"] = 1.6

        # 5. Decision Logic: Has Enough Info?
        category = state.get("category", "laptop")
        primary_uses = state.get("primary_uses", [])
        budget_max = state.get("budget_max")
        clarifications = set(state.get("clarifications_asked", []))
        preferences = state.get("preferences", {})
        hard_constraints = state.get("hard_constraints", {})

        # Scenario A: Primary use is completely missing -> Category-aware questioning
        if not primary_uses:
            category_questions = {
                "laptop": "What will you mainly use it for: general coursework, programming, gaming, creative work, or machine learning?",
                "monitor": "What will you mainly use this monitor for: programming/multitasking, competitive gaming, color-accurate creative work, or general desk use?",
                "headphones": "What is your primary use for these headphones: study focus with active noise cancellation, daily commute/travel, or calls and entertainment?",
                "smartphone": "What are your top priorities for this smartphone: photography/camera, gaming and speed, all-day battery life, or general daily use?",
                "tablet": "What will you mainly use this tablet for: digital note-taking & coursework, drawing and creative design, or watching media?",
            }
            question = category_questions.get(category, f"What will you mainly use your {category} for?")
            state["clarifications_asked"].append("asked_primary_use")
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["primary_use"],
                state=state,
            )

        # Scenario B: Laptop with Machine Learning, but local vs cloud is ambiguous AND budget is missing
        if (
            category == "laptop"
            and "machine_learning" in primary_uses
            and not preferences.get("ml_environment")
            and budget_max is None
        ):
            question = "What is your approximate budget? And do you need to run models locally, or will you mostly use cloud platforms?"
            state["clarifications_asked"].append("asked_budget_and_ml_env")
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["budget", "ml_environment"],
                state=state,
            )

        # Scenario C: Budget is missing
        if budget_max is None:
            question = f"What is your approximate budget for this {category}?"
            state["clarifications_asked"].append("asked_budget")
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["budget"],
                state=state,
            )

        # Scenario D: Machine Learning is selected, budget is known, but local vs cloud was never clarified
        # and user did not explicitly mention dedicated GPU
        if (
            category == "laptop"
            and "machine_learning" in primary_uses
            and not preferences.get("ml_environment")
            and hard_constraints.get("requires_gpu") is None
            and "asked_ml_env" not in clarifications
            and "asked_budget_and_ml_env" not in clarifications
        ):
            question = "Will you be training models locally (requiring a dedicated GPU), or running them primarily on cloud platforms like Google Colab or Kaggle?"
            state["clarifications_asked"].append("asked_ml_env")
            return AgentDecision(
                action="ask_clarification",
                message=question,
                follow_up_question=question,
                missing_info=["ml_environment"],
                state=state,
            )

        # 6. WE HAVE ENOUGH INFORMATION TO MAKE A SOUND RECOMMENDATION!
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

        # Step C: Handle zero match case dynamically from database
        if not eligible_products:
            explanation = RecommendationExplainer.generate_no_match_explanation(
                db=db,
                state=state,
                violations=violations,
            )
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

        # Step F: Craft final conversational message with dynamic and honest trade-off synthesis
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
            
            # Dynamic trade-off phrasing based on actual specs
            w1 = p1.specs.get("weight_kg", 2.0)
            w2 = p2.specs.get("weight_kg", 2.0)
            b1 = p1.specs.get("battery_life_hours", 6.0)
            b2 = p2.specs.get("battery_life_hours", 6.0)

            if w1 < w2:
                tradeoff_line = f"**Key Trade-off:** {p1.name} is slightly lighter ({w1}kg vs {w2}kg), whereas {p2.name} offers different features (~{b2}h battery)."
            elif w2 < w1:
                tradeoff_line = f"**Key Trade-off:** {p2.name} is lighter ({w2}kg vs {w1}kg), while {p1.name} emphasizes higher raw performance."
            else:
                tradeoff_line = f"**Key Trade-off:** Both weigh {w1}kg; {p1.name} focuses on raw compute power while {p2.name} balances endurance."

            if category == "laptop" and hard_constraints.get("requires_gpu") and min(w1, w2) >= 2.0:
                tradeoff_line += " (Note: Dedicated GPU laptops require cooling systems, so both are standard performance weights rather than ultra-thin notebooks)."

            summary_msg.append(f"\n⚖️ {tradeoff_line}")

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
