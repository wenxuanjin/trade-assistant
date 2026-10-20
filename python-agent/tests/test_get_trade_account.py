import unittest
from unittest.mock import Mock, patch

import httpx

from app.tools import get_trade_account


class GetTradeAccountTests(unittest.TestCase):
    @patch("app.tools.settings.trade_service_base_url", "http://localhost:8080")
    @patch("app.tools.httpx.get")
    def test_returns_account_on_200(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "orderId": "ORD-1001",
            "found": True,
            "accountId": "ACC-8801",
            "accountName": "Logan Zhang",
            "paymentChannel": "alipay",
            "maskedAccountNo": "138****1001",
            "currency": "CNY",
        }
        mock_get.return_value = response

        for raw_id in ("ORD-1001", "ord-1001", "1001"):
            with self.subTest(order_id=raw_id):
                mock_get.reset_mock()
                result = get_trade_account.invoke({"order_id": raw_id})
                self.assertEqual(
                    result,
                    {
                        "order_id": "ORD-1001",
                        "found": True,
                        "account_id": "ACC-8801",
                        "account_name": "Logan Zhang",
                        "payment_channel": "alipay",
                        "masked_account_no": "138****1001",
                        "currency": "CNY",
                    },
                )
                mock_get.assert_called_once_with(
                    "http://localhost:8080/api/orders/ORD-1001/trade-account",
                    timeout=5.0,
                )

    @patch("app.tools.httpx.get")
    def test_returns_missing_account_on_404(self, mock_get):
        response = Mock()
        response.status_code = 404
        response.json.return_value = {
            "status": 404,
            "message": "Order not found: ORD-9999",
        }
        mock_get.return_value = response

        result = get_trade_account.invoke({"order_id": "ORD-9999"})

        self.assertEqual(
            result,
            {
                "order_id": "ORD-9999",
                "found": False,
                "account_id": None,
                "account_name": None,
                "payment_channel": None,
                "masked_account_no": None,
                "currency": None,
            },
        )

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_when_service_fails(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        result = get_trade_account.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_timeout(self, mock_get):
        mock_get.side_effect = httpx.ReadTimeout("timed out")

        result = get_trade_account.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_http_500(self, mock_get):
        response = Mock()
        response.status_code = 500
        mock_get.return_value = response

        result = get_trade_account.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_invalid_json(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response

        result = get_trade_account.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")


if __name__ == "__main__":
    unittest.main()
