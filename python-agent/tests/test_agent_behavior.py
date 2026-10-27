"""Agent 工具调用编排测试。

模型是替身：它按测试脚本返回工具调用，最终回答只根据 Agent 回传的工具结果拼出。
这些回复不能当作真实模型会这样选工具或这样写句子的证据。
不会请求模型 API，也不会访问 Java 服务。
"""

import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from app.agent import graph
from app.rag.ingest import load_knowledge_chunks
from app.rag.retriever import build_index
from app.rag.tool import knowledge_search, search_trade_knowledge
from app.tools import get_order, get_trade_account, get_trade_flow
from tests.test_rag_retriever import BrokenEmbeddings, HashEmbeddings

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
            if "was not found" in text:
                parts.append("没有查到这笔订单")
            else:
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
        elif message.name == "search_trade_knowledge":
            parts.append(text)
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
            ["get_order", "get_trade_flow", "get_trade_account", "search_trade_knowledge"],
        )
        system = model.seen[0][0]
        self.assertIsInstance(system, SystemMessage)
        self.assertIn(
            "如果用户没有给出订单号，并且回答确实需要某一笔订单的实时事实，才向用户追问订单号。",
            system.content,
        )
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
        self.assertIn("如果用户没有给出订单号，并且回答确实需要某一笔订单的实时事实，才向用户追问订单号。", model.seen[0][0].content)
        mock_get.assert_not_called()


@contextmanager
def _configured_knowledge_search(
    embeddings,
    index_dir: Path,
    max_distance: float | None,
    top_k: int = 3,
    embedding_model_id: str | None = None,
):
    saved = (
        knowledge_search.embeddings,
        knowledge_search.index_dir,
        knowledge_search.top_k,
        knowledge_search.max_distance,
        knowledge_search.embedding_model_id,
    )
    knowledge_search.embeddings = embeddings
    knowledge_search.index_dir = index_dir
    knowledge_search.top_k = top_k
    knowledge_search.max_distance = max_distance
    knowledge_search.embedding_model_id = embedding_model_id
    try:
        yield
    finally:
        (
            knowledge_search.embeddings,
            knowledge_search.index_dir,
            knowledge_search.top_k,
            knowledge_search.max_distance,
            knowledge_search.embedding_model_id,
        ) = saved


class KnowledgeToolTests(unittest.TestCase):
    def test_order_tools_keep_their_parameters(self):
        self.assertEqual(get_order.name, "get_order")
        self.assertEqual(get_trade_flow.name, "get_trade_flow")
        self.assertEqual(get_trade_account.name, "get_trade_account")
        self.assertEqual(set(get_order.args), {"order_id"})
        self.assertEqual(set(get_trade_flow.args), {"order_id"})
        self.assertEqual(set(get_trade_account.args), {"order_id"})
        self.assertEqual(search_trade_knowledge.name, "search_trade_knowledge")
        self.assertEqual(set(search_trade_knowledge.args), {"query"})

    def test_unconfigured_embeddings_are_not_a_normal_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            with _configured_knowledge_search(None, Path(directory), None):
                text = search_trade_knowledge.invoke({"query": "待处理是什么意思"})

        self.assertIn("status: RETRIEVAL_ERROR", text)
        self.assertIn("Embedding 未配置", text)
        self.assertNotIn("无充分依据", text)
        self.assertNotIn("不是真实企业政策", text)

    def test_knowledge_question_returns_evidence_to_the_model(self):
        chunks = load_knowledge_chunks(Path(__file__).resolve().parents[1] / "knowledge")
        target = next(chunk for chunk in chunks if chunk.section == "订单状态定义 / 待处理")
        embeddings = HashEmbeddings()
        question = "待处理状态是什么意思"
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index(chunks, embeddings, index_dir)
            with _configured_knowledge_search(embeddings, index_dir, max_distance=0.0):
                result, model, mock_get = AgentBehaviorTests()._ask(
                    question,
                    [[
                        {
                            "name": "search_trade_knowledge",
                            "args": {"query": target.content},
                            "id": "call_knowledge",
                        }
                    ]],
                )

        tool_message = _tool_messages(result["messages"])[0]
        self.assertEqual(tool_message.name, "search_trade_knowledge")
        self.assertIn("status: HIT", tool_message.content)
        self.assertIn(target.title, tool_message.content)
        self.assertIn(target.section, tool_message.content)
        self.assertIn(target.source, tool_message.content)
        self.assertIn(target.chunk_id, tool_message.content)
        self.assertIn(target.content, tool_message.content)
        self.assertIn("squared_l2_distance", tool_message.content)
        self.assertEqual(_tool_messages(model.seen[1])[0].content, tool_message.content)
        self.assertIn(tool_message.content, result["messages"][-1].content)
        self.assertIn("只询问业务规范的问题不需要订单号。", model.seen[0][0].content)
        mock_get.assert_not_called()

    def test_flow_then_knowledge_returns_both_results(self):
        chunks = load_knowledge_chunks(Path(__file__).resolve().parents[1] / "knowledge")
        target = next(chunk for chunk in chunks if chunk.section == "发货后未送达的排查流程 / 核对订单是否已发货")
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index(chunks, embeddings, index_dir)
            with _configured_knowledge_search(embeddings, index_dir, max_distance=0.0):
                result, model, mock_get = AgentBehaviorTests()._ask(
                    "ORD-1001 为什么还没送达，规范上要怎么排查",
                    [
                        [{"name": "get_trade_flow", "args": {"order_id": "ORD-1001"}, "id": "call_flow"}],
                        [{
                            "name": "search_trade_knowledge",
                            "args": {"query": target.content},
                            "id": "call_knowledge",
                        }],
                    ],
                )

        self.assertEqual(
            [call["name"] for call in _tool_calls(result["messages"])],
            ["get_trade_flow", "search_trade_knowledge"],
        )
        self.assertEqual([message.name for message in _tool_messages(model.seen[1])], ["get_trade_flow"])
        self.assertEqual(
            [message.name for message in _tool_messages(model.seen[2])],
            ["get_trade_flow", "search_trade_knowledge"],
        )
        final = result["messages"][-1].content
        self.assertIn("尚未送达，因为配送步骤还是 pending", final)
        self.assertIn("status: HIT", final)
        self.assertIn(target.section, final)
        mock_get.assert_called_once()

    def test_order_and_knowledge_can_be_called_in_one_response(self):
        chunks = load_knowledge_chunks(Path(__file__).resolve().parents[1] / "knowledge")
        target = next(chunk for chunk in chunks if chunk.section == "退款处理规则 / 未发货退款")
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            index_dir = Path(directory)
            build_index(chunks, embeddings, index_dir)
            with _configured_knowledge_search(embeddings, index_dir, max_distance=0.0):
                result, model, mock_get = AgentBehaviorTests()._ask(
                    "ORD-1001 的金额是多少，未发货退款规则是什么",
                    [[
                        {"name": "get_order", "args": {"order_id": "ORD-1001"}, "id": "call_order"},
                        {
                            "name": "search_trade_knowledge",
                            "args": {"query": target.content},
                            "id": "call_knowledge",
                        },
                    ]],
                )

        returned = {(message.name, message.tool_call_id) for message in _tool_messages(model.seen[1])}
        self.assertEqual(
            returned,
            {("get_order", "call_order"), ("search_trade_knowledge", "call_knowledge")},
        )
        final = result["messages"][-1].content
        self.assertIn("金额是 599.00", final)
        self.assertIn(target.section, final)
        self.assertIn("未发货的订单可以按未出库处理退款", final)
        mock_get.assert_called_once()

    def test_insufficient_index_not_ready_and_retrieval_error_stay_distinct(self):
        chunks = load_knowledge_chunks(Path(__file__).resolve().parents[1] / "knowledge")
        embeddings = HashEmbeddings()
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "ready"
            missing = Path(directory) / "missing"
            build_index(chunks, embeddings, ready)
            with _configured_knowledge_search(embeddings, ready, max_distance=0.0):
                missed = search_trade_knowledge.invoke({"query": "与规范完全无关的句子"})
            with _configured_knowledge_search(embeddings, missing, max_distance=0.0):
                not_ready = search_trade_knowledge.invoke({"query": "待处理是什么意思"})
            with _configured_knowledge_search(BrokenEmbeddings(), ready, max_distance=0.0):
                failed = search_trade_knowledge.invoke({"query": "待处理是什么意思"})

        self.assertIn("status: INSUFFICIENT_EVIDENCE", missed)
        self.assertIn("检索已执行，但无充分依据。", missed)
        self.assertNotIn("业务规则不存在", missed)
        self.assertIn("status: INDEX_NOT_READY", not_ready)
        self.assertIn("索引尚未准备好", not_ready)
        self.assertNotIn("无充分依据", not_ready)
        self.assertIn("status: RETRIEVAL_ERROR", failed)
        self.assertIn("RuntimeError", failed)
        self.assertIn("这不是一次正常的无命中", failed)
        self.assertNotIn("无充分依据", failed)


if __name__ == "__main__":
    unittest.main()
