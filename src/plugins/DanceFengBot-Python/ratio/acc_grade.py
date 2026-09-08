"""舞立方成绩精确度评级，对应 Java 端 ``com.DanceCube.ratio.AccGrade``。"""

from __future__ import annotations

from enum import Enum


class AccGrade(Enum):
    SSS_AP = 100
    SSS = 98
    SS = 95
    S = 90
    A = 80
    B = 70
    C = 60
    D = 0

    @classmethod
    def get(cls, acc: float) -> "AccGrade":
        for grade in cls:
            if acc >= grade.value:
                return grade
        return AccGrade.D
