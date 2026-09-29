"""Agent tools.

Start with one tool. Add more later as extra @tool functions,
then pass them in app/agent.py.
"""

from langchain_core.tools import tool

from app.schemas import TradeAccount, TradeFlow, TradeFlowStep

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
    print(f"get_order: {order_id}")
    order = _lookup(order_id)
    if order is None:
        return f"Order {order_id} was not found."
    return (
        f"order_id={order['order_id']}, status={order['status']}, "
        f"item={order['item']}, amount={order['amount']}"
    )



# 和订单同一套 mock。key 用规范化后的 order_id。
_TRADE_FLOWS: dict[str, TradeFlow] = {
    "ORD-1001": TradeFlow(
        order_id="ORD-1001",
        found=True,
        current_status="shipped",
        steps=[
            TradeFlowStep(step=1, name="created", status="done", occurred_at="2026-09-20 10:00:00"),
            TradeFlowStep(step=2, name="paid", status="done", occurred_at="2026-09-20 10:05:00"),
            TradeFlowStep(step=3, name="shipped", status="done", occurred_at="2026-09-21 09:00:00"),
            TradeFlowStep(step=4, name="delivered", status="pending", occurred_at=None),
        ],
    ),
    "ORD-1002": TradeFlow(
        order_id="ORD-1002",
        found=True,
        current_status="pending",
        steps=[
            TradeFlowStep(step=1, name="created", status="done", occurred_at="2026-09-26 14:00:00"),
            TradeFlowStep(step=2, name="paid", status="pending", occurred_at=None),
            TradeFlowStep(step=3, name="shipped", status="pending", occurred_at=None),
            TradeFlowStep(step=4, name="delivered", status="pending", occurred_at=None),
        ],
    ),
}


@tool
def get_trade_flow(order_id: str) -> dict:
    """Look up the trade flow of an order by order id.

    Use when the user asks about transaction steps, payment, shipping,
    or the delivery timeline. Data is mock, not from a database.
    """
    print(f"get_trade_flow: {order_id}")
    order = _lookup(order_id)
    if order is None:
        return _missing_flow(order_id)
    flow = _TRADE_FLOWS.get(order["order_id"])
    if flow is None:
        return _missing_flow(order_id)
    return flow.model_dump()


def _missing_flow(order_id: str) -> dict:
    return TradeFlow(
        order_id=order_id,
        found=False,
        current_status="not_found",
        steps=[],
    ).model_dump()


_TRADE_ACCOUNTS: dict[str, TradeAccount] = {
    "ORD-1001": TradeAccount(
        order_id="ORD-1001",
        found=True,
        account_id="ACC-8801",
        account_name="Logan Zhang",
        payment_channel="alipay",
        masked_account_no="138****1001",
        currency="CNY",
    ),
    "ORD-1002": TradeAccount(
        order_id="ORD-1002",
        found=True,
        account_id="ACC-8802",
        account_name="Logan Zhang",
        payment_channel="wechat_pay",
        masked_account_no="138****1002",
        currency="CNY",
    ),
}


@tool
def get_trade_account(order_id: str) -> dict:
    """Look up the trade account of an order by order id.

    Use when the user asks about the payment account, payer name,
    payment channel, or masked account number.
    """
    print(f"get_trade_account: {order_id}")
    order = _lookup(order_id)
    if order is None:
        return _missing_account(order_id)
    account = _TRADE_ACCOUNTS.get(order["order_id"])
    if account is None:
        return _missing_account(order_id)
    return account.model_dump()


def _missing_account(order_id: str) -> dict:
    return TradeAccount(order_id=order_id, found=False).model_dump()