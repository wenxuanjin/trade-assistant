"""Agent tools.

Start with one tool. Add more later as extra @tool functions,
then pass them in app/agent.py.
"""

import httpx
from langchain_core.tools import tool
from pydantic import ValidationError

from app.config import settings
from app.schemas import TradeAccount, TradeFlow, TradeFlowStep


def _normalize_order_id(order_id: str) -> str:
    key = order_id.strip().upper()
    if not key.startswith("ORD-"):
        return f"ORD-{key}"
    return key


_ORDER_FIELDS = ("orderId", "status", "item", "amount")


def _valid_order_payload(order: object) -> bool:
    """成功响应必须是包含全部必需字符串字段的对象。"""
    if not isinstance(order, dict):
        return False
    return all(isinstance(order.get(field), str) for field in _ORDER_FIELDS)


@tool
def get_order(order_id: str) -> str:
    """Look up an order by order id.

    Use when the user asks about an order's status, item, or amount.
    """
    print(f"get_order: {order_id}")
    normalized = _normalize_order_id(order_id)
    url = f"{settings.trade_service_base_url.rstrip('/')}/api/orders/{normalized}"
    try:
        print(f"url: {url}")
        response = httpx.get(url, timeout=5.0)
    except httpx.TimeoutException:
        return "Trade service timed out."
    except httpx.HTTPError:
        return "Trade service is unavailable."

    if response.status_code == 404:
        return f"Order {normalized} was not found."
    if response.status_code != 200:
        return f"Trade service returned HTTP {response.status_code}."

    try:
        order = response.json()
    except ValueError:
        return "Trade service returned an invalid order response."
    if not _valid_order_payload(order):
        return "Trade service returned an invalid order response."

    return (
        f"order_id={order['orderId']}, status={order['status']}, "
        f"item={order['item']}, amount={order['amount']}"
    )



@tool
def get_trade_flow(order_id: str) -> dict | str:
    """Look up the trade flow of an order by order id.

    Use when the user asks about transaction steps, payment, shipping,
    or the delivery timeline.
    """
    print(f"get_trade_flow: {order_id}")
    normalized = _normalize_order_id(order_id)
    url = f"{settings.trade_service_base_url.rstrip('/')}/api/orders/{normalized}/trade-flow"
    try:
        response = httpx.get(url, timeout=5.0)
    except httpx.HTTPError:
        return _trade_service_unavailable()

    # Java 对不存在的订单返回 404：{"status":404,"message":"Order not found: ..."}
    # 这不是流程数据，转成原来的未找到结构。
    if response.status_code == 404:
        return _missing_flow(normalized)
    if response.status_code != 200:
        return _trade_service_unavailable()

    try:
        return _trade_flow_from_java(response.json())
    except (ValueError, KeyError, TypeError, ValidationError):
        return _trade_service_unavailable()


def _trade_flow_from_java(payload: dict) -> dict:
    """把 Java 的 camelCase 响应映射成 TradeFlow 的 snake_case 字典。"""
    steps = [
        TradeFlowStep(
            step=step["step"],
            name=step["name"],
            status=step["status"],
            occurred_at=step["occurredAt"],
        )
        for step in payload["steps"]
    ]
    return TradeFlow(
        order_id=payload["orderId"],
        found=payload["found"],
        current_status=payload["currentStatus"],
        steps=steps,
    ).model_dump()


def _missing_flow(order_id: str) -> dict:
    return TradeFlow(
        order_id=order_id,
        found=False,
        current_status="not_found",
        steps=[],
    ).model_dump()


def _trade_service_unavailable() -> str:
    """连接失败、超时或响应无法解析时返回，避免异常冒泡到 Agent。"""
    return "Trade service is unavailable."


@tool
def get_trade_account(order_id: str) -> dict | str:
    """Look up the trade account of an order by order id.

    Use when the user asks about the payment account, payer name,
    payment channel, or masked account number.
    """
    print(f"get_trade_account: {order_id}")
    normalized = _normalize_order_id(order_id)
    url = f"{settings.trade_service_base_url.rstrip('/')}/api/orders/{normalized}/trade-account"
    try:
        response = httpx.get(url, timeout=5.0)
    except httpx.HTTPError:
        return _trade_service_unavailable()

    # Java 对不存在的订单返回 404：{"status":404,"message":"Order not found: ..."}
    # 这不是账户数据，转成原来的未找到结构。
    if response.status_code == 404:
        return _missing_account(normalized)
    if response.status_code != 200:
        return _trade_service_unavailable()

    try:
        return _trade_account_from_java(response.json())
    except (ValueError, KeyError, TypeError, ValidationError):
        return _trade_service_unavailable()


def _trade_account_from_java(payload: dict) -> dict:
    """把 Java 的 camelCase 响应映射成 TradeAccount 的 snake_case 字典。"""
    return TradeAccount(
        order_id=payload["orderId"],
        found=payload["found"],
        account_id=payload["accountId"],
        account_name=payload["accountName"],
        payment_channel=payload["paymentChannel"],
        masked_account_no=payload["maskedAccountNo"],
        currency=payload["currency"],
    ).model_dump()


def _missing_account(order_id: str) -> dict:
    return TradeAccount(order_id=order_id, found=False).model_dump()