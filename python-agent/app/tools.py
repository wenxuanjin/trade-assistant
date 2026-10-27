"""Agent tools.

Start with one tool. Add more later as extra @tool functions,
then pass them in app/agent.py.
"""

from typing import Annotated

import httpx
from langchain_core.tools import tool
from pydantic import Field, ValidationError

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
def get_order(
    order_id: Annotated[str, Field(description="订单号。可以是 ORD-1001、ord-1001 或 1001。")],
) -> str:
    """按订单号查询这一笔订单的实时状态、商品和金额。

    用户询问某一笔订单的状态、商品或金额时使用。
    只依据本工具的返回回答，不要编造订单服务没有返回的信息。
    订单不存在时如实说明未找到，不要虚构状态、商品或金额。
    不要用它查询交易流程、支付账户或业务规范。
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
def get_trade_flow(
    order_id: Annotated[str, Field(description="订单号。可以是 ORD-1001、ord-1001 或 1001。")],
) -> dict | str:
    """按订单号查询交易流程，包括支付、发货、送达等步骤和时间。

    用户询问交易步骤、支付、发货或送达时间线时使用。
    只依据本工具返回的步骤事实回答。未完成的步骤不能说成已完成。
    不要把预计时间或推断说成真实交易记录。
    不要用它查询订单金额、支付账户或业务规范。
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
def get_trade_account(
    order_id: Annotated[str, Field(description="订单号。可以是 ORD-1001、ord-1001 或 1001。")],
) -> dict | str:
    """按订单号查询支付账户、付款人、支付渠道和掩码账号。

    用户询问付款账户、付款人或支付渠道时使用。
    只依据本工具的返回回答，不要编造支付账户信息。
    不要用它查询订单金额、交易流程或业务规范。
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