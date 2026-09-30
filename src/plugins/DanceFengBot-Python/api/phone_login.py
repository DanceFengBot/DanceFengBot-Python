"""手机号登录，对应 Java 端 ``com.DanceCube.api.PhoneLoginBuilder``。"""

from __future__ import annotations

import base64
import time

from ..token import Token
from ..utils import logger
from ..utils.http import http_get, http_post

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class PhoneLoginBuilder:
    def __init__(self, phone_number: str) -> None:
        self.phone_number = phone_number

    def get_graph_code(self) -> bytes | None:
        """获取图形验证码图片，返回 PNG 字节。"""
        logger.debug(f"[手机号登录] 获取图形验证码：phone={self.phone_number}")
        resp = http_get(
            f"{_BASE}/api/Common/GetGraphCode?phone={self.phone_number}",
            context="手机号登录-图形验证码",
        )
        if resp is None:
            logger.error(f"[手机号登录] 图形验证码请求失败：phone={self.phone_number}")
            return None
        if resp.status_code != 200:
            logger.error(
                f"[手机号登录] 图形验证码状态码 {resp.status_code}："
                f"{resp.text[:200]}"
            )
            return None
        try:
            raw = resp.text.strip().strip('"')
            data = base64.b64decode(raw)
            logger.debug(f"[手机号登录] 图形验证码获取成功，{len(data)} 字节")
            return data
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[手机号登录] 图形验证码解码失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            return None

    def get_sms_code(self, graph_code: str) -> bool:
        """通过图形验证码发送短信验证码。"""
        logger.debug(f"[手机号登录] 请求短信验证码：phone={self.phone_number}")
        resp = http_get(
            f"{_BASE}/api/Common/GetSMSCode?phone={self.phone_number}"
            f"&graphCode={graph_code}",
            context="手机号登录-短信验证码",
        )
        if resp is None:
            logger.error(f"[手机号登录] 短信验证码请求失败：phone={self.phone_number}")
            return False
        if resp.status_code != 200:
            logger.error(
                f"[手机号登录] 短信验证码失败，状态码 {resp.status_code}："
                f"{resp.text[:200]}"
            )
            return False
        logger.info(f"[手机号登录] 短信验证码已发送：phone={self.phone_number}")
        return True

    def login(self, sms_code: str) -> Token | None:
        """手机号登录，返回 Token。"""
        logger.debug(f"[手机号登录] 使用短信验证码登录：phone={self.phone_number}")
        resp = http_post(
            f"{_BASE}/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={
                "client_type": "phone",
                "grant_type": "client_credentials",
                "client_id": self.phone_number,
                "client_secret": sms_code,
            },
            context="手机号登录-换取Token",
        )
        if resp is None:
            logger.error(f"[手机号登录] 登录请求失败：phone={self.phone_number}")
            return None
        if resp.status_code != 200:
            logger.error(
                f"[手机号登录] 登录失败，状态码 {resp.status_code}：{resp.text[:200]}"
            )
            return None
        try:
            data = resp.json()
            token = Token(
                user_id=data.get("userId", 0),
                access_token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                rec_time=int(time.time() * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"[手机号登录] Token 响应解析失败：{exc}；"
                f"内容（前 200 字符）：{resp.text[:200]}"
            )
            return None
        logger.info(f"[手机号登录] 登录成功，userId={token.user_id}")
        return token
