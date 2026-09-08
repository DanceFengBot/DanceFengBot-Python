"""舞立方登录鉴权 Token，对应 Java 端 ``com.DanceCube.token.Token``。"""

from __future__ import annotations

import time
from typing import Any, Optional

from ..utils.http import http_get, http_post

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class Token:
    """用户登录令牌，用于账号操作时的身份识别和验证。"""

    def __init__(
        self,
        user_id: int = 0,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        rec_time: int = 0,
        available: bool = True,
    ) -> None:
        self.user_id = user_id
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.available = available
        self.rec_time = rec_time

    @property
    def bearer_token(self) -> str:
        return "bearer " + (self.access_token or "")

    def check_available(self) -> bool:
        """通过查看账户未读消息检测 Token 是否可用。"""
        resp = http_get(
            f"{_BASE}/api/Message/GetUnreadCount",
            headers={"Authorization": self.bearer_token},
        )
        self.available = resp is not None and resp.status_code == 200
        return not (
            not self.available or self.access_token is None or self.refresh_token is None
        )

    def refresh(self) -> bool:
        """刷新 Token，成功返回 ``True``。"""
        if not self.available:
            return False
        resp = http_post(
            f"{_BASE}/token",
            headers={"content-type": "application/x-www-form-urlencoded"},
            data={
                "client_type": "qrcode",
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token or "",
            },
        )
        if resp is None:
            return False
        if resp.status_code != 200:
            self.available = False
            return False
        try:
            data = resp.json()
        except Exception:
            return False
        self.access_token = data.get("access_token")
        self.refresh_token = data.get("refresh_token")
        self.rec_time = int(time.time() * 1000)
        return True

    def force_accessible(self) -> None:
        self.available = True

    def to_dict(self) -> dict[str, Any]:
        """序列化为与原 Gson 输出一致的 JSON 结构。"""
        return {
            "userId": self.user_id,
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token,
            "available": self.available,
            "recTime": self.rec_time,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Token":
        """从原 JSON 结构反序列化。"""
        return cls(
            user_id=d.get("userId", 0),
            access_token=d.get("accessToken"),
            refresh_token=d.get("refreshToken"),
            rec_time=d.get("recTime", 0),
            available=d.get("available", True),
        )

    def __str__(self) -> str:
        days = (time.time() * 1000 - self.rec_time) / 86_400_000
        return (
            "{\n"
            f'    "userId"="{self.user_id}",\n'
            f'    "accessToken"="{self.access_token}",\n'
            f'    "refreshToken"="{self.refresh_token}",\n'
            f'    "recTime"={self.rec_time}\n'
            f'    "desc"="当前token时长为{days:.3f}天。Token拥有账号的所有控制权，'
            '请务必保管好token以免泄露，你可以发送"退出登录"来删除当前会话token"\n'
            "}"
        )
