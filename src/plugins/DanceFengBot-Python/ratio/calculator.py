"""战力计算，对应 Java 端 ``com.DanceCube.ratio.RatioCalculator``。"""

from __future__ import annotations

import json
from typing import TypeVar

from ..utils.http import http_get
from .rank_music import RankMusicInfo
from .recent_music import RecentMusicInfo
from .recorded import RecordedMusicInfo

_BASE = "https://dancedemo.shenghuayule.com/Dance"

T = TypeVar("T", bound=RecordedMusicInfo)


def average(multi_info: list[T]) -> float:
    if not multi_info:
        return 0.0
    return sum(info.ratio for info in multi_info) / len(multi_info)


def _get_category_rank_list(json_str: str) -> list[RankMusicInfo]:
    try:
        arr = json.loads(json_str)
    except Exception:
        return []
    result: list[RankMusicInfo] = []
    for obj in arr:
        for info in obj.get("ItemRankList", []):
            result.append(
                RankMusicInfo(
                    obj.get("MusicID", 0),
                    obj.get("Name", ""),
                    obj.get("OwnerType", 0),
                    info,
                )
            )
    return result


def get_all_rank_list(auth: str) -> list[RankMusicInfo]:
    url = f"{_BASE}/api/User/GetMyRankNew?musicIndex="
    music_infos: list[RankMusicInfo] = []
    for i in range(2, 7):  # 2 3 4 5 6：国语 粤语 韩语 欧美 其它
        resp = http_get(url + str(i), headers={"Authorization": auth})
        if resp is not None:
            music_infos.extend(_get_category_rank_list(resp.text))
    return music_infos


def get_all_recent_list(auth: str) -> list[RecentMusicInfo]:
    resp = http_get(f"{_BASE}/api/User/GetLastPlay", headers={"Authorization": auth})
    if resp is None:
        return []
    try:
        arr = json.loads(resp.text)
    except Exception:
        return []
    return [RecentMusicInfo(e) for e in arr]


def is_ratio_valid(music_info: RecordedMusicInfo) -> bool:
    return music_info.level >= 0 and music_info.is_official()


def get_sub_rank_15_list(
    music_info_list: list[RankMusicInfo], ratio_valid_only: bool
) -> list[RankMusicInfo]:
    music_info_list.sort(key=lambda m: m.ratio, reverse=True)
    sub: list[RankMusicInfo] = []
    if ratio_valid_only:
        for m in music_info_list:
            if len(sub) >= 15:
                break
            if is_ratio_valid(m):
                sub.append(m)
    else:
        sub = music_info_list[:15]
    return sub


def get_sub_rank_30_list(
    music_info_list: list[RankMusicInfo], ratio_valid_only: bool
) -> list[RankMusicInfo]:
    music_info_list.sort(key=lambda m: m.ratio, reverse=True)
    sub: list[RankMusicInfo] = []
    if ratio_valid_only:
        for m in music_info_list:
            if len(sub) >= 30:
                break
            if is_ratio_valid(m):
                sub.append(m)
    else:
        sub = music_info_list[:15]  # 忠实保留原实现
    return sub


def get_sub_recent_15_list(
    music_info_list: list[RecentMusicInfo], official_only: bool
) -> list[RecentMusicInfo]:
    sub: list[RecentMusicInfo] = []
    if official_only:
        for m in music_info_list:
            if len(sub) >= 15:
                break
            if is_ratio_valid(m):
                sub.append(m)
    else:
        sub = music_info_list[:15]
    return sub


def get_sub_ap30_list(
    music_info_list: list[RankMusicInfo], ratio_valid_only: bool
) -> list[RankMusicInfo]:
    music_info_list.sort(key=lambda m: m.ratio, reverse=True)
    sub: list[RankMusicInfo] = []
    if ratio_valid_only:
        for m in music_info_list:
            if len(sub) >= 30:
                break
            if is_ratio_valid(m) and m.accuracy == 100.0:
                sub.append(m)
    else:
        for m in music_info_list[:15]:
            if m.accuracy == 100.0:
                sub.append(m)
    return sub


def get_level_scores_list(
    music_info_list: list[RankMusicInfo], ratio_valid_only: bool, level: int
) -> list[RankMusicInfo]:
    valid: list[RankMusicInfo] = []
    for m in music_info_list:
        if m.level != level:
            continue
        if ratio_valid_only and not is_ratio_valid(m):
            continue
        valid.append(m)
    return valid
