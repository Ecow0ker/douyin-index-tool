import unittest

from douyin_index_tool.api import AuthenticationError, DouyinIndexClient, parse_trend_payload
from douyin_index_tool.crypto import decrypt_response


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def request_json(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class ApiTests(unittest.TestCase):
    def payload(self):
        return {
            "status": 0,
            "data": {
                "hot_list": [{
                    "keyword": "女性",
                    "hot_list": [
                        {"datetime": "20250101", "index": 123},
                        {"datetime": "20250102", "index": "456.5"},
                    ],
                    "search_hot_list": [
                        {"datetime": "20250101", "index": 789},
                        {"datetime": "20250102", "index": 1000},
                    ],
                    "top_point_list": [{"datetime": "20250102", "type": "peak"}],
                }]
            },
        }

    def test_parse_trend_payload(self):
        rows = parse_trend_payload(self.payload(), ["女性"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].date, "2025-01-01")
        self.assertEqual(rows[0].composite_index, 123)
        self.assertEqual(rows[1].search_index, 1000)
        self.assertEqual(rows[1].composite_marker, "peak")

    def test_query_contract(self):
        transport = FakeTransport(self.payload())
        client = DouyinIndexClient("sessionid=fixture", transport=transport, retries=0)
        rows = client.query_keywords(["女性"], "2025-01-01", "2025-01-02")
        self.assertEqual(len(rows), 2)
        method, url, kwargs = transport.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/api/v2/index/get_multi_keyword_hot_trend"))
        self.assertEqual(kwargs["body"], {
            "keyword_list": ["女性"], "start_date": "20250101",
            "end_date": "20250102", "app_name": "aweme",
        })
        self.assertEqual(kwargs["headers"]["appsource"], "PC")

    def test_authentication_error(self):
        transport = FakeTransport({"status": 10001, "message": "请登录"})
        client = DouyinIndexClient("sessionid=fixture", transport=transport, retries=0)
        with self.assertRaises(AuthenticationError):
            client.hot_words()

    def test_latest_date(self):
        transport = FakeTransport({"status": 0, "data": {"end_date": "20250818"}})
        client = DouyinIndexClient("sessionid=fixture", transport=transport, retries=0)
        self.assertEqual(client.latest_valid_date(), "2025-08-18")

    def test_encrypted_response_version_2(self):
        encrypted = "Fppk7/UXADHCLN6ZsJQF05kgA3tC6ZjYkZCG/endXnOXbJDlGD6niq+gyEBP9YUES5oiXaYVAjmLQdGR/kcJi6R1esk8Bg3YkNpauDRenF4="
        value = decrypt_response(encrypted, "2")
        self.assertEqual(value["hot_words"][0]["keyword"], "fixture")


if __name__ == "__main__":
    unittest.main()
