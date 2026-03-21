import pytest


def test_authorize_success():
    from app.models import OrderState
    from app.state_machine import get_transition

    result = get_transition(OrderState.INITIALIZED, "authorize")
    assert result.success_state == OrderState.PAYMENT_AUTHORIZED
    assert result.failure_state == OrderState.REJECTED
    assert result.recovery_action is None


def test_capture_success():
    from app.models import OrderState
    from app.state_machine import get_transition

    result = get_transition(OrderState.PAYMENT_AUTHORIZED, "capture")
    assert result.success_state == OrderState.CAPTURED
    assert result.failure_state is None
    assert result.recovery_action == "void"


def test_void_success():
    from app.models import OrderState
    from app.state_machine import get_transition

    result = get_transition(OrderState.PAYMENT_AUTHORIZED, "void")
    assert result.success_state == OrderState.CANCELLED
    assert result.failure_state == OrderState.NEEDS_ATTENTION
    assert result.recovery_action is None


def test_fulfill_success():
    from app.models import OrderState
    from app.state_machine import get_transition

    result = get_transition(OrderState.CAPTURED, "fulfill")
    assert result.success_state == OrderState.COMPLETE
    assert result.failure_state == OrderState.NEEDS_ATTENTION
    assert result.recovery_action is None


def test_invalid_transition():
    from app.models import OrderState
    from app.state_machine import InvalidTransition, get_transition

    with pytest.raises(InvalidTransition):
        get_transition(OrderState.INITIALIZED, "capture")


def test_invalid_transition_from_terminal_state():
    from app.models import OrderState
    from app.state_machine import InvalidTransition, get_transition

    with pytest.raises(InvalidTransition):
        get_transition(OrderState.COMPLETE, "authorize")


def test_invalid_transition_from_rejected():
    from app.models import OrderState
    from app.state_machine import InvalidTransition, get_transition

    with pytest.raises(InvalidTransition):
        get_transition(OrderState.REJECTED, "authorize")
