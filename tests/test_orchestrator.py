import pytest

from app.models import Order, OrderState
from app.orchestrator import Orchestrator
from app.payment import StubPaymentProvider


@pytest.fixture
def orchestrator():
    return Orchestrator(payment_provider=StubPaymentProvider())


def test_authorize_success(orchestrator):
    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount_cents=10000, currency="USD")
    result = orchestrator.authorize(
        order, card_number="4242424242424242", exp_month=12, exp_year=2028
    )

    assert result.current_state == OrderState.PAYMENT_AUTHORIZED
    assert result.last4 == "4242"
    assert result.exp_month == 12
    assert result.exp_year == 2028
    assert result.authorization_id is not None
    assert result.capture_id is None
    assert len(result.history) == 1
    assert result.history[0].from_state == OrderState.INITIALIZED
    assert result.history[0].to_state == OrderState.PAYMENT_AUTHORIZED
    assert result.history[0].trigger == "authorize"
    assert result.history[0].errors == []


def test_authorize_decline(orchestrator):
    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount_cents=10000, currency="USD")
    result = orchestrator.authorize(
        order, card_number="4000000000000002", exp_month=12, exp_year=2028
    )

    assert result.current_state == OrderState.REJECTED
    assert len(result.history) == 1
    assert result.history[0].from_state == OrderState.INITIALIZED
    assert result.history[0].to_state == OrderState.REJECTED
    assert result.history[0].trigger == "authorize"
    assert len(result.history[0].errors) == 1
    assert result.history[0].errors[0].action == "authorize"


def test_authorize_invalid_state(orchestrator):
    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount_cents=10000, currency="USD")
    order.current_state = OrderState.PAYMENT_AUTHORIZED

    from app.state_machine import InvalidTransition

    with pytest.raises(InvalidTransition):
        orchestrator.authorize(
            order, card_number="4242424242424242", exp_month=12, exp_year=2028
        )


def _authorized_order(orchestrator, card_number="4242424242424242"):
    """Helper: create and authorize an order."""
    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount_cents=10000, currency="USD")
    return orchestrator.authorize(
        order, card_number=card_number, exp_month=12, exp_year=2028
    )


def test_complete_happy_path(orchestrator):
    order = _authorized_order(orchestrator)
    result = orchestrator.complete(order)

    assert result.current_state == OrderState.COMPLETE
    assert result.capture_id is not None
    assert result.capture_id.startswith("cap_")
    # History: authorize, capture->captured, fulfill->complete
    assert len(result.history) == 3
    assert result.history[1].from_state == OrderState.PAYMENT_AUTHORIZED
    assert result.history[1].to_state == OrderState.CAPTURED
    assert result.history[1].trigger == "complete"
    assert result.history[2].from_state == OrderState.CAPTURED
    assert result.history[2].to_state == OrderState.COMPLETE
    assert result.history[2].trigger == "complete"


def test_complete_capture_fails_void_succeeds(orchestrator):
    order = _authorized_order(orchestrator, card_number="4000000000000341")
    result = orchestrator.complete(order)

    assert result.current_state == OrderState.CANCELLED
    assert result.capture_id is None
    # History: authorize, then cancelled (with capture error)
    assert len(result.history) == 2
    assert result.history[1].from_state == OrderState.PAYMENT_AUTHORIZED
    assert result.history[1].to_state == OrderState.CANCELLED
    assert result.history[1].trigger == "auto_void"
    assert len(result.history[1].errors) == 1
    assert result.history[1].errors[0].action == "capture"


def test_complete_capture_fails_void_fails(orchestrator):
    order = _authorized_order(orchestrator, card_number="4000000000009995")
    result = orchestrator.complete(order)

    assert result.current_state == OrderState.NEEDS_ATTENTION
    assert result.capture_id is None
    # History: authorize, then needs_attention (with capture + void errors)
    assert len(result.history) == 2
    assert result.history[1].from_state == OrderState.PAYMENT_AUTHORIZED
    assert result.history[1].to_state == OrderState.NEEDS_ATTENTION
    assert result.history[1].trigger == "auto_escalation"
    assert len(result.history[1].errors) == 2
    assert result.history[1].errors[0].action == "capture"
    assert result.history[1].errors[1].action == "void"


def test_complete_fulfillment_fails(orchestrator):
    order = _authorized_order(orchestrator, card_number="4000000000000259")
    result = orchestrator.complete(order)

    assert result.current_state == OrderState.NEEDS_ATTENTION
    assert result.capture_id is not None
    assert result.capture_id.startswith("cap_")
    # History: authorize, captured, then needs_attention (with fulfill error)
    assert len(result.history) == 3
    assert result.history[1].from_state == OrderState.PAYMENT_AUTHORIZED
    assert result.history[1].to_state == OrderState.CAPTURED
    assert result.history[1].trigger == "complete"
    assert result.history[2].from_state == OrderState.CAPTURED
    assert result.history[2].to_state == OrderState.NEEDS_ATTENTION
    assert result.history[2].trigger == "auto_escalation"
    assert len(result.history[2].errors) == 1
    assert result.history[2].errors[0].action == "fulfill"


def test_complete_invalid_state(orchestrator):
    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount_cents=10000, currency="USD")  # still initialized, not authorized

    from app.state_machine import InvalidTransition

    with pytest.raises(InvalidTransition):
        orchestrator.complete(order)
