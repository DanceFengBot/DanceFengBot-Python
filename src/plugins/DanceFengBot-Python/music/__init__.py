"""舞立方歌曲与封面相关。"""

from .model import Music
from .util import get_music, is_official, update_ids_from_api, update_ids_from_file
from .cover import (
    download_cover,
    ensure_cover,
    ensure_covers,
    get_cover_or_default,
    is_cover_absent,
    read_local_cover_index,
    save_local_cover_index,
)
from .cover_update import (
    CoverUpdateBusy,
    CoverUpdateResult,
    fetch_official_cover_index,
    run_scheduled_update,
    update_official_covers,
)

__all__ = [
    "Music",
    "get_music",
    "is_official",
    "update_ids_from_api",
    "update_ids_from_file",
    "download_cover",
    "ensure_cover",
    "ensure_covers",
    "get_cover_or_default",
    "is_cover_absent",
    "read_local_cover_index",
    "save_local_cover_index",
    "CoverUpdateBusy",
    "CoverUpdateResult",
    "fetch_official_cover_index",
    "run_scheduled_update",
    "update_official_covers",
]
