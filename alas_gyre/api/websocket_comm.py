#!/usr/bin/env python3
# -_- coding: utf-8 -_-

from dataclasses import dataclass
from dataclasses import field
import threading
import time

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
            if self.connection_state == CONNECTION_STATE_STOPPED:
                self.connection_state = CONNECTION_STATE_CONNECTING

    def stop(self):
        """停止后台通讯线程。"""
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
        """刷新单个配置状态。"""
        raise WebSocketCommError("not_started")

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
        return self.get_snapshot()


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
    spec: dict = field(default_factory=dict)
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

    def apply_message(self, message):
        """合并 PyWebIO 消息到页面状态。"""
        if message.task_id:
            self.task_ids.add(message.task_id)
        if message.command == "set_session_id":
            self.session_id = str(message.spec or "")
        elif message.command == "pin_onchange":
            name = str(message.spec.get("name", "") or "")
            callback_id = str(message.spec.get("callback_id", "") or "")
            if name and callback_id:
                self.callback_ids[name] = callback_id
        elif message.command == "output":
            self.outputs.append(message.spec)
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
        scope = str(spec.get("scope", "") or "")
        method = str(spec.get("method", "") or "").lower()
        data = spec.get("data")
        if not scope:
            return
        if method == "append":
            if data is not None:
                self.outputs.append(data)
            return
        self.outputs = [
            item for item in self.outputs
            if not isinstance(item, dict) or str(item.get("scope", "") or "") != scope
        ]
        if method == "replace" and data is not None:
            self.outputs.append(data)


def parse_pywebio_message(raw):
    """解析 PyWebIO 原始消息。"""
    if not isinstance(raw, dict):
        return PyWebIOMessage("", {}, "", {})
    return PyWebIOMessage(
        command=str(raw.get("command", "") or ""),
        spec=raw.get("spec") if isinstance(raw.get("spec"), dict) else {},
        task_id=str(raw.get("task_id", "") or ""),
        raw=dict(raw),
    )
