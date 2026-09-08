"""已游玩谱面成绩父类，对应 Java 端 ``com.DanceCube.ratio.RecordedMusicInfo``。"""

from __future__ import annotations

from .acc_grade import AccGrade


class RecordedMusicInfo:
    def __init__(
        self,
        id: int,
        name: str,
        difficulty: int,
        level: int,
        level_type: int,
        accuracy: float,
        score: int,
        combo: int,
        miss: int,
    ) -> None:
        self.id = id
        self.name = name
        self.difficulty = difficulty
        self.level = level
        self.level_type = level_type
        self.accuracy = accuracy
        self.score = score
        self.combo = combo
        self.miss = miss
        self.ratio = accuracy * (level + 2)

    @property
    def ratio_int(self) -> int:
        return round(self.ratio)

    @property
    def acc_grade(self) -> AccGrade:
        return AccGrade.get(self.accuracy)

    def is_full_combo(self) -> bool:
        return self.miss == 0

    def is_all_perfect(self) -> bool:
        return self.accuracy == 100.0

    def is_official(self) -> bool:
        raise NotImplementedError
