"""NoneBot 命令所需的共享依赖与工具。"""

from __future__ import annotations

import asyncio
import base64

from nonebot import get_driver
from nonebot.adapters.onebot.v11 import (
    GroupMessageEvent,
    MessageEvent,
    MessageSegment,
    PrivateMessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.rule import Rule

from . import store
from .config import ADMINS
from .token import Token

ON_NO_LOGIN = '好像还没有登录诶(´。＿。｀)\n私信发送"登录"一起来玩吧！'
ON_INVALID = "小枫看到登录身份过期了💦\n重新私信登录恢复吧💦"


async def _is_private(event) -> bool:
    return isinstance(event, PrivateMessageEvent)


async def _is_group(event) -> bool:
    return isinstance(event, GroupMessageEvent)


private_rule = Rule(_is_private)
group_rule = Rule(_is_group)


def is_admin_user(user_id: int) -> bool:
    if user_id in ADMINS:
        return True
    try:
        superusers = get_driver().config.superusers
        return str(user_id) in superusers
    except Exception:
        return False


async def _is_admin(event) -> bool:
    return isinstance(event, MessageEvent) and is_admin_user(event.user_id)


admin_rule = Rule(_is_admin)


async def to_thread(func, *args, **kwargs):
    """在独立线程中运行阻塞调用，避免阻塞事件循环。"""
    return await asyncio.to_thread(func, *args, **kwargs)


def image_segment(png_bytes: bytes) -> MessageSegment:
    """将 PNG 字节封装为 OneBot v11 图片消息段。"""
    return MessageSegment.image(
        "base64://" + base64.b64encode(png_bytes).decode()
    )


async def resolve_token(
    matcher: Matcher,
    qq,
    no_login: str = ON_NO_LOGIN,
    invalid: str = ON_INVALID,
) -> Token | None:
    """按 QQ 号解析可用 Token；不存在或失效时发送提示并返回 ``None``。"""
    token = store.user_tokens_map.get(str(qq))
    if token is None:
        await matcher.send(no_login)
        return None
    if not await to_thread(token.check_available):
        await matcher.send(invalid)
        return None
    return token
