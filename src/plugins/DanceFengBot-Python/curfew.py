"""宵禁时段与全局回复延迟。

两个能力都通过 NoneBot 的全局运行预处理钩子（``run_preprocessor``）实现，
对**所有**已注册的功能生效：

* **宵禁**：处于配置的时段内时，直接静默忽略消息事件——不发送任何回复，
  只写一条日志，便于事后核对；``got`` / ``receive`` 产生的多步会话同样会被拦下；
* **延迟**：每个功能被触发时随机等待 3~4 秒再开始处理（多步会话的后续步骤
  不再重复等待），避免回复过快。

配置位于 ``DcConfig/Curfew.json``，文件缺失时按默认值自动创建；修改后
**无需重启**，下次调用会按文件修改时间自动重新加载：

.. code-block:: json

    {
        "enabled": true,
        "ranges": [
            {"start": "23:00", "end": "07:00"}
        ],
        "delay": {"min": 3.0, "max": 4.0},
        "admin_bypass": true
    }

字段说明：

* ``enabled``：宵禁总开关，``false`` 时不做任何拦截（延迟仍然生效）；
* ``ranges``：宵禁时段列表，``start`` 晚于 ``end`` 表示跨天（如 23:00-07:00），
  可配置多段；
* ``delay``：每条指令开始处理前的随机延迟（秒），``min`` 与 ``max`` 相同则为固定
  延迟，均设为 0 可关闭延迟；
* ``admin_bypass``：``true`` 时管理员（``config.ADMINS`` / ``SUPERUSERS``）
  在宵禁时段内仍可正常使用命令。

时间按**运行机器的本地时区**判断。
"""

from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time

from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import MessageEvent
from nonebot.exception import IgnoredException
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor

from .config import CONFIG_PATH
from .deps import is_admin_user
from .utils import logger

# 配置文件位置：与其它 DcConfig 配置放在同一目录
CONFIG_FILE = CONFIG_PATH / "Curfew.json"

# 默认配置：23:00-07:00 不回复，其它时间每条指令延迟 3~4 秒
DEFAULT_RANGES: tuple[tuple[str, str], ...] = (("23:00", "07:00"),)
DEFAULT_DELAY: tuple[float, float] = (3.0, 4.0)

# 延迟上限：即使配置写错（例如 3600 秒）也不会让指令卡住过久
_MAX_DELAY_SECONDS = 120.0

# 形如 "23:00"、"7:05"、"23:00:30"，兼容中文冒号
_TIME_RE = re.compile(r"^\s*(\d{1,2})\s*[:：]\s*(\d{1,2})(?:\s*[:：]\s*(\d{1,2}))?\s*$")

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class TimeWindow:
    """一个宵禁时段，支持跨天（``start`` 晚于 ``end``）。"""

    start: dt_time
    end: dt_time

    def contains(self, moment: dt_time) -> bool:
        if self.start < self.end:
            # 普通时段：如 12:00-14:00
            return self.start <= moment < self.end
        # 跨天时段：如 23:00-07:00
        return moment >= self.start or moment < self.end

    def __str__(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M}"


@dataclass(frozen=True)
class CurfewSettings:
    """宵禁与延迟的生效配置。"""

    enabled: bool = True
    windows: tuple[TimeWindow, ...] = field(default_factory=tuple)
    delay_min: float = DEFAULT_DELAY[0]
    delay_max: float = DEFAULT_DELAY[1]
    admin_bypass: bool = True


# 配置缓存：``(文件修改时间, 解析结果)``，文件改动后自动失效
_cache: tuple[float, CurfewSettings] | None = None


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return default


def _as_float(value: object) -> float | None:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if result != result or result in (float("inf"), float("-inf")):
        return None
    return result


def _parse_time(value: object) -> dt_time | None:
    """解析 ``HH:MM`` / ``HH:MM:SS``，非法值返回 ``None``。"""
    match = _TIME_RE.match(str(value))
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    if hour > 23 or minute > 59 or second > 59:
        return None
    return dt_time(hour, minute, second)


def _parse_windows(raw: object) -> tuple[TimeWindow, ...]:
    """解析 ``ranges``，跳过非法条目并提示，避免写错时整段失效而不自知。"""
    if raw is None:
        items: list[object] = [
            {"start": start, "end": end} for start, end in DEFAULT_RANGES
        ]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        logger.warning(f"[宵禁] ranges 配置格式不正确，已忽略：{raw!r}")
        return ()

    windows: list[TimeWindow] = []
    for item in items:
        start: dt_time | None = None
        end: dt_time | None = None
        if isinstance(item, dict):
            start = _parse_time(item.get("start", item.get("from", "")))
            end = _parse_time(item.get("end", item.get("to", "")))
            shown = f"{item.get('start')}-{item.get('end')}"
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            start, end = _parse_time(item[0]), _parse_time(item[1])
            shown = f"{item[0]}-{item[1]}"
        else:
            shown = repr(item)

        if start is None or end is None:
            logger.warning(f"[宵禁] 无法识别的时段，已忽略：{shown}")
            continue
        if start == end:
            # 相同起止时间含义模糊（可能是想整天静音），按无效处理更安全
            logger.warning(f"[宵禁] 时段起止时间相同，已忽略：{shown}")
            continue
        windows.append(TimeWindow(start, end))

    return tuple(windows)


def _parse_delay(raw: object) -> tuple[float, float]:
    """解析 ``delay``，支持 ``{"min": 3, "max": 4}``、``[3, 4]`` 或单个数字。"""
    low: float | None = None
    high: float | None = None
    if isinstance(raw, dict):
        low = _as_float(raw.get("min", raw.get("from")))
        high = _as_float(raw.get("max", raw.get("to")))
    elif isinstance(raw, (int, float)):
        low = high = _as_float(raw)
    elif isinstance(raw, (list, tuple)) and len(raw) == 2:
        low, high = _as_float(raw[0]), _as_float(raw[1])

    if low is None and high is None:
        return DEFAULT_DELAY
    if low is None:
        low = high
    if high is None:
        high = low
    assert low is not None and high is not None
    if low > high:
        low, high = high, low
    return (
        max(0.0, min(low, _MAX_DELAY_SECONDS)),
        max(0.0, min(high, _MAX_DELAY_SECONDS)),
    )


def _default_settings() -> CurfewSettings:
    return CurfewSettings(
        enabled=True,
        windows=_parse_windows(None),
        delay_min=DEFAULT_DELAY[0],
        delay_max=DEFAULT_DELAY[1],
        admin_bypass=True,
    )


def _write_default_config() -> None:
    """首次运行时生成默认配置，方便直接修改。"""
    payload = {
        "_说明": (
            "宵禁时段配置：ranges 内的时段不回复任何消息（支持跨天、可配置多段）；"
            "delay 为每条指令开始处理前的随机延迟（秒）；"
            "admin_bypass 为 true 时管理员在宵禁时段仍可使用命令。修改后无需重启。"
        ),
        "enabled": True,
        "ranges": [{"start": start, "end": end} for start, end in DEFAULT_RANGES],
        "delay": {"min": DEFAULT_DELAY[0], "max": DEFAULT_DELAY[1]},
        "admin_bypass": True,
    }
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        CONFIG_FILE.write_text(text, encoding="utf-8")
        logger.info(f"[宵禁] 未找到配置文件，已生成默认配置：{CONFIG_FILE}")
    except OSError as exc:
        logger.warning(f"[宵禁] 默认配置写入失败，本次使用内存默认值：{CONFIG_FILE} | {exc}")


def _load_settings(fallback: CurfewSettings | None = None) -> CurfewSettings:
    """读取配置文件；文件缺失 / 损坏时沿用上一次生效的配置，避免误静音。"""
    if not CONFIG_FILE.is_file():
        # 文件被删除时按默认值重新生成，并回到默认行为
        _write_default_config()
        return _default_settings()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        kept = "沿用上一次生效的配置" if fallback else "本次使用默认配置"
        logger.warning(f"[宵禁] 配置读取失败，{kept}：{CONFIG_FILE} | {exc}")
        return fallback or _default_settings()

    if not isinstance(data, dict):
        kept = "沿用上一次生效的配置" if fallback else "本次使用默认配置"
        logger.warning(f"[宵禁] 配置内容应为 JSON 对象，{kept}：{CONFIG_FILE}")
        return fallback or _default_settings()

    delay_min, delay_max = _parse_delay(data.get("delay"))
    return CurfewSettings(
        enabled=_as_bool(data.get("enabled", True), True),
        windows=_parse_windows(data.get("ranges")),
        delay_min=delay_min,
        delay_max=delay_max,
        admin_bypass=_as_bool(data.get("admin_bypass", True), True),
    )


def current_settings() -> CurfewSettings:
    """读取当前生效配置；文件修改后自动重新加载。"""
    global _cache
    try:
        mtime = CONFIG_FILE.stat().st_mtime
    except OSError:
        mtime = -1.0

    if _cache is not None and _cache[0] == mtime:
        return _cache[1]

    settings = _load_settings(_cache[1] if _cache is not None else None)
    if mtime < 0:
        # 刚生成的默认配置：补读一次修改时间，让后续调用命中缓存
        try:
            mtime = CONFIG_FILE.stat().st_mtime
        except OSError:
            mtime = -1.0
    _cache = (mtime, settings)
    return settings


def active_window(now: datetime | None = None) -> TimeWindow | None:
    """返回当前所处的宵禁时段；不在宵禁时段或未启用时返回 ``None``。"""
    settings = current_settings()
    if not settings.enabled:
        return None
    moment = (now or datetime.now()).time()
    for window in settings.windows:
        if window.contains(moment):
            return window
    return None


def describe() -> str:
    """生成一行生效配置摘要，供启动日志使用。"""
    settings = current_settings()
    if not settings.enabled:
        return "宵禁已关闭"
    if not settings.windows:
        return "宵禁已开启，但未配置有效时段（不会拦截）"

    ranges = "、".join(str(window) for window in settings.windows)
    bypass = "管理员不受限" if settings.admin_bypass else "管理员同样受限"
    return (
        f"宵禁时段 {ranges}（{bypass}），"
        f"每条指令延迟 {settings.delay_min:g}~{settings.delay_max:g} 秒"
    )


@run_preprocessor
async def _apply_curfew_and_delay(matcher: Matcher, event: Event) -> None:
    """全局运行前处理：宵禁时段静默拦截，其余情况按配置延迟。"""
    # 只处理消息事件；加好友请求等其它事件不受宵禁影响
    if not isinstance(event, MessageEvent):
        return

    settings = current_settings()
    user_id = getattr(event, "user_id", 0)

    window = active_window()
    if window is not None:
        if settings.admin_bypass and is_admin_user(user_id):
            logger.debug(f"[宵禁] 管理员 QQ={user_id} 在 {window} 内调用，已放行")
        else:
            logger.info(f"[宵禁] 当前处于 {window}，已静默忽略 QQ={user_id} 的调用")
            # 抛出后 NoneBot 会取消该响应器，不执行任何处理函数、不发送任何消息
            raise IgnoredException("curfew")

    # 多步会话（got / receive）产生的临时响应器不再重复延迟，只延迟功能首次触发
    if matcher.temp:
        return

    low, high = settings.delay_min, settings.delay_max
    if high <= 0:
        return
    delay = random.uniform(low, high) if high > low else low
    logger.debug(f"[延迟] 回复前等待 {delay:.2f} 秒（配置 {low:g}~{high:g} 秒）")
    await asyncio.sleep(delay)
