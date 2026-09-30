"""回复文本项统计，对应 Java 端 ``com.DanceCube.info.ReplyItem``。"""

from __future__ import annotations

from ..token import Token
from ..utils import logger
from ..utils.http import http_get

_URL = "https://dancedemo.shenghuayule.com/Dance/api/ReplyTextItem/GetAllList"


class ReplyItem:
    def __init__(self) -> None:
        self.victory_rates = 0.0
        self.team_victory_rates = 0.0
        self.played_age = ""
        self.dan_level = 0
        self.played_times = 0
        self.passed_songs = 0
        self.added_coins = 0

    @staticmethod
    def get(token: Token) -> "ReplyItem":
        item = ReplyItem()
        resp = http_get(
            f"{_URL}?machineId=0",
            headers={"Authorization": token.bearer_token},
            context="回复文本项统计",
        )
        if resp is None:
            logger.error(f"[回复文本项统计] 请求失败：userId={token.user_id}")
            return item
        try:
            arr = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[回复文本项统计] 响应解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            return item
        logger.debug(f"[回复文本项统计] 共 {len(arr)} 项原始数据")
        for e in arr:
            type_ = e.get("ItemType")
            content = str(e.get("Content", ""))
            try:
                if type_ == 13:
                    item.victory_rates = 0.0 if "无" in content else float(content.replace("%", ""))
                elif type_ == 9:
                    item.team_victory_rates = 0.0 if "无" in content else float(content.replace("%", ""))
                elif type_ == 3:
                    item.played_age = content
                elif type_ == 7:
                    item.dan_level = 0 if "无" in content else int(content)
                elif type_ == 5:
                    item.played_times = int(content)
                elif type_ == 6:
                    item.passed_songs = int(content)
                elif type_ == 10:
                    item.added_coins = int(content)
            except (ValueError, TypeError) as exc:
                logger.debug(
                    f"[回复文本项统计] 跳过无法解析的项 type={type_} "
                    f"content={content!r}：{exc}"
                )
                continue
        logger.debug(f"[回复文本项统计] 解析结果：{item}")
        return item

    def __repr__(self) -> str:
        return (
            f"ReplyItem(victoryRates={self.victory_rates}, "
            f"teamVictoryRates={self.team_victory_rates}, playedAge='{self.played_age}', "
            f"danLevel={self.dan_level}, playedTimes={self.played_times}, "
            f"passedSongs={self.passed_songs}, addedCoins={self.added_coins})"
        )
