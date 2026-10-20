"""Agent 工具调用编排测试。

模型是替身：它按测试脚本返回工具调用，最终回答只根据 Agent 回传的工具结果拼出。
这些回复不能当作真实模型会这样选工具或这样写句子的证据。
不会请求模型 API，也不会访问 Java 服务。
"""

import json
import unittest
from contextlib import contextmanager
from typing import Any
from unittest.mock import Mock, patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.agent import graph

_ORDER_PAYLOAD = {
    "orderId": "ORD-1001",
    "status": "shipped",
    "item": "Mechanical Keyboard",
    "amount": "599.00",
}
_FLOW_PAYLOAD = {
    "orderId": "ORD-1001",
    "found": True,
    "currentStatus": "shipped",
    "steps": [
        {"step": 1, "name": "created", "status": "done", "occurredAt": "2026-09-20 10:00:00"},
        {"step": 2, "name": "paid", "status": "done", "occurredAt": "2026-09-20 10:05:00"},
        {"step": 3, "name": "shipped", "status": "done", "occurredAt": "2026-09-21 09:00:00"},
        {"step": 4, "name": "delivered", "status": "pending", "occurredAt": None},
    ],
}
_ACCOUNT_PAYLOAD = {
    "orderId": "ORD-1001",
    "found": True,
    "accountId": "ACC-8801",
    "accountName": "Logan Zhang",
    "paymentChannel": "alipay",
    "maskedAccountNo": "138****1001",
    "currency": "CNY",
}


class ScriptedAgentModel(BaseChatModel):
    """按脚本走 LangChain 的工具调用协议。

    一步可以是若干工具调用、一句直接回复，或 None。
    None 表示这一步必须根据已经回传的 ToolMessage 组织回答。
    """

    steps: list[Any]
    step_index: int = 0
    seen: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-agent-model"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        if self.step_index >= len(self.steps):
            raise AssertionError("模型替身被调用的次数超过了脚本")
        step = self.steps[self.step_index]
        self.step_index += 1
        if step is None:
            message = AIMessage(content=_answer_from_tool_messages(messages))
        elif isinstance(step, str):
            message = AIMessage(content=step)
        else:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": call["name"],
                        "args": call["args"],
                        "id": call["id"],
                        "type": "tool_call",
                    }
                    for call in step
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


def _answer_from_tool_messages(messages: list[BaseMessage]) -> str:
    parts: list[str] = []
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        text = message.content if isinstance(message.content, str) else str(message.content)
        if message.name == "get_order":
            amount = text.split("amount=", 1)[1].split(",", 1)[0].strip()
            parts.append(f"金额是 {amount}")
        elif message.name == "get_trade_account":
            channel = json.loads(text)["payment_channel"]
            parts.append(f"支付渠道是 {channel}")
        elif message.name == "get_trade_flow":
            delivered = next(
                step for step in json.loads(text)["steps"] if step["name"] == "delivered"
            )
            if delivered["status"] == "done":
                parts.append("已经送达")
            else:
                parts.append("尚未送达，因为配送步骤还是 pending")
    if not parts:
        raise AssertionError("组织最终回答时还没有任何工具结果")
    return "；".join(parts) + "。"


def _model_cells():
    node = graph.nodes["model"].bound
    cells = []
    for fn in (node.func, node.afunc):
        for cell in fn.__closure__ or ():
            if isinstance(cell.cell_contents, BaseChatModel):
                cells.append(cell)
    if len(cells) != 2:
        raise AssertionError("无法在现有 Agent 图中定位模型")
    return cells


@contextmanager
def _use_script(steps: list[Any]):
    """把生产 Agent 图里的模型临时换成替身，结束时放回原来的模型。"""
    model = ScriptedAgentModel(steps=steps)
    cells = _model_cells()
    originals = [cell.cell_contents for cell in cells]
    for cell in cells:
        cell.cell_contents = model
    try:
        yield model
    finally:
        for cell, original in zip(cells, originals, strict=True):
            cell.cell_contents = original


def _fake_trade_service(url: str, timeout: float = 5.0):
    response = Mock()
    response.status_code = 200
    if url.endswith("/trade-flow"):
        response.json.return_value = _FLOW_PAYLOAD
    elif url.endswith("/trade-account"):
        response.json.return_value = _ACCOUNT_PAYLOAD
    else:
        response.json.return_value = _ORDER_PAYLOAD
    return response


def _tool_calls(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    calls = []
    for message in messages:
        if isinstance(message, AIMessage):
            calls.extend(message.tool_calls)
    return calls


def _tool_messages(messages: list[BaseMessage]) -> list[ToolMessage]:
    return [message for message in messages if isinstance(message, ToolMessage)]


class AgentBehaviorTests(unittest.TestCase):
    def _ask(self, question: str, steps: list[Any]):
        # 工具调用之后还要再问一次模型，由替身根据工具结果组织最终回答。
        if not steps or not isinstance(steps[-1], str):
            steps = [*steps, None]
        with (
            _use_script(steps) as model,
            patch("app.tools.settings.trade_service_base_url", "http://localhost:8080"),
            patch("app.tools.httpx.get", side_effect=_fake_trade_service) as mock_get,
        ):
            result = graph.invoke({"messages": [("user", question)]})
        self.assertEqual(
            model.bound_tool_names,
            ["get_order", "get_trade_flow", "get_trade_account"],
        )
        system = model.seen[0][0]
        self.assertIsInstance(system, SystemMessage)
        self.assertIn("If no order id is given, ask for one.", system.content)
        return result, model, mock_get

    def test_amount_question_calls_get_order_and_answers_from_tool_result(self):
        result, model, mock_get = self._ask(
            "ORD-1001 的金额是多少",
            [[{"name": "get_order", "args": {"order_id": "ORD-1001"}, "id": "call_order"}]],
        )

        calls = _tool_calls(result["messages"])
        self.assertEqual(
            [(call["name"], call["args"], call["id"]) for call in calls],
            [("get_order", {"order_id": "ORD-1001"}, "call_order")],
        )
        tool_messages = _tool_messages(result["messages"])
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(tool_messages[0].name, "get_order")
        self.assertEqual(tool_messages[0].tool_call_id, "call_order")
        self.assertIn("amount=599.00", tool_messages[0].content)
        self.assertEqual(result["messages"][-1].content, "金额是 599.00。")
        self.assertEqual(len(model.seen), 2)
        self.assertEqual(_tool_messages(model.seen[1])[0].content, tool_messages[0].content)
        mock_get.assert_called_once_with(
            "http://localhost:8080/api/orders/ORD-1001",
            timeout=5.0,
        )

    def test_delivery_question_calls_get_trade_flow(self):
        result, model, mock_get = self._ask(
            "ORD-1001 为什么还没送达",
            [[{"name": "get_trade_flow", "args": {"order_id": "ORD-1001"}, "id": "call_flow"}]],
        )

        calls = _tool_calls(result["messages"])
        self.assertEqual(
            [(call["name"], call["args"]) for call in calls],
            [("get_trade_flow", {"order_id": "ORD-1001"})],
        )
        self.assertEqual(result["messages"][-1].content, "尚未送达，因为配送步骤还是 pending。")
        self.assertEqual(len(model.seen), 2)
        self.assertEqual(_tool_messages(model.seen[1])[0].name, "get_trade_flow")
        mock_get.assert_called_once_with(
            "http://localhost:8080/api/orders/ORD-1001/trade-flow",
            timeout=5.0,
        )

    def test_amount_and_channel_call_two_tools_in_one_response(self):
        result, model, mock_get = self._ask(
            "ORD-1001 的金额和支付渠道是什么",
            [[
                {"name": "get_order", "args": {"order_id": "ORD-1001"}, "id": "call_order"},
                {"name": "get_trade_account", "args": {"order_id": "ORD-1001"}, "id": "call_account"},
            ]],
        )

        calls = _tool_calls(result["messages"])
        self.assertEqual(
            [(call["name"], call["args"], call["id"]) for call in calls],
            [
                ("get_order", {"order_id": "ORD-1001"}, "call_order"),
                ("get_trade_account", {"order_id": "ORD-1001"}, "call_account"),
            ],
        )
        self.assertEqual(len([message for message in result["messages"] if isinstance(message, AIMessage) and message.tool_calls]), 1)
        returned = {(message.name, message.tool_call_id) for message in _tool_messages(model.seen[1])}
        self.assertEqual(returned, {("get_order", "call_order"), ("get_trade_account", "call_account")})
        self.assertEqual(result["messages"][-1].content, "金额是 599.00；支付渠道是 alipay。")
        self.assertEqual(mock_get.call_count, 2)
        urls = {call.args[0] for call in mock_get.call_args_list}
        self.assertEqual(
            urls,
            {
                "http://localhost:8080/api/orders/ORD-1001",
                "http://localhost:8080/api/orders/ORD-1001/trade-account",
            },
        )

    def test_amount_channel_and_delivery_call_tools_across_turns(self):
        result, model, mock_get = self._ask(
            "ORD-1001 的金额、支付渠道是什么，为什么还没送达",
            [
                [{"name": "get_order", "args": {"order_id": "ORD-1001"}, "id": "call_order"}],
                [{"name": "get_trade_account", "args": {"order_id": "ORD-1001"}, "id": "call_account"}],
                [{"name": "get_trade_flow", "args": {"order_id": "ORD-1001"}, "id": "call_flow"}],
            ],
        )

        self.assertEqual(
            [(call["name"], call["args"], call["id"]) for call in _tool_calls(result["messages"])],
            [
                ("get_order", {"order_id": "ORD-1001"}, "call_order"),
                ("get_trade_account", {"order_id": "ORD-1001"}, "call_account"),
                ("get_trade_flow", {"order_id": "ORD-1001"}, "call_flow"),
            ],
        )
        self.assertEqual(
            [message.name for message in _tool_messages(model.seen[1])],
            ["get_order"],
        )
        self.assertEqual(
            [message.name for message in _tool_messages(model.seen[2])],
            ["get_order", "get_trade_account"],
        )
        self.assertEqual(
            [message.name for message in _tool_messages(model.seen[3])],
            ["get_order", "get_trade_account", "get_trade_flow"],
        )
        self.assertEqual(
            [(message.name, message.tool_call_id) for message in _tool_messages(result["messages"])],
            [
                ("get_order", "call_order"),
                ("get_trade_account", "call_account"),
                ("get_trade_flow", "call_flow"),
            ],
        )
        self.assertEqual(
            result["messages"][-1].content,
            "金额是 599.00；支付渠道是 alipay；尚未送达，因为配送步骤还是 pending。",
        )
        self.assertEqual(mock_get.call_count, 3)

    def test_missing_order_id_asks_instead_of_inventing_one(self):
        result, model, mock_get = self._ask("订单金额是多少", ["请提供订单号。"])

        self.assertEqual(result["messages"][-1].content, "请提供订单号。")
        self.assertNotIn("ORD-", result["messages"][-1].content)
        self.assertEqual(_tool_calls(result["messages"]), [])
        self.assertEqual(_tool_messages(result["messages"]), [])
        self.assertEqual(len(model.seen), 1)
        self.assertIn("ask for one", model.seen[0][0].content)
        mock_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
