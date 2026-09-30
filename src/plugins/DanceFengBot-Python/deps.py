"""NoneBot 命令所需的共享依赖与工具。"""

from __future__ import annotations

import asyncio
import base64
import time

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
from .utils import logger

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


class Timer:
    """统计一段业务耗时（毫秒），用于控制台调试输出。"""

    __slots__ = ("_start",)

    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)

    def __str__(self) -> str:
        return f"{self.elapsed_ms}ms"


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
        logger.debug(f"[Token解析] QQ={qq} 未登录，已提示重新登录")
        await matcher.send(no_login)
        return None
    if not await to_thread(token.check_available):
        logger.warning(f"[Token解析] QQ={qq} 的 Token 已失效，已提示重新登录")
        await matcher.send(invalid)
        return None
    logger.debug(f"[Token解析] QQ={qq} 的 Token 可用，userId={token.user_id}")
    return token
