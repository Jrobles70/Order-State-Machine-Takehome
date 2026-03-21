from fastapi import FastAPI, HTTPException, Path, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, model_validator

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
    event_id: str = Field(..., description="Identifier for the event being purchased", examples=["evt-123"])
    quantity: int = Field(..., gt=0, description="Number of tickets to purchase", examples=[2])
    section: str = Field(..., description="Seating section", examples=["A"])
    row: str = Field(..., description="Seating row", examples=["1"])
    amount_cents: int = Field(..., gt=0, description="Total order amount in cents", examples=[9999])
    currency: Currency = Field(..., description="Currency code", examples=["USD"])

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
    card_number: str = Field(..., description="Card number (13-19 digits). See test cards above.", examples=["4242424242424242"])
    exp_month: int = Field(..., ge=1, le=12, description="Card expiration month (1-12)", examples=[12])
    exp_year: int = Field(..., description="Card expiration year (4-digit)", examples=[2027])
    cvv: str = Field(..., description="Card security code (3-4 digits)", examples=["123"])

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


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message describing what went wrong")


def _get_order_or_404(order_id: str) -> Order:
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post(
    "/orders",
    status_code=201,
    response_model=Order,
    summary="Create an order",
    description="Creates a new order in the `initialized` state.",
    responses={422: {"description": "Validation error (e.g. negative amount, missing fields)", "content": {"application/json": {"example": {"detail": [{"type": "greater_than", "loc": ["body", "amount_cents"], "msg": "Input should be greater than 0", "input": -5, "ctx": {"gt": 0}}]}}}}},
)
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


@app.get(
    "/orders/{order_id}",
    response_model=Order,
    summary="Get order details",
    description="Returns the current state and full transition history of an order.",
    responses={
        404: {"model": ErrorResponse, "description": "Order not found", "content": {"application/json": {"example": {"detail": "Order not found"}}}},
        422: {"description": "Validation error", "content": {"application/json": {"example": {"detail": [{"type": "greater_than", "loc": ["body", "amount_cents"], "msg": "Input should be greater than 0", "input": -5, "ctx": {"gt": 0}}]}}}},
    },
)
def get_order(order_id: str = Path(..., description="The order UUID", examples=["550e8400-e29b-41d4-a716-446655440000"])):
    return _get_order_or_404(order_id)


@app.post(
    "/orders/{order_id}/authorize",
    response_model=Order,
    summary="Authorize payment",
    description=(
        "Authorizes payment for an order. The order must be in `initialized` state. "
        "On success the order transitions to `payment_authorized`. "
        "On decline the order transitions to `rejected`.\n\n"
        "**Test card numbers:**\n\n"
        "| Card Number | Behavior |\n"
        "| --- | --- |\n"
        "| `4111111111111111` | Success (or any valid card not listed below) |\n"
        "| `4000000000000002` | Authorization declined → `rejected` |\n"
        "| `4000000000000341` | Authorizes OK, capture fails, void succeeds → `cancelled` |\n"
        "| `4000000000009995` | Authorizes OK, capture fails, void fails → `needs_attention` |\n"
        "| `4000000000000259` | Authorizes OK, capture OK, fulfillment fails → `needs_attention` |\n"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state transition (order is not in `initialized` state)", "content": {"application/json": {"example": {"detail": "Invalid transition: cannot 'authorize' from 'payment_authorized'"}}}},
        404: {"model": ErrorResponse, "description": "Order not found", "content": {"application/json": {"example": {"detail": "Order not found"}}}},
        422: {"description": "Validation error (e.g. invalid card number, expired card)", "content": {"application/json": {"example": {"detail": [{"type": "value_error", "loc": ["body", "card_number"], "msg": "Value error, card_number must be 13-19 digits", "input": "123", "ctx": {"error": {}}}]}}}},
    },
)
def authorize_order(
    request: AuthorizeRequest,
    order_id: str = Path(..., description="The order UUID"),
):
    order = _get_order_or_404(order_id)
    order = orchestrator.authorize(
        order,
        card_number=request.card_number,
        exp_month=request.exp_month,
        exp_year=request.exp_year,
    )
    store.save(order)
    return order


@app.post(
    "/orders/{order_id}/complete",
    response_model=Order,
    summary="Complete order",
    description=(
        "Captures payment and fulfills the order. The order must be in `payment_authorized` state. "
        "On success: `payment_authorized` → `captured` → `complete`. "
        "On capture failure: attempts void — if void succeeds → `cancelled`, if void fails → `needs_attention`. "
        "On fulfillment failure: → `needs_attention`."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid state transition (order is not in `payment_authorized` state)", "content": {"application/json": {"example": {"detail": "Invalid transition: cannot 'capture' from 'initialized'"}}}},
        404: {"model": ErrorResponse, "description": "Order not found", "content": {"application/json": {"example": {"detail": "Order not found"}}}},
    },
)
def complete_order(order_id: str = Path(..., description="The order UUID")):
    order = _get_order_or_404(order_id)
    order = orchestrator.complete(order)
    store.save(order)
    return order
