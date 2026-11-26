"""Token 构建器，对应 Java 端 ``com.DanceCube.token.TokenBuilder``。

舞立方的 ``/api/Common/GetQrCode`` 接口不传 ``id`` 时会自动创建一个二维码会话，
并返回本次会话的 ``ID``。这个 ``ID`` 就是后续 ``/token`` 请求里的 ``client_id``，
因此不再需要手动维护 ``TokenIds.json``。
"""

from __future__ import annotations

import json
import time
import urllib.parse
from pathlib import Path
from typing import Optional

from ..utils import logger
from ..utils.http import http_get, http_post
from .token import Token

_BASE = "https://dancedemo.shenghuayule.com/Dance"


class TokenBuilder:
    """二维码登录：动态获取二维码会话 ID，并轮询换取 Token。"""

    def __init__(self) -> None:
        # 本次二维码会话的 ID（即 /token 的 client_id），由 GetQrCode 返回
        self.id = ""

    # ------------------------------------------------------------ qrcode url
    def get_qrcode_url(self, id: Optional[str] = None) -> str:
        """获取登录二维码。

        不传 ``id`` 时由服务端新建会话；传入 ``id`` 时可复用已有会话。
        """
        url = f"{_BASE}/api/Common/GetQrCode"
        if id:
            url += "?id=" + urllib.parse.quote(id, safe="")
            logger.debug(f"[二维码登录] 复用会话 ID={id} 获取登录二维码")
        else:
            logger.debug("[二维码登录] 不传 client_id，请求服务端新建二维码会话")

        resp = http_get(url, context="二维码登录-获取二维码")
        if resp is None:
            logger.error("[二维码登录] 获取二维码失败：无响应")
            return ""

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"[二维码登录] 二维码响应解析失败：{exc}")
            raise RuntimeError("二维码响应解析失败，请稍后重试") from exc

        if not isinstance(data, dict):
            logger.error("[二维码登录] 二维码响应格式异常")
            raise RuntimeError("二维码响应格式异常，请稍后重试")

        qr_url = str(data.get("QrcodeUrl") or "").strip()
        session_id = str(data.get("ID") or id or "").strip()
        if not qr_url or not session_id:
            logger.error(
                "[二维码登录] 二维码响应缺少 QrcodeUrl/ID："
                f"{str(data)[:200]}"
            )
            raise RuntimeError("二维码响应缺少必要字段，请稍后重试")

        self.id = session_id
        logger.debug(f"[二维码登录] 本次会话 ID={self.id}")
        logger.debug(f"[二维码登录] 二维码链接：{qr_url}")
        return qr_url

    # -------------------------------------------------------------- get token
    def get_token(self, id: Optional[str] = None) -> Optional[Token]:
        """轮询获取 Token，最多等待 5 分钟（每 4 秒请求一次）。"""
        if id is None:
            id = self.id
        if not id:
            logger.error("[二维码登录] 没有可用的二维码会话 ID，请先获取二维码")
            return None

        cur_time = int(time.time() * 1000)
        headers = {"content-type": "application/x-www-form-urlencoded"}
        body = {
            "client_type": "qrcode",
            "grant_type": "client_credentials",
            "client_id": id,
        }
        start = time.time()
        wait = time.time()
        attempts = 0
        logger.info("[二维码登录] 开始轮询扫码结果，最长等待 5 分钟")
        while time.time() - start < 300:
            if time.time() - wait < 4:
                time.sleep(0.5)
                continue
            wait = time.time()
            attempts += 1
            resp = http_post(
                f"{_BASE}/token", headers=headers, data=body, context="二维码登录-换取Token"
            )
            if resp is not None and resp.status_code == 200:
                try:
                    data = resp.json()
                    token = Token(
                        user_id=data.get("userId", 0),
                        access_token=data.get("access_token"),
                        refresh_token=data.get("refresh_token"),
                        rec_time=cur_time,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"[二维码登录] Token 响应解析失败：{exc}")
                    return None
                logger.info(
                    f"[二维码登录] 第 {attempts} 次轮询登录成功，"
                    f"userId={token.user_id}，耗时 {time.time() - start:.1f}s"
                )
                return token
            if resp is not None:
                logger.debug(
                    f"[二维码登录] 第 {attempts} 次轮询未完成，状态码 {resp.status_code}"
                )
        logger.warning(f"[二维码登录] 轮询超时（共 {attempts} 次请求）")
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
