"""最近游玩记录，对应 Java 端 ``com.DanceCube.ratio.RecentMusicInfo``。"""

from __future__ import annotations

from typing import Any

from ..music.util import is_official
from .recorded import RecordedMusicInfo


class RecentMusicInfo(RecordedMusicInfo):
    def __init__(
        self,
        obj: dict[str, Any] | None = None,
        *,
        id: int = 0,
        name: str = "",
        difficulty: int = 0,
        level: int = 0,
        level_type: int = 0,
        accuracy: float = 0.0,
        score: int = 0,
        combo: int = 0,
        perfect: int = 0,
        great: int = 0,
        good: int = 0,
        miss: int = 0,
        record_time: str = "",
    ) -> None:
        if obj is not None:
            super().__init__(
                obj.get("MusicID", 0),
                obj.get("MusicName", ""),
                obj.get("MusicLevOld", 0),
                obj.get("MusicLevel", 0),
                obj.get("MusicLev", 0),
                obj.get("PlayerPercent", 0.0) / 100,
                obj.get("PlayerScore", 0),
                obj.get("ComboCount", 0),
                obj.get("PlayerMiss", 0),
            )
            self.perfect = obj.get("PlayerPerfect", 0)
            self.great = obj.get("PlayerGreat", 0)
            self.good = obj.get("PlayerGood", 0)
            self.record_time = obj.get("RecordTime", "")
        else:
            super().__init__(
                id, name, difficulty, level, level_type, accuracy, score, combo, miss
            )
            self.perfect = perfect
            self.great = great
            self.good = good
            self.record_time = record_time

    def is_official(self) -> bool:
        return is_official(self.id)

    def __repr__(self) -> str:
        return (
            f"Name: {self.name}\nLevel: {self.level}\nPercent: {self.accuracy:.2f}\n"
            f"#Ratio: {self.ratio:.2f}\n"
        )
