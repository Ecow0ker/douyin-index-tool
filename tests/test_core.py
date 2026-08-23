import csv
import pathlib
import tempfile
import unittest

from douyin_index_tool.accounts import AccountStore, cookie_pairs, has_login_cookie
from douyin_index_tool.aggregate import aggregate_points
from douyin_index_tool.export import write_csv
from douyin_index_tool.models import IndexPoint
from douyin_index_tool.webview_gui import SystemWebViewApi


class CoreTests(unittest.TestCase):
    def test_about_and_repository_contract(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        html = (root / "src/douyin_index_tool/webview_ui/index.html").read_text(encoding="utf-8")
        script = (root / "src/douyin_index_tool/webview_ui/app.js").read_text(encoding="utf-8")
        self.assertIn('id="aboutButton"', html)
        self.assertIn('id="aboutModal"', html)
        self.assertIn("版本：v1.1.0", html)
        self.assertIn("QQ群：610645081", html)
        self.assertIn('placeholder="华为&#10;小米&#10;手机">华为</textarea>', html)
        self.assertIn("$('keywords').value = '华为'", script)
        self.assertIn("Ecow0ker/douyin-index-tool", script)
        self.assertTrue((root / "assets/douyin-index-icon.icns").is_file())
        self.assertTrue((root / "assets/douyin-index-icon.ico").is_file())
        self.assertTrue((root / ".github/workflows/build-macos.yml").is_file())
        self.assertTrue((root / ".github/workflows/build-windows.yml").is_file())

    def test_external_url_validation(self):
        api = SystemWebViewApi(demo=True)
        with self.assertRaises(ValueError):
            api.open_url("file:///tmp/local")

    def test_account_store(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(pathlib.Path(folder) / "accounts.json")
            account = store.add("sessionid=fixture; passport_csrf_token=token", "Fixture/1")
            accounts, strategy = store.load()
            self.assertEqual(len(accounts), 1)
            self.assertEqual(accounts[0].account_id, account.account_id)
            self.assertEqual(strategy, "round_robin")
            store.set_strategy("random")
            self.assertEqual(store.load()[1], "random")
            store.remove(account.account_id)
            self.assertEqual(store.load()[0], [])

    def test_cookie_helpers(self):
        self.assertTrue(has_login_cookie("a=1; sessionid_ss=fixture"))
        self.assertFalse(has_login_cookie("passport_csrf_token=only"))
        self.assertEqual(cookie_pairs("a=1; b=2"), {"a": "1", "b": "2"})

    def test_aggregate_and_export(self):
        rows = [
            IndexPoint("女性", "2025-01-01", 100, 200),
            IndexPoint("女性", "2025-01-02", 300, 400),
        ]
        monthly = aggregate_points(rows, "monthly")
        self.assertEqual(monthly[0].composite_index, 200)
        with tempfile.TemporaryDirectory() as folder:
            output = write_csv(monthly, pathlib.Path(folder) / "out.csv")
            with output.open(encoding="utf-8-sig", newline="") as handle:
                data = list(csv.reader(handle))
            self.assertEqual(data[0][0], "关键词")
            self.assertEqual(data[1][2], "200")

    def test_demo_query(self):
        with tempfile.TemporaryDirectory() as folder:
            store = AccountStore(pathlib.Path(folder) / "accounts.json")
            api = SystemWebViewApi(demo=True, sleep_fn=lambda _: None, account_store=store)
            result = api.query({
                "keywords": ["女性"], "startDate": "2025-01-01", "endDate": "2025-01-03",
                "period": "daily", "interval": 0, "channels": ["composite", "search"],
                "outputDir": folder,
            })
            self.assertFalse(result["cancelled"])
            self.assertEqual(len(result["rows"]), 3)
            self.assertTrue(pathlib.Path(result["outputs"][0]).is_file())


if __name__ == "__main__":
    unittest.main()
