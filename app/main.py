from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app import store
from app.models import Order
from app.orchestrator import Orchestrator
from app.payment import StubPaymentProvider
from app.state_machine import InvalidTransition

app = FastAPI(title="Order State Machine")
orchestrator = Orchestrator(payment_provider=StubPaymentProvider())


class CreateOrderRequest(BaseModel):
    amount: float


class AuthorizeRequest(BaseModel):
    card_number: str


@app.post("/orders", status_code=201)
def create_order(request: CreateOrderRequest):
    order = Order(amount=request.amount)
    store.save(order)
    return order


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/orders/{order_id}/authorize")
def authorize_order(order_id: str, request: AuthorizeRequest):
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        order = orchestrator.authorize(order, card_number=request.card_number)
    except InvalidTransition as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(order)
    return order


@app.post("/orders/{order_id}/complete")
def complete_order(order_id: str):
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        order = orchestrator.complete(order)
    except InvalidTransition as e:
        raise HTTPException(status_code=400, detail=str(e))
    store.save(order)
    return order
