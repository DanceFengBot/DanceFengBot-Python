"""战力分析（B30）图，对应 Java 端 ``com.DanceCube.image.UserRatioBest30Image``。"""

from __future__ import annotations

from ..api.lv_ratio_history import LvRatioHistory
from ..ratio.calculator import (
    average,
    get_all_rank_list,
    get_sub_rank_30_list,
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


class UserRatioBest30Image:
    @staticmethod
    def generate(token: Token) -> bytes | None:
        drawer, info, lv_ratio, _ = prepare_ratio_card(token, "Background2.png")
        if drawer is None:
            return None

        ratio_list = LvRatioHistory.get(token)
        all_rank_list = get_all_rank_list(token.bearer_token)
        rank30_list = get_sub_rank_30_list(all_rank_list, True)

        draw_music_grid(drawer, rank30_list, lv_ratio, dy_offset=0, max_rows=10)

        last = get_last_ratio(ratio_list, info)
        avg1 = average(rank30_list)
        extra = (
            f"上次战力：{last}\n"
            f"B-30 战力：{avg1:.4f}\n"
            + get_ratio_comment(lv_ratio)
        )
        drawer.font(INFO_FONT).color(BLACK).draw_text(
            extra, 720, 160, TextEffect().set_space_height(-6)
        )
        drawer.dispose()
        return drawer.get_image_bytes("png")
