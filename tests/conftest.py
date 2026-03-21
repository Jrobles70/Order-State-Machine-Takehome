import pytest

from app import store
from app.main import orchestrator


@pytest.fixture(autouse=True)
def clear_state():
    store.clear()
    orchestrator._payment._authorizations.clear()
    yield
    store.clear()
    orchestrator._payment._authorizations.clear()
