"""战力分析（B15/R15）图，对应 Java 端 ``com.DanceCube.image.UserRatioImage``。"""

from __future__ import annotations

from ..api.lv_ratio_history import LvRatioHistory
from ..ratio.calculator import (
    average,
    get_all_rank_list,
    get_all_recent_list,
    get_sub_rank_15_list,
    get_sub_recent_15_list,
)
from ..token import Token
from .common import (
    INFO_FONT,
    BLACK,
    TextEffect,
    draw_music_grid,
    get_last_ratio,
    get_ratio_comment,
    prepare_ratio_card,
)


class UserRatioImage:
    @staticmethod
    def generate(token: Token) -> bytes | None:
        drawer, info, lv_ratio, _ = prepare_ratio_card(token, "Background1.png")
        if drawer is None:
            return None

        ratio_list = LvRatioHistory.get(token)
        all_rank_list = get_all_rank_list(token.bearer_token)
        all_recent_list = get_all_recent_list(token.bearer_token)
        rank15_list = get_sub_rank_15_list(all_rank_list, True)
        recent15_list = get_sub_recent_15_list(all_recent_list, False)

        # B15
        draw_music_grid(drawer, rank15_list, lv_ratio, dy_offset=0, max_rows=5)
        # R15
        draw_music_grid(drawer, recent15_list, lv_ratio, dy_offset=1065, max_rows=5)

        last = get_last_ratio(ratio_list, info)
        avg1 = average(rank15_list)
        avg2 = average(recent15_list)
        all_avg = (avg1 + avg2) / 2
        extra = (
            f"上次战力：{last}\n"
            f"B-15 战力：{avg1:.4f}\n"
            f"R-15 战力：{avg2:.4f}\n"
            f"平均战力：{all_avg:.5f}\n"
            + get_ratio_comment(lv_ratio)
        )
        drawer.font(INFO_FONT).color(BLACK).draw_text(
            extra, 720, 160, TextEffect().set_space_height(-6)
        )
        drawer.dispose()
        return drawer.get_image_bytes("png")
