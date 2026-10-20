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


class RequirementsOverride(BaseModel):
    category: Optional[str] = Field(None, description="Product category override")
    budget_max: Optional[float] = Field(None, ge=0, description="Maximum budget cap in INR")
    budget_min: Optional[float] = Field(None, ge=0, description="Minimum budget in INR")
    primary_uses: Optional[List[str]] = Field(None, description="Primary use cases list")
    requires_gpu: Optional[bool] = Field(None, description="Explicit GPU requirement")
    min_ram_gb: Optional[int] = Field(None, ge=4, description="Minimum RAM capacity in GB")
    max_weight_kg: Optional[float] = Field(None, ge=0.5, description="Max acceptable weight in kg")
    portability_important: Optional[bool] = Field(None, description="High portability importance")
    battery_important: Optional[bool] = Field(None, description="Long battery life importance")
    brand_preference: Optional[str] = Field(None, description="Preferred brand")
    notes: Optional[str] = Field(None, description="Additional customer preference notes")


class FeedbackCreate(BaseModel):
    rating: str = Field(..., description="'thumbs_up', 'thumbs_down', or rating 1-5")
    purchase_intent: Optional[bool] = Field(None, description="Whether customer intends to purchase")
    selected_product_id: Optional[str] = Field(None, description="ID of chosen product if any")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional user comment")


class FeedbackResponse(BaseModel):
    status: str = "received"
    conversation_id: str
    recorded_at: str
    feedback: Dict[str, Any]


class ConversationDebugResponse(BaseModel):
    conversation_id: str
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    state: Dict[str, Any]
    hard_constraints: Dict[str, Any]
    preferences: Dict[str, Any]
    message_count: int
    latest_decision: Optional[Dict[str, Any]] = None
    catalog_diagnostics: Dict[str, Any]

