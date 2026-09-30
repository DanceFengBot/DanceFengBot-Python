"""玩家音乐相关接口，对应 Java 端 ``com.DanceCube.api.PlayerMusic``。"""

from __future__ import annotations

from ..token import Token
from ..utils import logger
from ..utils.http import http_post


def gain_music_by_code(token: Token, code: str):
    """兑换自制谱兑换码。"""
    logger.debug(f"[兑换码] 尝试兑换：code={code}，userId={token.user_id}")
    resp = http_post(
        f"https://dancedemo.shenghuayule.com/Dance/api/MusicData/GainMusicByCode"
        f"?code={code}",
        headers={"Authorization": token.bearer_token},
        data="",
        context="兑换码",
    )
    if resp is None:
        logger.error(f"[兑换码] 请求失败：code={code}")
    elif resp.status_code != 200:
        logger.error(
            f"[兑换码] 兑换失败，状态码 {resp.status_code}：{resp.text[:200]}"
        )
    else:
        logger.info(f"[兑换码] 兑换成功：code={code}")
    return resp
