"""同步 HTTP 工具，对应 Java 端 ``com.Tools.HttpUtil``。

基于 ``httpx`` 的同步客户端实现，接口形态与 OkHttp 的阻塞式调用保持一致。
在 NoneBot 事件处理中，这些阻塞调用应通过 ``asyncio.to_thread`` 放入线程池执行，
从而避免阻塞事件循环。

调试日志（输出到控制台）：

* 每个请求都会打印 **请求链接**（含 method，敏感参数自动掩码）；
* 每个请求都会打印 **请求结果**：成功时为状态码 / 耗时 / 响应体大小，
  失败时为详细错误信息（超时、连接失败、DNS 解析失败、响应体读取失败等）。

状态码 >= 400 仍按原有约定返回 ``httpx.Response``（交由调用方判断），
但会额外打印一条告警日志，便于在控制台直接定位问题。
"""

from __future__ import annotations

import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

from . import logger as log

_TIMEOUT = httpx.Timeout(30.0, connect=15.0)

_client = httpx.Client(timeout=_TIMEOUT, follow_redirects=True)

# URL 中需要掩码的参数名（小写比较）
_SENSITIVE_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "access_token",
        "refresh_token",
        "client_secret",
        "client_id",
        "token",
        "key",
        "secret",
        "password",
        "signature",
    }
)

_MASK = "***"


@dataclass(frozen=True)
class _RequestInfo:
    """一次请求的上下文，用于把请求日志与结果日志对应起来。"""

    method: str
    url: str


def _redact_query(url: str) -> str:
    """掩码 URL 查询串中的敏感参数，其它参数原样保留便于排查。"""
    try:
        parts = urllib.parse.urlsplit(url)
        if not parts.query:
            return url
        items = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if not items:
            return url
        safe_items = [
            (key, _MASK if key.lower() in _SENSITIVE_QUERY_KEYS else value)
            for key, value in items
        ]
        return urllib.parse.urlunsplit(
            parts._replace(query=urllib.parse.urlencode(safe_items))
        )
    except Exception:  # noqa: BLE001  # URL 解析失败时退回原串
        return url


def _headers_brief(headers: Optional[dict]) -> str:
    """请求头摘要：不打印具体值，只提示是否携带鉴权信息。"""
    if not headers:
        return "无自定义请求头"
    names = ", ".join(str(k) for k in headers)
    auth = "含 Authorization" if any(
        str(k).lower() == "authorization" for k in headers
    ) else "无 Authorization"
    return f"请求头={names}（{auth}）"


def _body_brief(data: Any) -> str:
    """请求体摘要：只打印类型与长度，避免泄露验证码 / Token。"""
    if data is None:
        return "无请求体"
    if isinstance(data, dict):
        keys = ", ".join(str(k) for k in data)
        return f"表单参数={keys}（共 {len(data)} 项，值已省略）"
    if isinstance(data, (bytes, bytearray)):
        return f"请求体={len(data)} 字节"
    if isinstance(data, str):
        return f"请求体=字符串 {len(data)} 字符"
    return f"请求体类型={type(data).__name__}"


def _size_brief(resp: httpx.Response) -> int:
    try:
        return len(resp.content)
    except Exception:  # noqa: BLE001  # 流式响应读取失败
        return -1


def _describe_error(exc: BaseException) -> str:
    """把 httpx 异常翻译成可读的详细错误信息。"""
    if isinstance(exc, httpx.ConnectTimeout):
        kind = "连接超时（超过 15 秒未建立连接）"
    elif isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
        kind = "读写超时（超过 30 秒无响应）"
    elif isinstance(exc, httpx.PoolTimeout):
        kind = "连接池排队超时"
    elif isinstance(exc, httpx.TimeoutException):
        kind = "请求超时"
    elif isinstance(exc, httpx.ConnectError):
        kind = "连接失败（网络不可达 / DNS 解析失败 / 目标拒绝连接）"
    elif isinstance(exc, httpx.TooManyRedirects):
        kind = "重定向次数过多"
    elif isinstance(exc, httpx.HTTPStatusError):
        kind = "HTTP 状态码异常"
    elif isinstance(exc, httpx.ProtocolError):
        kind = "HTTP 协议错误（响应不符合 HTTP 规范或连接被中断）"
    elif isinstance(exc, httpx.DecodingError):
        kind = "响应内容解码失败"
    elif isinstance(exc, httpx.HTTPError):
        kind = "HTTP 请求异常"
    else:
        kind = type(exc).__name__
    detail = str(exc).strip() or "无附加信息"
    return f"{kind} | {type(exc).__name__}: {detail}"


def _request(
    method: str,
    url: str,
    context: str,
    sender: Callable[[], httpx.Response],
    detail: str = "",
) -> Optional[httpx.Response]:
    """统一的请求执行与日志记录：请求链接 + 请求结果（状态码 / 详细错误）。"""
    safe_url = _redact_query(url)
    log.log_http_request(method, safe_url, context)

    start = time.perf_counter()
    try:
        resp = sender()
    except Exception as exc:  # noqa: BLE001  # 任何网络异常都只返回 None
        elapsed = int((time.perf_counter() - start) * 1000)
        log.log_http_error(method, safe_url, _describe_error(exc), elapsed, context)
        return None

    elapsed = int((time.perf_counter() - start) * 1000)
    size = _size_brief(resp)
    log.log_http_response(
        method, safe_url, resp.status_code, elapsed, size if size >= 0 else None, context
    )

    # 仅在异常或重定向时才输出额外细节，避免正常请求刷屏
    notes: list[str] = []
    if resp.status_code >= 400:
        notes.append(f"响应异常内容（前 500 字符）：{_text(resp)[:500]}")
    if resp.history:
        hops = [str(r.url) for r in resp.history]
        notes.append(
            f"发生重定向 {len(hops)} 次 -> {_redact_query(str(resp.url))}"
        )
    if detail:
        notes.append(detail)
    for note in notes:
        log.log_step(context, note)
    return resp


def _text(resp: httpx.Response) -> str:
    """安全读取响应文本，失败返回空串。"""
    try:
        return resp.text
    except Exception as exc:  # noqa: BLE001  # 编码 / 连接中断
        log.log_http_error("(body)", "(响应体读取)", _describe_error(exc))
        return ""


def http_get(
    url: str,
    headers: Optional[dict] = None,
    context: str = "",
) -> Optional[httpx.Response]:
    """GET 请求，失败返回 ``None``。"""
    return _request(
        "GET",
        url,
        context,
        lambda: _client.get(url, headers=headers),
        _headers_brief(headers),
    )


def http_post(
    url: str,
    headers: Optional[dict] = None,
    data=None,
    context: str = "",
) -> Optional[httpx.Response]:
    """POST 请求，失败返回 ``None``。

    ``data`` 为 ``dict`` 时以 ``application/x-www-form-urlencoded`` 编码；
    为 ``str`` 时按原样作为请求体。
    """
    return _request(
        "POST",
        url,
        context,
        lambda: _client.post(url, headers=headers, data=data),
        f"{_headers_brief(headers)}；{_body_brief(data)}",
    )


def http_put(
    url: str,
    headers: Optional[dict] = None,
    data=None,
    context: str = "",
) -> Optional[httpx.Response]:
    """PUT 请求，失败返回 ``None``。"""
    return _request(
        "PUT",
        url,
        context,
        lambda: _client.put(url, headers=headers, data=data),
        f"{_headers_brief(headers)}；{_body_brief(data)}",
    )


def fetch_url(
    url: str,
    headers: Optional[dict] = None,
    context: str = "",
) -> Optional[bytes]:
    """流式下载二进制资源（图片等），失败返回 ``None``。

    流式下载避免把大文件整体读入内存；下载过程中若状态码非 200 或中途出错，
    会打印对应的调试日志。
    """
    safe_url = _redact_query(url)
    log.log_http_request("GET", safe_url, context or "资源下载")

    start = time.perf_counter()
    try:
        with _client.stream("GET", url, headers=headers) as resp:
            if resp.status_code != 200:
                elapsed = int((time.perf_counter() - start) * 1000)
                log.log_http_response(
                    "GET", safe_url, resp.status_code, elapsed, context=context or "资源下载"
                )
                log.log_step(
                    context or "资源下载",
                    f"状态码非 200，放弃下载：{resp.status_code}",
                )
                return None
            chunks: list[bytes] = []
            for chunk in resp.iter_bytes():
                chunks.append(chunk)
            payload = b"".join(chunks)
            elapsed = int((time.perf_counter() - start) * 1000)
            log.log_http_response(
                "GET",
                safe_url,
                resp.status_code,
                elapsed,
                len(payload),
                context or "资源下载",
            )
            return payload
    except Exception as exc:  # noqa: BLE001  # 任何网络异常都只返回 None
        elapsed = int((time.perf_counter() - start) * 1000)
        log.log_http_error(
            "GET", safe_url, _describe_error(exc), elapsed, context or "资源下载"
        )
        return None


def get_bytes_from_url(url: str) -> Optional[bytes]:
    """下载 URL 资源为字节，失败返回 ``None``。"""
    if not url:
        log.log_step("资源下载", "URL 为空，跳过下载")
        return None
    return fetch_url(url, context="资源下载")


def get_text(url: str) -> str:
    """下载 URL 资源为文本，失败返回空字符串。"""
    data = get_bytes_from_url(url)
    if not data:
        return ""
    return data.decode("utf-8", errors="ignore")
