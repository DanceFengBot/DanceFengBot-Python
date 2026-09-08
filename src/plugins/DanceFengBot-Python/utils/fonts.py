"""字体加载工具。

原 Java 项目使用 AWT 字体（得意黑 / Microsoft YaHei UI / 庞门正道标题体），
字体文件存放于 ``DcConfig/Fonts``，这里映射到 Pillow 的 ``ImageFont``。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from ..config import CONFIG_PATH

FONTS_DIR: Path = CONFIG_PATH / "Fonts"

# 字体名 -> 字体文件（与 Java 端 ``new Font(name, ...)`` 对应）
_FONT_FILES: dict[str, str] = {
    "得意黑": "SmileySans-Oblique.ttf",
    "smileysans": "SmileySans-Oblique.ttf",
    "microsoft yahei ui": "MSYHBD.TTC",
    "微软雅黑": "MSYHBD.TTC",
    "庞门正道标题体": "PANGMENZHENGDAOBIAOTITI-1.TTF",
    "pangmen": "PANGMENZHENGDAOBIAOTITI-1.TTF",
}

# 兜底顺序
_FALLBACKS: tuple[str, ...] = (
    "SmileySans-Oblique.ttf",
    "SourceHanSans.otf",
    "SourceHanSans-Bold.otf",
    "MSYHBD.TTC",
    "PANGMENZHENGDAOBIAOTITI-1.TTF",
)


def _find(name: str) -> Path | None:
    key = name.strip().lower()
    fname = _FONT_FILES.get(name) or _FONT_FILES.get(key)
    if fname:
        p = FONTS_DIR / fname
        if p.exists():
            return p
    for cand in _FALLBACKS:
        p = FONTS_DIR / cand
        if p.exists():
            return p
    return None


@lru_cache(maxsize=128)
def load_font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """按字体名和字号加载 ``ImageFont``，带缓存。"""
    path = _find(name)
    if path is None:
        return ImageFont.load_default()
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        return ImageFont.load_default()
