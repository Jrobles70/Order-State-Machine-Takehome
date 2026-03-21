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

    response = client.post(f"/orders/{order_id}/authorize", json={"card_number": "4242424242424242"})
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "payment_authorized"
    assert len(data["history"]) == 1


def test_complete_order_happy_path(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4242424242424242"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "complete"
    assert len(data["history"]) == 3


def test_payment_decline(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]

    response = client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000002"})
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "rejected"
    assert len(data["history"][0]["errors"]) == 1


def test_capture_fail_void_succeeds(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000341"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "cancelled"


def test_capture_fail_void_fails(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000009995"})

    response = client.post(f"/orders/{order_id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "needs_attention"
    assert len(data["history"][1]["errors"]) == 2


def test_fulfillment_failure(client):
    create = client.post("/orders", json={"amount": 50.00})
    order_id = create.json()["id"]
    client.post(f"/orders/{order_id}/authorize", json={"card_number": "4000000000000259"})

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
