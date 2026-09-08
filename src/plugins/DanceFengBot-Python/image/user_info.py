"""个人信息图，对应 Java 端 ``com.DanceCube.image.UserInfoImage``。"""

from __future__ import annotations

from PIL import Image

from ..api.ladder import Ladder
from ..config import CONFIG_PATH
from ..info.account import AccountInfo
from ..info.reply_item import ReplyItem
from ..info.status import InfoStatus
from ..info.user import UserInfo
from ..token import Token
from ..utils.fonts import load_font
from .common import _badge_url
from .drawer import ImageDrawer, read_image
from .effect import TextEffect

_BG_PATH = CONFIG_PATH / "Images/UserInfoImage/Background2.png"

_FONT = load_font("得意黑", 36)
_FONT2 = load_font("得意黑", 20)


class UserInfoImage:
    @staticmethod
    def generate(token: Token, id: int) -> bytes | None:
        user_info = UserInfo.get_by_id(token, id)
        ladder = Ladder.get(token)
        current = next(
            (l for l in ladder if l.is_current and token.user_id == id), None
        )
        rank = current.level_grade if current else -1

        if user_info.status == InfoStatus.NONEXISTENT:
            return None
        if not user_info.headimg_url:
            return None

        try:
            bg = Image.open(_BG_PATH).convert("RGBA")
        except Exception:
            return None

        drawer = ImageDrawer(bg)
        drawer.set_anti_aliasing()

        drawer.draw_image(read_image(user_info.headimg_url), 120, 150, 137, 137)
        if user_info.headimg_box_path_or_none:
            drawer.draw_image(
                read_image(user_info.headimg_box_path_or_none), 74, 104, 230, 230
            )
        if user_info.title_url_clean:
            drawer.draw_image(read_image(user_info.title_url_clean), 95, 300, 190, 68)
        badge = _badge_url(rank)
        if badge:
            drawer.draw_image(read_image(badge), 25, 95, 183, 120)

        effect = TextEffect().set_max_width(235).set_space_height(0)
        drawer.font(_FONT)

        if user_info.status != InfoStatus.PRIVATE:
            gold = "不可见"
            played_times = "不可见"
            region = "无"
            ladder_score = "不可见"
            if token.user_id == id:
                account_info = AccountInfo.get(token)
                reply_item = ReplyItem.get(token)
                gold = str(account_info.gold)
                played_times = str(reply_item.played_times)
                if current is not None:
                    ladder_score = str(current.level_point)
                region = str(user_info.city_name)

            team = user_info.team_name_or_none if user_info.team_name_or_none else "无"
            drawer.draw_text(
                f"{user_info.user_name}\n\n战队：{team}\n战力：{user_info.lv_ratio}\n金币：{gold}",
                293,
                137,
                effect,
            ).draw_text(
                f"积分：{user_info.music_score}\n"
                f"全连率：{user_info.combo_percent / 100:.2f}%\n"
                f"全国排名：{user_info.rank_nation}\n"
                f"游玩次数：{played_times}\n"
                f"天梯分：{ladder_score}",
                106,
                472,
                effect,
            ).font(_FONT2).draw_text(
                f"ID：{user_info.user_id}\n地区：{region}", 293, 175, effect
            )
        else:
            city = user_info.city_name if user_info.city_name else "无"
            drawer.draw_text(
                f"{user_info.user_name}\n\n地区：{city}\n战力：{user_info.lv_ratio}",
                293,
                137,
                effect,
            ).draw_text("该账号已设置隐私", 106, 472).font(_FONT2).draw_text(
                "ID：" + str(user_info.user_id), 293, 170
            )

        drawer.dispose()
        return drawer.get_image_bytes("png")
