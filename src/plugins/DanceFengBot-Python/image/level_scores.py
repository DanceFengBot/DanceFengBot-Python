"""指定等级分数列表图，对应 Java 端 ``com.DanceCube.image.LevelScoresImage``。"""

from __future__ import annotations

import math

from ..ratio.calculator import average, get_all_rank_list
from ..ratio.rank_music import RankMusicInfo
from ..token import Token
from .common import (
    INFO_FONT,
    BLACK,
    TextEffect,
    draw_music_grid,
    prepare_ratio_card,
)


def _get_level_scores_for_level(
    music_info_list: list[RankMusicInfo], level: int
) -> list[RankMusicInfo]:
    valid = [m for m in music_info_list if m.level == level and m.is_official()]
    valid.sort(key=lambda m: m.accuracy, reverse=True)
    return valid


def _get_total_pages(music_info_list: list[RankMusicInfo], level: int) -> int:
    return math.ceil(len(_get_level_scores_for_level(music_info_list, level)) / 30)


def _get_paginated_level_scores(
    music_info_list: list[RankMusicInfo], level: int, page: int
) -> list[RankMusicInfo]:
    valid = _get_level_scores_for_level(music_info_list, level)
    start = (page - 1) * 30
    end = min(page * 30, len(valid))
    if start >= len(valid):
        return []
    return valid[start:end]


class LevelScoresImage:
    @staticmethod
    def generate(token: Token, level: int, pages: int) -> bytes | None:
        drawer, _, lv_ratio, _ = prepare_ratio_card(token, "Background4.png")
        if drawer is None:
            return None

        all_rank_list = get_all_rank_list(token.bearer_token)
        level_scores_list = _get_paginated_level_scores(all_rank_list, level, pages)

        draw_music_grid(drawer, level_scores_list, lv_ratio, dy_offset=0, max_rows=10)

        avg1 = average(level_scores_list)
        extra = (
            f"{level}分数列表\n"
            f"战力：{avg1:.4f}\n"
            f"第{pages}页，共{_get_total_pages(all_rank_list, level)}页\n"
        )
        drawer.font(INFO_FONT).color(BLACK).draw_text(
            extra, 720, 160, TextEffect().set_space_height(-6)
        )
        drawer.dispose()
        return drawer.get_image_bytes("png")
