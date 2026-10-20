from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.product import ProductResponse


class HardConstraints(BaseModel):
    max_budget: Optional[float] = None
    min_budget: Optional[float] = None
    category: str = "laptop"
    min_ram_gb: Optional[int] = None
    requires_dedicated_gpu: Optional[bool] = None
    required_os: Optional[str] = None
    brand: Optional[str] = None


class SoftPreferences(BaseModel):
    portability: Optional[bool] = None  # user carries around campus / travels
    max_weight_kg: Optional[float] = None
    min_battery_hours: Optional[float] = None
    high_refresh_rate: Optional[bool] = None
    display_type: Optional[str] = None  # OLED, IPS, etc.
    preferred_brands: List[str] = Field(default_factory=list)


class ExtractedState(BaseModel):
    category: str = "laptop"
    budget_max: Optional[float] = None
    budget_min: Optional[float] = None
    primary_uses: List[str] = Field(default_factory=list)  # e.g. ["programming", "machine_learning"]
    hard_constraints: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    clarifications_asked: List[str] = Field(default_factory=list)
    is_ready_for_recommendation: bool = False
    recommended_product_ids: List[str] = Field(default_factory=list)
    turn_count: int = 0


class RecommendationItem(BaseModel):
    product: ProductResponse
    why_recommended: str
    key_advantages: List[str] = Field(default_factory=list)
    potential_drawbacks: List[str] = Field(default_factory=list)
    suitability_score: float = 0.0


class TradeOffComparison(BaseModel):
    criterion: str
    product_1_verdict: str
    product_2_verdict: str
    trade_off_explanation: str


class AgentDecision(BaseModel):
    action: str  # "ask_clarification" | "recommend" | "no_match" | "greeting"
    message: str
    follow_up_question: Optional[str] = None
    missing_info: List[str] = Field(default_factory=list)
    recommendations: List[RecommendationItem] = Field(default_factory=list)
    trade_offs: List[TradeOffComparison] = Field(default_factory=list)
    state: Dict[str, Any] = Field(default_factory=dict)
