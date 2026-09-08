"""Pillow 版图片绘制器，对应 Java 端 ``com.Tools.image.ImageDrawer``。"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from ..utils.http import get_bytes_from_url
from .effect import ImageEffect, TextEffect

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# 舞立方静态资源 CDN 前缀（用于相对路径的头像框 / 称号）
CDN_BASE = "https://dancewebdemo.shenghuayule.com"


def make_round_corner(img: Image.Image, arc_w: int, arc_h: int) -> Image.Image:
    """为图片添加圆角。"""
    if arc_w < 0 or arc_h < 0:
        return img
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    radius = max(1, round(min(arc_w, arc_h) / 2))
    md.rounded_rectangle(
        [0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255
    )
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def read_image(source: str | None) -> Image.Image | None:
    """从 URL / 文件 / 相对路径读取图片，失败返回 ``None``。"""
    if not source:
        return None
    s = str(source).strip()
    data: bytes | None = None
    if s.startswith(("http://", "https://")):
        data = get_bytes_from_url(s)
    elif s.startswith("/"):
        data = get_bytes_from_url(CDN_BASE + s)
    else:
        p = Path(s)
        if p.exists():
            try:
                return Image.open(p).convert("RGBA")
            except Exception:
                return None
        data = get_bytes_from_url(CDN_BASE + "/" + s)
    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


class ImageDrawer:
    def __init__(self, image: Image.Image) -> None:
        self.image = image
        self.draw = ImageDraw.Draw(self.image)
        self.color = BLACK
        self.font = None

    def set_anti_aliasing(self) -> None:
        # Pillow 文本默认抗锯齿，无需额外处理
        return None

    def color(self, color) -> "ImageDrawer":
        self.color = color
        return self

    def font(self, font, color=None) -> "ImageDrawer":
        self.font = font
        if color is not None:
            self.color = color
        return self

    def _line_height(self) -> int:
        if self.font is None:
            return 10
        ascent, descent = self.font.getmetrics()
        return ascent + descent

    def _add_dots(self, text: str, max_width: int) -> str:
        if self.font is None:
            return text
        if self.draw.textlength(text, font=self.font) <= max_width:
            return text
        ellipsis = "..."
        while text and self.draw.textlength(text + ellipsis, font=self.font) > max_width:
            text = text[:-1]
        return text + ellipsis

    def draw_text(self, text: str, x: int, y: int, effect: TextEffect | None = None) -> "ImageDrawer":
        if effect is None:
            self.draw.text((x, y), text, font=self.font, fill=self.color)
            return self

        if effect.space_height is not None:
            line_height = self._line_height()
            for line in text.split("\n"):
                if effect.max_width is not None:
                    line = self._add_dots(line, effect.max_width)
                self.draw.text((x, y), line, font=self.font, fill=self.color)
                y += line_height + effect.space_height
        else:
            if effect.max_width is not None:
                text = self._add_dots(text, effect.max_width)
            self.draw.text((x, y), text, font=self.font, fill=self.color)
        return self

    def draw_image(
        self,
        img: Image.Image | None,
        x: int,
        y: int,
        width: int | None = None,
        height: int | None = None,
        effect: ImageEffect | None = None,
    ) -> "ImageDrawer":
        if img is None:
            return self
        if effect is not None:
            img = make_round_corner(img, effect.arc_w, effect.arc_h)
        if width is not None and height is not None:
            img = img.resize((width, height), Image.LANCZOS)
        img = img.convert("RGBA")
        self.image.paste(img, (x, y), img)
        return self

    def dispose(self) -> "ImageDrawer":
        return self

    def get_image_stream(self, fmt: str = "png") -> io.BytesIO:
        bio = io.BytesIO()
        out = self.image.convert("RGB") if fmt.lower() in ("jpg", "jpeg") else self.image
        out.save(bio, format="JPEG" if fmt.lower() in ("jpg", "jpeg") else "PNG")
        bio.seek(0)
        return bio

    def get_image_bytes(self, fmt: str = "png") -> bytes:
        return self.get_image_stream(fmt).getvalue()
