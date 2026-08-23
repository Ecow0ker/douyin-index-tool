from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .accounts import AccountStore, has_login_cookie, public_accounts
from .aggregate import aggregate_points
from .api import AuthenticationError, DouyinIndexClient, NoDataError, RateLimitError, validate_date_range
from .export import write_csv
from .models import Account, IndexPoint

APP_NAME = "抖音指数查询工具"
APP_VERSION = "1.1.0"
LOGIN_URL = "https://creator.douyin.com/creator-micro/creator-count/arithmetic-index"


def _default_dates() -> Tuple[str, str]:
    # 抖音指数通常存在数日的数据延迟；默认按页面当前行为预留 5 天。
    end = dt.date.today() - dt.timedelta(days=5)
    start = end - dt.timedelta(days=30)
    return start.isoformat(), end.isoformat()


class SystemWebViewApi:
    def __init__(self, demo: bool = False, sleep_fn=time.sleep, account_store: Optional[AccountStore] = None):
        self._demo = demo
        self._sleep_fn = sleep_fn
        self._store = account_store or AccountStore()
        self._main_window = None
        self._login_window = None
        self._login_factory = None
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()
        self._window_lock = threading.Lock()
        self._shutting_down = False

    def bind_main_window(self, window: Any) -> None:
        self._main_window = window

    def set_login_window_factory(self, factory) -> None:
        self._login_factory = factory

    def _window_is_closed(self, window: Any) -> bool:
        closed = getattr(getattr(window, "events", None), "closed", None)
        try:
            return bool(closed and closed.is_set())
        except Exception:
            return False

    def release_login_window(self, window: Any) -> None:
        with self._window_lock:
            if self._login_window is window:
                self._login_window = None

    def _ensure_login_window(self):
        with self._window_lock:
            window = self._login_window
            if window is not None and self._window_is_closed(window):
                self._login_window = None
                window = None
            if window is None and not self._shutting_down and self._login_factory:
                window = self._login_factory()
                self._login_window = window
            return window

    def shutdown(self) -> None:
        self._shutting_down = True
        with self._window_lock:
            window, self._login_window = self._login_window, None
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    def _emit(self, name: str, payload: Dict[str, Any]) -> None:
        if not self._main_window:
            return
        script = "window.__pythonEvent && window.__pythonEvent(%s,%s)" % (
            json.dumps(name, ensure_ascii=False), json.dumps(payload, ensure_ascii=False),
        )
        try:
            self._main_window.evaluate_js(script)
        except Exception:
            pass

    @staticmethod
    def _cookie_header(cookies: Sequence[Any]) -> str:
        selected: Dict[str, Tuple[Tuple[int, int, int], str]] = {}
        for cookie in cookies:
            if hasattr(cookie, "items"):
                entries = [(
                    str(name), str(getattr(morsel, "value", "") or ""),
                    str(morsel["domain"] or ""), str(morsel["path"] or "/"),
                ) for name, morsel in cookie.items()]
            else:
                entries = [(
                    str(getattr(cookie, "name", "") or ""),
                    str(getattr(cookie, "value", "") or ""),
                    str(getattr(cookie, "domain", "") or ""),
                    str(getattr(cookie, "path", "/") or "/"),
                )]
            for name, value, raw_domain, path in entries:
                domain = raw_domain.lstrip(".").lower()
                if domain != "douyin.com" and not domain.endswith(".douyin.com"):
                    continue
                score = (1 if domain == "douyin.com" else 0, 1 if path == "/" else 0, -len(path))
                if name and value and (name not in selected or score >= selected[name][0]):
                    selected[name] = (score, value)
        return "; ".join("%s=%s" % (name, selected[name][1]) for name in sorted(selected))

    def bootstrap(self) -> Dict[str, Any]:
        accounts, strategy = self._store.load()
        start, end = _default_dates()
        return {
            "version": APP_VERSION,
            "accounts": public_accounts(accounts),
            "strategy": strategy,
            "demo": self._demo,
            "startDate": start,
            "endDate": end,
            "outputDir": str(pathlib.Path.home() / "Downloads" / "抖音指数数据"),
        }

    def load_accounts(self) -> Dict[str, Any]:
        accounts, strategy = self._store.load()
        return {"accounts": public_accounts(accounts), "strategy": strategy, "count": len(accounts)}

    def set_strategy(self, strategy: str) -> Dict[str, Any]:
        return {"strategy": self._store.set_strategy(strategy)}

    def open_login(self) -> Dict[str, Any]:
        try:
            window = self._ensure_login_window()
            if not window:
                raise RuntimeError("登录窗口未创建")
            window.load_url(LOGIN_URL)
            window.show()
            return {"opened": True, "message": "登录窗口已打开；扫码后返回账号中心同步"}
        except Exception as exc:
            return {"opened": False, "message": "登录窗口启动失败：%s" % exc}

    def close_login(self) -> Dict[str, Any]:
        window = self._ensure_login_window()
        if window:
            try:
                window.hide()
            except Exception:
                self.release_login_window(window)
        return {"closed": True}

    def sync_login_cookies(self) -> Dict[str, Any]:
        window = self._ensure_login_window()
        if not window:
            return {"detected": False, "message": "请先打开登录窗口"}
        try:
            loaded = getattr(getattr(window, "events", None), "loaded", None)
            if loaded:
                loaded.wait(15)
            header = self._cookie_header(window.get_cookies() or [])
            user_agent = str(window.evaluate_js("navigator.userAgent") or "")
        except Exception as exc:
            return {"detected": False, "message": "读取登录状态失败：%s" % exc}
        if not has_login_cookie(header):
            return {"detected": False, "message": "尚未检测到登录状态，请完成扫码并确认页面已进入抖音指数"}
        account = self._store.add(header, user_agent)
        try:
            window.hide()
            if self._main_window:
                self._main_window.show()
        except Exception:
            pass
        accounts, strategy = self._store.load()
        return {
            "detected": True,
            "message": "%s 已保存；其他人可在登录窗口退出后继续扫码添加" % account.display_name,
            "accounts": public_accounts(accounts),
            "strategy": strategy,
            "count": len(accounts),
        }

    def remove_account(self, account_id: str) -> Dict[str, Any]:
        count = self._store.remove(str(account_id))
        accounts, strategy = self._store.load()
        return {"count": count, "accounts": public_accounts(accounts), "strategy": strategy}

    def clear_accounts(self) -> Dict[str, Any]:
        self._store.clear()
        return {"count": 0, "accounts": []}

    def _wait(self, seconds: float, label: str) -> None:
        duration = max(0.0, float(seconds))
        deadline = time.monotonic() + duration
        last = None
        while True:
            while self._pause_event.is_set():
                if self._cancel_event.wait(0.1):
                    raise InterruptedError("任务已停止")
                deadline += 0.1
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            current = max(1, int(math.ceil(remaining)))
            if current != last:
                self._emit("countdown", {"seconds": current, "label": label})
                last = current
            if self._cancel_event.wait(min(0.1, remaining)):
                raise InterruptedError("任务已停止")
        self._emit("countdown", {"seconds": 0, "label": label})

    @staticmethod
    def _demo_rows(keyword: str, start_date: str, end_date: str) -> List[IndexPoint]:
        start, end = dt.date.fromisoformat(start_date), dt.date.fromisoformat(end_date)
        seed = int(hashlib.sha256(keyword.encode("utf-8")).hexdigest()[:8], 16)
        rows = []
        day = start
        offset = 0
        while day <= end:
            composite = 500000 + seed % 900000 + ((offset * 7919 + seed) % 240000)
            search = 900000 + seed % 1500000 + ((offset * 12347 + seed) % 420000)
            rows.append(IndexPoint(keyword, day.isoformat(), composite, search))
            offset += 1
            day += dt.timedelta(days=1)
        return rows

    def _query_one(self, keyword: str, account: Account, config: Dict[str, Any]) -> List[IndexPoint]:
        if self._demo:
            return self._demo_rows(keyword, config["startDate"], config["endDate"])
        client = DouyinIndexClient(
            account.cookie, user_agent=account.user_agent,
            retries=1, retry_delay=max(2.0, float(config.get("interval") or 0)),
        )
        return client.query_keywords([keyword], config["startDate"], config["endDate"])

    def query(self, config: Dict[str, Any]) -> Dict[str, Any]:
        self._cancel_event.clear()
        self._pause_event.clear()
        keywords = list(dict.fromkeys(str(x).strip() for x in config.get("keywords", []) if str(x).strip()))
        if not keywords:
            raise ValueError("请至少输入一个关键词")
        validate_date_range(str(config.get("startDate") or ""), str(config.get("endDate") or ""))
        channels = set(config.get("channels") or [])
        if not channels.intersection({"composite", "search"}):
            raise ValueError("请至少选择一种指数")
        accounts, strategy = self._store.load()
        if self._demo and not accounts:
            accounts = [Account("demo-account", "sessionid=demo", "demo")]
        if not accounts:
            raise ValueError("请先在账号中心扫码登录并同步账号")
        interval = max(0.0, float(config.get("interval") or 0))
        raw_rows: List[IndexPoint] = []
        try:
            for task_index, keyword in enumerate(keywords):
                if task_index:
                    self._wait(interval, "等待查询 · %s" % keyword)
                last_error: Optional[Exception] = None
                batch: List[IndexPoint] = []
                for position, account in enumerate(AccountStore.order(accounts, task_index, strategy)):
                    try:
                        self._emit("log", {"text": "查询 %s · %s" % (keyword, account.display_name)})
                        batch = self._query_one(keyword, account, config)
                        last_error = None
                        break
                    except (AuthenticationError, RateLimitError) as exc:
                        last_error = exc
                        if position + 1 < len(accounts):
                            self._emit("log", {"text": "当前账号不可用，正在切换下一账号"})
                    except NoDataError:
                        batch = []
                        last_error = None
                        break
                if last_error:
                    raise last_error
                if "composite" not in channels:
                    batch = [dataclasses.replace(row, composite_index=None, composite_marker="") for row in batch]
                if "search" not in channels:
                    batch = [dataclasses.replace(row, search_index=None, search_marker="") for row in batch]
                raw_rows.extend(batch)
                self._emit("batch", {"rows": [dataclasses.asdict(row) for row in batch]})
                self._emit("progress", {"done": task_index + 1, "total": len(keywords), "label": keyword})
            period = str(config.get("period") or "daily")
            rows = aggregate_points(raw_rows, period)
            output_root = pathlib.Path(config.get("outputDir") or pathlib.Path.home() / "Downloads" / "抖音指数数据").expanduser()
            stamp = dt.datetime.now().strftime("%Y年%m月%d日 %H时%M分%S秒")
            run_dir = output_root / stamp
            output = run_dir / ("抖音指数-%s-%s-%s.csv" % (period, config["startDate"].replace("-", ""), config["endDate"].replace("-", "")))
            write_csv(rows, output)
            return {
                "cancelled": False,
                "rows": [dataclasses.asdict(row) for row in rows],
                "outputs": [str(output)],
                "runDir": str(run_dir),
            }
        except AuthenticationError as exc:
            raise RuntimeError("所有账号的登录状态均已失效，请重新扫码并同步") from exc
        except InterruptedError:
            return {"cancelled": True, "rows": [], "outputs": [], "runDir": ""}

    def cancel(self) -> Dict[str, Any]:
        self._cancel_event.set()
        self._pause_event.clear()
        return {"cancelled": True}

    def toggle_pause(self) -> Dict[str, Any]:
        if self._pause_event.is_set():
            self._pause_event.clear()
        else:
            self._pause_event.set()
        return {"paused": self._pause_event.is_set()}

    def choose_output_directory(self, current: str = "") -> Dict[str, Any]:
        import webview
        initial = pathlib.Path(current or pathlib.Path.home() / "Downloads").expanduser()
        if not initial.is_dir():
            initial = pathlib.Path.home() / "Downloads"
        selected = self._main_window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=str(initial), allow_multiple=False,
        ) if self._main_window else None
        return {"selected": bool(selected), "path": str(pathlib.Path(selected[0]) if selected else initial)}

    def open_path(self, path: str) -> Dict[str, Any]:
        target = str(pathlib.Path(path).expanduser())
        if sys.platform == "darwin":
            subprocess.Popen(["open", target])
        elif os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", target])
        return {"opened": target}

    def open_url(self, url: str) -> Dict[str, Any]:
        target = str(url).strip()
        if not target.startswith(("https://", "http://")):
            raise ValueError("只允许打开 HTTP/HTTPS 链接")
        if sys.platform == "darwin":
            subprocess.Popen(["open", target])
        elif os.name == "nt":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", target])
        return {"opened": target}


def _ui_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent / "webview_ui" / "index.html"


def launch_system_webview(
    demo: bool = False,
    auto_close_ms: int = 0,
    ui_self_test_output: str = "",
) -> int:
    import webview
    api = SystemWebViewApi(demo=demo)
    main_window = webview.create_window(
        APP_NAME, _ui_path().as_uri(), js_api=api,
        width=1480, height=920, min_size=(1080, 680), background_color="#f5f6f8",
    )
    api.bind_main_window(main_window)

    def create_login_window():
        window = webview.create_window(
            "抖音创作者中心登录", LOGIN_URL,
            width=1180, height=820, min_size=(800, 580), hidden=True,
        )
        if window:
            window.events.closed += lambda: api.release_login_window(window)
        return window

    api.set_login_window_factory(create_login_window)
    main_window.events.closed += api.shutdown

    def started():
        if ui_self_test_output:
            def run_ui_self_test():
                output = pathlib.Path(ui_self_test_output).expanduser()
                try:
                    main_window.events.loaded.wait(15)
                    main_window.resize(1120, 760)
                    ready_deadline = time.monotonic() + 15
                    while time.monotonic() < ready_deadline:
                        if main_window.evaluate_js("Boolean(window.__appReady)"):
                            break
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("interface bootstrap timeout")
                    value = main_window.evaluate_js(r"""
                    (function () {
                      const visible = element => {
                        const style = getComputedStyle(element);
                        const box = element.getBoundingClientRect();
                        return style.display !== 'none' && style.visibility !== 'hidden' && box.width > 0 && box.height > 0;
                      };
                      const checks = {};
                      checks.title = document.title === '抖音指数查询工具';
                      checks.navigation = [...document.querySelectorAll('.navItem b')].map(x => x.textContent).join('|') === '查询任务|账号中心|导出记录';
                      checks.navigationSingleLine = [...document.querySelectorAll('.navItem b')].every(x => getComputedStyle(x).whiteSpace === 'nowrap');
                      checks.brandIcon = (() => { const x = document.querySelector('.brandIcon'); return x && x.complete && x.naturalWidth > 0; })();
                      const fontEntries = [...document.querySelectorAll('body *')].filter(visible).map(x => ({element: x, size: parseFloat(getComputedStyle(x).fontSize)})).filter(x => Number.isFinite(x.size));
                      const minimumFont = Math.min(...fontEntries.map(x => x.size));
                      checks.minimumFont = minimumFont >= 12;
                      checks.noHorizontalOverflow = document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth;
                      checks.queryControls = Boolean(document.getElementById('startBtn') && document.getElementById('pauseBtn') && document.getElementById('stopBtn'));
                      checks.accountControls = Boolean(document.getElementById('openLogin') && document.getElementById('syncLogin') && document.getElementById('strategy'));
                      checks.exportControls = Boolean(document.getElementById('exportList') && document.getElementById('openLatest'));
                      document.querySelector('[data-page="accounts"]').click();
                      checks.accountPage = document.getElementById('page-accounts').classList.contains('active');
                      document.querySelector('[data-page="exports"]').click();
                      checks.exportPage = document.getElementById('page-exports').classList.contains('active');
                      document.querySelector('[data-page="query"]').click();
                      checks.queryPage = document.getElementById('page-query').classList.contains('active');
                      document.getElementById('aboutButton').click();
                      const modal = document.getElementById('aboutModal');
                      checks.aboutOpen = !modal.classList.contains('hidden');
                      checks.aboutVersion = modal.innerText.includes('版本：v1.1.0');
                      checks.aboutContact = modal.innerText.includes('QQ群：610645081');
                      checks.aboutGithub = modal.innerText.includes('GitHub 项目');
                      checks.aboutIcon = (() => {
                        const icon = document.querySelector('#aboutButton .aboutIcon');
                        if (!icon) return false;
                        const box = icon.getBoundingClientRect();
                        return box.width >= 20 && box.height >= 20 && icon.textContent.trim() === 'i';
                      })();
                      document.getElementById('closeAbout').click();
                      checks.aboutClose = modal.classList.contains('hidden');
                      checks.version = document.getElementById('version').textContent === 'v1.1.0';
                      checks.outputDirectory = Boolean(document.getElementById('outputDir').value);
                      checks.defaultKeyword = document.getElementById('keywords').value === '华为';
                      document.getElementById('keywords').value = '测试';
                      document.getElementById('resetBtn').click();
                      checks.resetKeyword = document.getElementById('keywords').value === '华为';
                      const smallFonts = fontEntries.filter(x => x.size < 12).map(x => `${x.element.tagName}.${x.element.className}:${x.size}`);
                      return JSON.stringify({allPass: Object.values(checks).every(Boolean), minimumFont, smallFonts, checks});
                    })()
                    """)
                    payload = json.loads(value) if isinstance(value, str) else value
                    if not isinstance(payload, dict):
                        payload = {"allPass": False, "error": "invalid UI self-test result"}
                    text = json.dumps(payload, ensure_ascii=False)
                except Exception as exc:
                    text = json.dumps({"allPass": False, "error": repr(exc)}, ensure_ascii=False)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(text, encoding="utf-8")
                api.shutdown()
                try:
                    main_window.destroy()
                except Exception:
                    pass
            threading.Thread(target=run_ui_self_test, daemon=True).start()
        if auto_close_ms:
            def close_later():
                time.sleep(max(0.2, auto_close_ms / 1000))
                api.shutdown()
                try:
                    main_window.destroy()
                except Exception:
                    pass
            threading.Thread(target=close_later, daemon=True).start()

    storage = AccountStore().path.parent / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    gui = "edgechromium" if os.name == "nt" else "cocoa" if sys.platform == "darwin" else None
    try:
        webview.start(started, gui=gui, debug=False, private_mode=False, storage_path=str(storage))
    finally:
        api.shutdown()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--auto-close-ms", type=int, default=0)
    parser.add_argument("--ui-self-test-output", default="")
    args = parser.parse_args(argv)
    return launch_system_webview(args.demo, args.auto_close_ms, args.ui_self_test_output)


if __name__ == "__main__":
    raise SystemExit(main())
