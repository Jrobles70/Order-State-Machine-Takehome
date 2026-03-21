from dataclasses import dataclass
from typing import Optional

from app.models import OrderState


class InvalidTransition(Exception):
    def __init__(self, state: OrderState, action: str):
        self.state = state
        self.action = action
        super().__init__(f"Invalid transition: cannot '{action}' from '{state.value}'")


@dataclass(frozen=True)
class TransitionRule:
    success_state: OrderState
    failure_state: Optional[OrderState] = None
    recovery_action: Optional[str] = None


TRANSITIONS = {
    (OrderState.INITIALIZED, "authorize"): TransitionRule(
        success_state=OrderState.PAYMENT_AUTHORIZED,
        failure_state=OrderState.REJECTED,
    ),
    (OrderState.PAYMENT_AUTHORIZED, "capture"): TransitionRule(
        success_state=OrderState.CAPTURED,
        recovery_action="void",
    ),
    (OrderState.PAYMENT_AUTHORIZED, "void"): TransitionRule(
        success_state=OrderState.CANCELLED,
        failure_state=OrderState.NEEDS_ATTENTION,
    ),
    (OrderState.CAPTURED, "fulfill"): TransitionRule(
        success_state=OrderState.COMPLETE,
        failure_state=OrderState.NEEDS_ATTENTION,
    ),
}


def get_transition(current_state: OrderState, action: str) -> TransitionRule:
    key = (current_state, action)
    if key not in TRANSITIONS:
        raise InvalidTransition(current_state, action)
    return TRANSITIONS[key]
