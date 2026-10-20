import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.conversation import Conversation, Message
from app.models.product import Product
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    MessageSendResponse,
    RequirementsOverride,
    FeedbackCreate,
    FeedbackResponse,
    ConversationDebugResponse,
)
from app.agent.state import create_initial_state, set_category
from app.agent.filter_rank import FilterAndRankingEngine
from app.agent.orchestrator import SalesAgentOrchestrator


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/conversations", tags=["Conversations & Recommendations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED, summary="Start a new conversation")
def create_conversation(payload: Optional[ConversationCreate] = None, db: Session = Depends(get_db)):
    try:
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        initial_state = create_initial_state()

        conv = Conversation(
            id=conv_id,
            status="active",
            state=initial_state,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        return ConversationResponse(**conv.to_dict())
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error creating conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize conversation due to a database error.",
        )


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Retrieve conversation history and current state")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conversation_id}' not found",
            )
        return ConversationResponse(**conv.to_dict())
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error retrieving conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation due to a database error.",
        )


@router.post("/{conversation_id}/messages", response_model=MessageSendResponse, summary="Send message and receive agent recommendation/response")
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
):
    cleaned_content = payload.content.strip()
    if not cleaned_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty or whitespace only",
        )

    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    except SQLAlchemyError as e:
        logger.error(f"Database query error for conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database connection error while retrieving conversation.",
        )

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    try:
        # 1. Save customer message
        user_msg = Message(
            conversation_id=conversation_id,
            sender="customer",
            content=cleaned_content,
            metadata_json={},
        )
        db.add(user_msg)
        db.flush()

        # 2. Extract conversation history
        history = [msg.to_dict() for msg in conv.messages]

        # 3. Process turn through Sales Agent Orchestrator
        decision = await SalesAgentOrchestrator.process_turn(
            db=db,
            customer_message=cleaned_content,
            conversation_history=history,
            current_state=conv.state or create_initial_state(),
        )

        # 4. Save agent response message
        agent_msg = Message(
            conversation_id=conversation_id,
            sender="agent",
            content=decision.message,
            metadata_json={
                "action": decision.action,
                "missing_info": decision.missing_info,
                "recommendations": [r.model_dump() for r in decision.recommendations],
                "trade_offs": [t.model_dump() for t in decision.trade_offs],
            },
        )
        db.add(agent_msg)

        # 5. Update conversation state and status
        conv.state = decision.state
        if decision.action == "recommend":
            conv.status = "recommended"
        elif decision.action == "no_match":
            conv.status = "no_match"

        db.commit()
        db.refresh(user_msg)
        db.refresh(agent_msg)

        return MessageSendResponse(
            conversation_id=conversation_id,
            user_message=MessageResponse(**user_msg.to_dict()),
            agent_message=MessageResponse(**agent_msg.to_dict()),
            decision=decision,
        )
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database commit error in conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while saving conversation messages.",
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected agent error in conversation {conversation_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing your message.",
        )


@router.post("/{conversation_id}/reset", response_model=ConversationResponse, summary="Reset conversation requirements state")
def reset_conversation(conversation_id: str, db: Session = Depends(get_db)):
    try:
        conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conversation_id}' not found",
            )

        conv.state = create_initial_state()
        conv.status = "active"

        sys_msg = Message(
            conversation_id=conversation_id,
            sender="system",
            content="Conversation requirements have been reset.",
            metadata_json={},
        )
        db.add(sys_msg)
        db.commit()
        db.refresh(conv)

        return ConversationResponse(**conv.to_dict())
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error resetting conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while resetting the conversation.",
        )


@router.put("/{conversation_id}/requirements", response_model=ConversationResponse, summary="Manually override agent state & constraints via UI controls")
def update_requirements(
    conversation_id: str,
    payload: RequirementsOverride,
    db: Session = Depends(get_db),
):
    """
    Direct State Override: Allows hybrid UI controls (e.g. budget sliders, spec toggle chips)
    to update customer requirements directly without forcing natural language chat input.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    state = dict(conv.state or create_initial_state())
    state.setdefault("hard_constraints", {})
    state.setdefault("preferences", {})

    changes = []
    if payload.category is not None:
        cat_lower = payload.category.lower().strip()
        state = set_category(state, cat_lower)
        changes.append(f"category: {cat_lower}")

    if payload.budget_max is not None:
        state["budget_max"] = payload.budget_max
        state["hard_constraints"]["max_budget"] = payload.budget_max
        changes.append(f"budget_max: ₹{payload.budget_max:,.0f}")

    if payload.budget_min is not None:
        state["budget_min"] = payload.budget_min
        changes.append(f"budget_min: ₹{payload.budget_min:,.0f}")

    if payload.primary_uses is not None:
        state["primary_uses"] = payload.primary_uses
        changes.append(f"uses: {', '.join(payload.primary_uses)}")

    if payload.requires_gpu is not None:
        state["hard_constraints"]["requires_gpu"] = payload.requires_gpu
        changes.append(f"requires_gpu: {payload.requires_gpu}")

    if payload.min_ram_gb is not None:
        state["hard_constraints"]["min_ram_gb"] = payload.min_ram_gb
        changes.append(f"min_ram_gb: {payload.min_ram_gb}")

    if payload.max_weight_kg is not None:
        state["hard_constraints"]["max_weight_kg"] = payload.max_weight_kg
        state["preferences"]["max_weight_kg"] = payload.max_weight_kg
        changes.append(f"max_weight: {payload.max_weight_kg}kg")

    if payload.portability_important is not None:
        state["preferences"]["portability_important"] = payload.portability_important
        changes.append(f"portability: {payload.portability_important}")

    if payload.battery_important is not None:
        state["preferences"]["battery_important"] = payload.battery_important
        changes.append(f"battery: {payload.battery_important}")

    if payload.brand_preference is not None:
        state["preferences"]["brand"] = payload.brand_preference
        changes.append(f"brand: {payload.brand_preference}")

    conv.state = state

    change_desc = "; ".join(changes) if changes else "No spec changes provided"
    sys_msg = Message(
        conversation_id=conversation_id,
        sender="system",
        content=f"Requirements updated via UI controls ({change_desc}).",
        metadata_json={"ui_override": True, "changes": changes},
    )
    db.add(sys_msg)
    db.commit()
    db.refresh(conv)

    return ConversationResponse(**conv.to_dict())


@router.delete("/{conversation_id}", summary="Clear conversation history and reset state (Privacy & Reset)")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """
    Privacy & Reset: Completely deletes conversation history and requirements state from SQLite,
    allowing customer to start a clean session safely.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    try:
        db.delete(conv)
        db.commit()
        return {
            "status": "deleted",
            "conversation_id": conversation_id,
            "message": "Conversation context and history cleared successfully.",
        }
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation due to a database error.",
        )


@router.post("/{conversation_id}/feedback", response_model=FeedbackResponse, summary="Submit recommendation feedback & purchase intent (Analytics)")
def submit_feedback(
    conversation_id: str,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """
    Product Analytics: Records user sentiment (thumbs up/down, rating), selected product,
    and purchase intent to evaluate AI recommendation relevance and conversion success.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    feedback_entry = {
        "rating": payload.rating,
        "purchase_intent": payload.purchase_intent,
        "selected_product_id": payload.selected_product_id,
        "comment": payload.comment,
        "submitted_at": now_iso,
    }

    state = dict(conv.state or {})
    feedbacks = state.get("feedbacks", [])
    feedbacks.append(feedback_entry)
    state["feedbacks"] = feedbacks
    conv.state = state

    sys_msg = Message(
        conversation_id=conversation_id,
        sender="system",
        content=f"Feedback submitted: {payload.rating} (purchase intent: {payload.purchase_intent})",
        metadata_json={"feedback": feedback_entry},
    )
    db.add(sys_msg)
    db.commit()

    return FeedbackResponse(
        status="received",
        conversation_id=conversation_id,
        recorded_at=now_iso,
        feedback=feedback_entry,
    )


@router.get("/{conversation_id}/debug", response_model=ConversationDebugResponse, summary="Retrieve agent decision-making traces, state, and catalog diagnostics (Engineering Rigor)")
def get_conversation_debug(conversation_id: str, db: Session = Depends(get_db)):
    """
    Engineering Rigor: Exposes the full internal requirements state, hard constraint boundary evaluation,
    soft preference scoring breakdown, and candidate catalog diagnostics.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    latest_decision = None
    for msg in reversed(conv.messages):
        if msg.sender == "agent" and msg.metadata_json:
            latest_decision = msg.metadata_json
            break

    all_products = db.query(Product).all()
    state = conv.state or create_initial_state()
    category = state.get("category", "laptop")
    cat_prods = [p for p in all_products if p.category.lower() == category.lower()]

    eligible_prods, violations = FilterAndRankingEngine.filter_hard_constraints(all_products, state)
    ranked_candidates = []
    for p in eligible_prods:
        score, breakdown = FilterAndRankingEngine.calculate_score(p, state)
        ranked_candidates.append({
            "product": p,
            "total_score": score,
            "score_breakdown": breakdown,
        })
    ranked_candidates.sort(key=lambda x: x["total_score"], reverse=True)

    return ConversationDebugResponse(
        conversation_id=conv.id,
        status=conv.status,
        created_at=conv.created_at.isoformat() if conv.created_at else None,
        updated_at=conv.updated_at.isoformat() if conv.updated_at else None,
        state=state,
        hard_constraints=state.get("hard_constraints", {}),
        preferences=state.get("preferences", {}),
        message_count=len(conv.messages),
        latest_decision=latest_decision,
        catalog_diagnostics={
            "total_catalog_products": len(all_products),
            "category": category,
            "category_products_count": len(cat_prods),
            "passing_hard_filters_count": len(eligible_prods),
            "rejections_summary": violations,
            "top_candidates": [
                {
                    "id": item["product"].id,
                    "name": item["product"].name,
                    "price": item["product"].price,
                    "total_score": round(item["total_score"], 2),
                    "score_breakdown": item["score_breakdown"],
                }
                for item in ranked_candidates[:3]
            ],
        },
    )


