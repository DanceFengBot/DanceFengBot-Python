"""请求加解密工具，对应 Java 端 ``com.Tools.DanceCubeRequestCrypto``。

说明：原 Java 项目中 ``dataBuild`` / ``decryptWithDesCbc`` / ``cryptoWithDesCbc``
均未被任何业务代码调用（经全局检索确认），此处为保持转换完整性而移植。
"""

from __future__ import annotations

import base64
import json
from typing import Mapping


def data_build(
    path: str,
    params: Mapping[str, str],
    method: str,
    data: dict,
    content_type: str,
) -> str:
    """构建待处理的数据结构，与原实现一致。"""
    params_str = convert_map_to_string(params)
    result = (
        '{"path":"%s","param":"%s","data":%s,"method":"%s","contentType":"%s"}'
        % (path, params_str, json.dumps(data, ensure_ascii=False), method, content_type)
    )
    return result


def convert_map_to_string(map_: Mapping[str, str]) -> str:
    """将 map 编码为 ``k=v&k=v`` 字符串。"""
    return "&".join(f"{k}={v}" for k, v in map_.items())


def decrypt_with_des_cbc(cipher_text: str, key: bytes, iv: bytes) -> str:
    """DES/CBC/PKCS5Padding 解密（Base64 输入）。"""
    from Crypto.Cipher import DES

    cipher = DES.new(key, DES.MODE_CBC, iv)
    raw = base64.b64decode(cipher_text)
    return cipher.decrypt(raw).decode("utf-8")


def crypto_with_des_cbc(plain_text: str, key: bytes, iv: bytes) -> str:
    """原实现有误（按解密方式处理），这里忠实保留原行为。"""
    from Crypto.Cipher import DES

    cipher = DES.new(key, DES.MODE_CBC, iv)
    raw = base64.b64decode(plain_text)
    return cipher.decrypt(raw).decode("utf-8")


def hex_to_bytes(hex_: str) -> bytes:
    return bytes.fromhex(hex_)
