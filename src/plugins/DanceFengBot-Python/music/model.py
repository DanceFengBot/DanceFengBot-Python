"""歌曲模型，对应 Java 端 ``com.DanceCube.music.Music``。"""

from __future__ import annotations


class Music:
    def __init__(self, name: str, id: int, cover_url: str) -> None:
        self.name = name
        self.id = id
        self.cover_url = cover_url
