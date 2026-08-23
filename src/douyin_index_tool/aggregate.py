from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .models import IndexPoint


def _period_key(date_text: str, period: str) -> str:
    date = dt.date.fromisoformat(date_text)
    if period == "weekly":
        monday = date - dt.timedelta(days=date.weekday())
        return monday.isoformat()
    if period == "monthly":
        return date.strftime("%Y-%m")
    if period == "quarterly":
        return "%d-Q%d" % (date.year, (date.month - 1) // 3 + 1)
    if period == "yearly":
        return str(date.year)
    return date.isoformat()


def _mean(values) -> Optional[float | int]:
    present = [float(x) for x in values if x is not None]
    if not present:
        return None
    value = sum(present) / len(present)
    return int(value) if value.is_integer() else round(value, 2)


def aggregate_points(points: Iterable[IndexPoint], period: str = "daily") -> List[IndexPoint]:
    if period == "daily":
        return sorted(points, key=lambda row: (row.keyword, row.date))
    groups: Dict[tuple, List[IndexPoint]] = defaultdict(list)
    for point in points:
        groups[(point.keyword, _period_key(point.date, period))].append(point)
    result = []
    for (keyword, date), rows in sorted(groups.items()):
        result.append(IndexPoint(
            keyword,
            date,
            _mean(row.composite_index for row in rows),
            _mean(row.search_index for row in rows),
            "、".join(dict.fromkeys(row.composite_marker for row in rows if row.composite_marker)),
            "、".join(dict.fromkeys(row.search_marker for row in rows if row.search_marker)),
        ))
    return result
