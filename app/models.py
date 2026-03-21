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
    action: str
    message: str


class HistoryEntry(BaseModel):
    from_state: OrderState
    to_state: OrderState
    trigger: str
    errors: List[TransitionError] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    current_state: OrderState = OrderState.INITIALIZED
    event_id: str
    quantity: int
    section: str
    row: str
    amount_cents: int
    currency: Currency
    last4: Optional[str] = None
    exp_month: Optional[int] = None
    exp_year: Optional[int] = None
    authorization_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    history: List[HistoryEntry] = []


class PaymentResult(BaseModel):
    success: bool
    authorization_id: Optional[str] = None
    error: str = ""
