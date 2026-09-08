"""全民赛季（天梯）信息，对应 Java 端 ``com.DanceCube.api.Ladder``。"""

from __future__ import annotations

from ..token import Token
from ..utils.http import http_get

_URL = "https://dancedemo.shenghuayule.com/Dance/api/Match/GetQuanMinSeasons"


class Ladder:
    def __init__(self) -> None:
        self.match_define_id = 0
        self.match_name = ""
        self.start_time = ""
        self.stop_time = ""
        self.match_time_text = ""
        self.level_point = 0
        self.level_grade = 0
        self.is_last = False
        self.is_current = False
        self.is_topest = False

    @staticmethod
    def get(token: Token) -> list["Ladder"]:
        resp = http_get(_URL, headers={"Authorization": token.bearer_token})
        if resp is None:
            return []
        try:
            arr = resp.json()
        except Exception:
            return []
        result: list[Ladder] = []
        for e in arr:
            ladder = Ladder()
            ladder.match_define_id = e.get("MatchDefineId", 0)
            ladder.match_name = e.get("MatchName", "")
            ladder.start_time = e.get("StartTime", "")
            ladder.stop_time = e.get("StopTime", "")
            ladder.match_time_text = e.get("MatchTimeText", "")
            ladder.level_point = e.get("LevelPoint", 0)
            ladder.level_grade = e.get("LevelGrade", 0)
            ladder.is_last = e.get("IsLast", False)
            ladder.is_current = e.get("IsCurrent", False)
            ladder.is_topest = e.get("IsTopest", False)
            result.append(ladder)
        return result
