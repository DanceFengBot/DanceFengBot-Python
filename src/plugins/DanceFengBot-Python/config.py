"""DanceFengBot 全局配置与路径解析。

对应 Java 端 ``com.DanceFengBot.config.AbstractConfig``：负责解析
``DcConfig`` 目录位置以及 ``ApiKeys.yml`` 中的第三方平台密钥。

启动时会校验 ``DcConfig`` 目录及其必需文件/目录，缺失时直接抛错退出；
另外校验黑名单 / 白名单（``blacklist.json`` / ``whitelist.json``）不可同时启用。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import yaml

# 机器人管理员（大铃），对应 Java 端 ``PlainTextHandler.adminsSet``。
# 除此之外，NoneBot 的 ``SUPERUSERS`` 配置同样会被视为管理员。
ADMINS: set[int] = {2587037271}

# 黑名单 / 白名单文件名（标准 JSON：{"enabled": 0/1, "users": [QQ号], "groups": [群号]}）
BLACKLIST_FILE_NAME = "blacklist.json"
WHITELIST_FILE_NAME = "whitelist.json"

# 兼容旧写法：匹配行首 ``enabled=0`` / ``enabled: 1``
_ENABLED_RE = re.compile(r"^enabled\s*[:=]\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

# 真值写法
_TRUE_VALUES = {"1", "true", "yes", "on"}


def resolve_config_path() -> Path:
    """解析 ``DcConfig`` 目录，默认位于项目运行目录（当前工作目录）下。

    可通过环境变量 ``DCF_CONFIG_PATH`` 显式指定其它位置。
    """
    env = os.environ.get("DCF_CONFIG_PATH")
    if env:
        return Path(env).resolve()
    return Path("./DcConfig").resolve()


# 全局配置目录
CONFIG_PATH: Path = resolve_config_path()

# 运行必需的文件与目录（缺失则启动报错并退出）
_REQUIRED_FILES: tuple[str, ...] = (
    "ApiKeys.yml",
    "TokenIds.json",
    "OfficialMusicIds.json",
)
_REQUIRED_DIRS: tuple[str, ...] = (
    "Images",
    "Images/UserRatioImage",
    "Images/UserInfoImage",
    "Fonts",
)


def validate_config() -> None:
    """校验 ``DcConfig`` 目录及其必需文件/目录，缺失时抛出异常退出。"""
    if not CONFIG_PATH.exists():
        raise RuntimeError(
            f"DcConfig 目录不存在：{CONFIG_PATH}\n"
            "请在项目运行目录（当前工作目录）下创建 DcConfig 目录，"
            "或通过环境变量 DCF_CONFIG_PATH 指定其实际位置。"
        )
    if not CONFIG_PATH.is_dir():
        raise RuntimeError(f"DcConfig 路径不是目录：{CONFIG_PATH}")

    missing: list[str] = []
    for rel in _REQUIRED_FILES:
        if not (CONFIG_PATH / rel).is_file():
            missing.append(f"  - 文件 {rel}")
    for rel in _REQUIRED_DIRS:
        if not (CONFIG_PATH / rel).is_dir():
            missing.append(f"  - 目录 {rel}")

    if missing:
        raise RuntimeError(
            f"DcConfig 配置不完整（{CONFIG_PATH}）：\n"
            + "\n".join(missing)
            + "\n请补齐上述文件/目录后重新启动。"
        )


def _read_enabled(path: Path) -> bool:
    """读取名单配置的 ``enabled`` 开关（文件缺失或未声明时视为未启用）。

    标准格式为 JSON 的 ``{"enabled": 0/1, "users": [...], "groups": [...]}``；
    同时兼容历史写法（``"ids"`` 单数组、旧文本格式 ``enabled=0/1`` + 数组），
    避免升级后误判。
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return False

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        value = data.get("enabled", 0)
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return str(value).strip().lower() in _TRUE_VALUES
    if isinstance(data, list):
        # 只有数组、没有开关：按未启用处理
        return False

    match = _ENABLED_RE.search(text)
    if match is None:
        return False
    return match.group(1).strip().strip('",').lower() in _TRUE_VALUES


def check_access_lists() -> None:
    """校验黑名单 / 白名单：两者不可同时启用，同时启用时报错退出。

    ``blacklist.json`` 与 ``whitelist.json`` 中 ``"enabled": 1`` 表示启用。
    两者都启用时属于配置错误：先打印明确错误，再终止进程，避免以含义不明的
    状态继续运行。
    """
    blacklist_enabled = _read_enabled(CONFIG_PATH / BLACKLIST_FILE_NAME)
    whitelist_enabled = _read_enabled(CONFIG_PATH / WHITELIST_FILE_NAME)
    if not (blacklist_enabled and whitelist_enabled):
        return

    print(
        "=" * 50 + "\n"
        "[DanceFengBot] 配置错误：黑名单与白名单不可同时启用\n"
        f"  - {CONFIG_PATH / BLACKLIST_FILE_NAME} （enabled 为 1）\n"
        f"  - {CONFIG_PATH / WHITELIST_FILE_NAME} （enabled 为 1）\n"
        '请把其中一个文件的 "enabled" 改为 0 后重新启动。\n'
        + "=" * 50,
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(1)


# 模块导入即校验，缺失时抛错并终止启动
validate_config()

# 名单冲突属于致命配置错误：导入阶段直接退出（不依赖 NoneBot 的插件导入容错）
check_access_lists()


class _ApiKeys:
    """腾讯 OCR 与高德地图 SDK 密钥，懒加载自 ``ApiKeys.yml``。"""

    def __init__(self) -> None:
        self.gaode_api_key = ""
        self.tencent_secret_id = ""
        self.tencent_secret_key = ""
        self._load()

    def _load(self) -> None:
        yml = CONFIG_PATH / "ApiKeys.yml"
        data: dict = {}
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        except Exception:
            data = {}
        tencent = data.get("tencentScannerKeys") or {}
        gaode = data.get("gaodeMapKeys") or {}
        self.tencent_secret_id = str(tencent.get("secretId") or "")
        self.tencent_secret_key = str(tencent.get("secretKey") or "")
        self.gaode_api_key = str(gaode.get("apiKey") or "")


api_keys = _ApiKeys()
