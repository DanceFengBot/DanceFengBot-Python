"""腾讯云 OCR（二维码识别），对应 Java 端 ``HttpUtil.qrDecodeTencent``。

使用 TC3-HMAC-SHA256 签名规范直接调用 QrcodeOCR 接口，避免引入重量级 SDK。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

from ..config import api_keys
from . import logger
from .http import http_post

_SERVICE = "ocr"
_HOST = "ocr.tencentcloudapi.com"
_ACTION = "QrcodeOCR"
_VERSION = "2018-11-19"
_REGION = "ap-shanghai"


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def qr_decode_tencent(img_url: str) -> str:
    """识别图片中的二维码 URL，失败返回空字符串。"""
    secret_id = api_keys.tencent_secret_id
    secret_key = api_keys.tencent_secret_key
    if not secret_id or not secret_key:
        logger.error("[二维码识别] 未配置腾讯云 OCR 密钥，跳过识别")
        return ""
    logger.debug(f"[二维码识别] 开始识别图片：{img_url}")

    payload = json.dumps({"ImageUrl": img_url}, ensure_ascii=False)
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))

    # 1. 拼接规范请求串
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{_HOST}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = (
        f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n"
        f"{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    # 2. 拼接待签名字符串
    algorithm = "TC3-HMAC-SHA256"
    credential_scope = f"{date}/{_SERVICE}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = (
        f"{algorithm}\n{timestamp}\n{credential_scope}\n{hashed_canonical}"
    )

    # 3. 计算签名
    secret_date = _sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _sign(secret_date, _SERVICE)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": _HOST,
        "X-TC-Action": _ACTION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": _VERSION,
        "X-TC-Region": _REGION,
    }

    resp = http_post(
        f"https://{_HOST}",
        headers=headers,
        data=payload,
        context="二维码识别-腾讯OCR",
    )
    if resp is None:
        logger.error("[二维码识别] 腾讯 OCR 请求失败")
        return ""
    if resp.status_code != 200:
        logger.error(
            f"[二维码识别] 腾讯 OCR 返回状态码 {resp.status_code}：{resp.text[:200]}"
        )
        return ""
    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error(
            f"[二维码识别] 响应解析失败：{exc}；内容（前 200 字符）：{resp.text[:200]}"
        )
        return ""

    response = data.get("Response", {})
    if response.get("Error"):
        error = response["Error"]
        logger.error(
            f"[二维码识别] 腾讯 OCR 业务错误："
            f"{error.get('Code')} - {error.get('Message')}"
        )
        return ""
    results = response.get("CodeResults") or []
    if not results:
        logger.warning("[二维码识别] 腾讯 OCR 未识别到二维码")
        return ""
    url = results[0].get("Url", "")
    logger.debug(f"[二维码识别] 识别结果：{url or '空'}")
    return url
