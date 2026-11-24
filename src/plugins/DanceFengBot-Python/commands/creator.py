"""创作者（谱师）相关命令：创作者信息、自制谱作品、兑换码生成。

功能对标 DcNana 的「创作者」菜单：

* ``创作者信息``：创作等级 / 创作金币；
* ``我的自制谱``：已发布的自制谱列表（可翻页）；
* ``生成兑换码``：为指定自制谱批量生成兑换码；
* ``兑换码全家桶``：为所有已发布自制谱各生成一个兑换码。

兑换码属于敏感信息，生成类命令只允许私聊使用；兑换兑换码沿用既有的
「私聊发送兑换码」功能即可。
"""

from __future__ import annotations

import time

from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from ..api.maker import MakerInfo, PublishedMusic, generate_music_code
from ..deps import resolve_token, to_thread
from ..token import Token
from ..utils import logger

# 作品列表展示时每页数量（QQ 文本消息不宜过长）
_PAGE_SIZE = 10

# 单个谱面一次最多生成的兑换码数量（与 DcNana 的上限一致）
_MAX_CODES = 50

# 全家桶最多覆盖的谱面数量，避免一次生成过多兑换码
_MAX_FAMILY = 30

# 连续生成失败达到该次数时提前停止，避免无意义的重复请求
_MAX_CONSECUTIVE_FAILURES = 3

_ONLY_PRIVATE = "兑换码比较敏感，请私聊小枫生成哦～"


def format_maker_info(info: MakerInfo) -> str:
    """格式化创作者信息。"""
    return "\n".join(
        [
            "🎨 创作者信息",
            f"名称：{info.user_name or '未知'}",
            f"ID：{info.user_id}",
            f"创作等级：Lv.{info.maker_grade}",
            f"创作经验：{info.maker_exp:,}",
            f"创作金币：{info.total_profit:,}",
            "创作者认证：已开通",
            "",
            "发送“我的自制谱”查看已发布作品",
        ]
    )


def format_not_creator(info: MakerInfo) -> str:
    """格式化「还不是创作者」的提示。"""
    return "\n".join(
        [
            "🎨 创作者信息",
            f"名称：{info.user_name or '未知'}",
            f"ID：{info.user_id}",
            "创作者认证：未开通",
            "",
            "你好像还不是舞立方的创作者哦～",
            "在舞立方完成谱师认证并发布自制谱后，就能查看创作数据、生成兑换码啦",
        ]
    )


def format_published(
    items: list[PublishedMusic], page: int, total: int = 0, has_more: bool = False
) -> str:
    """格式化一页已发布作品。"""
    lines = [f"🎼 我的自制谱（第 {page} 页）"]
    for item in items:
        line = f"{item.music_id}  {item.name}"
        details: list[str] = []
        if item.price_sale:
            details.append(f"{item.price_sale} 金币/天")
        if item.clicks_ratio:
            details.append(f"点播 {item.clicks_ratio}")
        if details:
            line += "  " + "  ".join(details)
        lines.append(line)

    if total:
        pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
        lines.append(f"共 {total} 首，第 {page}/{pages} 页")
    else:
        lines.append(f"本页 {len(items)} 首")
    if has_more:
        lines.append(f"发送“我的自制谱 {page + 1}”查看下一页")
    return "\n".join(lines)


def format_codes(music_id: int, codes: list[str], requested: int) -> str:
    """格式化批量生成的兑换码。"""
    title = f"🎟 兑换码生成完成（歌曲 {music_id}，共 {len(codes)} 个）"
    if requested != len(codes):
        title = (
            f"🎟 兑换码部分生成成功（歌曲 {music_id}，"
            f"请求 {requested} 个，成功 {len(codes)} 个）"
        )
    return "\n".join(
        [title, "", *codes, "", "⚠️ 兑换码仅可使用一次，请勿公开分享"]
    )


def format_family(entries: list[tuple[PublishedMusic, str]], skipped: int) -> str:
    """格式化兑换码全家桶。"""
    lines = [f"🎟 兑换码全家桶（共 {len(entries) + skipped} 首）", ""]
    for music, code in entries:
        lines.append(f"{music.music_id}  {music.name}")
        lines.append(code)
    if skipped:
        lines.append(f"（有 {skipped} 首生成失败，可能已下架或没有权限）")
    lines.extend(["", "⚠️ 兑换码仅可使用一次，请勿公开分享"])
    return "\n".join(lines)


def _generate_codes(token: Token, music_id: int, count: int) -> list[str]:
    """为一个谱面连续生成 ``count`` 个兑换码（失败会自动提前停止）。"""
    codes: list[str] = []
    consecutive_failures = 0
    for index in range(count):
        code = generate_music_code(token, music_id, index)
        if code:
            codes.append(code)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            logger.warning(
                f"[创作者] 第 {index + 1}/{count} 个兑换码生成失败：musicId={music_id}"
            )
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                logger.warning(f"[创作者] 连续失败，停止生成：musicId={music_id}")
                break
        time.sleep(0.1)
    return codes


def _generate_family(
    token: Token,
) -> tuple[list[tuple[PublishedMusic, str]], int] | None:
    """为所有已发布谱面各生成一个兑换码。

    返回 ``(成功列表, 失败数量)``；第一页就请求失败时返回 ``None``。
    """
    charts: list[PublishedMusic] = []
    page = 1
    while len(charts) < _MAX_FAMILY:
        result = PublishedMusic.get_page(token, page, 15)
        if result is None:
            if page == 1:
                return None
            logger.warning(f"[创作者] 全家桶：第 {page} 页作品获取失败，使用已取到的作品")
            break
        items, total = result
        if not items:
            break
        charts.extend(items)
        if total and page * 15 >= total:
            break
        if len(items) < 15:
            break
        page += 1

    if not charts:
        return [], 0

    if len(charts) > _MAX_FAMILY:
        logger.info(f"[创作者] 全家桶作品过多（{len(charts)} 首），仅处理前 {_MAX_FAMILY} 首")
        charts = charts[:_MAX_FAMILY]

    entries: list[tuple[PublishedMusic, str]] = []
    skipped = 0
    for index, music in enumerate(charts):
        code = generate_music_code(token, music.music_id, index)
        if code:
            entries.append((music, code))
        else:
            skipped += 1
            logger.warning(f"[创作者] 全家桶生成失败：musicId={music.music_id}")
        time.sleep(0.1)
    return entries, skipped


# ---------------------------------------------------------------- 创作者信息
maker_info_cmd = on_command(
    "创作者信息",
    aliases={"谱师信息", "maker", "makerinfo"},
    priority=5,
    block=True,
)


@maker_info_cmd.handle()
async def _maker_info(event, matcher: Matcher) -> None:
    qq = str(event.user_id)
    token = await resolve_token(matcher, qq)
    if token is None:
        return

    info = await to_thread(MakerInfo.get, token)
    if info is None:
        await matcher.finish("创作者信息获取失败，请稍后再试")
    if not info.is_creator:
        logger.info(
            f"[创作者] QQ={qq} 不是创作者（等级={info.maker_grade} "
            f"认证={info.auth_status} 收益={info.total_profit}）"
        )
        await matcher.finish(format_not_creator(info))

    logger.info(
        f"[创作者] QQ={qq} 查看创作者信息："
        f"等级={info.maker_grade} 经验={info.maker_exp} 金币={info.total_profit}"
    )
    await matcher.finish(format_maker_info(info))


# ---------------------------------------------------------------- 我的自制谱
my_music_cmd = on_command(
    "我的自制谱",
    aliases={"我的作品", "自制谱列表", "mypublish"},
    priority=5,
    block=True,
)


@my_music_cmd.handle()
async def _my_music(
    event, matcher: Matcher, args: Message = CommandArg()
) -> None:
    qq = str(event.user_id)
    raw = args.extract_plain_text().strip()
    page = 1
    if raw:
        try:
            page = int(raw.split()[0])
        except (ValueError, IndexError):
            await matcher.finish("页码需要是数字哦\n例：我的自制谱 2")
    if page < 1:
        page = 1

    token = await resolve_token(matcher, qq)
    if token is None:
        return

    result = await to_thread(PublishedMusic.get_page, token, page, _PAGE_SIZE)
    if result is None:
        await matcher.finish("自制谱列表获取失败，请稍后再试")
    items, total = result
    if not items:
        if page == 1:
            await matcher.finish(
                "你还没有发布过自制谱哦～\n成为创作者后就能在这里查看作品啦"
            )
        await matcher.finish(f"第 {page} 页没有作品了")

    pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE if total else 0
    has_more = page < pages if pages else len(items) >= _PAGE_SIZE
    logger.info(
        f"[创作者] QQ={qq} 查看自制谱第 {page} 页：{len(items)} 首，总数={total or '未知'}"
    )
    await matcher.finish(format_published(items, page, total, has_more))


# ---------------------------------------------------------------- 生成兑换码
gen_code_cmd = on_command(
    "生成兑换码",
    aliases={"批量生成兑换码", "gencode"},
    priority=5,
    block=True,
)


@gen_code_cmd.handle()
async def _gen_code(
    event, matcher: Matcher, args: Message = CommandArg()
) -> None:
    if isinstance(event, GroupMessageEvent):
        await matcher.finish(_ONLY_PRIVATE)

    qq = str(event.user_id)
    parts = args.extract_plain_text().split()
    if not parts:
        await matcher.finish(
            "格式：生成兑换码 (歌曲id) (数量，可选)\n例：生成兑换码 12345 3"
        )
    try:
        music_id = int(parts[0])
    except ValueError:
        await matcher.finish("歌曲id 需要是数字哦")
    if music_id <= 0:
        await matcher.finish("歌曲id 需要是正整数哦")

    count = 1
    if len(parts) >= 2:
        try:
            count = int(parts[1])
        except ValueError:
            await matcher.finish("数量需要是数字哦")
    count = max(1, min(count, _MAX_CODES))

    token = await resolve_token(matcher, qq)
    if token is None:
        return

    logger.info(f"[创作者] QQ={qq} 为歌曲 {music_id} 生成 {count} 个兑换码")
    await matcher.send(f"正在为歌曲 {music_id} 生成 {count} 个兑换码，请稍候…")
    codes = await to_thread(_generate_codes, token, music_id, count)
    if not codes:
        logger.warning(
            f"[创作者] QQ={qq} 歌曲 {music_id} 兑换码全部生成失败（请求 {count} 个）"
        )
        await matcher.finish(
            "兑换码生成失败：可能这首歌不是你发布的，或当前账号没有创作者权限"
        )
    logger.info(f"[创作者] QQ={qq} 歌曲 {music_id} 生成 {len(codes)}/{count} 个兑换码")
    await matcher.finish(format_codes(music_id, codes, count))


# ---------------------------------------------------------------- 兑换码全家桶
family_cmd = on_command(
    "兑换码全家桶",
    aliases={"全家桶", "familycode"},
    priority=5,
    block=True,
)


@family_cmd.handle()
async def _family(event, matcher: Matcher) -> None:
    if isinstance(event, GroupMessageEvent):
        await matcher.finish(_ONLY_PRIVATE)

    qq = str(event.user_id)
    token = await resolve_token(matcher, qq)
    if token is None:
        return

    logger.info(f"[创作者] QQ={qq} 请求生成兑换码全家桶")
    await matcher.send("正在整理你的自制谱并生成兑换码，请稍候…")
    result = await to_thread(_generate_family, token)
    if result is None:
        await matcher.finish("自制谱列表获取失败，请稍后再试")
    entries, skipped = result
    if not entries and not skipped:
        await matcher.finish("你还没有发布过自制谱哦～\n成为创作者后就能使用全家桶啦")

    logger.info(
        f"[创作者] QQ={qq} 全家桶完成：成功 {len(entries)} 首，失败 {skipped} 首"
    )
    await matcher.finish(format_family(entries, skipped))
