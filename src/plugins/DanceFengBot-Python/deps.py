"""NoneBot 命令所需的共享依赖与工具。"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime
from pathlib import Path

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
from .config import ADMINS, CONFIG_PATH
from .token import Token
from .utils import logger

ON_NO_LOGIN = '好像还没有登录诶(´。＿。｀)\n私信发送"登录"一起来玩吧！'
ON_INVALID = "小枫看到登录身份过期了💦\n重新私信登录恢复吧💦"

# 生成图片的缓存目录：生成完毕后先落盘，再直接发送缓存内的源文件
CACHE_DIR: Path = CONFIG_PATH / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 缓存文件名中的日期格式，形如 ``UserInfoImage_2587037271_20261008.png``
_DATE_FORMAT = "%Y%m%d"


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


def _today_stamp() -> str:
    """当天日期戳（``YYYYMMDD``），用于拼接缓存文件名。"""
    return datetime.now().strftime(_DATE_FORMAT)


def save_generated_image(
    image_bytes: bytes, method: str, qq: str | int, ext: str = "png"
) -> Path:
    """把代码生成的图片保存到 ``DcConfig/cache`` 目录。

    文件名为 ``<操作>_<QQ号>_<日期>.<ext>``，日期格式为 ``YYYYMMDD``，
    例如 ``UserInfoImage_2587037271_20261008.png``。同一天内同一操作的图片
    会覆盖同名文件，避免缓存无限膨胀；每天 0:00 会清空该目录。
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{method}_{qq}_{_today_stamp()}.{ext.lstrip('.')}"
    path.write_bytes(image_bytes)
    logger.debug(f"[图片缓存] 生成图片已保存：{path}")
    return path


def generated_image_segment(
    image_bytes: bytes, method: str, qq: str | int, ext: str = "png"
) -> MessageSegment:
    """把生成的图片存入 ``DcConfig/cache`` 后，以源文件（本地文件路径）形式发送。"""
    path = save_generated_image(image_bytes, method, qq, ext)
    return MessageSegment.image(path.resolve().as_uri())


def clear_cache(keep_current_day: bool = False) -> int:
    """清理 ``DcConfig/cache`` 内的图片缓存，返回删除的文件数。

    ``keep_current_day=True`` 时保留文件名日期为当天的缓存（用于启动时清掉上一次
    运行遗留的图片）；默认清空目录内的全部文件，由每天 0:00 的定时任务调用。
    单个文件删除失败（例如正被其它进程占用）只记录告警，不影响其余文件。
    """
    if not CACHE_DIR.is_dir():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        return 0

    today = _today_stamp()
    removed = 0
    for item in CACHE_DIR.iterdir():
        try:
            if not item.is_file():
                continue
            if keep_current_day and item.stem.endswith(f"_{today}"):
                continue
            item.unlink()
            removed += 1
        except OSError as exc:
            logger.warning(f"[缓存清理] 删除失败：{item} | {exc}")
    logger.info(
        f"[缓存清理] 已清理 {removed} 个缓存图片"
        f"{'（保留当天缓存）' if keep_current_day else ''}：{CACHE_DIR}"
    )
    return removed


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
