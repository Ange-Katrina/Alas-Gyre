#!/usr/bin/env python3
# -_- coding: utf-8 -_-

from dataclasses import dataclass
from dataclasses import field
import json
import logging
import re
import threading
import time
from typing import Any

import requests
import websocket

from alas_gyre.api.client import alas_gui_url
from alas_gyre.api.client import pywebio_ws_url

CONNECTION_STATE_STOPPED = "stopped"
CONNECTION_STATE_CONNECTING = "connecting"
CONNECTION_STATE_INITIAL_SCANNING = "initial_scanning"
CONNECTION_STATE_READY = "ready"
CONNECTION_STATE_DEGRADED = "degraded"
CONNECTION_STATE_PAUSED = "paused"

POLL_MODE_ROUND_ROBIN = "round_robin"
POLL_MODE_FULL_SCAN = "full_scan"
DEFAULT_POLL_INTERVAL = 3

ERROR_TARGET_SCOPE_NOT_FOUND = "target_scope_not_found"
ERROR_CONFIG_CALLBACK_NOT_FOUND = "config_callback_not_found"
ERROR_ACTION_CALLBACK_NOT_FOUND = "config_action_callback_not_found"
ERROR_TRANSPORT_UNAVAILABLE = "transport_unavailable"
ERROR_INTERNAL_ALAS_GUI_ERROR = "internal_alas_gui_error"
ERROR_SESSION_CLOSED = "session_closed"

TRANSPORT_FAILURE_THRESHOLD = 3
PAGE_MISSING_FAILURE_THRESHOLD = 3
PAUSE_SECONDS = 10.0
RECONNECT_DELAY_SECONDS = 1.0
COLLECT_TIMEOUT_SECONDS = 1.5
CONTROL_RESYNC_DELAY_SECONDS = 0.5


class WebSocketCommError(Exception):
    """WebSocket 通讯基础错误。"""


@dataclass
class ControlCommand:
    """WebSocket 通讯控制命令。"""

    config_name: str
    action: str


class WebSocketCommManager:
    """ALAS GUI WebSocket 通讯管理器。"""

    def __init__(self, config):
        self.config = dict(config or {})
        self._lock = threading.Lock()
        self._control_queue = []
        self.configs = []
        self.statuses = {}
        self.tasks = {}
        self.scan_errors = {}
        self.control_errors = {}
        self.connection_state = CONNECTION_STATE_STOPPED
        self.ready = False
        self.bootstrapped = False
        self.transport_available = False
        self.last_transport_error = ""
        self.failure_count = 0
        self.consecutive_degraded_count = 0
        self.poll_interval = self._normalize_poll_interval(
            self.config.get("websocket_poll_interval", DEFAULT_POLL_INTERVAL)
        )
        self.poll_mode = self._normalize_poll_mode(
            self.config.get("websocket_poll_mode", POLL_MODE_ROUND_ROBIN)
        )
        self.last_scan_config = ""
        self.initial_scan_completed = False
        self.pause_until = 0.0
        self.stop_event = threading.Event()
        self.worker_thread = None
        self.round_robin_index = 0
        self._sidebar_nav_callback_id = ""
        self._sidebar_nav_callbacks = {}
        self._page_missing_counts = {}
        self._page_missing_skip_until = {}
        self._page_state = PyWebIOPageState()

    def _normalize_poll_interval(self, value):
        """规范化轮询间隔。"""
        try:
            interval = int(value)
        except (TypeError, ValueError):
            interval = DEFAULT_POLL_INTERVAL
        return min(max(interval, 1), 60)

    def _normalize_poll_mode(self, value):
        """规范化轮询模式。"""
        if value == POLL_MODE_FULL_SCAN:
            return POLL_MODE_FULL_SCAN
        return POLL_MODE_ROUND_ROBIN

    def start(self):
        """启动后台通讯线程。"""
        with self._lock:
            if self.worker_thread is not None and self.worker_thread.is_alive():
                return
            self.stop_event.clear()
            self.connection_state = CONNECTION_STATE_CONNECTING
            self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
            self.worker_thread.start()

    def stop(self):
        """停止后台通讯线程。"""
        self.stop_event.set()
        thread = self.worker_thread
        if thread is not None:
            thread.join(timeout=3)
        with self._lock:
            self.connection_state = CONNECTION_STATE_STOPPED
            self.ready = False
            self.transport_available = False

    def update_config(self, config):
        """更新通讯配置。"""
        with self._lock:
            self.config = dict(config or {})
            self.poll_interval = self._normalize_poll_interval(
                self.config.get("websocket_poll_interval", DEFAULT_POLL_INTERVAL)
            )
            self.poll_mode = self._normalize_poll_mode(
                self.config.get("websocket_poll_mode", POLL_MODE_ROUND_ROBIN)
            )

    def update_settings(self, poll_interval, poll_mode):
        """更新轮询设置。"""
        with self._lock:
            self.poll_interval = self._normalize_poll_interval(poll_interval)
            self.poll_mode = self._normalize_poll_mode(poll_mode)

    def refresh_config(self, config_name):
        """刷新单个配置的状态（当前不实现，忽略）。"""
        logging.getLogger("alas_gyre.websocket").debug("refresh_config 未实现: %s", config_name)

    def post_action(self, config_name, action):
        """提交开始或停止控制命令。"""
        if action not in {"start", "stop"}:
            raise WebSocketCommError("unsupported_action")
        command = ControlCommand(str(config_name), str(action))
        with self._lock:
            self._control_queue = [
                item for item in self._control_queue
                if item.config_name != command.config_name
            ]
            self._control_queue.append(command)
            return {
                "submitted": True,
                "queued": True,
                "transport_available": self.transport_available,
                "connection_state": self.connection_state,
            }

    def get_configs(self):
        """返回配置列表快照。"""
        with self._lock:
            return list(self.configs)

    def get_snapshot(self):
        """返回通讯状态快照。"""
        with self._lock:
            return {
                "configs": list(self.configs),
                "statuses": dict(self.statuses),
                "tasks": dict(self.tasks),
                "scan_errors": dict(self.scan_errors),
                "control_errors": dict(self.control_errors),
                "connection_state": self.connection_state,
                "ready": self.ready,
                "bootstrapped": self.bootstrapped,
                "transport_available": self.transport_available,
                "last_transport_error": self.last_transport_error,
                "failure_count": self.failure_count,
                "consecutive_degraded_count": self.consecutive_degraded_count,
                "pending_controls": [
                    {"config": item.config_name, "action": item.action}
                    for item in self._control_queue
                ],
                "poll_interval": self.poll_interval,
                "poll_mode": self.poll_mode,
                "last_scan_config": self.last_scan_config,
                "initial_scan_completed": self.initial_scan_completed,
            }

    def get_status_all(self):
        """返回 UI 状态快照。"""
        snapshot = self.get_snapshot()
        configs = snapshot.get("configs", [])
        statuses = snapshot.get("statuses", {})
        if (
            snapshot.get("connection_state") == CONNECTION_STATE_INITIAL_SCANNING
            and configs
            and len(statuses) < len(configs)
        ):
            snapshot["configs"] = []
            snapshot["statuses"] = {}
            snapshot["tasks"] = {}
        return snapshot

    def _mark_config_missing(self, config_name, error):
        """标记配置页面状态不可确认，递增逐配置缺失计数并在达到阈值后暂缓扫描。"""
        name = str(config_name)
        with self._lock:
            self.statuses[name] = "disconnected"
            self.tasks[name] = ""
            self.scan_errors[name] = str(error)

            # 递增逐配置缺失计数（防御 __new__ 构造的未初始化对象）
            counts = getattr(self, '_page_missing_counts', None)
            if counts is None:
                counts = {}
                self._page_missing_counts = counts
            current_count = counts.get(name, 0) + 1
            counts[name] = current_count
            if current_count >= PAGE_MISSING_FAILURE_THRESHOLD:
                skip_until = getattr(self, '_page_missing_skip_until', None)
                if skip_until is None:
                    skip_until = {}
                    self._page_missing_skip_until = skip_until
                skip_until[name] = time.monotonic() + PAUSE_SECONDS

    def _apply_config_status(self, config_name, status):
        """写入经过页面证据确认的配置状态，成功时清除该配置的缺失计数和跳过时间。"""
        name = str(config_name)
        if status:
            with self._lock:
                self.statuses[name] = status
                self.tasks[name] = ""
                self.scan_errors.pop(name, None)
                self.last_scan_config = name
                # 清除该配置的逐配置缺失跟踪（防御 __new__ 构造的未初始化对象）
                counts = getattr(self, '_page_missing_counts', None)
                if counts is not None:
                    counts.pop(name, None)
                skip = getattr(self, '_page_missing_skip_until', None)
                if skip is not None:
                    skip.pop(name, None)
            return True
        self._mark_config_missing(name, ERROR_TARGET_SCOPE_NOT_FOUND)
        return False

    def _is_config_page_missing_skip(self, config_name):
        """检查配置是否因页面缺失而被暂缓扫描（自动清理过期条目）。"""
        name = str(config_name)
        with self._lock:
            skip_dict = getattr(self, '_page_missing_skip_until', None)
            if skip_dict is None:
                return False
            skip_until = skip_dict.get(name, 0.0)
            if skip_until <= 0.0:
                return False
            if time.monotonic() >= skip_until:
                # 跳过时间已过期，清理该条目
                counts = getattr(self, '_page_missing_counts', None)
                if counts is not None:
                    counts.pop(name, None)
                skip_dict.pop(name, None)
                return False
            return True

    def _run_loop(self):
        """后台通讯循环——通过 PyWebIO WebSocket 与 ALAS GUI 通讯。"""
        # 阶段一：连接建立
        ws = self._establish_connection()
        if ws is None:
            with self._lock:
                self.connection_state = CONNECTION_STATE_PAUSED
                self.pause_until = time.monotonic() + PAUSE_SECONDS
        else:
            # 阶段二：初始化全量扫描
            try:
                self._perform_initial_scan(ws)
            except (websocket.WebSocketException, ConnectionError, OSError) as exc:
                # 传输层异常——标记为传输失败，进入轮询循环尝试恢复
                self._record_transport_failure(exc)
            except Exception as exc:
                # 非传输异常（如 JSON decode）——记录日志，允许降级运行
                self._log_error("初始化扫描非传输异常: %s", exc)
                with self._lock:
                    self.initial_scan_completed = True
                    self.connection_state = CONNECTION_STATE_DEGRADED

        # 阶段三：后续轮询循环
        while not self.stop_event.is_set():
            # 检查是否需要暂停恢复
            if self._should_recover_from_pause():
                new_ws = self._attempt_connection_recovery()
                if new_ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
                    ws = new_ws
                else:
                    self._interruptible_sleep(RECONNECT_DELAY_SECONDS)
                    continue

            if self.connection_state == CONNECTION_STATE_PAUSED:
                self._interruptible_sleep(1.0)
                continue

            # ws 仍未建立（首次连接失败后等待恢复），跳过本轮通讯操作
            if ws is None:
                self._interruptible_sleep(1.0)
                continue

            # 处理控制队列（优先级高于轮询）
            try:
                self._drain_control_queue(ws)
            except (websocket.WebSocketException, ConnectionError, OSError) as exc:
                ws = self._handle_transport_error(ws, exc)
                continue

            # 根据轮询模式执行状态扫描
            try:
                if self.poll_mode == POLL_MODE_FULL_SCAN:
                    self._poll_full_scan(ws)
                else:
                    self._poll_round_robin(ws)
            except (websocket.WebSocketException, ConnectionError, OSError) as exc:
                ws = self._handle_transport_error(ws, exc)
                continue
            except Exception as exc:
                self._log_error("轮询扫描异常: %s", exc)
                self._interruptible_sleep(RECONNECT_DELAY_SECONDS)
                continue

            # 轮询间隔 sleep
            self._interruptible_sleep(self.poll_interval)

        # 清理
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def _handle_transport_error(self, ws, exc):
        """处理传输层异常，记录失败、关闭旧连接并返回 None。"""
        self._record_transport_failure(exc)
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        self._interruptible_sleep(RECONNECT_DELAY_SECONDS)
        return None

    @staticmethod
    def _log_error(fmt, *args):
        """记录错误日志。"""
        logger = logging.getLogger("alas_gyre.websocket")
        logger.error(fmt, *args)

    def _interruptible_sleep(self, duration):
        """可中断的 sleep，每 0.5 秒检查一次 stop_event。"""
        end = time.monotonic() + duration
        while time.monotonic() < end:
            if self.stop_event.is_set():
                return
            remaining = end - time.monotonic()
            time.sleep(min(0.5, max(0.0, remaining)))

    def _should_recover_from_pause(self):
        """检查是否应该从暂停状态恢复。"""
        with self._lock:
            if self.connection_state != CONNECTION_STATE_PAUSED:
                return False
            return time.monotonic() >= self.pause_until

    def _establish_connection(self):
        """建立 HTTP 探测 + WebSocket 连接，成功返回 ws 对象，失败返回 None。"""
        try:
            self._http_probe_alas_gui()
        except Exception as exc:
            self._record_transport_failure(exc)
            return None

        try:
            ws = self._connect_ws()
            with self._lock:
                self.transport_available = True
                self._page_state = PyWebIOPageState()
            return ws
        except Exception as exc:
            self._record_transport_failure(exc)
            return None

    def _http_probe_alas_gui(self):
        """HTTP GET ALAS GUI 根页面，确认包含 PyWebIO 特征。"""
        url = alas_gui_url(self.config)
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        body = resp.text.lower()
        if "pywebio" not in body:
            raise WebSocketCommError("alas_gui_no_pywebio_signature")

    def _connect_ws(self):
        """建立 WebSocket 连接，返回 ws 对象。"""
        url = pywebio_ws_url(self.config)
        ws = websocket.create_connection(url, timeout=10)
        return ws

    def _collect_page_messages(self, ws, timeout):
        """从 WebSocket 收集消息直到超时，返回累积的 PyWebIOPageState。

        通过设置 socket 短超时来逐条读取消息，累积到页面状态中。
        """
        state = getattr(self, "_page_state", None)
        if state is None:
            state = PyWebIOPageState()
            self._page_state = state
        # 记录当前 session_id 用于检测 session 重置
        previous_session_id = None

        ws.settimeout(min(timeout, 0.5))
        start = time.monotonic()

        while time.monotonic() - start < timeout:
            try:
                raw_data = ws.recv()
            except websocket.WebSocketTimeoutException:
                # 超时是正常的——消息间可能没有新数据
                continue
            except Exception:
                break

            if not raw_data:
                break

            try:
                raw = json.loads(raw_data)
            except (json.JSONDecodeError, TypeError):
                continue

            message = parse_pywebio_message(raw)
            state.apply_message(message)
            self._handle_pywebio_runtime_message(ws, message)

            # 检测 session 重置（set_session_id 变化）
            if message.command == "set_session_id":
                new_session = state.session_id
                if previous_session_id and new_session != previous_session_id:
                    raise WebSocketCommError(ERROR_SESSION_CLOSED)
                previous_session_id = new_session

            # 检测服务端内部错误
            if message.command == "eval_js":
                js_code = ""
                if isinstance(message.spec, dict):
                    js_code = str(message.spec.get("code", "") or "")
                if "internal_error" in js_code.lower() or "traceback" in js_code.lower():
                    raise WebSocketCommError(ERROR_INTERNAL_ALAS_GUI_ERROR)

        return state

    @staticmethod
    def _handle_pywebio_runtime_message(ws, message):
        """处理 PyWebIO 运行时消息并发送必要响应。

        PyWebIO 浏览器端收到 run_script(eval=True) 后会执行 JavaScript，
        并通过 js_yield 事件把结果回传。非浏览器客户端也必须回传该事件，
        否则服务端会停在等待 JS 返回值，后续 output/output_ctl 不会下发。
        """
        if message.command != "run_script" or not isinstance(message.spec, dict):
            return False
        if not message.spec.get("eval"):
            return False
        payload = {
            "event": "js_yield",
            "task_id": message.task_id,
            "data": None,
        }
        ws.send(json.dumps(payload))
        return True

    def _send_callback(self, ws, callback_id, value):
        """发送 PyWebIO pin callback 事件到 WebSocket。"""
        payload = {
            "event": "callback",
            "task_id": "main",
            "data": {"callback_id": str(callback_id), "value": str(value)},
        }
        ws.send(json.dumps(payload))

    def _send_button_callback(self, ws, callback_id, value):
        """发送 PyWebIO buttons callback 事件到 WebSocket。"""
        payload = {
            "event": "callback",
            "task_id": str(callback_id),
            "data": value,
        }
        ws.send(json.dumps(payload))

    def _perform_initial_scan(self, ws):
        """初始化全量扫描——发现配置列表并提取各配置状态。"""
        with self._lock:
            self.connection_state = CONNECTION_STATE_INITIAL_SCANNING

        # 收集侧边栏页面消息
        state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
        config_names = extract_instance_names(state)
        nav_callbacks = extract_instance_nav_callbacks(state)

        # 存储侧边栏导航 callback_id（从 pin_onchange 获取）
        sidebar_callback_id = ""
        for pin_name, cid in state.callback_ids.items():
            sidebar_callback_id = cid
            break

        with self._lock:
            self._sidebar_nav_callback_id = sidebar_callback_id
            self._sidebar_nav_callbacks = dict(nav_callbacks)

        # 无配置时回退为默认
        if not config_names:
            config_names = ["alas"]
            with self._lock:
                self.configs = list(config_names)
            for name in config_names:
                self._mark_config_missing(name, ERROR_TARGET_SCOPE_NOT_FOUND)
        else:
            with self._lock:
                self.configs = list(config_names)

        # 逐配置进入页面并提取状态
        any_recovered = False
        for config_name in config_names:
            try:
                self._navigate_to_config(ws, config_name)
                page_state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
                status = extract_config_status(page_state)
                if self._apply_config_status(config_name, status):
                    any_recovered = True
            except Exception as exc:
                self._mark_config_missing(config_name, str(exc))

        with self._lock:
            self.initial_scan_completed = True
            if any_recovered:
                self.connection_state = CONNECTION_STATE_READY
                self.ready = True
            else:
                self.connection_state = CONNECTION_STATE_DEGRADED
                self.ready = False

    def _navigate_to_config(self, ws, config_name):
        """通过 WebSocket 进入指定配置页。

        简化假设：侧边栏导航 callback 取第一个 pin_onchange 的 callback_id。
        实际 ALAS GUI 侧边栏使用单一 selector 切换配置，因此取任意一个
        pin_onchange callback 即可完成导航。如果未来侧边栏引入了多个独立的
        pin_onchange 组件，则需要在此处按名称精确匹配。
        """
        with self._lock:
            nav_callback = getattr(self, "_sidebar_nav_callbacks", {}).get(config_name)
            callback_id = self._sidebar_nav_callback_id

        if nav_callback:
            callback_id, value = nav_callback
            self._send_button_callback(ws, callback_id, value)
            time.sleep(0.5)
            return

        if not callback_id:
            # 侧边栏 callback_id 缺失，尝试重新从当前页面收集
            state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
            for pin_name, cid in state.callback_ids.items():
                callback_id = cid
                with self._lock:
                    self._sidebar_nav_callback_id = cid
                break

        if not callback_id:
            raise WebSocketCommError(ERROR_CONFIG_CALLBACK_NOT_FOUND)

        self._send_callback(ws, callback_id, config_name)
        # 等待页面跳转
        time.sleep(0.5)

    def _scan_config(self, ws, config_name):
        """扫描单个配置页——进入页面、收集消息、提取状态。"""
        self._navigate_to_config(ws, config_name)
        page_state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
        status = extract_config_status(page_state)
        self._apply_config_status(config_name, status)

    def _drain_control_queue(self, ws):
        """处理控制队列中所有待执行的命令。"""
        commands = []
        with self._lock:
            commands = list(self._control_queue)
            self._control_queue.clear()

        for cmd in commands:
            try:
                self._execute_control_command(ws, cmd)
            except Exception as exc:
                with self._lock:
                    self.control_errors[cmd.config_name] = str(exc)

    def _execute_control_command(self, ws, cmd):
        """执行单个控制命令（start/stop）。

        Args:
            ws: WebSocket 连接对象。
            cmd: ControlCommand 实例，包含 config_name 和 action。
        """
        # 进入目标配置页
        self._navigate_to_config(ws, cmd.config_name)

        # 收集页面状态以查找按钮
        page_state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)

        target_labels = START_BUTTON_LABELS if cmd.action == "start" else STOP_BUTTON_LABELS

        # 在 scheduler_btn scope 中查找目标按钮
        callback_id, value = self._find_button_action(page_state, target_labels)

        if not callback_id:
            with self._lock:
                self.control_errors[cmd.config_name] = ERROR_ACTION_CALLBACK_NOT_FOUND
            return

        # 发送按钮点击
        self._send_button_callback(ws, callback_id, value)
        time.sleep(CONTROL_RESYNC_DELAY_SECONDS)

        # 重新扫描该配置状态
        page_state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
        status = extract_config_status(page_state)
        self._apply_config_status(cmd.config_name, status)

        with self._lock:
            self.control_errors.pop(cmd.config_name, None)

    @staticmethod
    def _find_button_action(page_state, target_labels):
        """在页面状态中查找匹配标签的按钮并返回 callback_id 与 value。"""
        for output in page_state.outputs:
            if not isinstance(output, dict):
                continue
            if "scheduler_btn" not in _scope_identity(output):
                continue
            for button_group, buttons in _extract_buttons(output):
                if "scheduler_btn" not in _scope_identity(button_group):
                    continue
                callback_id = str(button_group.get("callback_id", "") or "")
                if not callback_id:
                    continue
                for button in buttons:
                    if not isinstance(button, dict):
                        continue
                    label = _flatten_text(button.get("label", "")).strip().lower()
                    if not any(t.lower() == label for t in target_labels):
                        continue
                    if _is_button_disabled(button):
                        continue
                    return callback_id, button.get("value")

        callback_id = WebSocketCommManager._find_button_callback(page_state, target_labels)
        if callback_id:
            return callback_id, ""
        return "", ""

    @staticmethod
    def _find_button_callback(page_state, target_labels):
        """在页面状态中查找匹配标签的按钮并返回其 callback_id。

        Args:
            page_state: PyWebIOPageState 实例。
            target_labels: 目标按钮标签元组。

        Returns:
            str: callback_id，未找到时返回空字符串。
        """
        for output in page_state.outputs:
            if not isinstance(output, dict):
                continue
            scope = str(output.get("scope", "") or "")
            if "scheduler_btn" not in scope:
                continue

            content = output.get("content")
            if content is None:
                continue
            if not isinstance(content, (list, tuple)):
                content = [content]

            cid = _extract_button_callback_from_content(content, target_labels)
            if cid:
                return cid

        # 回退：尝试从 page_state.callback_ids 中按 scope 匹配
        for output in page_state.outputs:
            if not isinstance(output, dict):
                continue
            scope = str(output.get("scope", "") or "")
            if "scheduler_btn" not in scope:
                continue
            for pin_name, cid in page_state.callback_ids.items():
                if scope in pin_name or pin_name in scope:
                    return cid

        return ""

    def _poll_round_robin(self, ws):
        """round_robin 模式轮询一个配置的状态，跳过被暂缓的缺失配置。"""
        with self._lock:
            configs = list(self.configs)
            start_idx = self.round_robin_index % len(configs) if configs else 0

        if not configs:
            return

        # 在锁外查找第一个不在跳过列表中的配置
        config_name = None
        next_index = start_idx
        for offset in range(len(configs)):
            idx = (start_idx + offset) % len(configs)
            name = configs[idx]
            if not self._is_config_page_missing_skip(name):
                config_name = name
                next_index = (idx + 1) % len(configs)
                break

        if config_name is None:
            # 所有配置都在跳过列表中，本轮不扫描
            return

        with self._lock:
            self.round_robin_index = next_index

        try:
            self._scan_config(ws, config_name)
        except Exception as exc:
            self._mark_config_missing(config_name, str(exc))

    def _poll_full_scan(self, ws):
        """full_scan 模式遍历所有配置的状态，跳过被暂缓的缺失配置。"""
        with self._lock:
            configs = list(self.configs)

        for config_name in configs:
            # 跳过被暂缓的缺失配置（方法内部有锁）
            if self._is_config_page_missing_skip(config_name):
                continue
            try:
                self._scan_config(ws, config_name)
            except Exception as exc:
                self._mark_config_missing(config_name, str(exc))

    def _attempt_connection_recovery(self):
        """尝试恢复连接，成功返回新 ws 对象并重跑扫描，失败返回 None。

        多次降级恢复失败后应用退避延迟，避免频繁重连。
        """
        # 多次降级恢复尝试后应用退避延迟
        degraded = getattr(self, 'consecutive_degraded_count', 0)
        if degraded >= 3:
            backoff = RECONNECT_DELAY_SECONDS * degraded
            self._interruptible_sleep(backoff)

        try:
            self._http_probe_alas_gui()
            ws = self._connect_ws()
            with self._lock:
                self.connection_state = CONNECTION_STATE_DEGRADED
                self.failure_count = 0
                self.transport_available = True
                self.consecutive_degraded_count = 0
                self._sidebar_nav_callback_id = ""
                self._sidebar_nav_callbacks = {}
                # 清除逐配置缺失跟踪（新连接后重新统计）
                self._page_missing_counts.clear()
                self._page_missing_skip_until.clear()
                configs_snapshot = list(self.configs)
            # 标记所有配置为 disconnected，等待后续扫描更新（方法内部有锁）
            for name in configs_snapshot:
                self._mark_config_missing(name, ERROR_TRANSPORT_UNAVAILABLE)
            # 恢复后重跑初始化扫描
            self._recover_and_rescan(ws)
            return ws
        except Exception as exc:
            self._record_transport_failure(exc)
            return None

    def _recover_and_rescan(self, ws):
        """恢复连接后重跑初始化扫描——使用已有配置列表，不重置 configs。"""
        with self._lock:
            self.connection_state = CONNECTION_STATE_INITIAL_SCANNING

        # 收集侧边栏页面消息，更新侧边栏 callback_id
        state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
        nav_callbacks = extract_instance_nav_callbacks(state)
        sidebar_callback_id = ""
        for pin_name, cid in state.callback_ids.items():
            sidebar_callback_id = cid
            break
        if sidebar_callback_id:
            with self._lock:
                self._sidebar_nav_callback_id = sidebar_callback_id
        if nav_callbacks:
            with self._lock:
                self._sidebar_nav_callbacks.update(nav_callbacks)

        # 检查是否有新配置出现（不删除已有配置，避免 UI 闪烁）
        fresh_names = extract_instance_names(state)
        with self._lock:
            existing = set(self.configs)
            for name in fresh_names:
                if name not in existing:
                    self.configs.append(name)

        # 获取当前配置列表快照
        with self._lock:
            config_names = list(self.configs)

        # 逐配置进入页面并提取状态（保留已有配置列表作为后备）
        any_recovered = False
        for config_name in config_names:
            try:
                self._navigate_to_config(ws, config_name)
                page_state = self._collect_page_messages(ws, COLLECT_TIMEOUT_SECONDS)
                status = extract_config_status(page_state)
                if self._apply_config_status(config_name, status):
                    any_recovered = True
            except Exception as exc:
                self._mark_config_missing(config_name, str(exc))

        with self._lock:
            self.initial_scan_completed = True
            if any_recovered:
                self.connection_state = CONNECTION_STATE_READY
                self.ready = True
            else:
                self.connection_state = CONNECTION_STATE_DEGRADED
                self.ready = False

    def _record_transport_failure(self, exc):
        """记录传输异常并按阈值暂停。"""
        with self._lock:
            self.failure_count += 1
            self.last_transport_error = str(exc)
            self.transport_available = False
            if self.failure_count >= TRANSPORT_FAILURE_THRESHOLD:
                self.connection_state = CONNECTION_STATE_PAUSED
                self.ready = False
                self.pause_until = time.monotonic() + PAUSE_SECONDS
                self.consecutive_degraded_count += 1
            else:
                self.connection_state = CONNECTION_STATE_DEGRADED


_manager = None
_manager_lock = threading.Lock()


def get_persistent_manager():
    """返回进程级 WebSocket 通讯管理器。"""
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = WebSocketCommManager({})
        return _manager


@dataclass
class PyWebIOMessage:
    """PyWebIO 服务端消息。"""

    command: str
    spec: Any = field(default_factory=dict)
    task_id: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class PyWebIOPageState:
    """PyWebIO 页面状态。"""

    session_id: str = ""
    task_ids: set = field(default_factory=set)
    callback_ids: dict = field(default_factory=dict)
    outputs: list = field(default_factory=list)
    inputs: list = field(default_factory=list)
    scripts: list = field(default_factory=list)
    current_scope: str = ""

    def apply_message(self, message):
        """合并 PyWebIO 消息到页面状态。"""
        if message.task_id:
            self.task_ids.add(message.task_id)
        if message.command == "set_session_id":
            self.session_id = str(message.spec or "") if isinstance(message.spec, str) else ""
        elif message.command == "pin_onchange":
            if isinstance(message.spec, dict):
                name = str(message.spec.get("name", "") or "")
                callback_id = str(message.spec.get("callback_id", "") or "")
                if name and callback_id:
                    self.callback_ids[name] = callback_id
        elif message.command == "output":
            output = message.spec
            if isinstance(output, dict) and self.current_scope and "scope" not in output:
                output = dict(output)
                output["scope"] = self.current_scope
            self.outputs.append(output)
        elif message.command == "input":
            self.inputs.append(message.spec)
        elif message.command == "run_script":
            self.scripts.append(message.spec)
        elif message.command == "output_ctl":
            self._apply_output_ctl(message.spec)

    def _apply_output_ctl(self, spec):
        """应用 output_ctl 到 outputs。"""
        if not isinstance(spec, dict):
            return
        set_scope = str(spec.get("set_scope", "") or "")
        if set_scope:
            self.current_scope = set_scope if set_scope.startswith("#") else f"#{set_scope}"
            if spec.get("if_exist") == "clear":
                self._clear_scope(self.current_scope)
            return
        clear_scope = str(spec.get("clear", "") or "")
        if clear_scope:
            self._clear_scope(clear_scope)
            return
        scope = str(spec.get("scope", "") or "")
        method = str(spec.get("method", "") or "").lower()
        data = spec.get("data")
        if not scope:
            return
        if method == "append":
            if data is not None:
                self.outputs.append(data)
            return
        self._clear_scope(scope)
        if method == "replace" and data is not None:
            self.outputs.append(data)

    def _clear_scope(self, scope):
        """清理指定 PyWebIO scope 的输出。"""
        normalized = scope if str(scope).startswith("#") else f"#{scope}"
        raw = normalized[1:]
        self.outputs = [
            item for item in self.outputs
            if not isinstance(item, dict)
            or normalized not in _scope_identity(item)
            and raw not in _scope_identity(item)
        ]


def parse_pywebio_message(raw):
    """解析 PyWebIO 原始消息。"""
    if not isinstance(raw, dict):
        return PyWebIOMessage("", {}, "", {})
    return PyWebIOMessage(
        command=str(raw.get("command", "") or ""),
        spec=raw.get("spec"),  # 保留原始类型（可能是 dict 或字符串）
        task_id=str(raw.get("task_id", "") or ""),
        raw=dict(raw),
    )


START_BUTTON_LABELS = ("启动", "啟動", "実行", "start")
STOP_BUTTON_LABELS = ("停止", "中止", "stop")


def _flatten_text(value):
    """提取嵌套结构中的可见文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(
            _flatten_text(item)
            for key, item in value.items()
            if key not in {"scope", "dom_id", "callback_id", "type"}
        )
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _walk_dicts(value):
    """遍历嵌套结构中的所有 dict 节点。"""
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _walk_dicts(item)


def _scope_identity(value):
    """返回 PyWebIO 输出节点关联的 scope 标识文本。"""
    if not isinstance(value, dict):
        return ""
    parts = []
    for key in ("scope", "dom_id", "set_scope", "container", "clear"):
        raw = value.get(key)
        if raw:
            parts.append(str(raw))
    return " ".join(parts)


def _extract_buttons(value):
    """遍历嵌套结构中的 PyWebIO buttons 节点。"""
    for item in _walk_dicts(value):
        buttons = item.get("buttons")
        if isinstance(buttons, list):
            yield item, buttons


def extract_instance_names(state):
    """从侧边栏输出提取配置名。"""
    names = []
    seen = set()
    for output in state.outputs:
        if not isinstance(output, dict):
            continue
        if "alas-instance-" not in _scope_identity(output):
            continue
        found_button = False
        for button_group, buttons in _extract_buttons(output):
            if "alas-instance-" not in _scope_identity(button_group):
                continue
            found_button = True
            for button in buttons:
                if not isinstance(button, dict):
                    continue
                name = str(button.get("label", "") or "").strip()
                if name and name not in seen:
                    seen.add(name)
                    names.append(name)
        if not found_button:
            name = str(output.get("content", "") or "").strip()
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def extract_instance_nav_callbacks(state):
    """从侧边栏按钮输出提取配置导航 callback。"""
    callbacks = {}
    for output in state.outputs:
        if not isinstance(output, dict):
            continue
        if "alas-instance-" not in _scope_identity(output):
            continue
        for button_group, buttons in _extract_buttons(output):
            if "alas-instance-" not in _scope_identity(button_group):
                continue
            callback_id = str(button_group.get("callback_id", "") or "")
            if not callback_id:
                continue
            for button in buttons:
                if not isinstance(button, dict):
                    continue
                name = str(button.get("label", "") or "").strip()
                if not name:
                    continue
                callbacks[name] = (callback_id, button.get("value"))
    return callbacks


def extract_config_status(state):
    """从目标配置页提取配置状态。"""
    header_text = ""
    scheduler_text = ""
    for output in state.outputs:
        if not isinstance(output, dict):
            continue
        scope = _scope_identity(output)
        text = _flatten_text(output).lower()
        if "header_status" in scope:
            header_text += " " + text
        if "scheduler_btn" in scope:
            scheduler_text += " " + text
    if any(label in header_text for label in ("运行中", "running")):
        return "running"
    if any(label in header_text for label in ("空闲", "idle", "未运行")):
        return "idle"
    if any(label in header_text for label in ("错误", "error")):
        return "error"
    if any(label in header_text for label in ("更新中", "update")):
        return "update"
    if any(label in header_text for label in ("未连接", "disconnected")):
        return "disconnected"
    if any(label.lower() in scheduler_text for label in STOP_BUTTON_LABELS):
        return "running"
    if any(label.lower() in scheduler_text for label in START_BUTTON_LABELS):
        return "idle"
    return ""


def _extract_button_callback_from_content(content, target_labels):
    """从页面输出内容中查找匹配目标标签的按钮并提取 callback_id。

    Args:
        content: PyWebIO 输出内容列表。
        target_labels: 目标按钮标签元组。

    Returns:
        str: callback_id，未找到时返回空字符串。
    """
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("tag") != "button":
            continue

        label = _flatten_text(item.get("content", "")).strip().lower()
        if not any(t.lower() == label for t in target_labels):
            continue

        if _is_button_disabled(item):
            continue

        # 方式一：直接从按钮 dict 获取 callback_id
        cid = str(item.get("callback_id", "") or "")
        if cid:
            return cid

        # 方式二：从 attributes 获取
        attrs = item.get("attributes")
        if isinstance(attrs, dict):
            cid = str(attrs.get("callback_id", "") or "")
            if cid:
                return cid

            # 方式三：从 onclick 属性提取
            onclick = str(attrs.get("onclick", "") or "")
            if onclick:
                cid = _parse_callback_id_from_onclick(onclick)
                if cid:
                    return cid

        # 方式四：从内嵌 scope 的 callback_id 查找
        sub_content = item.get("content")
        if isinstance(sub_content, (list, tuple)):
            for sub in sub_content:
                if isinstance(sub, dict):
                    nested_cid = str(sub.get("callback_id", "") or "")
                    if nested_cid:
                        return nested_cid

    return ""


_CALLBACK_ID_RE = re.compile(
    r"""(?:trigger_callback_id|trigger_callback)\s*\([^)]*["']([^"']+)["']\s*\)""",
    re.IGNORECASE,
)


def _extract_last_callback_id_from_onclick(onclick):
    """从 onclick 中提取双参形式的最后一个 callback_id。

    对 trigger_callback("task", "abc123") 这样的双参调用，
    正则默认从左捕获会取到第一个参数。此函数返回最后一个匹配的引号参数，
    即目标 callback_id。
    """
    matches = re.findall(
        r"""(?:trigger_callback_id|trigger_callback)\s*\([^)]*["']([^"']+)["']\s*\)""",
        onclick,
        re.IGNORECASE,
    )
    if matches:
        return matches[-1]
    return ""


def _parse_callback_id_from_onclick(onclick):
    """从 onclick JavaScript 字符串中解析 callback_id。

    支持格式：
        WebIO.trigger_callback_id("abc123")           —— 单参，取第一个匹配
        scope.trigger_callback("task", "abc123")      —— 双参，取最后一个匹配

    Args:
        onclick: onclick 属性字符串。

    Returns:
        str: callback_id，未匹配时返回空字符串。
    """
    # trigger_callback 双参形式：取最后一个引号参数（目标 callback_id）
    if "trigger_callback(" in onclick.lower() or "trigger_callback (" in onclick.lower():
        return _extract_last_callback_id_from_onclick(onclick)
    # trigger_callback_id 单参形式：取第一个匹配
    match = _CALLBACK_ID_RE.search(onclick)
    if match:
        return match.group(1)
    return ""


def _is_button_disabled(button):
    """判断按钮是否禁用。"""
    if not isinstance(button, dict):
        return False
    if bool(button.get("disabled", False)):
        return True
    attrs = button.get("attributes")
    if isinstance(attrs, dict) and attrs.get("disabled"):
        return True
    return False
