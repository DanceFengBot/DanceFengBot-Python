"""官方曲目封面更新。

参照 ``1v7w/nonebot-plugin-dancecube`` 的 ``updatecover`` 实现：分页拉取舞立方
「歌曲排行榜」接口 ``api/User/GetMusicRankingNew``（``musicIndex=0`` 为全部歌曲），
从返回的 ``Cover`` 字段取得封面地址，按 id 下载到
``DcConfig/Images/Cover/OfficialImage``；已存在的封面默认跳过。

拉取到的最新封面地址会合并写入本地索引 ``DcConfig/Images/Cover/CoverData``，
``music.cover`` 在远端索引不可用时会用它兜底，因此更新一次后即使没有外网
索引也能正常取图。

触发方式：

* 管理员命令 ``#updateCover``（带 ``force`` 参数时强制重下已存在的封面）；
* 每天 03:00 的定时任务（只补缺失的封面）。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..utils import logger
from ..utils.http import http_get
from .cover import download_cover, is_cover_absent, save_local_cover_index

# 歌曲排行榜接口：musicIndex=0 表示全部歌曲（2~6 为各语种分类）
_RANKING_API = "https://dancedemo.shenghuayule.com/Dance/api/User/GetMusicRankingNew"
_ALL_MUSIC_INDEX = 0
_FALLBACK_MUSIC_INDEXES: tuple[int, ...] = (2, 3, 4, 5, 6)

# 接口单页最多返回 20 条，这里按 50 请求；翻页上限用于防止接口异常时死循环
_PAGE_SIZE = 50
_MAX_PAGES = 500
_MAX_PAGE_FAILURES = 3

# 同一时间只允许一个更新任务（定时任务与管理员命令可能撞车）
_UPDATE_LOCK = threading.Lock()


class CoverUpdateBusy(RuntimeError):
    """已有封面更新任务正在执行。"""


@dataclass(frozen=True)
class CoverUpdateResult:
    """一次封面更新的统计结果。"""

    total: int
    downloaded: int
    skipped: int
    failed: int
    elapsed: float
    index_size: int

    def summary(self) -> str:
        return "\n".join(
            [
                "官方曲目封面更新完成！",
                f"清单：{self.total} 首（本地索引 {self.index_size} 条）",
                f"新下载：{self.downloaded} 张",
                f"已存在：{self.skipped} 张",
                f"失败：{self.failed} 张",
                f"耗时：{self.elapsed:.1f} 秒",
            ]
        )


def _normalize_cover_url(url: str) -> str:
    """去掉封面地址末尾的尺寸后缀（如 ``/200``），取原图。"""
    url = url.strip()
    if url.endswith("/200"):
        return url[:-4]
    return url


def _fetch_category(index: int) -> dict[int, str]:
    """按 ``musicIndex`` 翻页拉取歌曲封面地址，返回 ``{歌曲 id: 封面地址}``。"""
    found: dict[int, str] = {}
    page = 1
    failures = 0

    while page <= _MAX_PAGES:
        url = (
            f"{_RANKING_API}?musicIndex={index}"
            f"&page={page}&pagesize={_PAGE_SIZE}"
        )
        resp = http_get(
            url, context=f"官方封面-歌曲列表(musicIndex={index}, page={page})"
        )
        if resp is None or resp.status_code != 200:
            failures += 1
            status = resp.status_code if resp is not None else "无响应"
            logger.warning(
                f"[封面更新] musicIndex={index} 第 {page} 页获取失败"
                f"（状态 {status}，连续失败 {failures}/{_MAX_PAGE_FAILURES}）"
            )
            if failures >= _MAX_PAGE_FAILURES:
                logger.error(f"[封面更新] musicIndex={index} 连续失败，停止翻页")
                break
            page += 1
            continue

        failures = 0
        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[封面更新] musicIndex={index} 第 {page} 页解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            break

        items = data.get("List") if isinstance(data, dict) else None
        if not items:
            break

        for item in items:
            music_id = item.get("MusicID")
            cover_url = item.get("Cover")
            if music_id is None or not cover_url:
                continue
            found[int(music_id)] = _normalize_cover_url(str(cover_url))

        logger.debug(
            f"[封面更新] musicIndex={index} 第 {page} 页 {len(items)} 首，"
            f"累计 {len(found)} 首"
        )
        page += 1

    return found


def fetch_official_cover_index() -> dict[int, str]:
    """拉取官方曲目封面清单（优先 ``musicIndex=0`` 的全部歌曲）。"""
    logger.info("[封面更新] 开始拉取官方曲目封面清单")
    index = _fetch_category(_ALL_MUSIC_INDEX)
    if not index:
        logger.warning("[封面更新] 全部歌曲清单为空，改为按语种分类拉取")
        for music_index in _FALLBACK_MUSIC_INDEXES:
            index.update(_fetch_category(music_index))
    logger.info(f"[封面更新] 官方曲目封面清单共 {len(index)} 首")
    return index


def _download_one(item: tuple[int, str]) -> bool:
    music_id, cover_url = item
    try:
        download_cover(music_id, cover_url)
        return True
    except Exception as exc:  # noqa: BLE001  # 单张失败不影响整体
        logger.warning(f"[封面更新] id={music_id} 封面下载失败：{exc}")
        return False


def update_official_covers(
    force: bool = False,
    max_workers: int = 8,
    refresh_index: bool = True,
) -> CoverUpdateResult:
    """更新官方曲目封面。

    参数:
        force: 为 ``True`` 时重新下载所有封面（默认只补本地缺失的）；
        max_workers: 并发下载线程数；
        refresh_index: 是否把最新封面地址合并写入本地索引 ``CoverData``。

    返回:
        统计结果；获取封面清单失败时抛出 ``RuntimeError``，已有任务在跑时
        抛出 ``CoverUpdateBusy``。
    """
    if not _UPDATE_LOCK.acquire(blocking=False):
        raise CoverUpdateBusy("官方曲目封面正在更新中")

    started = time.perf_counter()
    try:
        logger.info(
            f"[封面更新] 开始更新官方曲目封面（{'全部重下' if force else '仅补缺失'}）"
        )
        index = fetch_official_cover_index()
        if not index:
            raise RuntimeError("获取官方曲目清单失败，请稍后重试")

        index_size = save_local_cover_index(index) if refresh_index else len(index)

        targets: list[tuple[int, str]] = []
        skipped = 0
        for music_id, cover_url in sorted(index.items()):
            if not force and not is_cover_absent(music_id):
                skipped += 1
                continue
            targets.append((music_id, cover_url))

        downloaded = failed = 0
        if targets:
            workers = max(1, min(max_workers, len(targets)))
            logger.info(
                f"[封面更新] 待下载 {len(targets)} 张（已存在 {skipped} 张），"
                f"并发 {workers}"
            )
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for done, ok in enumerate(pool.map(_download_one, targets), start=1):
                    if ok:
                        downloaded += 1
                    else:
                        failed += 1
                    if done % 50 == 0 or done == len(targets):
                        logger.info(
                            f"[封面更新] 进度 {done}/{len(targets)}："
                            f"成功 {downloaded}，失败 {failed}"
                        )

        elapsed = time.perf_counter() - started
        result = CoverUpdateResult(
            total=len(index),
            downloaded=downloaded,
            skipped=skipped,
            failed=failed,
            elapsed=elapsed,
            index_size=index_size,
        )
        logger.info(
            f"[封面更新] 更新结束：清单 {result.total} 首，"
            f"下载 {downloaded}，跳过 {skipped}，失败 {failed}，耗时 {elapsed:.1f}s"
        )
        return result
    finally:
        _UPDATE_LOCK.release()


def run_scheduled_update() -> None:
    """每日定时任务入口：只补缺失封面，异常只记录日志。"""
    try:
        result = update_official_covers()
    except CoverUpdateBusy:
        logger.info("[封面更新] 已有更新任务在运行，跳过本次定时任务")
        return
    except Exception as exc:  # noqa: BLE001  # 定时任务不应抛出
        logger.error(f"[封面更新] 定时更新失败：{exc}")
        return
    logger.info(f"[封面更新] 定时任务完成：{result.summary().replace(chr(10), '；')}")
