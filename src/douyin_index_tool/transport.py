from __future__ import annotations

import json
import ssl
from typing import Any, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class NetworkError(RuntimeError):
    pass


class HttpError(NetworkError):
    def __init__(self, status: int, message: str):
        super().__init__("HTTP %s: %s" % (status, message))
        self.status = status


class UrlLibTransport:
    def __init__(self, timeout: float = 25.0, ca_file: Optional[str] = None):
        self.timeout = timeout
        self.context = ssl.create_default_context(cafile=ca_file)
        self.last_response_headers = {}
        self.last_status = 0

    def request_json(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        body: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params, doseq=True)
        data = None
        request_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json; charset=UTF-8")
        request = Request(url, data=data, headers=request_headers, method=method.upper())
        try:
            with urlopen(request, timeout=self.timeout, context=self.context) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                self.last_response_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                self.last_status = int(getattr(response, "status", 200))
        except HTTPError as exc:
            message = exc.read().decode("utf-8", "replace")[:800]
            raise HttpError(exc.code, message) from exc
        except (URLError, TimeoutError, OSError, ssl.SSLError) as exc:
            raise NetworkError(str(exc)) from exc
        text = raw.decode(charset, "replace")
        if text.lstrip().lower().startswith("<!doctype"):
            raise NetworkError("接口返回了登录页面")
        try:
            return json.loads(text)
        except ValueError as exc:
            raise NetworkError("服务器返回的内容不是 JSON") from exc
