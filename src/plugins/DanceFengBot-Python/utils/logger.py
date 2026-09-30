"""NoneBot 日志工具（控制台输出 + 按日期落盘）。

本模块是插件内部统一的日志出口，同时负责把 **NoneBot 输出的全部日志**
（消息收发、事件分发、适配器、uvicorn、apscheduler、插件调试信息等）按日期
写入 ``./logs`` 目录。

设计要点：

* **尽量不抛异常**：日志本身绝不应该影响业务流程，内部异常一律吞掉
  （日志目录不可写、磁盘满等情况只提示一次，不影响机器人运行）。
* **Rich 标记安全**：NoneBot 的日志 sink 使用 Rich 渲染，消息中的 ``[...]``
  会被当作标记解析（URL 的 IPv6 / 数组下标等都可能命中），因此这里统一转义。
* **可脱敏**：Token、签名、API Key 等敏感字段在打印前会被掩码，避免泄露。
* **按日期落盘**：日志写入 ``<运行目录>/logs/YYYY-MM-DD.log``（UTF-8、按天轮转，
  自动清理 30 天前的旧文件）。目录可通过环境变量 ``DANCEFENG_LOG_DIR`` 指定，
  设为 ``0`` / ``false`` / ``off`` 可关闭文件日志。
* **可关闭插件调试输出**：设置环境变量 ``DANCEFENG_DEBUG=0`` 可关闭插件的调试
  输出（此时控制台仅保留 NoneBot 自身的日志，文件日志仍照常记录全部内容）。
* **保留 NoneBot 原有日志**：NoneBot 的 sink 受 ``LOG_LEVEL``（默认 INFO）过滤，
  DEBUG 级调试信息默认不可见。本模块在**同一条 loguru logger 上追加**一个只放行
  本插件模块的 sink，因此插件调试信息稳定可见，而 NoneBot 自身的消息收发、事件、
  uvicorn 与错误日志照常按 ``LOG_LEVEL`` 输出。
  插件日志由插件 sink 独占输出，不会重复；实现上**绝不调用** ``remove()``，
  否则会连同 NoneBot 的 sink 一起删掉，机器人将失去日志。
  输出级别可用环境变量 ``DANCEFENG_LOG_LEVEL`` 调整（默认 ``DEBUG``，
  设为 ``INFO`` 可只保留请求链接与结果等关键信息）。
* **可独立导入**：NoneBot 不可用时（例如单文件脚本、本地图像测试）自动回退到
  标准库 ``logging``，保证同样的日志依旧能打印到控制台。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# 环境变量开关：设置 DANCEFENG_DEBUG=0 时关闭插件调试输出
_DEBUG_ENV = "DANCEFENG_DEBUG"

# 环境变量：插件控制台日志级别（默认 DEBUG，即全部调试信息）
_LEVEL_ENV = "DANCEFENG_LOG_LEVEL"

# 环境变量：日志文件目录（默认运行目录下的 logs）；设为 0/false/off 关闭文件日志
_LOG_DIR_ENV = "DANCEFENG_LOG_DIR"

# 日志文件名（按日期命名）
_LOG_FILE_FORMAT = "{time:YYYY-MM-DD}.log"

# 日志保留天数
_LOG_RETENTION = "30 days"

# 插件日志在控制台上的名称（不依赖调用栈推断，保证 sink 过滤稳定命中）
PLUGIN_LOG_NAME = "DanceFengBot"

# 本插件日志的 loguru 记录 name 前缀（NoneBot 以插件目录名作为模块名）
_MODULE_PREFIX = "DanceFengBot-Python"

# 插件 sink 的格式：与 NoneBot 默认格式一致，名称取自 ``{name}``
# （本 sink 只接收本插件的记录，因此 {name} 一定是本插件模块，可安全用于过滤与展示）
_CONSOLE_FORMAT = (
    "<g>{time:MM-DD HH:mm:ss}</g> "
    "[<lvl>{level}</lvl>] "
    "<c><u>{name}</u></c> | "
    "{message}"
)

# 文件 sink 的格式：纯文本、不带上色标记，便于检索与长期保存
# （function 取真实的日志调用方；导出函数名 ``_call`` 无信息量，故不展示）
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} "
    "[{level: <8}] "
    "{name} | "
    "{message}"
)

# 敏感查询参数（出现即掩码）
_SENSITIVE_KEYS: tuple[str, ...] = (
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "token",
    "key",
    "secret",
    "password",
    "signature",
)

_MASK = "***"


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


DEBUG_ENABLED: bool = _env_flag(_DEBUG_ENV, True)

# 是否启用按日期落盘的日志文件
FILE_LOG_ENABLED: bool = _env_flag(_LOG_DIR_ENV, True)

# 插件日志对象（NoneBot 环境下替换为 loguru 实例）
_plugin_logger: Any = None

# 内部状态：索引 0 保存插件控制台 sink 的 id，索引 1 保存文件 sink 的 id
_internal_holder: list[Optional[int]] = [None, None]

# 文件 sink 的日志目录（解析后缓存；None 表示未解析或已关闭）
_log_dir_cache: Optional[Path] = None

# 目录创建失败时只提示一次，避免刷屏
_log_dir_warned = False


def resolve_log_dir() -> Optional[Path]:
    """解析日志目录，默认 ``<当前工作目录>/logs``。

    * 环境变量 ``DANCEFENG_LOG_DIR`` 可指定任意目录；
    * 设为 ``0`` / ``false`` / ``off`` 时返回 ``None``（不写文件日志）；
    * 相对路径按当前工作目录解析，与 ``DcConfig`` 的解析方式保持一致。
    """
    if not FILE_LOG_ENABLED:
        return None
    if _log_dir_cache is not None:
        return _log_dir_cache
    raw = (os.environ.get(_LOG_DIR_ENV) or "").strip()
    if raw.lower() in ("0", "false", "no", "off"):
        return None
    path = Path(raw) if raw else Path("./logs")
    try:
        path = path.expanduser().resolve()
    except Exception:  # noqa: BLE001  # 解析失败时退回相对路径
        path = Path("./logs")
    return path


def current_log_file() -> Optional[Path]:
    """返回当前日期对应的日志文件路径（``logs/YYYY-MM-DD.log``）。"""
    log_dir = resolve_log_dir()
    if log_dir is None:
        return None
    return log_dir / f"{datetime.now():%Y-%m-%d}.log"


def _ensure_log_dir(path: Path) -> bool:
    """创建日志目录，失败时给出一次明确提示。"""
    global _log_dir_warned
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as exc:  # noqa: BLE001  # 目录不可写不应影响机器人运行
        if not _log_dir_warned:
            _log_dir_warned = True
            print(
                f"[DanceFengBot] 日志目录不可用，已跳过文件日志：{path} | "
                f"{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        return False


def setup_file_sink() -> Optional[Path]:
    """把所有日志按日期写入 ``./logs/YYYY-MM-DD.log``。

    * 记录**全部**日志（NoneBot 的消息收发、事件、适配器、uvicorn、apscheduler
      以及本插件的调试信息），等级门槛沿用 NoneBot 的 ``LOG_LEVEL``；
    * 按天轮转：文件名为 ``YYYY-MM-DD.log``，每天 0 点自动切换；
    * 自动清理 30 天前的旧日志；UTF-8 编码（Windows 下按 UTF-8 写入，避免中文乱码）。

    幂等；目录不可用或 loguru 不可用时返回 ``None``，不影响机器人运行。
    """
    log_dir = resolve_log_dir()
    if log_dir is None:
        return None
    if _internal_holder[1] is not None:
        return current_log_file()
    if not _ensure_log_dir(log_dir):
        return None

    try:
        from loguru import logger as _loguru_logger
        from nonebot.log import default_filter

        sink_id = _loguru_logger.add(
            log_dir / _LOG_FILE_FORMAT,
            level=0,
            filter=_make_file_filter(default_filter),
            format=_FILE_FORMAT,
            # 按天轮转：每天 0 点开新文件；文件名中的 {time:YYYY-MM-DD} 随之更新
            rotation="00:00",
            retention=_LOG_RETENTION,
            encoding="utf-8",
            # 同步写入：日志量不大，且在受限环境（无命名管道权限）中 enqueue 会直接
            # 失败导致文件为空；同步写入还能保证进程崩溃时日志已经落盘
            enqueue=False,
            backtrace=True,
            diagnose=False,
            colorize=False,
        )
    except Exception as exc:  # noqa: BLE001  # 文件日志失败不应影响启动
        if not _log_dir_warned:
            print(
                f"[DanceFengBot] 文件日志注册失败，已跳过：{type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
        return None

    _internal_holder[1] = sink_id
    return current_log_file()


def _make_file_filter(orig_filter):
    """文件 sink 的过滤条件：沿用 NoneBot 的等级过滤。

    NoneBot 以 ``record["extra"]["nonebot_log_level"]`` 决定等级门槛，采用它的
    ``default_filter`` 可保证文件日志与控制台日志的等级语义完全一致。
    若该过滤条件不可用（NoneBot 内部结构变化），则退化为全部记录。
    """
    if orig_filter is None:
        return None

    def _filter(record: dict) -> bool:
        try:
            return bool(orig_filter(record))
        except Exception:  # noqa: BLE001  # 过滤条件异常时保持放行
            return True

    return _filter


def _resolve_level() -> Any:
    """解析 ``DANCEFENG_LOG_LEVEL``，非法值回退到 ``DEBUG``。"""
    raw = (os.environ.get(_LEVEL_ENV) or "DEBUG").strip()
    if not raw:
        return "DEBUG"
    if raw.isdigit():
        # loguru 内置等级：TRACE=5 DEBUG=10 INFO=20 SUCCESS=25 WARNING=30 ERROR=40
        return max(5, min(50, int(raw)))
    return raw.upper()


def _plugin_record_filter(record: dict) -> bool:
    """只放行本插件模块产生的日志。

    以 ``record["name"]``（模块名）为准：NoneBot 的插件模块名就是插件目录名，
    因此本插件内所有模块都以 ``DanceFengBot-Python`` 开头。
    """
    name = str(record.get("name", ""))
    return name.startswith(_MODULE_PREFIX) or name == PLUGIN_LOG_NAME


def _install_plugin_dedup(plugin_sink_id: Optional[int]) -> list[int]:
    """让 NoneBot 原有 sink 忽略本插件日志，交给插件 sink 独占输出。

    只在插件 sink 注册成功时调用。做法是包装其它 sink 现有的 ``filter``：

    * 插件日志（``record["name"]`` 属于本插件）→ 返回 ``False``，由插件 sink 输出，
      这样即使 ``LOG_LEVEL=DEBUG`` 也不会出现两份重复日志；
    * 其余所有记录（NoneBot 的消息收发、事件、uvicorn、错误日志等）→ 一律走原有
      ``filter``，等级语义完全保留，行为与未装本插件时一致。

    返回已被包装的 sink id 列表。若无法识别出可包装的 sink，则跳过
    （宁可少一层去重，也不破坏 NoneBot 的日志）。
    """
    from loguru import logger as _loguru_logger

    wrapped: list[int] = []
    for sink_id, handler in list(_loguru_logger._core.handlers.items()):
        # 排除插件自己的控制台 sink 与文件 sink。注意 loguru 的 Handler 重载了
        # __eq__（按 id 比较），不能用 ``handler in [...]`` 判断，必须按 sink id 判断
        if sink_id in (
            plugin_sink_id,
            _internal_holder[1],
        ):
            continue
        sink_obj = getattr(handler, "_sink", None)
        # 文件 sink 必须保留全部日志（包括插件日志），跳过；它写的是文件而非控制台
        if hasattr(sink_obj, "_file_path"):
            continue
        # 指向同一控制台输出对象的 sink 也要跳过，否则会连插件日志一起屏蔽
        if sink_obj is sys.stdout:
            continue
        original = handler._filter
        if getattr(original, "_dancefeng_wrapped", False):
            continue

        def _make_wrapped(orig):
            def _wrapped(record: dict) -> bool:
                if _plugin_record_filter(record):
                    return False
                if orig is None:
                    return True
                try:
                    return bool(orig(record))
                except Exception:  # noqa: BLE001  # 原 filter 异常时保持放行
                    return True

            _wrapped._dancefeng_wrapped = True  # type: ignore[attr-defined]
            return _wrapped

        try:
            handler._filter = _make_wrapped(original)
        except Exception:  # noqa: BLE001  # loguru 内部结构变化时放弃去重
            continue
        wrapped.append(sink_id)
    return wrapped


def _stdout_supports_color() -> bool:
    """仅在真实终端上启用 ANSI 颜色，重定向到文件时不写入转义序列。"""
    try:
        return bool(sys.stdout.isatty())
    except Exception:  # noqa: BLE001  # 某些包装过的 stdout 没有 isatty
        return False


def setup_console_sink() -> Optional[int]:
    """为插件调试信息追加一个控制台 sink，**保留 NoneBot 原有日志**。

    NoneBot 的 sink 受 ``config.log_level``（默认 INFO）过滤，DEBUG 级调试信息
    默认不可见。这里在同一条 loguru logger 上**追加**一个只放行本插件模块的 sink：

    * 插件调试信息（含 DEBUG）稳定可见；
    * NoneBot 自身的消息收发、事件、uvicorn、错误日志照常按 ``LOG_LEVEL`` 输出；
    * 插件日志由插件 sink 独占输出（见 :func:`_install_plugin_dedup`），不重复打印；
    * 绝不调用 ``remove()``，否则会删掉 NoneBot 已有的 sink，导致机器人失去日志。

    幂等：重复调用只注册一次；非 NoneBot 环境（loguru 不可用）返回 ``None``。
    ``DANCEFENG_DEBUG=0`` 时不追加任何内容，仅保留 NoneBot 原有日志。
    """
    global _plugin_logger
    if _internal_holder[0] is not None:
        return _internal_holder[0]
    if not DEBUG_ENABLED:
        return None
    try:
        from loguru import logger as _loguru_logger

        sink_id = _loguru_logger.add(
            sys.stdout,
            level=_resolve_level(),
            filter=_plugin_record_filter,
            format=_CONSOLE_FORMAT,
            colorize=_stdout_supports_color(),
            diagnose=False,
            enqueue=False,
        )
    except Exception:  # noqa: BLE001  # 日志配置失败不应影响启动
        return None

    _internal_holder[0] = sink_id
    # 复用同一条 loguru logger（NoneBot 的 sink 与插件 sink 并存）
    _plugin_logger = _loguru_logger
    try:
        _install_plugin_dedup(sink_id)
    except Exception:  # noqa: BLE001  # 去重失败不影响日志可用性
        pass
    return sink_id


def setup_logging() -> dict[str, Any]:
    """统一初始化：按日期落盘的日志文件 + 插件调试控制台输出。

    先注册文件 sink（记录全部日志），再注册控制台插件 sink 并做控制台去重，
    顺序保证去重时不会误伤文件 sink。返回一份便于排查的状态摘要。
    """
    file_path = None
    try:
        file_path = setup_file_sink()
    except Exception:  # noqa: BLE001  # 文件日志失败不影响控制台日志
        file_path = None
    console_sink = None
    try:
        console_sink = setup_console_sink()
    except Exception:  # noqa: BLE001
        console_sink = None
    return {
        "file_log": file_path,
        "file_sink": _internal_holder[1],
        "console_sink": console_sink,
        "log_dir": resolve_log_dir(),
    }


def escape(text: Any) -> str:
    """转义 Rich 标记，避免日志消息被 NoneBot 的渲染器解析。"""
    return str(text).replace("[", r"\[")


def redact(value: Any) -> str:
    """掩码敏感文本：保留前 6 位与后 4 位，便于比对是否换了 Token。"""
    text = "" if value is None else str(value)
    if not text:
        return ""
    if text.lower().startswith("bearer "):
        return "bearer " + redact(text[7:])
    if len(text) <= 12:
        return _MASK
    return f"{text[:6]}...{text[-4:]}(len={len(text)})"


def redact_mapping(data: Any) -> dict[str, Any]:
    """把字典中的敏感键替换为掩码，用于安全打印表单 / JSON 参数。"""
    if not isinstance(data, dict):
        return {}
    result: dict[str, Any] = {}
    for key, value in data.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            result[key] = redact(value)
        else:
            result[key] = value
    return result


def _safe(func):
    """把日志调用包成“永不抛异常”，调试信息失败不影响业务。"""

    def wrapper(*args, **kwargs):
        if not DEBUG_ENABLED:
            return None
        try:
            return func(*args, **kwargs)
        except Exception:  # noqa: BLE001  # 日志失败必须被忽略
            return None

    return wrapper


class _FallbackLogger:
    """NoneBot 不可用时的标准库日志实现，输出格式与 NoneBot 保持一致。"""

    def __init__(self, name: str) -> None:
        import logging

        self._logger = logging.getLogger(name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-7s | DanceFengBot | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
            self._logger.addHandler(handler)
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(escape(message))

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.info(escape(message))

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(escape(message))

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.error(escape(message))

    def exception(self, message: str, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(escape(message))


try:  # pragma: no cover - 依赖运行环境
    from nonebot.log import logger as _base_logger  # noqa: F401  # 仅用于探测环境
except Exception:  # noqa: BLE001  # 非 NoneBot 环境（单文件脚本 / 本地测试）
    _base_logger: Any = _FallbackLogger("DanceFengBot")


# 注意：这里**不使用** ``opt(depth=...)`` 修正归属。
# loguru 会按深度沿调用栈推断 ``record["name"]``，插件内部还有一层封装函数，
# 深度一旦算错就会把日志归到调用方模块（如 ``__main__``、``commands.misc``），
# 使插件 sink 的过滤条件失配、调试信息整体丢失。因此本模块约定：
#   * 归属判定统一按真实模块名 ``record["name"]``（见 _plugin_record_filter），
#     不依赖调用栈深度，行为稳定可预期；


class _ScopedLogger:
    """统一的插件日志出口，转发到 loguru（NoneBot 环境）或标准库回退实现。"""

    __slots__ = ()

    def __getattr__(self, name: str):
        def _call(message: str, *args: Any):
            target = _plugin_logger if _plugin_logger is not None else _base_logger
            return getattr(target, name.lower())(message, *args)

        return _call


# 插件统一日志出口，NoneBot 环境中即为控制台输出
logger: Any = _ScopedLogger()

# 初始化日志：先登记按日期落盘的日志文件（记录全部日志），
# 再追加插件控制台 sink（幂等；NoneBot 默认 LOG_LEVEL=INFO 时也能看到调试信息）
setup_logging()


@_safe
def debug(message: str, *args: Any) -> None:
    logger.debug(escape(message), *args)


@_safe
def info(message: str, *args: Any) -> None:
    logger.info(escape(message), *args)


@_safe
def warning(message: str, *args: Any) -> None:
    logger.warning(escape(message), *args)


@_safe
def error(message: str, *args: Any) -> None:
    logger.error(escape(message), *args)


@_safe
def exception(message: str, *args: Any) -> None:
    logger.exception(escape(message), *args)


@_safe
def log_http_request(method: str, url: str, context: str = "") -> None:
    """打印 HTTP 请求链接（含被掩码的敏感参数）。"""
    label = f"[{context}] " if context else ""
    logger.info(f"→ HTTP {label}{method} {url}")


@_safe
def log_http_response(
    method: str,
    url: str,
    status: int | None,
    elapsed_ms: int | None = None,
    length: int | None = None,
    context: str = "",
) -> None:
    """打印 HTTP 请求结果：状态码、耗时与响应体大小。"""
    label = f"[{context}] " if context else ""
    detail = [f"状态码 {status}" if status is not None else "状态码 -"]
    if elapsed_ms is not None:
        detail.append(f"耗时 {elapsed_ms}ms")
    if length is not None:
        detail.append(f"响应体 {length} 字节")
    logger.info(f"← HTTP {label}{method} {url} | " + " | ".join(detail))


@_safe
def log_http_error(
    method: str,
    url: str,
    message: str,
    elapsed_ms: int | None = None,
    context: str = "",
) -> None:
    """打印 HTTP 请求失败详情（超时 / 连接失败 / 其它异常）。"""
    label = f"[{context}] " if context else ""
    suffix = f" (耗时 {elapsed_ms}ms)" if elapsed_ms is not None else ""
    logger.error(f"✗ HTTP {label}{method} {url} | 请求失败：{message}{suffix}")


@_safe
def log_step(context: str, message: str) -> None:
    """打印业务步骤调试信息。"""
    label = f"[{context}] " if context else ""
    logger.debug(f"{label}{message}")
