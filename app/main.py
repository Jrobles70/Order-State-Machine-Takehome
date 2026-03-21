from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

from pydantic import BaseModel, field_validator, model_validator

from app import store
from app.models import Order, Currency
from app.orchestrator import Orchestrator
from app.payment import StubPaymentProvider
from app.state_machine import InvalidTransition

app = FastAPI(title="Order State Machine")


@app.exception_handler(InvalidTransition)
def handle_invalid_transition(_request: Request, exc: InvalidTransition):
    return JSONResponse(status_code=400, content={"detail": str(exc)})
orchestrator = Orchestrator(payment_provider=StubPaymentProvider())


class CreateOrderRequest(BaseModel):
    event_id: str
    quantity: int
    section: str
    row: str
    amount_cents: int
    currency: Currency

    @field_validator("amount_cents")
    @classmethod
    def amount_cents_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_cents must be greater than 0")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v


class AuthorizeRequest(BaseModel):
    card_number: str
    exp_month: int
    exp_year: int
    cvv: str

    @field_validator("card_number")
    @classmethod
    def card_number_must_be_valid(cls, v: str) -> str:
        if not v.isdigit() or not (13 <= len(v) <= 19):
            raise ValueError("card_number must be 13-19 digits")
        return v

    @field_validator("exp_month")
    @classmethod
    def exp_month_must_be_valid(cls, v: int) -> int:
        if not (1 <= v <= 12):
            raise ValueError("exp_month must be between 1 and 12")
        return v

    @field_validator("exp_year")
    @classmethod
    def exp_year_must_be_4_digits(cls, v: int) -> int:
        if not (1000 <= v <= 9999):
            raise ValueError("exp_year must be a 4-digit year")
        return v

    @model_validator(mode="after")
    def card_must_not_be_expired(self) -> "AuthorizeRequest":
        now = datetime.now(timezone.utc)
        # Card is valid through the end of its expiry month
        if (self.exp_year, self.exp_month) < (now.year, now.month):
            raise ValueError("card is expired")
        return self

    @field_validator("cvv")
    @classmethod
    def cvv_must_be_valid(cls, v: str) -> str:
        if not v.isdigit() or not (3 <= len(v) <= 4):
            raise ValueError("cvv must be 3-4 digits")
        return v


def _get_order_or_404(order_id: str) -> Order:
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders", status_code=201)
def create_order(request: CreateOrderRequest):
    order = Order(
        event_id=request.event_id,
        quantity=request.quantity,
        section=request.section,
        row=request.row,
        amount_cents=request.amount_cents,
        currency=request.currency,
    )
    store.save(order)
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return _get_order_or_404(order_id)


@app.post("/orders/{order_id}/authorize")
def authorize_order(order_id: str, request: AuthorizeRequest):
    order = _get_order_or_404(order_id)
    order = orchestrator.authorize(
        order,
        card_number=request.card_number,
        exp_month=request.exp_month,
        exp_year=request.exp_year,
    )
    store.save(order)
    return order


@app.post("/orders/{order_id}/complete")
def complete_order(order_id: str):
    order = _get_order_or_404(order_id)
    order = orchestrator.complete(order)
    store.save(order)
    return order
