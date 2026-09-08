"""封面工具，对应 Java 端 ``com.DanceCube.music.CoverUtil``。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..config import CONFIG_PATH
from ..utils.http import get_bytes_from_url
from .util import get_music, is_official

official_img_path: Path = CONFIG_PATH / "Images/Cover/OfficialImage"
custom_img_path: Path = CONFIG_PATH / "Images/Cover/CustomImage"
cover_img_path: Path = CONFIG_PATH / "Images/Cover"

official_img_path.mkdir(parents=True, exist_ok=True)
custom_img_path.mkdir(parents=True, exist_ok=True)


def _get_img_path(id: int) -> Path:
    if id == 0:
        return cover_img_path / "default.jpg"
    base = official_img_path if is_official(id) else custom_img_path
    return base / f"{id}.jpg"


def is_cover_absent(id: int) -> bool:
    return not _get_img_path(id).exists()


def download_cover(id: int) -> None:
    music = get_music(id)
    data = get_bytes_from_url(music.cover_url)
    if not data:
        raise RuntimeError(f"{id} 的 id 封面 url 无效")
    import io

    img = Image.open(io.BytesIO(data))
    img.convert("RGB").save(_get_img_path(id), "JPEG")


def get_cover_or_default(id: int) -> Image.Image | None:
    if is_cover_absent(id):
        id = 0
    try:
        return Image.open(_get_img_path(id)).convert("RGBA")
    except Exception:
        return None
