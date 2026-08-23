from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import random
import sys
import threading
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from .models import Account

LOGIN_COOKIE_NAMES = ("sessionid_ss", "sessionid", "sid_guard", "uid_tt", "uid_tt_ss")


def account_path() -> pathlib.Path:
    if sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = pathlib.Path(os.environ.get("APPDATA") or pathlib.Path.home() / "AppData" / "Roaming")
    else:
        base = pathlib.Path(os.environ.get("XDG_CONFIG_HOME") or pathlib.Path.home() / ".config")
    return base / "CrossPlatformTools" / "抖音指数查询工具" / "accounts.json"


def cookie_pairs(header: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in (header or "").split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name:
            result[name] = value
    return result


def has_login_cookie(header: str) -> bool:
    values = cookie_pairs(header)
    return any(values.get(name) for name in LOGIN_COOKIE_NAMES)


def _identity(header: str) -> str:
    values = cookie_pairs(header)
    raw = next((values.get(name) for name in LOGIN_COOKIE_NAMES if values.get(name)), header)
    return hashlib.sha256(str(raw).encode("utf-8")).hexdigest()[:12]


class AccountStore:
    def __init__(self, path: pathlib.Path | None = None):
        self.path = pathlib.Path(path or account_path())
        self._lock = threading.Lock()

    def _read(self) -> Mapping[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            value = {}
        return value if isinstance(value, Mapping) else {}

    def load(self) -> tuple[List[Account], str]:
        value = self._read()
        rows = value.get("accounts") if isinstance(value.get("accounts"), list) else []
        accounts: List[Account] = []
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            cookie = str(row.get("cookie") or "").strip()
            account_id = str(row.get("id") or _identity(cookie))
            if has_login_cookie(cookie) and account_id not in seen:
                accounts.append(Account(account_id, cookie, str(row.get("userAgent") or ""), str(row.get("createdAt") or "")))
                seen.add(account_id)
        strategy = str(value.get("strategy") or "round_robin")
        if strategy not in ("round_robin", "random"):
            strategy = "round_robin"
        return accounts, strategy

    def _write(self, accounts: Sequence[Account], strategy: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({
            "strategy": strategy if strategy in ("round_robin", "random") else "round_robin",
            "accounts": [{
                "id": row.account_id,
                "cookie": row.cookie,
                "userAgent": row.user_agent,
                "createdAt": row.created_at,
            } for row in accounts],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(self.path)

    def add(self, cookie: str, user_agent: str = "") -> Account:
        if not has_login_cookie(cookie):
            raise ValueError("未检测到抖音登录 Cookie")
        with self._lock:
            accounts, strategy = self.load()
            account_id = _identity(cookie)
            account = Account(account_id, cookie.strip(), user_agent.strip(), dt.datetime.now().isoformat(timespec="seconds"))
            accounts = [row for row in accounts if row.account_id != account_id]
            accounts.append(account)
            self._write(accounts, strategy)
            return account

    def remove(self, account_id: str) -> int:
        with self._lock:
            accounts, strategy = self.load()
            accounts = [row for row in accounts if row.account_id != account_id]
            self._write(accounts, strategy)
            return len(accounts)

    def clear(self) -> None:
        with self._lock:
            _, strategy = self.load()
            self._write([], strategy)

    def set_strategy(self, strategy: str) -> str:
        strategy = strategy if strategy in ("round_robin", "random") else "round_robin"
        with self._lock:
            accounts, _ = self.load()
            self._write(accounts, strategy)
        return strategy

    @staticmethod
    def order(accounts: Sequence[Account], task_index: int, strategy: str) -> List[Account]:
        if not accounts:
            return []
        start = random.SystemRandom().randrange(len(accounts)) if strategy == "random" else task_index % len(accounts)
        return [accounts[(start + offset) % len(accounts)] for offset in range(len(accounts))]


def public_accounts(accounts: Iterable[Account]) -> List[Dict[str, str]]:
    return [{"id": row.account_id, "name": row.display_name, "createdAt": row.created_at} for row in accounts]
