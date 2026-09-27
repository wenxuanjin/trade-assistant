"""Agent tools.

Start with one tool. Add more later as extra @tool functions,
then pass them in app/agent.py.
"""

from langchain_core.tools import tool

# 内存假数据，相当于一个写死的 Repository。后面再换成真实查询。
_ORDERS: dict[str, dict[str, str]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "status": "shipped",
        "item": "Mechanical Keyboard",
        "amount": "599.00",
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "status": "pending",
        "item": "USB-C Cable",
        "amount": "29.00",
    },
}


def _lookup(order_id: str) -> dict[str, str] | None:
    key = order_id.strip().upper()
    if key in _ORDERS:
        return _ORDERS[key]
    if not key.startswith("ORD-"):
        return _ORDERS.get(f"ORD-{key}")
    return None


@tool
def get_order(order_id: str) -> str:
    """Look up an order by order id.

    Use when the user asks about an order's status, item, or amount.
    """
    order = _lookup(order_id)
    if order is None:
        return f"Order {order_id} was not found."
    return (
        f"order_id={order['order_id']}, status={order['status']}, "
        f"item={order['item']}, amount={order['amount']}"
    )
