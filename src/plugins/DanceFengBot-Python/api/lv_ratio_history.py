"""历史战力，对应 Java 端 ``com.DanceCube.api.LvRatioHistory``。"""

from __future__ import annotations

import json
from datetime import datetime

from ..token import Token
from ..utils import logger
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
            context="历史战力",
        )
        if resp is None:
            logger.warning("[历史战力] 请求失败，返回空列表")
            return []
        try:
            arr = json.loads(resp.text)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[历史战力] 响应解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            return []
        if not isinstance(arr, list):
            logger.warning(f"[历史战力] 响应不是数组，类型={type(arr).__name__}")
            return []
        result: list[LvRatioHistory] = []
        for o in arr:
            try:
                log_time = o.get("LogTime", "")
                dt = _parse_time(log_time)
                ratio = int(o.get("LvRatio", 0))
                result.append(LvRatioHistory(dt, ratio))
            except Exception as exc:  # noqa: BLE001
                logger.error(f"[历史战力] 单条记录解析失败：{exc}；原始数据={o}")
                return []
        logger.debug(f"[历史战力] 共 {len(result)} 条记录")
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
