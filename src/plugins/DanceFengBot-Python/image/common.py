"""战力图 / 分数图共享的素材与绘制逻辑。"""

from __future__ import annotations

from functools import lru_cache

from PIL import Image

from ..config import CONFIG_PATH
from ..music.cover import get_cover_or_default
from ..ratio.acc_grade import AccGrade
from ..ratio.recorded import RecordedMusicInfo
from ..utils.fonts import load_font
from .drawer import BLACK, WHITE, ImageDrawer, read_image
from .effect import ImageEffect, TextEffect

RATIO_IMAGE_PATH = CONFIG_PATH / "Images/UserRatioImage"

# 字体（与 Java 端 new Font(...) 对应）
INFO_FONT = load_font("得意黑", 45)
ID_FONT = load_font("得意黑", 30)
TITLE_FONT = load_font("Microsoft YaHei UI", 32)
SCORE_FONT = load_font("庞门正道标题体", 52)
COMBO_FONT = load_font("庞门正道标题体", 15)
LEVEL_FONT = load_font("庞门正道标题体", 23)


@lru_cache(maxsize=None)
def _asset(name: str) -> Image.Image | None:
    p = RATIO_IMAGE_PATH / name
    try:
        return Image.open(p).convert("RGBA")
    except Exception:
        return None


def _grade_asset(grade: AccGrade) -> str:
    return {
        AccGrade.SSS_AP: "AP.png",
        AccGrade.SSS: "SSS.png",
        AccGrade.SS: "SS.png",
        AccGrade.S: "S.png",
        AccGrade.A: "A.png",
        AccGrade.B: "B.png",
        AccGrade.C: "C.png",
        AccGrade.D: "D.png",
    }.get(grade, "D.png")


def _card_asset(difficulty: int) -> str:
    if difficulty in (0, -1):
        return "Card1.png"
    if difficulty == 1:
        return "Card2.png"
    if difficulty == 2:
        return "Card3.png"
    return "Card1.png"


def _fix(grade: AccGrade) -> int:
    if grade in (AccGrade.SSS, AccGrade.C):
        return 0
    if grade == AccGrade.SS:
        return -17
    if grade == AccGrade.S:
        return -6
    return 5  # A B D 与 AP


def _badge_url(rank: int) -> str | None:
    base = "https://dancewebdemo.shenghuayule.com/dance/static/userCenter_img/"
    mapping = {
        0: "quanminxingBadge0.png",
        1: "quanminxingBadge1.png",
        2: "quanminxingBadge2.png",
        3: "quanminxingBadge3.png",
        4: "quanminxingBadge5.png",
        5: "quanminxingBadge6.png",
        6: "quanminxingBadge7.png",
    }
    name = mapping.get(rank)
    return base + name if name else None


def prepare_ratio_card(token, background_name: str):
    """准备战力图 / 分数图：返回 (drawer, info, lv_ratio, rank)。"""
    from ..api.ladder import Ladder
    from ..info.user import UserInfo

    info = UserInfo.get(token)
    ladder = Ladder.get(token)
    current = next((l for l in ladder if l.is_current), None)
    rank = current.level_grade if current else -1

    bg = _asset(background_name)
    if bg is None:
        return None, info, 0, rank

    drawer = ImageDrawer(bg.copy())
    drawer.set_anti_aliasing()
    draw_header(drawer, info, rank)
    lv_ratio = info.lv_ratio
    draw_user_info_text(drawer, info, token, lv_ratio)
    return drawer, info, lv_ratio, rank


def draw_header(drawer: ImageDrawer, info, rank: int) -> None:
    """绘制头像、头像框、称号与段位徽章。"""
    drawer.draw_image(read_image(info.headimg_url), 34, 180, 174, 174)
    drawer.draw_image(read_image(info.headimg_box_path_or_none), -24, 122, 290, 290)
    if info.title_url_clean:
        drawer.draw_image(read_image(info.title_url_clean), 13, 373, 230, 79)
    badge = _badge_url(rank)
    if badge:
        drawer.draw_image(read_image(badge), -60, 122, 183, 120)


def draw_user_info_text(drawer: ImageDrawer, info, token, lv_ratio: int) -> None:
    """绘制左侧用户文本信息。"""
    user_info_text = (
        f"{info.user_name}\n\n战队：{info.team_name_or_none}\n"
        f"排名：{info.rank_nation}\n战力：{lv_ratio}"
    )
    drawer.color(BLACK).font(ID_FONT).draw_text(f"ID：{token.user_id}", 245, 200)
    drawer.font(ID_FONT).draw_text(f"地区：{info.city_name}", 245, 230)
    drawer.font(INFO_FONT).draw_text(
        user_info_text, 245, 160, TextEffect().set_max_width(230).set_space_height(0)
    )


def draw_music_grid(
    drawer: ImageDrawer,
    music_list: list[RecordedMusicInfo],
    lv_ratio: int,
    dy_offset: int = 0,
    max_rows: int = 5,
) -> None:
    """绘制歌曲卡片网格。"""
    dx, dy = 395, 180
    index = 0
    for row in range(max_rows):
        for col in range(3):
            if index >= len(music_list):
                return
            info = music_list[index]
            index += 1
            dx2 = col * dx
            dy2 = row * dy + dy_offset

            cover = get_cover_or_default(info.id)
            card = _asset(_card_asset(info.difficulty))
            grade = _asset(_grade_asset(info.acc_grade))
            fix = _fix(info.acc_grade)
            effect = ImageEffect().set_arc(35)

            diff = (
                f"+{info.ratio_int - lv_ratio}"
                if info.ratio_int > lv_ratio
                else str(info.ratio_int - lv_ratio)
            )

            drawer.draw_image(cover, 16 + dx2, 621 + dy2, 130, 158, effect)
            drawer.draw_image(card, 15 + dx2, 620 + dy2)
            drawer.draw_image(grade, 285 + fix + dx2, 715 + dy2)
            drawer.font(TITLE_FONT, BLACK).draw_text(
                info.name, 160 + dx2, 624 + dy2, TextEffect().set_max_width(220)
            )
            drawer.font(SCORE_FONT).draw_text(str(info.score), 160 + dx2, 662 + dy2)
            drawer.font(COMBO_FONT).draw_text(
                f"{info.combo}\n{info.miss}\n{info.accuracy:.2f}%",
                230 + dx2,
                726 + dy2,
                TextEffect().set_space_height(1),
            )
            drawer.draw_text(f"> {info.ratio_int} ({diff})", 163 + dx2, 708 + dy2)
            drawer.font(LEVEL_FONT, WHITE).draw_text(
                str(info.level), 17 + dx2, 747 + dy2
            )


def get_last_ratio(ratio_list: list, info) -> int:
    if ratio_list:
        return ratio_list[-(2 if len(ratio_list) > 1 else 1)].ratio
    return info.lv_ratio


RATIO_COMMENTS = [
    '  "你已初步了解这款游戏了\n  继续练习吧~"',
    '  "你已经适应10级的歌曲了\n  继续练习吧~"',
    '  "你正在对线14级的歌了\n  继续加油~"',
    '  "你即将迈入大佬的行列\n  加油加油！"',
    '  "恭喜突破1800守门员\n  正式成为大佬啦！"',
    '  "你即将成神\n  请继续和1819对线"',
    '  "你已步入神的行列\n  快快杀19吧~"',
    '  "你已经成为外星人\n  正在薄纱一切歌曲"',
]


def get_ratio_comment(ratio: int) -> str:
    if ratio <= 1000:
        return RATIO_COMMENTS[0]
    if ratio < 1300:
        return RATIO_COMMENTS[1]
    if ratio < 1500:
        return RATIO_COMMENTS[2]
    if ratio < 1800:
        return RATIO_COMMENTS[3]
    if ratio < 1900:
        return RATIO_COMMENTS[4]
    if ratio < 2000:
        return RATIO_COMMENTS[5]
    if ratio < 2080:
        return RATIO_COMMENTS[6]
    if ratio <= 2100:
        return RATIO_COMMENTS[7]
    return ""
