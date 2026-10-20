import unittest
from unittest.mock import Mock, patch

import httpx

from app.tools import get_trade_flow


class GetTradeFlowTests(unittest.TestCase):
    @patch("app.tools.settings.trade_service_base_url", "http://localhost:8080")
    @patch("app.tools.httpx.get")
    def test_returns_flow_on_200(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "orderId": "ORD-1001",
            "found": True,
            "currentStatus": "shipped",
            "steps": [
                {
                    "step": 1,
                    "name": "created",
                    "status": "done",
                    "occurredAt": "2026-09-20 10:00:00",
                },
                {
                    "step": 2,
                    "name": "paid",
                    "status": "done",
                    "occurredAt": "2026-09-20 10:05:00",
                },
                {
                    "step": 3,
                    "name": "shipped",
                    "status": "done",
                    "occurredAt": "2026-09-21 09:00:00",
                },
                {
                    "step": 4,
                    "name": "delivered",
                    "status": "pending",
                    "occurredAt": None,
                },
            ],
        }
        mock_get.return_value = response

        for raw_id in ("ORD-1001", "ord-1001", "1001"):
            with self.subTest(order_id=raw_id):
                mock_get.reset_mock()
                result = get_trade_flow.invoke({"order_id": raw_id})
                self.assertEqual(
                    result,
                    {
                        "order_id": "ORD-1001",
                        "found": True,
                        "current_status": "shipped",
                        "steps": [
                            {
                                "step": 1,
                                "name": "created",
                                "status": "done",
                                "occurred_at": "2026-09-20 10:00:00",
                            },
                            {
                                "step": 2,
                                "name": "paid",
                                "status": "done",
                                "occurred_at": "2026-09-20 10:05:00",
                            },
                            {
                                "step": 3,
                                "name": "shipped",
                                "status": "done",
                                "occurred_at": "2026-09-21 09:00:00",
                            },
                            {
                                "step": 4,
                                "name": "delivered",
                                "status": "pending",
                                "occurred_at": None,
                            },
                        ],
                    },
                )
                mock_get.assert_called_once_with(
                    "http://localhost:8080/api/orders/ORD-1001/trade-flow",
                    timeout=5.0,
                )

    @patch("app.tools.httpx.get")
    def test_returns_missing_flow_on_404(self, mock_get):
        response = Mock()
        response.status_code = 404
        response.json.return_value = {
            "status": 404,
            "message": "Order not found: ORD-9999",
        }
        mock_get.return_value = response

        result = get_trade_flow.invoke({"order_id": "ORD-9999"})

        self.assertEqual(
            result,
            {
                "order_id": "ORD-9999",
                "found": False,
                "current_status": "not_found",
                "steps": [],
            },
        )

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_when_service_fails(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        result = get_trade_flow.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_timeout(self, mock_get):
        mock_get.side_effect = httpx.ReadTimeout("timed out")

        result = get_trade_flow.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_http_500(self, mock_get):
        response = Mock()
        response.status_code = 500
        mock_get.return_value = response

        result = get_trade_flow.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_invalid_json(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response

        result = get_trade_flow.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")


if __name__ == "__main__":
    unittest.main()
