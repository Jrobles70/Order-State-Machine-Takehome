from typing import List, Optional

from app.models import HistoryEntry, Order, TransitionError
from app.payment import PaymentProvider
from app.state_machine import get_transition


class Orchestrator:
    def __init__(self, payment_provider: PaymentProvider):
        self._payment = payment_provider

    def _apply_transition(
        self,
        order: Order,
        new_state: str,
        trigger: str,
        errors: Optional[List[TransitionError]] = None,
    ) -> None:
        from_state = order.current_state
        order.current_state = new_state
        order.history.append(
            HistoryEntry(
                from_state=from_state,
                to_state=new_state,
                trigger=trigger,
                errors=errors or [],
            )
        )

    def authorize(self, order: Order, card_number: str, exp_month: int, exp_year: int) -> Order:
        rule = get_transition(order.current_state, "authorize")
        result = self._payment.authorize(card_number, order.amount_cents)

        if result.success:
            order.last4 = card_number[-4:]
            order.exp_month = exp_month
            order.exp_year = exp_year
            order.authorization_id = result.authorization_id
            self._apply_transition(order, rule.success_state, "authorize")
        else:
            self._apply_transition(
                order, rule.failure_state, "authorize",
                [TransitionError(action="authorize", message=result.error)],
            )

        return order

    def complete(self, order: Order) -> Order:
        # Phase 1: Capture payment
        capture_rule = get_transition(order.current_state, "capture")
        capture_result = self._payment.capture(order.authorization_id)
        errors: List[TransitionError] = []

        if not capture_result.success:
            errors.append(TransitionError(action="capture", message=capture_result.error))

            # Recovery: attempt void
            void_rule = get_transition(order.current_state, "void")
            void_result = self._payment.void(order.authorization_id)

            if void_result.success:
                self._apply_transition(order, void_rule.success_state, "auto_void", errors)
            else:
                errors.append(TransitionError(action="void", message=void_result.error))
                self._apply_transition(order, void_rule.failure_state, "auto_escalation", errors)
            return order

        # Capture succeeded
        self._apply_transition(order, capture_rule.success_state, "complete")

        # Phase 2: Fulfill order
        fulfill_rule = get_transition(order.current_state, "fulfill")

        if self._payment.should_fail_fulfillment(order.authorization_id):
            self._apply_transition(
                order, fulfill_rule.failure_state, "auto_escalation",
                [TransitionError(action="fulfill", message="fulfillment failed")],
            )
        else:
            self._apply_transition(order, fulfill_rule.success_state, "complete")

        return order
