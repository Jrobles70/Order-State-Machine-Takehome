import uuid
from abc import ABC, abstractmethod
from typing import Dict

from app.models import PaymentResult

# Cards that trigger specific failure modes
DECLINE_CARD = "4000000000000002"
CAPTURE_FAIL_VOID_OK_CARD = "4000000000000341"
CAPTURE_FAIL_VOID_FAIL_CARD = "4000000000009995"
FULFILLMENT_FAIL_CARD = "4000000000000259"


class PaymentProvider(ABC):
    @abstractmethod
    def authorize(self, card_number: str, amount_cents: int) -> PaymentResult: ...

    @abstractmethod
    def capture(self, authorization_id: str) -> PaymentResult: ...

    @abstractmethod
    def void(self, authorization_id: str) -> PaymentResult: ...


class StubPaymentProvider(PaymentProvider):
    def __init__(self):
        # Maps authorization_id -> card_number for behavior lookup
        self._authorizations: Dict[str, str] = {}

    def authorize(self, card_number: str, amount_cents: int) -> PaymentResult:
        if card_number == DECLINE_CARD:
            return PaymentResult(success=False, error="card declined")

        auth_id = f"auth_{uuid.uuid4().hex[:12]}"
        self._authorizations[auth_id] = card_number
        return PaymentResult(success=True, authorization_id=auth_id)

    def capture(self, authorization_id: str) -> PaymentResult:
        card = self._authorizations.get(authorization_id, "")
        if card in (CAPTURE_FAIL_VOID_OK_CARD, CAPTURE_FAIL_VOID_FAIL_CARD):
            return PaymentResult(success=False, error="capture failed")
        capture_id = f"cap_{uuid.uuid4().hex[:12]}"
        return PaymentResult(
            success=True,
            authorization_id=authorization_id,
            capture_id=capture_id,
        )

    def void(self, authorization_id: str) -> PaymentResult:
        card = self._authorizations.get(authorization_id, "")
        if card == CAPTURE_FAIL_VOID_FAIL_CARD:
            return PaymentResult(success=False, error="void failed")
        return PaymentResult(success=True, authorization_id=authorization_id)

    def should_fail_fulfillment(self, authorization_id: str) -> bool:
        card = self._authorizations.get(authorization_id, "")
        return card == FULFILLMENT_FAIL_CARD
