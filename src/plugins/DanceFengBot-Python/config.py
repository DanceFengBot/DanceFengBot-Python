"""DanceFengBot 全局配置与路径解析。

对应 Java 端 ``com.DanceFengBot.config.AbstractConfig``：负责解析
``DcConfig`` 目录位置以及 ``ApiKeys.yml`` 中的第三方平台密钥。

启动时会校验 ``DcConfig`` 目录及其必需文件/目录，缺失时直接抛错退出。
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# 机器人管理员（大铃），对应 Java 端 ``PlainTextHandler.adminsSet``。
# 除此之外，NoneBot 的 ``SUPERUSERS`` 配置同样会被视为管理员。
ADMINS: set[int] = {2587037271}


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


# 模块导入即校验，缺失时抛错并终止启动
validate_config()


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
