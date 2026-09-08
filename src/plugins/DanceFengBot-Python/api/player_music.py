"""玩家音乐相关接口，对应 Java 端 ``com.DanceCube.api.PlayerMusic``。"""

from __future__ import annotations

from ..token import Token
from ..utils.http import http_post


def gain_music_by_code(token: Token, code: str):
    """兑换自制谱兑换码。"""
    return http_post(
        f"https://dancedemo.shenghuayule.com/Dance/api/MusicData/GainMusicByCode"
        f"?code={code}",
        headers={"Authorization": token.bearer_token},
        data="",
    )
