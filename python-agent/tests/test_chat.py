"""POST /chat 的隔离测试。

run_agent 被替身替换，不会调用真实模型，也不会请求 Java 服务。
"""

import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.agent import run_agent
from app.main import app


class ChatApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("app.main.run_agent", return_value="订单金额是 599.00。")
    def test_chat_returns_agent_reply(self, mock_run_agent):
        response = self.client.post("/chat", json={"message": "查一下订单 ORD-1001"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"reply": "订单金额是 599.00。"})
        mock_run_agent.assert_called_once_with("查一下订单 ORD-1001")

    @patch("app.main.run_agent")
    def test_chat_rejects_empty_message(self, mock_run_agent):
        response = self.client.post("/chat", json={"message": ""})

        self.assertEqual(response.status_code, 422)
        mock_run_agent.assert_not_called()

    @patch("app.main.run_agent")
    def test_chat_rejects_blank_message(self, mock_run_agent):
        for message in (" ", "\t", "\n", " \n\t "):
            with self.subTest(message=repr(message)):
                mock_run_agent.reset_mock()
                response = self.client.post("/chat", json={"message": message})

                self.assertEqual(response.status_code, 422)
                self.assertIn("消息不能为空", response.text)
                mock_run_agent.assert_not_called()

    @patch("app.main.run_agent", return_value="ok")
    def test_chat_preserves_message_text(self, mock_run_agent):
        response = self.client.post("/chat", json={"message": "  查一下 ORD-1001  "})

        self.assertEqual(response.status_code, 200)
        mock_run_agent.assert_called_once_with("  查一下 ORD-1001  ")

    def test_chat_rejects_missing_message(self):
        response = self.client.post("/chat", json={})

        self.assertEqual(response.status_code, 422)

    def test_chat_rejects_non_json_body(self):
        response = self.client.post(
            "/chat",
            content=b"not-json",
            headers={"Content-Type": "application/json"},
        )

        self.assertEqual(response.status_code, 422)

    @patch("app.main.run_agent", side_effect=RuntimeError("model failed"))
    def test_chat_returns_500_when_agent_fails(self, _mock_run_agent):
        response = self.client.post("/chat", json={"message": "查一下订单 ORD-1001"})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {"detail": "订单助手暂时无法回答，请稍后再试。"})
        self.assertNotIn("model failed", response.text)
        self.assertNotIn("Traceback", response.text)


class RunAgentTests(unittest.TestCase):
    """只检查 run_agent 如何取出最终文本，不检查模型会选哪个工具。"""

    @patch("app.agent.graph.invoke")
    def test_returns_final_message_text(self, mock_invoke):
        mock_invoke.return_value = {
            "messages": [
                {"role": "user", "content": "没有订单号"},
                type("Message", (), {"content": "请提供订单号。"})(),
            ]
        }

        self.assertEqual(run_agent("没有订单号"), "请提供订单号。")
        mock_invoke.assert_called_once_with({"messages": [("user", "没有订单号")]})

    @patch("app.agent.graph.invoke")
    def test_stringifies_non_text_final_content(self, mock_invoke):
        mock_invoke.return_value = {
            "messages": [type("Message", (), {"content": [{"type": "text", "text": "ok"}]})()]
        }

        self.assertEqual(
            run_agent("查订单"),
            "[{'type': 'text', 'text': 'ok'}]",
        )


if __name__ == "__main__":
    unittest.main()
