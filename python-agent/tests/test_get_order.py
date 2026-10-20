import unittest
from unittest.mock import Mock, patch

import httpx

from app.tools import get_order


class GetOrderTests(unittest.TestCase):
    @patch("app.tools.settings.trade_service_base_url", "http://localhost:8080")
    @patch("app.tools.httpx.get")
    def test_returns_order_on_200(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "orderId": "ORD-1001",
            "status": "shipped",
            "item": "Mechanical Keyboard",
            "amount": "599.00",
        }
        mock_get.return_value = response

        for raw_id in ("ORD-1001", "ord-1001", "1001"):
            with self.subTest(order_id=raw_id):
                mock_get.reset_mock()
                result = get_order.invoke({"order_id": raw_id})
                self.assertEqual(
                    result,
                    "order_id=ORD-1001, status=shipped, item=Mechanical Keyboard, amount=599.00",
                )
                mock_get.assert_called_once_with(
                    "http://localhost:8080/api/orders/ORD-1001",
                    timeout=5.0,
                )

    @patch("app.tools.httpx.get")
    def test_returns_not_found_on_404(self, mock_get):
        response = Mock()
        response.status_code = 404
        mock_get.return_value = response

        result = get_order.invoke({"order_id": "ORD-9999"})

        self.assertEqual(result, "Order ORD-9999 was not found.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_when_service_fails(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("connection refused")

        result = get_order.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service is unavailable.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_timeout(self, mock_get):
        mock_get.side_effect = httpx.ReadTimeout("timed out")

        result = get_order.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service timed out.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_http_500(self, mock_get):
        response = Mock()
        response.status_code = 500
        mock_get.return_value = response

        result = get_order.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service returned HTTP 500.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_on_invalid_json(self, mock_get):
        response = Mock()
        response.status_code = 200
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response

        result = get_order.invoke({"order_id": "ORD-1001"})

        self.assertEqual(result, "Trade service returned an invalid order response.")

    @patch("app.tools.httpx.get")
    def test_returns_unavailable_when_required_fields_missing(self, mock_get):
        complete = {
            "orderId": "ORD-1001",
            "status": "shipped",
            "item": "Mechanical Keyboard",
            "amount": "599.00",
        }
        for field in ("orderId", "status", "item", "amount"):
            with self.subTest(field=field):
                payload = {key: value for key, value in complete.items() if key != field}
                response = Mock()
                response.status_code = 200
                response.json.return_value = payload
                mock_get.return_value = response

                result = get_order.invoke({"order_id": "ORD-1001"})

                self.assertEqual(result, "Trade service returned an invalid order response.")
                self.assertNotIn("order_id=", result)

        for label, payload in (
            ("not an object", ["ORD-1001"]),
            ("non-string amount", {**complete, "amount": 599}),
        ):
            with self.subTest(field=label):
                response = Mock()
                response.status_code = 200
                response.json.return_value = payload
                mock_get.return_value = response

                result = get_order.invoke({"order_id": "ORD-1001"})

                self.assertEqual(result, "Trade service returned an invalid order response.")
                self.assertNotIn("order_id=", result)


if __name__ == "__main__":
    unittest.main()
