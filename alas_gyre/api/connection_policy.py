#!/usr/bin/env python3
# -_- coding: utf-8 -*-
"""连接策略决策模块——连接模式判断和降级策略的唯一入口。"""

import re
from dataclasses import dataclass

from alas_gyre.api.client import alas_gui_url
from alas_gyre.api.client import api_headers
from alas_gyre.api.client import api_request
from alas_gyre.api.client import gyre_api_url
from alas_gyre.api.client import pywebio_ws_url

VALID_MESSAGE_KEYS = {
    "test_success",
    "test_failed_short",
    "test_overlay_success",
    "test_websocket_success",
    "test_overlay_failed_websocket_success",
    "test_overlay_and_websocket_failed",
}


@dataclass(frozen=True)
class ConnectionTestResult:
    """连接测试结果数据结构。"""

    success: bool
    source: str
    overlay_error: str = ""
    websocket_error: str = ""
    message_key: str = ""


def normalize_connection_mode(config) -> str:
    """标准化连接模式配置值，将 legacy 'overlay' 映射为 'auto'。"""
    mode = str((config or {}).get("connection_mode") or "auto").strip().lower()
    if mode == "websocket":
        return "websocket"
    return "auto"


def should_use_websocket_directly(config) -> bool:
    """判断是否应直接使用 WebSocket 模式。"""
    return normalize_connection_mode(config) == "websocket"


def should_fallback_to_websocket(config, overlay_failure) -> bool:
    """判断 overlay 失败后是否应降级到 WebSocket。

    Args:
        config: 配置字典
        overlay_failure: 保留参数，预留未来按失败类型决策

    Returns:
        当前 auto 模式下对所有 Overlay 失败均降级。
    """
    return normalize_connection_mode(config) == "auto"


def _format_error(exc_or_text):
    """格式化异常对象或错误文本，限制长度 300 字符。"""
    if not exc_or_text:
        return ""
    return str(exc_or_text)[:300]


def _test_overlay(config):
    """测试 overlay 连接是否可用，成功返回空字符串，失败返回错误信息。"""
    resp = api_request(
        "GET",
        gyre_api_url(config, "health"),
        headers=api_headers(config),
        timeout=2.0,
    )
    if resp.status_code == 200:
        return ""
    return f"HTTP {resp.status_code}"


def _test_websocket(config):
    """测试 ALAS WebUI WebSocket 通讯是否可达。

    优先尝试建立一次短 WebSocket 连接验证通道；回退到 HTTP 页面探测。
    成功返回空字符串，失败返回错误信息。
    """
    try:
        import websocket as _ws_test
        test_url = re.sub(
            r'session=[^&]+', 'session=test', pywebio_ws_url(config)
        )
        test_ws = _ws_test.create_connection(
            test_url,
            timeout=3,
        )
        test_ws.close()
        return ""
    except Exception:
        pass
    resp = api_request("GET", alas_gui_url(config), timeout=5)
    if resp.status_code == 200 and "pywebio" in (resp.text or "").lower():
        return ""
    return f"HTTP {resp.status_code}"


def test_connection_with_fallback(config) -> ConnectionTestResult:
    """执行连接测试并自动降级。

    根据配置的连接模式，依次测试 overlay 和 websocket 连接，
    返回包含成功状态和错误详情的 ConnectionTestResult。
    """
    if should_use_websocket_directly(config):
        try:
            websocket_error = _test_websocket(config)
        except Exception as exc:
            websocket_error = _format_error(exc)
        if not websocket_error:
            return ConnectionTestResult(
                True, "websocket", message_key="test_websocket_success"
            )
        return ConnectionTestResult(
            False,
            "websocket",
            websocket_error=websocket_error,
            message_key="test_failed_short",
        )

    overlay_error = ""
    try:
        overlay_error = _test_overlay(config)
    except Exception as exc:
        overlay_error = _format_error(exc)
    if not overlay_error:
        return ConnectionTestResult(
            True, "overlay", message_key="test_overlay_success"
        )

    if not should_fallback_to_websocket(config, overlay_error):
        return ConnectionTestResult(
            False,
            "overlay",
            overlay_error=overlay_error,
            message_key="test_failed_short",
        )

    try:
        websocket_error = _test_websocket(config)
    except Exception as exc:
        websocket_error = _format_error(exc)
    if not websocket_error:
        return ConnectionTestResult(
            True,
            "websocket_fallback",
            overlay_error=overlay_error,
            message_key="test_overlay_failed_websocket_success",
        )
    return ConnectionTestResult(
        False,
        "websocket_fallback",
        overlay_error=overlay_error,
        websocket_error=websocket_error,
        message_key="test_overlay_and_websocket_failed",
    )
