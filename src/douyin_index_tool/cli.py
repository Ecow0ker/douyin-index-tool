from __future__ import annotations

import argparse
import os
import pathlib
from typing import Optional, Sequence

from .aggregate import aggregate_points
from .api import DouyinIndexClient
from .export import write_csv


def _cookie(args) -> str:
    if args.cookie_file:
        return pathlib.Path(args.cookie_file).expanduser().read_text(encoding="utf-8").strip()
    return os.environ.get("DOUYIN_INDEX_COOKIE", "").strip()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="抖音指数命令行工具")
    sub = parser.add_subparsers(dest="command", required=True)
    query = sub.add_parser("query", help="查询关键词指数")
    query.add_argument("--keyword", action="append", required=True)
    query.add_argument("--start", required=True)
    query.add_argument("--end", required=True)
    query.add_argument("--cookie-file")
    query.add_argument("--period", choices=["daily", "weekly", "monthly", "quarterly", "yearly"], default="daily")
    query.add_argument("--output", required=True)
    hot = sub.add_parser("hot-words", help="查看热门关键词")
    hot.add_argument("--cookie-file")
    args = parser.parse_args(argv)
    cookie = _cookie(args)
    if not cookie:
        parser.error("请使用 --cookie-file 或 DOUYIN_INDEX_COOKIE 提供登录 Cookie")
    client = DouyinIndexClient(cookie)
    if args.command == "hot-words":
        for row in client.hot_words():
            print(row.get("keyword") or row)
        return 0
    rows = []
    for keyword in args.keyword:
        rows.extend(client.query_keywords([keyword], args.start, args.end))
    output = write_csv(aggregate_points(rows, args.period), pathlib.Path(args.output))
    print(output)
    return 0
