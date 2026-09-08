"""歌曲工具，对应 Java 端 ``com.DanceCube.music.MusicUtil``。"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import CONFIG_PATH
from ..utils.http import http_get
from .model import Music

OFFICIAL_IDS: set[int] = set()

_OFFICIAL_IDS_FILE = CONFIG_PATH / "OfficialMusicIds.json"


def update_ids_from_file(path: Path | str | None = None) -> bool:
    global OFFICIAL_IDS
    p = Path(path) if path else _OFFICIAL_IDS_FILE
    try:
        ids = json.loads(p.read_text(encoding="utf-8"))
        OFFICIAL_IDS = {int(i) for i in ids}
        return True
    except Exception:
        return False


def update_ids_from_api(path: Path | str | None = None) -> bool:
    global OFFICIAL_IDS
    resp = http_get(
        "https://dancedemo.shenghuayule.com/Dance/Music/GetMusicList",
        headers={
            "getAdvanced": "true",
            "getNotDisplay": "false",
            "category": "0",
        },
    )
    if resp is None:
        return False
    try:
        arr = resp.json()
    except Exception:
        return False
    for obj in arr:
        OFFICIAL_IDS.add(obj.get("MusicID", 0))
    p = Path(path) if path else _OFFICIAL_IDS_FILE
    try:
        p.write_text(
            json.dumps(sorted(OFFICIAL_IDS), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return True


def is_official(id: int) -> bool:
    return id in OFFICIAL_IDS


def get_music(id: int) -> Music:
    resp = http_get(
        f"https://dancedemo.shenghuayule.com/Dance/MusicData/GetInfo?musicId={id}"
    )
    name = ""
    cover_url = ""
    if resp is not None:
        try:
            j = resp.json()
            name = j.get("Name", "")
            for f in j.get("MusicFileList", []):
                if f.get("FileTypeText") == "背景图片":
                    cover_url = f.get("Url", "")
        except Exception:
            pass
    return Music(name, id, cover_url)


# 模块导入时加载本地官谱 ID（与 Java 静态块行为一致）
update_ids_from_file()
