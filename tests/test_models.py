from datetime import datetime, timezone


def test_order_state_enum_values():
    from app.models import OrderState

    assert OrderState.INITIALIZED.value == "initialized"
    assert OrderState.PAYMENT_AUTHORIZED.value == "payment_authorized"
    assert OrderState.CAPTURED.value == "captured"
    assert OrderState.COMPLETE.value == "complete"
    assert OrderState.CANCELLED.value == "cancelled"
    assert OrderState.REJECTED.value == "rejected"
    assert OrderState.NEEDS_ATTENTION.value == "needs_attention"


def test_history_entry_creation():
    from app.models import HistoryEntry, OrderState

    entry = HistoryEntry(
        from_state=OrderState.INITIALIZED,
        to_state=OrderState.PAYMENT_AUTHORIZED,
        trigger="authorize",
        errors=[],
    )
    assert entry.from_state == OrderState.INITIALIZED
    assert entry.to_state == OrderState.PAYMENT_AUTHORIZED
    assert entry.trigger == "authorize"
    assert entry.errors == []
    assert isinstance(entry.timestamp, datetime)


def test_history_entry_with_errors():
    from app.models import HistoryEntry, OrderState, TransitionError

    entry = HistoryEntry(
        from_state=OrderState.PAYMENT_AUTHORIZED,
        to_state=OrderState.NEEDS_ATTENTION,
        trigger="auto_escalation",
        errors=[
            TransitionError(action="capture", message="capture failed"),
            TransitionError(action="void", message="void failed"),
        ],
    )
    assert len(entry.errors) == 2
    assert entry.errors[0].action == "capture"
    assert entry.errors[1].action == "void"


def test_order_creation():
    from app.models import Order

    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount=99.99)
    assert order.id is not None
    assert order.current_state.value == "initialized"
    assert order.amount == 99.99
    assert order.last4 is None
    assert order.authorization_id is None
    assert order.exp_month is None
    assert order.exp_year is None
    assert order.history == []
    assert order.created_at is not None


def test_order_add_history():
    from app.models import HistoryEntry, Order, OrderState

    order = Order(event_id="EVT-001", quantity=2, section="A", row="1", amount=50.00)
    entry = HistoryEntry(
        from_state=OrderState.INITIALIZED,
        to_state=OrderState.PAYMENT_AUTHORIZED,
        trigger="authorize",
        errors=[],
    )
    order.history.append(entry)
    assert len(order.history) == 1
