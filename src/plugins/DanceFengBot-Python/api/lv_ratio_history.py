"""历史战力，对应 Java 端 ``com.DanceCube.api.LvRatioHistory``。"""

from __future__ import annotations

import json
from datetime import datetime

from ..token import Token
from ..utils.http import http_get

_URL = "https://dancedemo.shenghuayule.com/Dance/api/User/GetLvRatioHistory"


class LvRatioHistory:
    def __init__(self, calendar: datetime, ratio: int) -> None:
        self.calendar = calendar
        self.ratio = ratio

    @staticmethod
    def get(token: Token) -> list["LvRatioHistory"]:
        resp = http_get(
            f"{_URL}?userId={token.user_id}",
            headers={"Authorization": token.bearer_token},
        )
        if resp is None:
            return []
        try:
            arr = json.loads(resp.text)
        except Exception:
            return []
        if not isinstance(arr, list):
            return []
        result: list[LvRatioHistory] = []
        for o in arr:
            try:
                log_time = o.get("LogTime", "")
                dt = _parse_time(log_time)
                ratio = int(o.get("LvRatio", 0))
                result.append(LvRatioHistory(dt, ratio))
            except Exception:
                return []
        return result

    def __repr__(self) -> str:
        return f"LvRatioHistory(calendar={self.calendar}, ratio={self.ratio})"


def _parse_time(text: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %I:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return datetime.now()
