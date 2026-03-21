import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_order(client):
    response = client.post("/orders", json={"amount": 99.99})
    assert response.status_code == 201
    data = response.json()
    assert data["current_state"] == "initialized"
    assert data["amount"] == 99.99
    assert data["history"] == []


def test_authorize_order(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={
            "card_number": "4242424242424242",
            "exp_month": 12,
            "exp_year": 2028,
            "cvv": "123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "payment_authorized"
    assert data["exp_month"] == 12
    assert data["exp_year"] == 2028
    assert len(data["history"]) == 1


def test_authorize_rejects_invalid_exp_month(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "4242424242424242", "exp_month": 13, "exp_year": 2028, "cvv": "123"},
    )
    assert response.status_code == 422


def test_authorize_rejects_invalid_cvv(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "4242424242424242", "exp_month": 12, "exp_year": 2028, "cvv": "12"},
    )
    assert response.status_code == 422


def test_authorize_rejects_non_4_digit_exp_year(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "4242424242424242", "exp_month": 12, "exp_year": 28, "cvv": "123"},
    )
    assert response.status_code == 422


def test_authorize_rejects_expired_card(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "4242424242424242", "exp_month": 1, "exp_year": 2020, "cvv": "123"},
    )
    assert response.status_code == 422


def test_authorize_rejects_expired_card_current_year_past_month(client):
    """A card that expired earlier this year should be rejected."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    # Use a month in the past of the current year (only valid if we're not in January)
    if now.month > 1:
        response = client.post("/orders", json={"amount": 50.00})
        order_id = response.json()["id"]

        resp = client.post(
            f"/orders/{order_id}/authorize",
            json={
                "card_number": "4242424242424242",
                "exp_month": now.month - 1,
                "exp_year": now.year,
                "cvv": "123",
            },
        )
        assert resp.status_code == 422


def test_authorize_rejects_non_digit_card_number(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "abcd1234abcd1234", "exp_month": 12, "exp_year": 2028, "cvv": "123"},
    )
    assert response.status_code == 422


def test_authorize_rejects_card_number_wrong_length(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "123456", "exp_month": 12, "exp_year": 2028, "cvv": "123"},
    )
    assert response.status_code == 422


def test_cvv_not_on_order(client):
    """CVV must never be stored on the Order model."""
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    client.post(
        f"/orders/{order_id}/authorize",
        json={"card_number": "4242424242424242", "exp_month": 12, "exp_year": 2028, "cvv": "123"},
    )
    response = client.get(f"/orders/{order_id}")
    assert "cvv" not in response.json()


def test_complete_order_happy_path(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4242424242424242", "exp_month": 12, "exp_year": 2028, "cvv": "123"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "complete"
    assert len(data["history"]) == 3


def test_payment_decline(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000002", "exp_month": 12, "exp_year": 2028, "cvv": "123"})
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "rejected"
    assert len(data["history"][0]["errors"]) == 1


def test_capture_fail_void_succeeds(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000341", "exp_month": 12, "exp_year": 2028, "cvv": "123"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "cancelled"


def test_capture_fail_void_fails(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000009995", "exp_month": 12, "exp_year": 2028, "cvv": "123"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "needs_attention"
    assert len(data["history"][1]["errors"]) == 2


def test_fulfillment_failure(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000259", "exp_month": 12, "exp_year": 2028, "cvv": "123"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "needs_attention"
    assert len(data["history"]) == 3


def test_get_order(client):
    create = client.post("/orders", json={"amount": 75.00})
    order_id = create.json()["id"]

    response = client.get(f"/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["id"] == order_id


def test_get_order_not_found(client):
    response = client.get("/orders/nonexistent")
    assert response.status_code == 404


def test_invalid_transition_returns_400(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    # Try to complete without authorizing first
    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 400
