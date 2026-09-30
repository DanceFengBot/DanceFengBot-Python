"""DanceFengBot — 舞立方 QQ 机器人（NoneBot2 + OneBot V11）。

对应 Java 版 DanceFengBot 的入口：负责加载 Token、定时刷新 Token，
并注册所有命令事件响应器。
"""

from __future__ import annotations

import time

from nonebot import get_driver, on_request
from nonebot.adapters.onebot.v11 import Bot, FriendRequestEvent

from . import store
from .commands import login, info_ratio, misc  # noqa: F401  # 注册命令
from .utils import logger

# 黑名单 / 白名单：导入即加载配置文件并注册全局拦截器
# from . import access_list as _access_list  # noqa: E402  # 需在日志初始化之后导入

driver = get_driver()

# 记录插件加载起点，用于在启动完成时报告启动耗时
_PLUGIN_LOAD_START = time.perf_counter()
_STARTED = False


def _format_address(host: str, port: int) -> str:
    """格式化监听地址（IPv6 需要加方括号）。"""
    host = str(host or "127.0.0.1")
    shown = f"[{host}]" if ":" in host else host
    return f"{shown}:{port}"


def _describe_connect_paths() -> list[str]:
    """从驱动的 ASGI 应用路由中找出 WebSocket 连接路径。"""
    paths: list[str] = []
    try:
        app = getattr(driver, "server_app", None)
        for route in getattr(app, "routes", []):
            path = getattr(route, "path", "")
            if isinstance(path, str) and path.endswith("/ws"):
                paths.append(path)
    except Exception:  # noqa: BLE001  # 探测失败不影响启动
        return []
    return paths


def _log_startup_ready() -> None:
    """打印“已开始监听”的明确信息。

    NoneBot 使用 loguru，而 uvicorn 自身的日志经 ``LoguruHandler`` 转发时受限，
    控制台里通常看不到 "Uvicorn running on ..." 这类提示，容易误判为启动卡死。
    这里在启动钩子结束时给出可核对的信息：监听地址、WS 路径与启动耗时。
    """
    host = getattr(driver.config, "host", None) or "127.0.0.1"
    port = getattr(driver.config, "port", None) or 0
    address = _format_address(host, port)
    elapsed = time.perf_counter() - _PLUGIN_LOAD_START

    lines = [
        "=" * 50,
        " DanceFengBot 启动完成，服务已开始监听",
        f"   监听地址：{address}（启动耗时 {elapsed:.2f}s）",
    ]
    paths = _describe_connect_paths()
    if paths:
        lines.append(f"   OneBot 连接路径：{'、'.join(paths)}")
        lines.append(f"   例：ws://{address}{paths[0]}")
    lines.append("   若此处长时间无后续日志：说明服务已在跑，等待 OneBot 端连接即可")
    lines.append("=" * 50)
    for line in lines:
        logger.info(line)


# ---------------------------------------------------------------- Token 刷新任务
def refresh_all_tokens() -> None:
    """刷新全部 Token 并落盘（对应 Java 端 RefreshTokenJob）。"""
    total = len(store.user_tokens_map)
    logger.info(f"[定时任务] 开始刷新全部 Token，共 {total} 条")
    valid = 0
    for qq, token in list(store.user_tokens_map.items()):
        try:
            if token.refresh():
                valid += 1
            else:
                logger.warning(f"[定时任务] QQ={qq} 的 Token 刷新失败")
        except Exception:  # noqa: BLE001
            logger.exception(f"[定时任务] QQ={qq} 刷新 token 异常")
    store.save_tokens()
    logger.info(f"#读取共{total}个token，有效token共{valid}个")


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
        logger.debug("[定时任务] 已注册每日 03:10 的 Token 刷新任务")
    except Exception:  # noqa: BLE001
        logger.warning("nonebot_plugin_apscheduler 不可用，已跳过每日自动刷新 Token")


# ---------------------------------------------------------------- 黑白名单
# def _start_access_list() -> None:
#     """加载黑白名单配置，并在控制台说明当前启用状态。
#
#     两者同时启用属于配置错误，按需求直接报错退出。
#     """
#     # 启动阶段再解析一次：输出格式提示与当前启用状态
#     _access_list.load_all()
#     try:
#         _access_list.validate()
#     except _access_list.AccessListError as exc:
#         logger.error(f"[黑白名单] 配置错误：{exc}")
#         raise SystemExit(1) from exc
#     _access_list.report(prefix="[黑白名单]")


# ---------------------------------------------------------------- 生命周期
@driver.on_startup
async def _on_startup() -> None:
    global _STARTED
    logger.info("[启动] 开始加载本地 Token 文件")
    store.user_tokens_map = store.load_tokens(False)
    logger.info(f"刷新加载成功！共{len(store.user_tokens_map)}条")
    # _start_access_list()
    _log_startup_ready()
    _STARTED = True


@driver.on_shutdown
async def _on_shutdown() -> None:
    logger.info("[关闭] 正在保存 Token")
    n = store.save_tokens()
    logger.info(f"保存成功！共{n}条")
    logger.info("[关闭] 机器人已停止，可以安全退出")


_setup_scheduler()


# ---------------------------------------------------------------- 连接状态提示
# 对应 OneBot 实现（如 go-cqhttp / LLOneBot）连接与断开，便于确认机器人是否真正在线
try:
    from nonebot.internal.driver import Driver as _AnyDriver
except Exception:  # noqa: BLE001  # 内部模块路径变化时退化为不注册连接钩子
    _AnyDriver = None  # type: ignore[assignment]


if _AnyDriver is not None:

    @_AnyDriver.on_bot_connect
    async def _on_bot_connected(bot: Bot) -> None:
        logger.info(
            f"[连接] OneBot 已接入：self_id={bot.self_id}，"
            f"适配器={bot.adapter.get_name()}，现在可以正常收发消息"
        )
        if not _STARTED:
            logger.warning("[连接] 收到 OneBot 连接，但启动流程尚未完成")

    @_AnyDriver.on_bot_disconnect
    async def _on_bot_disconnected(bot: Bot) -> None:
        logger.warning(
            f"[连接] OneBot 已断开：self_id={bot.self_id}，"
            "请确认 OneBot 端进程是否仍在运行"
        )


# ---------------------------------------------------------------- 加好友自动同意
friend_request = on_request(priority=1, block=False)


@friend_request.handle()
async def _friend_request(event: FriendRequestEvent, bot: Bot) -> None:
    # 加好友按私聊处理：只看 users 中的 QQ 号
    # allowed, reason = _access_list.check_target(
    #     group_id=None, user_id=event.user_id, sender_id=event.user_id
    # )
    # if not allowed:
    #     logger.info(f"[加好友] 名单拦截，已忽略 QQ={event.user_id} 的好友请求：{reason}")
    #     return
    logger.info(f"[加好友] 收到 QQ={event.user_id} 的好友请求，自动同意")
    await event.approve(bot)
    try:
        await bot.send_private_msg(
            user_id=event.user_id,
            message="🥰呐~ 现在我们是好朋友啦！\n请发送“help”查看功能哦！",
        )
        logger.debug(f"[加好友] 已向 QQ={event.user_id} 发送欢迎语")
    except Exception:  # noqa: BLE001
        logger.exception("发送加好友欢迎语失败")
