"""手机号登录，对应 Java 端 ``com.DanceCube.api.PhoneLoginBuilder``。"""

from __future__ import annotations

import base64
import time

from ..token import Token
from ..utils.http import http_get, http_post

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class PhoneLoginBuilder:
    def __init__(self, phone_number: str) -> None:
        self.phone_number = phone_number

    def get_graph_code(self) -> bytes | None:
        """获取图形验证码图片，返回 PNG 字节。"""
        resp = http_get(f"{_BASE}/api/Common/GetGraphCode?phone={self.phone_number}")
        if resp is None or resp.status_code != 200:
            return None
        try:
            raw = resp.text.strip().strip('"')
            return base64.b64decode(raw)
        except Exception:
            return None

    def get_sms_code(self, graph_code: str) -> bool:
        """通过图形验证码发送短信验证码。"""
        resp = http_get(
            f"{_BASE}/api/Common/GetSMSCode?phone={self.phone_number}"
            f"&graphCode={graph_code}"
        )
        return resp is not None and resp.status_code == 200

    def login(self, sms_code: str) -> Token | None:
        """手机号登录，返回 Token。"""
        resp = http_post(
            f"{_BASE}/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={
                "client_type": "phone",
                "grant_type": "client_credentials",
                "client_id": self.phone_number,
                "client_secret": sms_code,
            },
        )
        if resp is None or resp.status_code != 200:
            return None
        try:
            data = resp.json()
            return Token(
                user_id=data.get("userId", 0),
                access_token=data.get("access_token"),
                refresh_token=data.get("refresh_token"),
                rec_time=int(time.time() * 1000),
            )
        except Exception:
            return None
