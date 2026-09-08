"""Token 构建器，对应 Java 端 ``com.DanceCube.token.TokenBuilder``。"""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from ..config import CONFIG_PATH
from ..utils.http import http_get, http_post
from .token import Token

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class TokenBuilder:
    """负责二维码登录的 ``client_id`` 管理以及轮询换取 Token。"""

    ids: list[str] = []
    pointer: int = 0

    def __init__(self) -> None:
        if not TokenBuilder.ids:
            TokenBuilder.init_ids()
        self.index = TokenBuilder.pointer
        self.id = self._get_id()

    # ------------------------------------------------------------------ ids
    @classmethod
    def init_ids(cls) -> list[str]:
        path = CONFIG_PATH / "TokenIds.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]", encoding="utf-8")
        try:
            ids = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            ids = []
        if not ids:
            raise RuntimeError("# id缺失，请手动补充 TokenIds.json！")
        cls.ids = list(ids)
        return cls.ids

    @classmethod
    def update_ids(cls) -> list[str]:
        cls.ids = cls.init_ids()
        return cls.ids

    @classmethod
    def get_size(cls) -> int:
        return len(cls.ids)

    @classmethod
    def _get_id(cls) -> str:
        if cls.pointer > cls.get_size() - 1:
            cls.pointer = 0
        idx = cls.pointer
        cls.pointer += 1
        return cls.ids[idx]

    # ------------------------------------------------------------ qrcode url
    def get_qrcode_url(self, id: Optional[str] = None) -> str:
        if id is None:
            id = self.id
        encoded = urllib.parse.quote(id, safe="")
        resp = http_get(f"{_BASE}/api/Common/GetQrCode?id={encoded}")
        if resp is None:
            return ""
        try:
            return resp.json().get("QrcodeUrl", "")
        except Exception:
            # ID 已失效，移除
            try:
                TokenBuilder.ids.remove(id)
            except ValueError:
                pass
            raise RuntimeError(
                f"# ID:{id} 响应解析失败，可能已失效，还剩{self.get_size()}条"
            )

    # -------------------------------------------------------------- get token
    def get_token(self, id: Optional[str] = None) -> Optional[Token]:
        """轮询获取 Token，最多等待 5 分钟（每 4 秒请求一次）。"""
        if id is None:
            id = self.id
        cur_time = int(time.time() * 1000)
        headers = {"content-type": "application/x-www-form-urlencoded"}
        body = {
            "client_type": "qrcode",
            "grant_type": "client_credentials",
            "client_id": id,
        }
        start = time.time()
        wait = time.time()
        while time.time() - start < 300:
            if time.time() - wait < 4:
                time.sleep(0.5)
                continue
            wait = time.time()
            resp = http_post(f"{_BASE}/token", headers=headers, data=body)
            if resp is not None and resp.status_code == 200:
                try:
                    data = resp.json()
                    return Token(
                        user_id=data.get("userId", 0),
                        access_token=data.get("access_token"),
                        refresh_token=data.get("refresh_token"),
                        rec_time=cur_time,
                    )
                except Exception:
                    return None
        return None

    # ------------------------------------------------------------- file io
    @staticmethod
    def tokens_to_file(token_map: dict[str, Token], file_path: Path | str) -> None:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in token_map.items()}
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def tokens_from_file(
        file_path: Path | str, refreshing: bool = False
    ) -> dict[str, Token]:
        path = Path(file_path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
        result: dict[str, Token] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            token = Token.from_dict(value)
            if refreshing:
                token.refresh()
            result[str(key)] = token
        return result
