"""榜单成绩记录，对应 Java 端 ``com.DanceCube.ratio.RankMusicInfo``。"""

from __future__ import annotations

from typing import Any

from .recorded import RecordedMusicInfo


class RankMusicInfo(RecordedMusicInfo):
    def __init__(self, id: int, name: str, owner_type: int, details: dict[str, Any]) -> None:
        super().__init__(
            id,
            name,
            details.get("MusicLevOld", 0),
            details.get("MusicRank", 0),
            details.get("MusicLev", 0),
            details.get("PlayerPercent", 0.0) / 100,
            details.get("PlayerScore", 0),
            details.get("ComboCount", 0),
            details.get("PlayerMiss", 0),
        )
        self.ranking = details.get("MusicRanking", 0)
        self._is_official = owner_type == 1

    def is_official(self) -> bool:
        return self._is_official

    def __repr__(self) -> str:
        return (
            f"RankMusicInfo(difficulty={self.difficulty}, level={self.level}, "
            f"acc={self.accuracy}, ratio={self.ratio})"
        )
