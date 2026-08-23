from __future__ import annotations

import csv
import pathlib
from typing import Iterable

from .models import IndexPoint

HEADERS = ["关键词", "日期", "抖音综合指数", "抖音搜索指数", "综合指数标记", "搜索指数标记"]


def _format(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def write_csv(points: Iterable[IndexPoint], output: pathlib.Path) -> pathlib.Path:
    output = pathlib.Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADERS)
        for row in points:
            writer.writerow([
                row.keyword, row.date, _format(row.composite_index), _format(row.search_index),
                row.composite_marker, row.search_marker,
            ])
    return output
