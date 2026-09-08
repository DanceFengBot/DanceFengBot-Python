"""账号信息可见状态，对应 Java 端 ``com.DanceCube.info.InfoStatus``。"""

from __future__ import annotations

from enum import Enum


class InfoStatus(Enum):
    OPEN = "open"
    PRIVATE = "private"
    NONEXISTENT = "nonexistent"
