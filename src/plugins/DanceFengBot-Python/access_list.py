"""黑名单 / 白名单（准入控制）。

配置文件位于 ``DcConfig`` 目录下：

* ``blacklist.json`` —— 黑名单，命中即拦截；
* ``whitelist.json`` —— 白名单，未命中即拦截。

两个文件均为**标准 JSON**，结构与 ``blacklist.json`` 一致：``enabled`` 为 0/1
开关，``users`` 为 QQ 号数组，``groups`` 为群号数组。例如::

    {
      "enabled": 0,
      "users": [
        10000,
        12345
      ],
      "groups": [

      ]
    }

处理规则：

* 两者**不可同时启用**：同时启用属于配置错误，启动时直接报错退出
  （见 config 模块导入阶段的冲突校验）；
* 两个文件**缺失时在启动阶段自动创建**，默认 ``enabled`` 为 0、两个数组为空；
* 两者都未启用（或文件不存在）时不作任何限制，仅在控制台说明未启用；
* 名单**按会话匹配**：群聊只看 ``groups`` 中的群号，私聊只看 ``users`` 中的 QQ 号；
* 超级管理员（``.env`` 中的 ``SUPERUSERS``）不受任何名单限制；
* 配置文件变更后自动热加载，无需重启。

解析上仍**兼容历史写法**（``"ids"`` 单数组、旧文本格式 ``enabled=0/1`` + 数组），
遇到非标准写法会在控制台提示改用上面的 JSON 结构。

本模块对外提供 :func:`check_target`（判断某条消息是否放行）与 :func:`register`
（注册全局拦截器并把启用状态打印到控制台）。
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Iterable, Optional

from nonebot import get_driver, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    MessageEvent,
    PrivateMessageEvent,
)
from nonebot.matcher import Matcher
from nonebot.rule import Rule

from .config import CONFIG_PATH
from .utils import logger

# 配置文件文件名
BLACKLIST_FILE_NAME = "BlackList.json"
WHITELIST_FILE_NAME = "WhiteList.json"

# 两种模式同时启用的报错文案（含启动阶段兜底检测）
BOTH_ENABLED_ERROR = (
    "黑名单与白名单不可同时启用，请检查配置文件：\n"
    f"  - {CONFIG_PATH / BLACKLIST_FILE_NAME}\n"
    f"  - {CONFIG_PATH / WHITELIST_FILE_NAME}"
)

# 名单类型常量（用于日志与判定分支）
MODE_BLACKLIST = "BlackList"
MODE_WHITELIST = "WhiteList"

# 被拦截时给用户的提示
NOTICE_BLOCKED = "小枫现在不能回复你哦～"
NOTICE_NOT_ALLOWED = "小枫现在不能回复你哦～"

# 文件变更检测的最小间隔（秒），避免每条消息都 stat 磁盘
RELOAD_INTERVAL_SECONDS = 3.0

# 从任意文本中兜底提取整数（仅用于兼容旧格式的容错解析）
_INT_RE = re.compile(r"\d+")

# 旧格式（非标准 JSON）的行首 ``enabled=1`` / ``enabled: 1`` 写法
_ENABLED_LINE_RE = re.compile(r"^\s*enabled\s*[:=]\s*([^\s,}\]]+)", re.IGNORECASE | re.MULTILINE)

# 兼容的历史数组字段名（标准字段为 users / groups）
_ALT_ARRAY_KEYS: tuple[str, ...] = ("ids", "list", "qq", "users", "groups", "data")


class AccessListError(Exception):
    """名单配置错误（例如两者同时启用）。"""


def is_superuser(user_id: int | str) -> bool:
    """判断是否为超级管理员（``.env`` 中的 ``SUPERUSERS``）。

    读取失败时返回 ``False``（宁可拦截，也不误放行）。
    """
    try:
        superusers = get_driver().config.superusers
    except Exception:  # noqa: BLE001  # 未初始化 / 配置缺失时不豁免
        return False
    return str(user_id) in {str(item) for item in superusers}


def _normalize_id(raw: object) -> Optional[str]:
    """把配置项规范化为纯数字字符串；无法解析时返回 ``None``。"""
    text = str(raw).strip().strip('"').strip("'").rstrip(",")
    if not text.isdigit():
        return None
    return str(int(text))


def _parse_enabled_value(value: object) -> Optional[bool]:
    """把 ``enabled`` 字段的值解析为布尔值，无法识别时返回 ``None``。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("1", "true", "yes", "on"):
            return True
        if text in ("0", "false", "no", "off", ""):
            return False
    return None


def _normalize_numbers(values: object, path: Path, field: str, quiet: bool) -> set[str]:
    """把数组字段规范化为纯数字字符串集合（非数组按空处理，非法项跳过）。"""
    if values is None:
        return set()
    if not isinstance(values, list):
        if not quiet:
            logger.warning(
                f"[黑白名单] {path.name} 的 {field} 不是数组"
                f"（实际为 {type(values).__name__}），按空处理"
            )
        return set()
    numbers: set[str] = set()
    for item in values:
        normalized = _normalize_id(item)
        if normalized is None:
            if not quiet:
                logger.warning(
                    f"[黑白名单] 忽略无法解析的条目：{item!r}（{path.name} 的 {field}）"
                )
            continue
        numbers.add(normalized)
    return numbers


def _legacy_enabled(text: str) -> Optional[bool]:
    """兼容旧写法：从行首 ``enabled=0/1`` 中解析开关，未找到时返回 ``None``。"""
    match = _ENABLED_LINE_RE.search(text)
    return None if match is None else _parse_enabled_value(match.group(1))


def _strip_legacy_enabled(text: str) -> str:
    """去掉旧写法中的 ``enabled=...`` 行，只留下名单数组。"""
    lines = [line for line in text.splitlines() if not _ENABLED_LINE_RE.match(line)]
    return "\n".join(lines).strip()


def _split_payload(text: str) -> tuple[str, str]:
    """按首个 ``[`` / ``{`` 把文本切成头部与名单主体。"""
    positions = [pos for pos in (text.find("["), text.find("{")) if pos >= 0]
    if not positions:
        return text, ""
    cut = min(positions)
    return text[:cut], text[cut:]


def _legacy_mapping(text: str) -> Optional[dict]:
    """兼容旧写法：把 ``[`` / ``{`` 之后的内容解析成 ``users`` / ``groups``。"""
    payload = _split_payload(_strip_legacy_enabled(text))[1].strip()
    if not payload:
        return {}
    try:
        values = json.loads(payload)
    except json.JSONDecodeError:
        values = None
    if isinstance(values, dict):
        return values
    if isinstance(values, list):
        # 旧写法只有一个数组：QQ 号与群号混在一起，按“两者都匹配”处理
        return {"users": values, "groups": values}
    # 连数组都不是（例如每行一个号码）时兜底提取数字
    return {"users": [int(num) for num in _INT_RE.findall(payload)]}


def parse_config(text: str, path: Path, quiet: bool = False) -> tuple[bool, set[str], set[str]]:
    """解析名单配置，返回 ``(是否启用, QQ 号集合, 群号集合)``。

    标准格式（也是自动生成时写入的格式）::

        {
          "enabled": 0,
          "users": [10000, 12345],
          "groups": [987654321]
        }

    ``quiet=True`` 时抑制格式提示，用于纯粹的内容探测。
    """
    text = text.lstrip("\ufeff").strip()
    if not text:
        return False, set(), set()

    # 1) 标准 JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict):
        # ``enabled`` 既可以写数字 0/1，也可以写 true/false
        enabled = _parse_enabled_value(data.get("enabled", 0))
        if enabled is None:
            if not quiet:
                logger.warning(
                    f"[黑白名单] {path.name} 的 enabled 取值无法识别："
                    f"{data.get('enabled')!r}，已按未启用处理"
                )
            enabled = False

        if "users" in data or "groups" in data:
            users = _normalize_numbers(data.get("users"), path, "users", quiet)
            groups = _normalize_numbers(data.get("groups"), path, "groups", quiet)
            return enabled, users, groups

        # 兼容历史写法：只有一个 ids / list 数组
        for key in _ALT_ARRAY_KEYS:
            if isinstance(data.get(key), list):
                if not quiet:
                    logger.warning(
                        f"[黑白名单] {path.name} 使用了历史字段 {key!r}，"
                        '建议改用标准结构 {"enabled": 0, "users": [], "groups": []}'
                    )
                shared = _normalize_numbers(data[key], path, key, quiet)
                return enabled, shared, shared

        if not quiet:
            logger.warning(
                f"[黑白名单] {path.name} 缺少 users / groups 数组，按空名单处理"
            )
        return enabled, set(), set()

    if isinstance(data, list):
        # 只有一个数组、没有开关：按未启用处理，避免误拦截
        if not quiet:
            logger.warning(f"[黑白名单] {path.name} 缺少 enabled 字段，已按未启用处理")
        shared = _normalize_numbers(data, path, "ids", quiet)
        return False, shared, shared

    # 2) 旧写法：``enabled=0/1`` + 数组
    if not quiet:
        logger.warning(
            f"[黑白名单] {path.name} 不是标准 JSON 格式（已兼容读取），"
            '建议改用：{"enabled": 0, "users": [QQ号], "groups": [群号]}'
        )
    legacy = _legacy_mapping(text) or {}
    users = _normalize_numbers(legacy.get("users"), path, "users", quiet)
    groups = _normalize_numbers(legacy.get("groups"), path, "groups", quiet)
    return (_legacy_enabled(text) or False), users, groups


class AccessList:
    """单个名单（黑名单或白名单）的状态与解析结果。"""

    def __init__(self, path: Path, mode: str, label: str) -> None:
        self.path = path
        self.mode = mode
        self.label = label
        self.enabled = False
        self.users: set[str] = set()
        self.groups: set[str] = set()
        # 文件指纹：(存在, 修改时间, 大小, inode)，用于变更检测
        self.stamp: tuple = ()
        self._checked_at = 0.0

    # ------------------------------------------------------------ 解析
    def reload(self, quiet: bool = False) -> bool:
        """重新读取配置文件，返回名单内容是否发生变化。"""
        previous = self.snapshot()
        self.stamp = self._stat()
        if not self.path.is_file():
            self.enabled, self.users, self.groups = False, set(), set()
            return previous != self.snapshot()

        try:
            text = self.path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001  # 读取失败不应影响机器人运行
            logger.error(f"[黑白名单] 读取 {self.path.name} 失败：{type(exc).__name__}: {exc}")
            self.enabled, self.users, self.groups = False, set(), set()
            return previous != self.snapshot()

        # 未启用时也解析一遍，便于控制台日志如实反映“已配置但未生效”的内容
        self.enabled, self.users, self.groups = parse_config(text, self.path, quiet)
        return previous != self.snapshot()

    def snapshot(self) -> tuple:
        """当前内容快照，用于判断是否发生变化。"""
        return (self.enabled, frozenset(self.users), frozenset(self.groups))

    def _stat(self) -> tuple:
        try:
            info = self.path.stat()
        except OSError:
            return (False,)
        return (True, info.st_mtime_ns, info.st_size, getattr(info, "st_ino", 0))

    def poll(self, now: Optional[float] = None) -> bool:
        """按最小间隔检查文件是否变更，变更则重新加载并返回 ``True``。

        格式类提示只会在 ``poll_files`` 报告状态时输出，避免同一次变更打印重复提示。
        """
        current = time.monotonic() if now is None else now
        if current - self._checked_at < RELOAD_INTERVAL_SECONDS:
            return False
        self._checked_at = current
        if self._stat() == self.stamp:
            return False
        return self.reload(quiet=True)

    # ------------------------------------------------------------ 保存
    def save(self) -> None:
        """按标准 JSON 格式写回配置文件。

        结构参照 ``blacklist.json``：``enabled`` 写 0/1，``users`` / ``groups``
        为号码数组（按大小排序），使用两空格缩进与 UTF-8 编码。文件不存在时
        （启动阶段自动创建）写入默认内容：``enabled`` 为 0、两个数组为空。
        """
        data = {
            "enabled": 1 if self.enabled else 0,
            "users": [int(item) for item in sorted(self.users, key=int)],
            "groups": [int(item) for item in sorted(self.groups, key=int)],
        }
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.stamp = self._stat()

    # ------------------------------------------------------------ 判定
    def id_count(self) -> int:
        return len(self.users) + len(self.groups)

    def all_ids(self) -> Iterable[str]:
        return sorted(self.users | self.groups, key=int)


# 全局单例
blacklist = AccessList(CONFIG_PATH / BLACKLIST_FILE_NAME, MODE_BLACKLIST, "黑名单")
whitelist = AccessList(CONFIG_PATH / WHITELIST_FILE_NAME, MODE_WHITELIST, "白名单")

# 需要自动生成的文件是否已经处理过（避免重复打印“已自动创建”）
_files_ensured = False


def ensure_files() -> list[Path]:
    """启动时确保两个配置文件存在；缺失则按默认内容自动创建。

    默认内容为标准 JSON：``{"enabled": 0, "users": [], "groups": []}``。
    返回本次新建的文件路径列表（已存在时不改动、不覆盖）。
    """
    created: list[Path] = []
    for current in (blacklist, whitelist):
        if current.path.is_file():
            continue
        try:
            current.enabled, current.users, current.groups = False, set(), set()
            current.save()
        except Exception as exc:  # noqa: BLE001  # 创建失败不应影响机器人运行
            logger.error(
                f"[黑白名单] 创建 {current.path.name} 失败：{type(exc).__name__}: {exc}"
            )
            continue
        created.append(current.path)
    return created


def load_all(quiet: bool = False) -> None:
    """启动阶段：确保配置文件存在，再读取两者内容。

    模块导入时静默解析一次，启动钩子中再解析一次并输出格式提示与启用状态。
    """
    global _files_ensured
    if not _files_ensured:
        _files_ensured = True
        for path in ensure_files():
            logger.info(f"[黑白名单] 未找到配置文件，已自动创建（默认 enabled=0）：{path}")
    blacklist.reload(quiet=quiet)
    whitelist.reload(quiet=quiet)


def active_list() -> Optional[AccessList]:
    """返回当前生效的名单；均未启用时返回 ``None``。"""
    if blacklist.enabled and whitelist.enabled:
        raise AccessListError(BOTH_ENABLED_ERROR)
    if blacklist.enabled:
        return blacklist
    if whitelist.enabled:
        return whitelist
    return None


def validate() -> None:
    """校验配置：两者同时启用时抛出 :class:`AccessListError`。"""
    if blacklist.enabled and whitelist.enabled:
        raise AccessListError(BOTH_ENABLED_ERROR)


def check_target(
    group_id: Optional[int],
    user_id: Optional[int],
    sender_id: Optional[int] = None,
) -> tuple[bool, str]:
    """判断一条消息是否放行。

    * 群聊（``group_id`` 不为 ``None``）只看 ``groups`` 中的群号；
    * 私聊只看 ``users`` 中的 QQ 号；
    * ``sender_id`` 为发送者 QQ（群聊时用于超级管理员豁免判断）；
    * 超级管理员一律放行；
    * 均未启用时一律放行。

    返回 ``(是否放行, 拦截原因)``。
    """
    who = sender_id if sender_id is not None else user_id
    if who is not None and is_superuser(who):
        return True, "超级管理员豁免"

    is_group = group_id is not None
    target = group_id if is_group else user_id
    if target is None:
        return True, "无法识别会话对象"

    target = str(target)
    kind = "群号" if is_group else "QQ"

    current = active_list()
    if current is None:
        return True, "未启用名单"

    listed = target in (current.groups if is_group else current.users)
    if current.mode == MODE_BLACKLIST:
        return (not listed), (f"命中黑名单（{kind} {target}）" if listed else "不在黑名单")

    # 白名单：仅名单内放行
    return listed, (f"不在白名单（{kind} {target}）" if not listed else "命中白名单")


def poll_files() -> None:
    """检查两个配置文件是否被修改，变更则热加载并在控制台说明。"""
    for current in (blacklist, whitelist):
        try:
            changed = current.poll()
        except Exception as exc:  # noqa: BLE001  # 热加载失败不影响正常消息
            logger.error(
                f"[黑白名单] 热加载 {current.path.name} 失败：{type(exc).__name__}: {exc}"
            )
            continue
        if not changed:
            continue
        logger.info(f"[黑白名单] 检测到 {current.path.name} 变更，已重新加载")
        try:
            validate()
        except AccessListError as exc:
            # 运行期间的配置冲突不直接杀进程，改为放行所有消息并持续报错提示
            logger.error(f"[黑白名单] 配置错误：{exc}")
            logger.error("[黑白名单] 冲突期间不拦截任何消息，请修正配置文件后重试")
            continue
        report(prefix="[黑白名单] 重新加载后")


# ---------------------------------------------------------------- 控制台输出
def _describe_ids(current: AccessList) -> list[str]:
    """把名单内容整理成便于阅读的文本行。"""
    if current.id_count() == 0:
        return ["   名单条目：共 0 个（当前不会匹配任何会话）"]
    lines = [f"   名单条目：QQ {len(current.users)} 个、群号 {len(current.groups)} 个"]
    for label, values in (("用户QQ", sorted(current.users, key=int)), ("群号", sorted(current.groups, key=int))):
        # 每行最多展示 10 个，避免条目过多刷屏
        for start in range(0, len(values), 10):
            lines.append(f"     {label}：" + "、".join(values[start : start + 10]))
    return lines


def report(prefix: str = "") -> None:
    """把当前启用状态打印到控制台。"""
    head = f"{prefix} " if prefix else ""
    if blacklist.enabled and whitelist.enabled:
        logger.error(f"{head}配置错误：{BOTH_ENABLED_ERROR}")
        return

    current = active_list()
    if current is None:
        logger.info(
            f"{head}黑名单与白名单均未启用，所有消息正常处理"
            f'（如需启用请把 {BLACKLIST_FILE_NAME} / {WHITELIST_FILE_NAME} 中的 "enabled" 改为 1）'
        )
        return

    lines = [
        f"{head}已启用{current.label}（{current.path.name}）",
        "   生效范围：按会话匹配——群聊只看 groups 中的群号，私聊只看 users 中的 QQ 号",
        f"   处理方式：{'命中即拦截' if current.mode == MODE_BLACKLIST else '未命中即拦截'}",
        "   豁免对象：超级管理员（SUPERUSERS）不受限制",
        *_describe_ids(current),
    ]
    if current.id_count() == 0:
        lines.append("   提示：名单为空，本次启动不会拦截任何会话")
    for line in lines:
        logger.info(line)


# ---------------------------------------------------------------- 全局拦截
async def _access_rule(event: MessageEvent) -> bool:
    """NoneBot 规则：放行返回 ``True``，需拦截返回 ``False``。"""
    try:
        poll_files()
        if isinstance(event, GroupMessageEvent):
            # 群聊按群号判定，同时带上发送者 QQ 以便超级管理员豁免
            group_id, user_id = event.group_id, None
        else:
            group_id, user_id = None, event.user_id
        allowed, reason = check_target(
            group_id=group_id, user_id=user_id, sender_id=event.user_id
        )
    except Exception as exc:  # noqa: BLE001  # 名单本身出错时放行，避免机器人整体失效
        logger.error(f"[黑白名单] 判定失败，已放行该消息：{type(exc).__name__}: {exc}")
        return True

    if not allowed:
        target = group_id if group_id is not None else user_id
        logger.info(f"[黑白名单] 已拦截消息：{reason}，会话={target}")
    return allowed


async def _notify_blocked(event: MessageEvent, bot: Bot) -> None:
    """被拦截时给用户一次性提示（发送失败不影响机器人运行）。"""
    try:
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_msg(
                group_id=event.group_id,
                message=f"[CQ:at,qq={event.user_id}] {NOTICE_NOT_ALLOWED}",
            )
        else:
            await bot.send_private_msg(user_id=event.user_id, message=NOTICE_BLOCKED)
    except Exception as exc:  # noqa: BLE001  # 未加好友 / 被禁言等情况下直接忽略
        logger.debug(f"[黑白名单] 发送拦截提示失败：{type(exc).__name__}: {exc}")


def _is_admin_event(event: MessageEvent) -> bool:
    """超级管理员不会被拦截，因此无需发送提示。"""
    return is_superuser(event.user_id)


def register() -> None:
    """注册全局拦截器（在其它命令响应器之前执行）。

    规则判定放在 :func:`_access_rule` 中：名单不允许时规则不成立，
    本响应器以外的其它命令响应器便不会被触发，实现全局静默。
    """
    matcher = on_message(rule=Rule(_access_rule), priority=0, block=True)

    @matcher.handle()
    async def _notify(event: MessageEvent, bot: Bot, matcher: Matcher) -> None:
        # 走到这里说明消息已被名单拦截；超级管理员不会被拦截，无需提示
        if not _is_admin_event(event):
            await _notify_blocked(event, bot)
        await matcher.finish()


# 模块导入即加载配置文件（静默）并注册全局拦截器；
# 两者同时启用属于致命配置错误，由 config 模块在导入阶段报错退出
load_all(quiet=True)
register()
