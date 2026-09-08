"""同步 HTTP 工具，对应 Java 端 ``com.Tools.HttpUtil``。

基于 ``httpx`` 的同步客户端实现，接口形态与 OkHttp 的阻塞式调用保持一致。
在 NoneBot 事件处理中，这些阻塞调用应通过 ``asyncio.to_thread`` 放入线程池执行，
从而避免阻塞事件循环。
"""

from __future__ import annotations

from typing import Optional

import httpx

_TIMEOUT = httpx.Timeout(30.0, connect=15.0)

_client = httpx.Client(timeout=_TIMEOUT, follow_redirects=True)


def http_get(url: str, headers: Optional[dict] = None) -> Optional[httpx.Response]:
    """GET 请求，失败返回 ``None``。"""
    try:
        return _client.get(url, headers=headers)
    except httpx.HTTPError:
        return None


def http_post(
    url: str,
    headers: Optional[dict] = None,
    data=None,
) -> Optional[httpx.Response]:
    """POST 请求，失败返回 ``None``。

    ``data`` 为 ``dict`` 时以 ``application/x-www-form-urlencoded`` 编码；
    为 ``str`` 时按原样作为请求体。
    """
    try:
        return _client.post(url, headers=headers, data=data)
    except httpx.HTTPError:
        return None


def http_put(
    url: str,
    headers: Optional[dict] = None,
    data=None,
) -> Optional[httpx.Response]:
    """PUT 请求，失败返回 ``None``。"""
    try:
        return _client.put(url, headers=headers, data=data)
    except httpx.HTTPError:
        return None


def get_bytes_from_url(url: str) -> Optional[bytes]:
    """下载 URL 资源为字节，失败返回 ``None``。"""
    if not url:
        return None
    try:
        resp = _client.get(url)
        if resp.status_code == 200:
            return resp.content
    except httpx.HTTPError:
        return None
    return None


def get_text(url: str) -> str:
    """下载 URL 资源为文本，失败返回空字符串。"""
    data = get_bytes_from_url(url)
    return data.decode("utf-8", errors="ignore") if data else ""
