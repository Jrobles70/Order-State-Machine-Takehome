import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderState(str, Enum):
    INITIALIZED = "initialized"
    PAYMENT_AUTHORIZED = "payment_authorized"
    CAPTURED = "captured"
    COMPLETE = "complete"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    NEEDS_ATTENTION = "needs_attention"


class Currency(str, Enum):
    USD = "USD"
    CAD = "CAD"


class TransitionError(BaseModel):
    action: str = Field(examples=["capture"])
    message: str = Field(examples=["Card declined"])


class HistoryEntry(BaseModel):
    from_state: OrderState = Field(examples=[OrderState.INITIALIZED])
    to_state: OrderState = Field(examples=[OrderState.PAYMENT_AUTHORIZED])
    trigger: str = Field(examples=["authorize"])
    errors: List[TransitionError] = []
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        examples=["2026-03-21T12:00:00Z"],
    )


class Order(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    current_state: OrderState = OrderState.INITIALIZED
    event_id: str = Field(examples=["EVT-001"])
    quantity: int = Field(examples=[2])
    section: str = Field(examples=["A"])
    row: str = Field(examples=["1"])
    amount_cents: int = Field(examples=[9999])
    currency: Currency = Field(examples=[Currency.USD])
    last4: Optional[str] = Field(default=None, examples=["4242"])
    exp_month: Optional[int] = Field(default=None, examples=[12])
    exp_year: Optional[int] = Field(default=None, examples=[2027])
    authorization_id: Optional[str] = Field(
        default=None, examples=["auth-abc123"]
    )
    capture_id: Optional[str] = Field(
        default=None, examples=["cap-xyz789"]
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        examples=["2026-03-21T12:00:00Z"],
    )
    history: List[HistoryEntry] = []


class PaymentResult(BaseModel):
    success: bool
    authorization_id: Optional[str] = None
    capture_id: Optional[str] = None
    error: str = ""
