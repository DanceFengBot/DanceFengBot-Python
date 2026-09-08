"""控制台可用指令列表打印。

NoneBot 启动完成后，枚举本插件注册的所有事件响应器（Matcher），
将其触发词整理为可读的指令清单打印到控制台，方便运维确认指令是否正常加载。
"""

from __future__ import annotations

from nonebot import get_plugin_by_module_name
from nonebot.matcher import Matcher
from nonebot.rule import (
    CommandRule,
    EndswithRule,
    FullmatchRule,
    KeywordsRule,
    RegexRule,
    ShellCommandRule,
    StartswithRule,
)


def _call_of(checker) -> object | None:
    """取出 RuleChecker 依赖背后的真实可调用对象。"""
    return getattr(checker, "call", None)


def _extract_triggers(matcher: type[Matcher]) -> list[str]:
    """从事件响应器规则中提取用户可输入的触发词。"""
    triggers: list[str] = []
    for checker in matcher.rule.checkers:
        call = _call_of(checker)
        if isinstance(call, (CommandRule, ShellCommandRule)):
            # cmds 形如 (("手机号登录",), ("验证码登录",))
            for cmd in call.cmds:
                triggers.append(".".join(cmd))
        elif isinstance(call, FullmatchRule):
            triggers.extend(call.msg)
        elif isinstance(call, StartswithRule):
            triggers.extend(f"{prefix}…" for prefix in call.msg)
        elif isinstance(call, EndswithRule):
            triggers.extend(f"…{suffix}" for suffix in call.msg)
        elif isinstance(call, KeywordsRule):
            triggers.extend(call.keywords)
        elif isinstance(call, RegexRule):
            triggers.append(f"正则:{call.regex}")
    return triggers


def collect_commands() -> dict[str, list[str]]:
    """按模块名归类本插件的所有触发词（去重并排序）。"""
    plugin = get_plugin_by_module_name(__name__)
    if plugin is None:
        return {}

    grouped: dict[str, set[str]] = {}
    for matcher in plugin.matcher:
        module = (matcher.module_name or "").rsplit(".", 1)[-1]
        for trigger in _extract_triggers(matcher):
            grouped.setdefault(module, set()).add(trigger)

    return {name: sorted(triggers) for name, triggers in sorted(grouped.items())}


def print_command_list() -> None:
    """把可用指令列表打印到控制台。"""
    grouped = collect_commands()
    if not grouped:
        print("[DanceFengBot] 未收集到任何可用指令")
        return

    width = 50
    lines = ["=" * width, " DanceFengBot 可用指令列表", "=" * width]
    for module, triggers in grouped.items():
        lines.append("")
        lines.append(f"【{module}】")
        lines.extend(f"  · {trigger}" for trigger in triggers)
    lines.append("=" * width)

    for line in lines:
        print(line, flush=True)
