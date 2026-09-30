"""歌曲工具，对应 Java 端 ``com.DanceCube.music.MusicUtil``。"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import CONFIG_PATH
from ..utils import logger
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
        logger.debug(f"[歌曲] 从 {p} 载入 {len(OFFICIAL_IDS)} 个官谱 ID")
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[歌曲] 官谱 ID 文件读取失败：{p} | {exc}")
        return False


def update_ids_from_api(path: Path | str | None = None) -> bool:
    global OFFICIAL_IDS
    logger.info("[歌曲] 从接口批量更新官谱 ID 列表")
    resp = http_get(
        "https://dancedemo.shenghuayule.com/Dance/Music/GetMusicList",
        headers={
            "getAdvanced": "true",
            "getNotDisplay": "false",
            "category": "0",
        },
        context="歌曲-官谱列表",
    )
    if resp is None:
        logger.error("[歌曲] 官谱列表请求失败")
        return False
    try:
        arr = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[歌曲] 官谱列表解析失败：{exc}；内容（前 200 字符）：{resp.text[:200]}"
        )
        return False
    for obj in arr:
        OFFICIAL_IDS.add(obj.get("MusicID", 0))
    p = Path(path) if path else _OFFICIAL_IDS_FILE
    try:
        p.write_text(
            json.dumps(sorted(OFFICIAL_IDS), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[歌曲] 官谱 ID 写入失败：{p} | {exc}")
    logger.info(f"[歌曲] 官谱 ID 更新完成，共 {len(OFFICIAL_IDS)} 个 -> {p}")
    return True


def is_official(id: int) -> bool:
    return id in OFFICIAL_IDS


def get_music(id: int) -> Music:
    resp = http_get(
        f"https://dancedemo.shenghuayule.com/Dance/MusicData/GetInfo?musicId={id}",
        context=f"歌曲信息(id={id})",
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
            logger.debug(f"[歌曲] id={id} 名称={name or '-'} 封面={cover_url or '无'}")
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[歌曲] id={id} 信息解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
    else:
        logger.error(f"[歌曲] id={id} 信息请求失败")
    return Music(name, id, cover_url)


# 模块导入时加载本地官谱 ID（与 Java 静态块行为一致）
update_ids_from_file()
