"""全局内存状态：用户 Token 与登录状态。

对应 Java 端 ``com.DanceFengBot.config.AbstractConfig`` 中的
``userTokensMap`` 与 ``logStatus``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import CONFIG_PATH
from .token import Token, TokenBuilder
from .utils import logger

# QQ 号（字符串） -> Token，与 Java 端 HashMap<Long, Token> 一致（键为 QQ 号）
user_tokens_map: dict[str, Token] = {}

# 正在登录流程中的 QQ 号
log_status: set[str] = set()

USER_TOKENS_FILE: Path = CONFIG_PATH / "UserTokens.json"


def load_tokens(refresh: bool = False) -> dict[str, Token]:
    """从磁盘加载 Token，可选择同时刷新。"""
    logger.debug(
        f"[Token存储] 从 {USER_TOKENS_FILE} 加载 Token（refresh={refresh}）"
    )
    tokens = TokenBuilder.tokens_from_file(USER_TOKENS_FILE, refreshing=refresh)
    logger.info(f"[Token存储] 加载完成，共 {len(tokens)} 条")
    return tokens


def save_tokens() -> int:
    """保存 Token 到磁盘，返回条数。"""
    TokenBuilder.tokens_to_file(user_tokens_map, USER_TOKENS_FILE)
    logger.debug(f"[Token存储] 已写入 {USER_TOKENS_FILE}，共 {len(user_tokens_map)} 条")
    return len(user_tokens_map)


def get_token(qq: str | int) -> Optional[Token]:
    """按 QQ 号取 Token。"""
    return user_tokens_map.get(str(qq))
