"""账户信息，对应 Java 端 ``com.DanceCube.info.AccountInfo``。"""

from __future__ import annotations

from ..token import Token
from ..utils.http import http_get

_URL = "https://dancedemo.shenghuayule.com/Dance/api/User/GetAccountInfo"


class AccountInfo:
    def __init__(self) -> None:
        self.user_id = 0
        self.gold = 0

    @staticmethod
    def get(token: Token) -> "AccountInfo":
        resp = http_get(
            f"{_URL}?userId={token.user_id}",
            headers={"Authorization": token.bearer_token},
        )
        info = AccountInfo()
        if resp is None:
            return info
        try:
            data = resp.json()
        except Exception:
            return info
        info.user_id = data.get("UserID", data.get("userID", 0))
        info.gold = data.get("Gold", data.get("gold", 0))
        return info

    def __repr__(self) -> str:
        return f"AccountInfo(userID={self.user_id}, gold={self.gold})"
