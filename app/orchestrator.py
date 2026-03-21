from typing import List

from app.models import HistoryEntry, Order, TransitionError
from app.payment import PaymentProvider
from app.state_machine import get_transition


class Orchestrator:
    def __init__(self, payment_provider: PaymentProvider):
        self._payment = payment_provider

    def authorize(self, order: Order, card_number: str) -> Order:
        rule = get_transition(order.current_state, "authorize")
        result = self._payment.authorize(card_number, order.amount)

        if result.success:
            from_state = order.current_state
            order.current_state = rule.success_state
            order.card_number = card_number
            order.authorization_id = result.authorization_id
            order.history.append(
                HistoryEntry(
                    from_state=from_state,
                    to_state=rule.success_state,
                    trigger="authorize",
                    errors=[],
                )
            )
        else:
            from_state = order.current_state
            order.current_state = rule.failure_state
            order.history.append(
                HistoryEntry(
                    from_state=from_state,
                    to_state=rule.failure_state,
                    trigger="authorize",
                    errors=[TransitionError(action="authorize", message=result.error)],
                )
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
                from_state = order.current_state
                order.current_state = void_rule.success_state
                order.history.append(
                    HistoryEntry(
                        from_state=from_state,
                        to_state=void_rule.success_state,
                        trigger="auto_void",
                        errors=errors,
                    )
                )
            else:
                errors.append(TransitionError(action="void", message=void_result.error))
                from_state = order.current_state
                order.current_state = void_rule.failure_state
                order.history.append(
                    HistoryEntry(
                        from_state=from_state,
                        to_state=void_rule.failure_state,
                        trigger="auto_escalation",
                        errors=errors,
                    )
                )
            return order

        # Capture succeeded — record state change
        from_state = order.current_state
        order.current_state = capture_rule.success_state
        order.history.append(
            HistoryEntry(
                from_state=from_state,
                to_state=capture_rule.success_state,
                trigger="complete",
                errors=[],
            )
        )

        # Phase 2: Fulfill order
        fulfill_rule = get_transition(order.current_state, "fulfill")

        if self._payment.should_fail_fulfillment(order.authorization_id):
            from_state = order.current_state
            order.current_state = fulfill_rule.failure_state
            order.history.append(
                HistoryEntry(
                    from_state=from_state,
                    to_state=fulfill_rule.failure_state,
                    trigger="auto_escalation",
                    errors=[TransitionError(action="fulfill", message="fulfillment failed")],
                )
            )
        else:
            from_state = order.current_state
            order.current_state = fulfill_rule.success_state
            order.history.append(
                HistoryEntry(
                    from_state=from_state,
                    to_state=fulfill_rule.success_state,
                    trigger="complete",
                    errors=[],
                )
            )

        return order
