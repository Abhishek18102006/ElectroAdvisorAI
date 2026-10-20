import uuid
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_db
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    MessageSendResponse,
)
from app.agent.state import create_initial_state
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
