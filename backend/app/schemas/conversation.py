from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.agent import AgentDecision


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="Customer message text")


class MessageResponse(BaseModel):
    id: int
    conversation_id: str
    sender: str  # "customer", "agent", "system"
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class ConversationCreate(BaseModel):
    initial_message: Optional[str] = None


class ConversationResponse(BaseModel):
    id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    state: Dict[str, Any] = Field(default_factory=dict)
    messages: List[MessageResponse] = Field(default_factory=list)


class MessageSendResponse(BaseModel):
    conversation_id: str
    user_message: MessageResponse
    agent_message: MessageResponse
    decision: AgentDecision
