from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

Number = Union[int, float]


@dataclass(frozen=True)
class IndexPoint:
    keyword: str
    date: str
    composite_index: Optional[Number]
    search_index: Optional[Number]
    composite_marker: str = ""
    search_marker: str = ""


@dataclass(frozen=True)
class Account:
    account_id: str
    cookie: str
    user_agent: str = ""
    created_at: str = ""

    @property
    def display_name(self) -> str:
        return "账号 · %s" % self.account_id[-6:].upper()
