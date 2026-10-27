"""回答风格约束。模型仍是替身，这些测试检查提示词和工具事实，不证明真实模型的文风。"""

import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import graph
from tests.test_agent_behavior import (
    AgentBehaviorTests,
    _tool_messages,
    _use_script,
)

_DEVELOPER_PHRASES = (
    "订单服务确认的事实",
    "知识库中的模拟业务规范",
    "结论与下一步建议",
    "当前系统能力边界",
)


def _style_problems(answer: str, *, required: tuple[str, ...] = (), forbidden: tuple[str, ...] = ()) -> list[str]:
    """检查一段回答是否直白、短、没有报告腔。不要求整句与样例完全一致。"""
    problems: list[str] = []
    for line in answer.splitlines():
        if line.strip().startswith("#"):
            problems.append("使用了 Markdown 标题")
    if "**" in answer:
        problems.append("使用了粗体")
    for phrase in _DEVELOPER_PHRASES:
        if phrase in answer:
            problems.append(f"使用了开发向说法：{phrase}")
    for phrase in forbidden:
        if phrase in answer:
            problems.append(f"包含不该出现的说法：{phrase}")
    for phrase in required:
        if phrase not in answer:
            problems.append(f"缺少必要事实：{phrase}")
    return problems


class AnswerStyleTests(unittest.TestCase):
    def _prompt_for(self, question: str, steps: list) -> str:
        _, model, _ = AgentBehaviorTests()._ask(question, steps)
        system = model.seen[0][0]
        self.assertIsInstance(system, SystemMessage)
        asked = [message.content for message in model.seen[-1] if isinstance(message, HumanMessage)]
        self.assertIn(question, asked)
        return system.content

    def test_prompt_asks_for_plain_customer_language(self):
        prompt = self._prompt_for("你好", ["好的。"])
        self.assertIn("自然、口语、礼貌", prompt)
        self.assertIn("先直接回答用户最关心的问题", prompt)
        self.assertIn("简单问题用自然段", prompt)
        self.assertIn("不要用 Markdown 标题", prompt)
        for phrase in _DEVELOPER_PHRASES:
            self.assertIn(phrase, prompt)
        self.assertLess(prompt.index("不要说给开发人员听的话"), prompt.index(_DEVELOPER_PHRASES[0]))
        self.assertIn("不要每句都加", prompt)
        self.assertIn("只追问一个最有帮助的问题", prompt)

    def test_refund_answer_must_stay_conditional(self):
        prompt = self._prompt_for("ORD-1001 是否能退款", ["先看订单和退款规则。"])
        self.assertIn("问退款等规则时，说明当前规则和还需要确认的条件", prompt)
        self.assertIn("不是真实企业的退款政策", prompt)
        self.assertIn("暂时还不能确定，不能说成肯定不能退", prompt)
        self.assertIn("不得声称已经执行退款", prompt)
        self.assertIn("我暂时无法查询实时物流，所以还不能确认最终能否退款。", prompt)
        natural = "这笔订单已经发货。按照目前的退款规则，需要先确认物流情况，我暂时还不能确定能不能退。"
        self.assertEqual(
            _style_problems(natural, forbidden=("肯定不能退", "已经帮你退了", "公司正式规定")),
            [],
        )
        report = "结论与下一步建议：根据知识库中的模拟业务规范，肯定不能退款。"
        self.assertTrue(_style_problems(report, forbidden=("肯定不能退",)))

    def test_progress_answer_must_not_treat_missing_delivery_as_confirmed(self):
        result, model, _ = AgentBehaviorTests()._ask(
            "ORD-1001 现在到哪一步了",
            [[{"name": "get_trade_flow", "args": {"order_id": "ORD-1001"}, "id": "call_flow"}]],
        )
        prompt = model.seen[0][0].content
        self.assertIn("没有送达记录，只能说系统里还没有送达记录，不能说成已经确认货物还没送到。", prompt)
        self.assertEqual(prompt.count("已经确认货物还没送到"), 1)
        self.assertIn("没完成的步骤不能说成已完成", prompt)
        flow = _tool_messages(result["messages"])[0].content
        self.assertIn('"status": "pending"', flow)

    def test_missing_order_asks_for_one_next_step_without_inventing_details(self):
        def missing(_url: str, timeout: float = 5.0):
            response = Mock()
            response.status_code = 404
            response.json.return_value = {"status": 404, "message": "Order not found: ORD-9999"}
            return response

        with (
            _use_script([
                [{"name": "get_order", "args": {"order_id": "ORD-9999"}, "id": "call_order"}],
                None,
            ]) as model,
            patch("app.tools.settings.trade_service_base_url", "http://localhost:8080"),
            patch("app.tools.httpx.get", side_effect=missing),
        ):
            result = graph.invoke({"messages": [("user", "ORD-9999 查不到怎么办")]})
        prompt = model.seen[0][0].content
        self.assertIn("订单不存在时直接说没查到，不要编状态、商品、金额或物流。", prompt)
        self.assertIn("只追问一个最有帮助的问题", prompt)
        answer = result["messages"][-1].content
        self.assertEqual(_style_problems(answer, required=("没有查到这笔订单",)), [])
        self.assertNotIn("599.00", answer)
        self.assertNotIn("Mechanical Keyboard", answer)

    def test_amount_only_answer_stays_short(self):
        result, _, _ = AgentBehaviorTests()._ask(
            "ORD-1001 的金额是多少",
            [[{"name": "get_order", "args": {"order_id": "ORD-1001"}, "id": "call_order"}]],
        )
        answer = result["messages"][-1].content
        problems = _style_problems(answer, required=("599.00",), forbidden=("退款", "物流", "政策"))
        self.assertEqual(problems, [])
        self.assertLess(len(answer), 40)
        self.assertEqual(answer.count("\n"), 0)
