from typing import Dict, Optional

from app.models import Order


_orders: Dict[str, Order] = {}


def save(order: Order) -> None:
    _orders[order.id] = order


def get(order_id: str) -> Optional[Order]:
    return _orders.get(order_id)


def clear() -> None:
    _orders.clear()
