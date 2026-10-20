from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(50), primary_key=True, index=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    status = Column(String(20), default="active")  # active, completed, idle

    # Persisted agent requirements state
    # {
    #   "category": "laptop",
    #   "budget_max": 80000.0,
    #   "budget_min": None,
    #   "primary_uses": ["programming", "machine_learning"],
    #   "hard_constraints": {"max_budget": 80000, "requires_gpu": True, "min_ram_gb": 16},
    #   "preferences": {"portability": True, "weight_kg_max": 2.2},
    #   "missing_info": [],
    #   "is_ready_for_recommendation": True,
    #   "recommended_product_ids": ["LAP-001", "LAP-004"]
    # }
    state = Column(JSON, nullable=False, default=dict)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.id")

    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "state": self.state or {},
            "messages": [msg.to_dict() for msg in self.messages] if self.messages else [],
        }


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    conversation_id = Column(String(50), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender = Column(String(20), nullable=False)  # "customer", "agent", "system"
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True, default=dict)
    created_at = Column(DateTime, default=utcnow)

    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "sender": self.sender,
            "content": self.content,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
