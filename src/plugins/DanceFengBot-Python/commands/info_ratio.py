"""个人信息与战力分析相关命令。"""

from __future__ import annotations

from nonebot import on_command, on_fullmatch
from nonebot.adapters.onebot.v11 import Message
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from .. import store
from ..deps import image_segment, resolve_token, to_thread
from ..image import (
    LevelScoresImage,
    UserInfoImage,
    UserRatioAP30Image,
    UserRatioBest30Image,
    UserRatioImage,
)
from ..info.reply_item import ReplyItem

# ---------------------------------------------------------------- 个人信息
user_info = on_fullmatch(
    ("个人信息", "看看我的", "我的信息", "我的舞立方", "mydc", "mywlf"),
    priority=5,
    block=True,
)


@user_info.handle()
async def _user_info(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    png = await to_thread(UserInfoImage.generate, token, token.user_id)
    if png is None:
        await matcher.finish("个人信息获取失败，请稍后再试")
    await matcher.finish(image_segment(png))


# ---------------------------------------------------------------- 查看他人（弃用）
others_info = on_command("看看你的", aliases={"康康你的"}, priority=5, block=True)


@others_info.handle()
async def _others_info(event, matcher: Matcher, args: Message = CommandArg()) -> None:
    arg = args.extract_plain_text().strip()
    if not arg:
        return
    try:
        num = int(arg)
    except ValueError:
        return

    token = await resolve_token(
        matcher,
        str(event.user_id),
        invalid="小枫这登录身份过期了💦\n重新私信登录恢复吧💦",
    )
    if token is None:
        return

    if 9999 < num < 99_999_999:  # 舞立方 ID
        target_id = num
    elif num > 999_999 and str(num) in store.user_tokens_map:  # QQ 号
        target_id = store.user_tokens_map[str(num)].user_id
    else:
        await matcher.finish("唔...小枫好像不认识他")

    png = await to_thread(UserInfoImage.generate, token, target_id)
    if png is None:
        await matcher.finish("这个账号未保存或不存在！")
    await matcher.finish(image_segment(png))


# ---------------------------------------------------------------- 战力分析
user_ratio = on_fullmatch(
    ("战力分析", "我的战力", "查看战力", "myrt"), priority=5, block=True
)


@user_ratio.handle()
async def _user_ratio(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    await matcher.send("小枫正在计算中,等一下下💦...")
    png = await to_thread(UserRatioImage.generate, token)
    if png is None:
        await matcher.finish("战力图生成失败，请稍后再试")
    await matcher.finish(image_segment(png))


user_ratio_b30 = on_fullmatch(("战力分析b30", "myrtb30"), priority=5, block=True)


@user_ratio_b30.handle()
async def _user_ratio_b30(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    await matcher.send("小枫正在计算中,等一下下💦...")
    png = await to_thread(UserRatioBest30Image.generate, token)
    if png is None:
        await matcher.finish("战力图生成失败，请稍后再试")
    await matcher.finish(image_segment(png))


user_ratio_ap30 = on_fullmatch(("战力分析ap30", "myrtap30"), priority=5, block=True)


@user_ratio_ap30.handle()
async def _user_ratio_ap30(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    await matcher.send("小枫正在计算中,等一下下💦...")
    png = await to_thread(UserRatioAP30Image.generate, token)
    if png is None:
        await matcher.finish("战力图生成失败，请稍后再试")
    await matcher.finish(image_segment(png))


# ---------------------------------------------------------------- 分数列表
level_scores = on_command("分数列表", priority=5, block=True)


@level_scores.handle()
async def _level_scores(event, matcher: Matcher, args: Message = CommandArg()) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    parts = args.extract_plain_text().split()
    level, pages = 1, 1
    if parts:
        try:
            level = int(parts[0])
            if len(parts) > 1:
                pages = int(parts[1])
        except ValueError:
            await matcher.finish("啊...这个数字是什么")

    await matcher.send("小枫正在计算中,等一下下💦...")
    png = await to_thread(LevelScoresImage.generate, token, level, pages)
    if png is None:
        await matcher.finish("分数列表生成失败，请稍后再试")
    await matcher.finish(image_segment(png))


# ---------------------------------------------------------------- ReplyItem（Beta）
reply_item = on_fullmatch("myri", priority=5, block=True)


@reply_item.handle()
async def _reply_item(event, matcher: Matcher) -> None:
    token = await resolve_token(matcher, str(event.user_id))
    if token is None:
        return
    item = await to_thread(ReplyItem.get, token)
    await matcher.finish(str(item))
