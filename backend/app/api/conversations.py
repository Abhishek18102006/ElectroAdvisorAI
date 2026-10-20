import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

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

router = APIRouter(prefix="/conversations", tags=["Conversations & Recommendations"])


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED, summary="Start a new conversation")
def create_conversation(payload: Optional[ConversationCreate] = None, db: Session = Depends(get_db)):
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


@router.get("/{conversation_id}", response_model=ConversationResponse, summary="Retrieve conversation history and current state")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )
    return ConversationResponse(**conv.to_dict())


@router.post("/{conversation_id}/messages", response_model=MessageSendResponse, summary="Send message and receive agent recommendation/response")
async def send_message(
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    # 1. Save customer message
    user_msg = Message(
        conversation_id=conversation_id,
        sender="customer",
        content=payload.content.strip(),
        metadata_json={},
    )
    db.add(user_msg)
    db.flush()

    # 2. Extract conversation history
    history = [msg.to_dict() for msg in conv.messages]

    # 3. Process turn through Sales Agent Orchestrator
    try:
        decision = await SalesAgentOrchestrator.process_turn(
            db=db,
            customer_message=payload.content,
            conversation_history=history,
            current_state=conv.state or create_initial_state(),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent orchestration failed: {str(e)}",
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


@router.post("/{conversation_id}/reset", response_model=ConversationResponse, summary="Reset conversation requirements state")
def reset_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found",
        )

    conv.state = create_initial_state()
    conv.status = "active"

    # Add a system reset note
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
