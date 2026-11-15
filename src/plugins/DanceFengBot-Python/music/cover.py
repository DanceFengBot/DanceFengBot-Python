"""封面工具，对应 Java 端 ``com.DanceCube.music.CoverUtil``。

下载封面时先判定歌曲类型（官谱 / 非官谱），再访问 ``dfb-miscellaneous``
仓库维护的封面索引（JSON 集），按歌曲 id 取出封面地址后下载到封面目录：

* 官谱：``DanceCubeCover/Official/CoverData.json``（字段 ``CoverURL``）
* 非官谱：``DanceCubeCover/Custom/CoverData.json``（字段 ``PicPath``）

索引中找不到对应 id 时，退回官方接口 ``MusicData/GetInfo`` 提供的封面地址。
"""

from __future__ import annotations

import io
import json
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from ..config import CONFIG_PATH
from ..utils import logger
from ..utils.http import get_bytes_from_url, http_get
from .util import get_music, is_official

official_img_path: Path = CONFIG_PATH / "Images/Cover/OfficialImage"
custom_img_path: Path = CONFIG_PATH / "Images/Cover/CustomImage"
cover_img_path: Path = CONFIG_PATH / "Images/Cover"

official_img_path.mkdir(parents=True, exist_ok=True)
custom_img_path.mkdir(parents=True, exist_ok=True)

# 本地封面索引（由 「更新官方曲目封面」 维护）；远端索引不可用时用它兜底。
# 与 DcConfig/Images/Cover/CoverData 保持一致的文件格式：
# [{"MusicID": 2, "CoverURL": "https://..."}, ...]
local_cover_index_file: Path = cover_img_path / "CoverData"

# 官谱 / 非官谱封面索引（JSON 集）地址
_OFFICIAL_COVER_DATA_URL = (
    "https://raw.githubusercontent.com/DanceFengBot/dfb-miscellaneous/"
    "main/DanceCubeCover/Official/CoverData.json"
)
_CUSTOM_COVER_DATA_URL = (
    "https://raw.githubusercontent.com/DanceFengBot/dfb-miscellaneous/"
    "main/DanceCubeCover/Custom/CoverData.json"
)

# 索引中封面地址的字段名：官谱用 CoverURL，非官谱用 PicPath
_OFFICIAL_URL_KEY = "CoverURL"
_CUSTOM_URL_KEY = "PicPath"

_cover_index_lock = threading.Lock()
_cover_index_cache: dict[bool, dict[int, str]] = {}


def read_local_cover_index() -> dict[int, str]:
    """读取本地封面索引（``DcConfig/Images/Cover/CoverData``），失败返回空表。"""
    try:
        data = json.loads(local_cover_index_file.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            f"[封面索引] 本地索引读取失败，已忽略：{local_cover_index_file} | {exc}"
        )
        return {}

    if not isinstance(data, list):
        logger.warning(
            f"[封面索引] 本地索引格式不正确，已忽略：{local_cover_index_file}"
        )
        return {}

    index: dict[int, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            music_id = int(item.get("MusicID"))
        except (TypeError, ValueError):
            continue
        cover_url = item.get("CoverURL") or item.get("PicPath")
        if cover_url:
            index[music_id] = str(cover_url)
    return index


def save_local_cover_index(urls: dict[int, str]) -> int:
    """把封面地址合并写入本地索引，返回合并后的总条数。"""
    merged = read_local_cover_index()
    for raw_id, cover_url in urls.items():
        if cover_url:
            merged[int(raw_id)] = str(cover_url)

    payload = [
        {"MusicID": music_id, "CoverURL": cover_url}
        for music_id, cover_url in sorted(merged.items())
    ]
    try:
        local_cover_index_file.parent.mkdir(parents=True, exist_ok=True)
        local_cover_index_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.error(
            f"[封面索引] 本地索引写入失败：{local_cover_index_file} | {exc}"
        )

    with _cover_index_lock:
        cached = _cover_index_cache.get(True)
        if cached is None:
            _cover_index_cache[True] = dict(merged)
        else:
            cached.update(merged)
    logger.info(
        f"[封面索引] 本地索引已更新，共 {len(merged)} 条：{local_cover_index_file}"
    )
    return len(merged)


def _load_cover_index(official: bool, *, force: bool = False) -> dict[int, str]:
    """加载封面索引（按官谱 / 非官谱区分），结果在进程内缓存。

    官谱会额外合并本地索引（``CoverData``），远端索引不可用时也能取到封面。
    返回 ``{歌曲 id: 封面地址}``；加载失败时返回空表（调用方会退回接口地址）。
    """
    with _cover_index_lock:
        if not force and official in _cover_index_cache:
            return _cover_index_cache[official]

    url = _OFFICIAL_COVER_DATA_URL if official else _CUSTOM_COVER_DATA_URL
    url_key = _OFFICIAL_URL_KEY if official else _CUSTOM_URL_KEY
    kind = "官谱" if official else "非官谱"
    index: dict[int, str] = {}

    resp = http_get(url, context=f"封面索引({kind})")
    if resp is not None:
        try:
            for item in resp.json():
                music_id = item.get("MusicID")
                cover_url = item.get(url_key)
                if music_id is not None and cover_url:
                    index[int(music_id)] = str(cover_url)
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[封面索引] {kind} 解析失败：{exc}")

    if official:
        local = read_local_cover_index()
        for music_id, cover_url in local.items():
            index.setdefault(music_id, cover_url)
        if local:
            logger.debug(f"[封面索引] 官谱索引已合并本地索引 {len(local)} 条")

    if index:
        logger.debug(f"[封面索引] {kind} 已加载 {len(index)} 条封面地址")
    else:
        logger.error(f"[封面索引] {kind} 加载失败，索引为空：{url}")

    with _cover_index_lock:
        _cover_index_cache[official] = index
    return index


def _resolve_cover_url(id: int) -> str:
    """按官谱 / 非官谱访问对应 JSON 集，用 id 取封面地址；找不到时退回接口地址。"""
    official = is_official(id)
    kind = "官谱" if official else "非官谱"
    url = _load_cover_index(official).get(id, "")
    if url:
        logger.debug(f"[歌曲封面] id={id}（{kind}）从 JSON 集取到封面：{url}")
        return url
    logger.warning(
        f"[歌曲封面] id={id}（{kind}）未在 JSON 集中找到封面，改用官方接口地址"
    )
    return get_music(id).cover_url


def _get_img_path(id: int) -> Path:
    if id == 0:
        return cover_img_path / "default.jpg"
    base = official_img_path if is_official(id) else custom_img_path
    return base / f"{id}.jpg"


def is_cover_absent(id: int) -> bool:
    return not _get_img_path(id).exists()


def download_cover(id: int, url: str | None = None) -> None:
    """下载 id 对应的封面到封面目录。

    默认按官谱 / 非官谱查对应 JSON 集解析地址；传入 ``url`` 时直接使用该地址
    （供「更新官方曲目封面」批量下载时跳过索引查询）。
    """
    cover_url = url or _resolve_cover_url(id)
    data = get_bytes_from_url(cover_url) if cover_url else None
    if not data:
        logger.error(f"[歌曲封面] id={id} 封面下载失败，URL 无效：{cover_url!r}")
        raise RuntimeError(f"{id} 的 id 封面 url 无效")
    img = Image.open(io.BytesIO(data))
    img.convert("RGB").save(_get_img_path(id), "JPEG")
    logger.debug(f"[歌曲封面] id={id} 封面已保存：{_get_img_path(id)}")


def ensure_cover(id: int) -> bool:
    """发现封面不存在时自动下载，返回本地是否已有可用封面。"""
    if not is_cover_absent(id):
        return True
    logger.debug(f"[歌曲封面] id={id} 本地缺失，尝试自动下载")
    try:
        download_cover(id)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[歌曲封面] id={id} 自动下载失败：{exc}")
        return False


def ensure_covers(ids: Iterable[int], max_workers: int = 8) -> int:
    """批量补齐缺失的封面（并发下载），返回成功补齐的数量。

    用于绘制歌曲网格前预取封面：一次性把缺失的封面下好，避免在绘制循环里
    逐张串行等待网络。单个封面下载失败不影响其它封面。
    """
    missing: list[int] = []
    seen: set[int] = set()
    for raw in ids:
        music_id = int(raw)
        if music_id in seen:
            continue
        seen.add(music_id)
        if is_cover_absent(music_id):
            missing.append(music_id)
    if not missing:
        return 0
    logger.debug(f"[歌曲封面] 共 {len(missing)} 张封面缺失，开始并发下载：{missing}")
    workers = max(1, min(max_workers, len(missing)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        done = sum(1 for ok in pool.map(ensure_cover, missing) if ok)
    logger.debug(f"[歌曲封面] 封面补齐完成：{done}/{len(missing)}")
    return done


def get_cover_or_default(id: int) -> Image.Image | None:
    if is_cover_absent(id):
        logger.debug(f"[歌曲封面] id={id} 本地封面缺失，使用默认封面")
        id = 0
    try:
        return Image.open(_get_img_path(id)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[歌曲封面] 封面读取失败：{_get_img_path(id)} | {exc}")
        return None
