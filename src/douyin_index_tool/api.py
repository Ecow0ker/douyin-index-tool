from __future__ import annotations

import datetime as dt
import time
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from .models import IndexPoint
from .transport import HttpError, NetworkError, UrlLibTransport
from .crypto import decrypt_response

BASE_URL = "https://creator.douyin.com"
REFERER = BASE_URL + "/creator-micro/creator-count/arithmetic-index"


class ApiError(RuntimeError):
    pass


class AuthenticationError(ApiError):
    pass


class RateLimitError(ApiError):
    pass


class NoDataError(ApiError):
    pass


class ResponseFormatError(ApiError):
    pass


def parse_date(value: str) -> dt.date:
    try:
        return dt.datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD：%s" % value) from exc


def validate_date_range(start_date: str, end_date: str, max_days: int = 184) -> None:
    start, end = parse_date(start_date), parse_date(end_date)
    if start > end:
        raise ValueError("开始日期晚于结束日期")
    if end >= dt.date.today():
        raise ValueError("结束日期应早于今天")
    if (end - start).days + 1 > max_days:
        raise ValueError("单次查询最多支持过去半年（%d 天）" % max_days)


def _compact_date(value: str) -> str:
    return parse_date(value).strftime("%Y%m%d")


def _iso_date(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit() and len(text) == 8:
        return dt.datetime.strptime(text, "%Y%m%d").date().isoformat()
    if text.isdigit() and len(text) in (10, 13):
        stamp = int(text) / (1000 if len(text) == 13 else 1)
        return dt.datetime.fromtimestamp(stamp).date().isoformat()
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except (ValueError, TypeError):
        return text[:10]


def _number(value: Any):
    if value in (None, "", "--", "-"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _marker_map(values: Any) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not isinstance(values, list):
        return result
    for item in values:
        if not isinstance(item, Mapping):
            continue
        date = _iso_date(item.get("datetime") or item.get("date"))
        marker = str(item.get("type") or item.get("point_type") or item.get("name") or "")
        if date:
            result[date] = marker
    return result


def parse_trend_payload(payload: Any, requested: Sequence[str]) -> List[IndexPoint]:
    """Parse the current get_multi_keyword_hot_trend response shape."""
    if isinstance(payload, Mapping) and isinstance(payload.get("data"), Mapping):
        payload = payload["data"]
    if not isinstance(payload, Mapping):
        raise ResponseFormatError("趋势接口返回格式错误")
    groups = payload.get("hot_list")
    if not isinstance(groups, list):
        raise ResponseFormatError("趋势接口缺少 hot_list")
    rows: List[IndexPoint] = []
    requested_set = {str(x) for x in requested}
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        keyword = str(group.get("keyword") or "")
        if not keyword and len(requested) == 1:
            keyword = str(requested[0])
        if requested_set and keyword not in requested_set:
            continue
        composite = group.get("hot_list") if isinstance(group.get("hot_list"), list) else []
        search = group.get("search_hot_list") if isinstance(group.get("search_hot_list"), list) else []
        composite_map = {
            _iso_date(item.get("datetime") or item.get("date")): _number(item.get("index"))
            for item in composite if isinstance(item, Mapping)
        }
        search_map = {
            _iso_date(item.get("datetime") or item.get("date")): _number(item.get("index"))
            for item in search if isinstance(item, Mapping)
        }
        markers = group.get("top_point_list")
        composite_markers = _marker_map(markers)
        search_markers = _marker_map(group.get("search_top_point_list") or markers)
        for date in sorted(set(composite_map) | set(search_map)):
            if not date:
                continue
            rows.append(IndexPoint(
                keyword=keyword,
                date=date,
                composite_index=composite_map.get(date),
                search_index=search_map.get(date),
                composite_marker=composite_markers.get(date, ""),
                search_marker=search_markers.get(date, ""),
            ))
    if not rows:
        raise NoDataError("该条件没有可用的抖音指数数据")
    return rows


class DouyinIndexClient:
    TREND_PATH = "/api/v2/index/get_multi_keyword_hot_trend"
    VALID_DATE_PATH = "/api/v2/index/get_keyword_valid_date"
    HOT_WORDS_PATH = "/api/v2/index/get_hot_words"
    HOT_TOPICS_PATH = "/api/v2/index/get_hot_topics"

    def __init__(
        self,
        cookie: str,
        *,
        user_agent: str = "",
        timeout: float = 25.0,
        retries: int = 2,
        retry_delay: float = 2.0,
        transport: Optional[Any] = None,
        base_url: str = BASE_URL,
    ):
        if not (cookie or "").strip():
            raise ValueError("Cookie 为空")
        self.cookie = cookie.strip()
        self.base_url = base_url.rstrip("/")
        self.transport = transport or UrlLibTransport(timeout=timeout)
        self.retries = max(0, int(retries))
        self.retry_delay = max(0.0, float(retry_delay))
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Cookie": self.cookie,
            "Origin": self.base_url,
            "Pragma": "no-cache",
            "Referer": REFERER,
            "User-Agent": user_agent or "Mozilla/5.0 AppleWebKit/537.36 Chrome/140 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "appsource": "PC",
        }

    @staticmethod
    def _unwrap(response: Any) -> Any:
        if not isinstance(response, Mapping):
            raise ResponseFormatError("接口 JSON 顶层格式错误")
        status = response.get("status")
        message = str(response.get("msg") or response.get("message") or "")
        base_resp = response.get("BaseResp")
        if isinstance(base_resp, Mapping):
            status = base_resp.get("StatusCode", status)
            message = str(base_resp.get("StatusMessage") or message)
        success = status in (None, 0, "0") or message.lower() == "success"
        if success:
            return response.get("data", response)
        lowered = message.lower()
        if any(word in lowered for word in ("login", "登录", "session", "cookie")) or status in (10001, 10002, 401, 403):
            raise AuthenticationError("账号登录状态已失效")
        if any(word in lowered for word in ("频繁", "限制", "risk", "verify", "captcha", "rate")) or status in (429, 10006):
            raise RateLimitError(message or "请求频率受限")
        raise ApiError("接口状态 %r：%s" % (status, message or "未知错误"))

    def _request(self, method: str, path: str, *, params=None, body=None) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                response = self.transport.request_json(
                    method, self.base_url + path, params=params, body=body, headers=self.headers,
                )
                response_headers = getattr(self.transport, "last_response_headers", {}) or {}
                encrypted_mode = response_headers.get("x-encrypted") or response_headers.get("X-Encrypted")
                if encrypted_mode and isinstance(response, Mapping) and isinstance(response.get("data"), str):
                    response = decrypt_response(response["data"], str(encrypted_mode))
                return self._unwrap(response)
            except HttpError as exc:
                if exc.status in (401, 403):
                    raise AuthenticationError("账号登录状态已失效") from exc
                last_error = exc
            except (NetworkError, RateLimitError) as exc:
                last_error = exc
            if attempt < self.retries:
                time.sleep(self.retry_delay * (2**attempt))
        if last_error:
            raise last_error
        raise ApiError("请求失败")

    def latest_valid_date(self, app_name: str = "aweme") -> str:
        payload = self._request("POST", self.VALID_DATE_PATH, body={"app_name": app_name})
        if isinstance(payload, Mapping):
            for key in ("end_date", "latest_date", "date", "datetime", "day"):
                if payload.get(key):
                    return _iso_date(payload[key])
        raise ResponseFormatError("有效日期接口未返回日期")

    def query_keywords(
        self,
        keywords: Sequence[str],
        start_date: str,
        end_date: str,
        *,
        app_name: str = "aweme",
        region: Optional[Iterable[str]] = None,
    ) -> List[IndexPoint]:
        cleaned = list(dict.fromkeys(str(x).strip() for x in keywords if str(x).strip()))
        if not cleaned:
            raise ValueError("关键词列表为空")
        if len(cleaned) > 5:
            raise ValueError("单次接口请求最多 5 个对比词")
        validate_date_range(start_date, end_date)
        body: Dict[str, Any] = {
            "keyword_list": cleaned,
            "start_date": _compact_date(start_date),
            "end_date": _compact_date(end_date),
            "app_name": app_name,
        }
        regions = [str(x).strip() for x in (region or []) if str(x).strip()]
        if regions:
            body["region"] = regions
        payload = self._request("POST", self.TREND_PATH, body=body)
        return parse_trend_payload(payload, cleaned)

    def hot_words(self, app_name: str = "aweme") -> List[Mapping[str, Any]]:
        payload = self._request("GET", self.HOT_WORDS_PATH, params={"app_name": app_name})
        if isinstance(payload, Mapping) and isinstance(payload.get("hot_words"), list):
            return payload["hot_words"]
        return []

    def hot_topics(self, app_name: str = "aweme") -> List[Mapping[str, Any]]:
        payload = self._request("GET", self.HOT_TOPICS_PATH, params={"app_name": app_name})
        if isinstance(payload, Mapping) and isinstance(payload.get("hot_topics"), list):
            return payload["hot_topics"]
        return []
