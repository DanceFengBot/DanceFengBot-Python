"""服务器状态查询命令（``#status``）。"""

from __future__ import annotations

from nonebot import on_command
from nonebot.matcher import Matcher

from ..deps import admin_rule, to_thread
from ..info.server_status import collect_status
from ..utils import logger

server_status = on_command(
    "#status",
    aliases={"服务器状态"},
    rule=admin_rule,
    priority=4,
    block=True,
)


@server_status.handle()
async def _server_status(matcher: Matcher) -> None:
    logger.info("[服务器状态] 收到 #status 请求")
    status = await to_thread(collect_status)
    logger.debug(
        f"[服务器状态] 采集完成：CPU={status.cpu_percent} "
        f"内存={status.memory_used}/{status.memory_total} "
        f"运行时长={status.uptime_seconds:.0f}s"
    )
    await matcher.finish(status.format())
