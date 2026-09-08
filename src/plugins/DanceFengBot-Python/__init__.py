"""DanceFengBot — 舞立方 QQ 机器人（NoneBot2 + OneBot V11）。

对应 Java 版 DanceFengBot 的入口：负责加载 Token、定时刷新 Token，
并注册所有命令事件响应器。
"""

from __future__ import annotations

from nonebot import get_driver, on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent
from nonebot.log import logger

from . import store
from .command_list import print_command_list
from .commands import login, info_ratio, misc  # noqa: F401  # 注册命令

driver = get_driver()


# ---------------------------------------------------------------- Token 刷新任务
def refresh_all_tokens() -> None:
    """刷新全部 Token 并落盘（对应 Java 端 RefreshTokenJob）。"""
    valid = 0
    for token in list(store.user_tokens_map.values()):
        try:
            if token.refresh():
                valid += 1
        except Exception:  # noqa: BLE001
            logger.exception("刷新 token 失败")
    store.save_tokens()
    logger.info(f"#读取共{len(store.user_tokens_map)}个token，有效token共{valid}个")


def _setup_scheduler() -> None:
    """使用 nonebot-plugin-apscheduler 注册每日 Token 刷新任务。"""
    try:
        from nonebot import require

        require("nonebot_plugin_apscheduler")
        from nonebot_plugin_apscheduler import scheduler

        scheduler.add_job(
            refresh_all_tokens,
            "cron",
            hour=3,
            minute=10,
            id="dance_feng_bot_refresh_tokens",
            replace_existing=True,
        )
    except Exception:  # noqa: BLE001
        logger.warning("nonebot_plugin_apscheduler 不可用，已跳过每日自动刷新 Token")


# ---------------------------------------------------------------- 生命周期
@driver.on_startup
async def _on_startup() -> None:
    store.user_tokens_map = store.load_tokens(False)
    logger.info(f"刷新加载成功！共{len(store.user_tokens_map)}条")
    print_command_list()


@driver.on_shutdown
async def _on_shutdown() -> None:
    n = store.save_tokens()
    logger.info(f"保存成功！共{n}条")


_setup_scheduler()


# ---------------------------------------------------------------- 加好友自动同意
friend_request = on_request(priority=1, block=False)


@friend_request.handle()
async def _friend_request(event: FriendRequestEvent, bot: Bot) -> None:
    await event.approve(bot)
    try:
        await bot.send_private_msg(
            user_id=event.user_id,
            message="🥰呐~ 现在我们是好朋友啦！\n请发送“help”查看功能哦！",
        )
    except Exception:  # noqa: BLE001
        logger.exception("发送加好友欢迎语失败")
