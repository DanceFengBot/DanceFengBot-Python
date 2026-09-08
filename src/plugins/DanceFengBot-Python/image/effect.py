"""图片与文本绘制效果，对应 Java 端 ``ImageEffect`` 与 ``TextEffect``。"""

from __future__ import annotations


class ImageEffect:
    def __init__(self) -> None:
        self.arc_w = -1
        self.arc_h = -1
        self.blur = -1

    def set_arc(self, arc: int) -> "ImageEffect":
        self.arc_w = arc
        self.arc_h = arc
        return self

    def set_arc_w(self, arc_w: int) -> "ImageEffect":
        self.arc_w = arc_w
        return self

    def set_arc_h(self, arc_h: int) -> "ImageEffect":
        self.arc_h = arc_h
        return self

    def set_blur(self, blur: int) -> "ImageEffect":
        self.blur = blur
        return self


class TextEffect:
    def __init__(self) -> None:
        self.max_width: int | None = None
        self.space_height: int | None = None

    def set_max_width(self, max_width: int) -> "TextEffect":
        self.max_width = max_width
        return self

    def set_space_height(self, space_height: int) -> "TextEffect":
        self.space_height = space_height
        return self
