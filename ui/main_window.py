import os
import json
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QFrame,
    QVBoxLayout, QHBoxLayout, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal
import threading
import time

from alas_gyre.api.client import api_headers, api_request, gyre_api_url
from alas_gyre.api.connection_policy import normalize_connection_mode
from alas_gyre.api.connection_policy import should_fallback_to_websocket
from alas_gyre.api.connection_policy import should_use_websocket_directly
from alas_gyre.api.websocket_comm import get_persistent_manager
from alas_gyre.core.paths import (
    app_base_dir as app_base_dir, asset_path, config_path,
)
from alas_gyre.core.status import normalize_status
from .window_snap import snap_to_available_screen
from .i18n import get_language, tr
from .message_dialog import ask_confirm, show_info, show_warning
from .window_behavior import install_title_bar_drag, schedule_frameless_stabilize
from .widgets import (
    BottomIconButton,
    ConfigActionButton,
    ConfigDeleteButton,
    MarqueeLabel,
    StatusIndicator,
    WindowButton,
    build_bottom_icon,
    load_bottom_icon,
)



__all__ = [
    "AlasConsole",
    "BottomIconButton",
    "CardWidget",
    "ConfigActionButton",
    "ConfigDeleteButton",
    "MainConfigRow",
    "StatusIndicator",
    "WindowButton",
    "app_base_dir",
    "asset_path",
    "build_bottom_icon",
    "config_path",
    "get_status_text",
    "load_bottom_icon",
    "normalize_status",
]


try:
    from shiboken6 import isValid
except Exception:
    def isValid(widget):
        return widget is not None


MAIN_CARD_WIDTH = 294
MAIN_TITLE_HEIGHT = 30
MAIN_BOTTOM_HEIGHT = 40
MAIN_ROW_HEIGHT = 46
MAIN_ROW_SPACING = 2
MAIN_LIST_TOP_MARGIN = 8
MAIN_LIST_BOTTOM_MARGIN = 6
MAIN_VISIBLE_ROWS = 3
MAIN_LIST_HEIGHT = (
    MAIN_LIST_TOP_MARGIN
    + MAIN_LIST_BOTTOM_MARGIN
    + MAIN_VISIBLE_ROWS * MAIN_ROW_HEIGHT
    + max(MAIN_VISIBLE_ROWS - 1, 0) * MAIN_ROW_SPACING
    + 8
)
MAIN_CARD_HEIGHT = MAIN_TITLE_HEIGHT + MAIN_LIST_HEIGHT + MAIN_BOTTOM_HEIGHT


def get_status_text(status):
    return tr(normalize_status(status))


def safe_emit_signal(signal, *args):
    """安全发射 Qt 信号，忽略已删除信号源异常。"""
    try:
        signal.emit(*args)
        return True
    except RuntimeError:
        return False


class MainConfigRow(QWidget):
    btn_enable_signal = Signal(bool)

    def __init__(self, config_name, main_card, parent=None):
        super().__init__(parent)
        self.config_name = config_name
        self.main_card = main_card
        self.current_status = None
        self.current_task = ""
        self.setFixedHeight(46)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 2, 6, 2)
        layout.setSpacing(10)

        self.statusIndicator = StatusIndicator()
        layout.addWidget(self.statusIndicator, alignment=Qt.AlignVCenter)

        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self.statusLabel = MarqueeLabel()
        self.statusLabel.setObjectName("rowStatusLabel")
        self.statusLabel.setAlignment(Qt.AlignVCenter)

        self.taskLabel = MarqueeLabel()
        self.taskLabel.setObjectName("rowTaskLabel")
        self.taskLabel.setAlignment(Qt.AlignVCenter)
        font = self.taskLabel.font()
        font.setPointSize(font.pointSize() - 2)
        self.taskLabel.setFont(font)
        self.taskLabel.setStyleSheet("color: #888888;")
        self.taskLabel.hide()

        vbox.addWidget(self.statusLabel)
        vbox.addWidget(self.taskLabel)

        layout.addLayout(vbox, stretch=1)

        self.deleteBtn = ConfigDeleteButton()
        self.deleteBtn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.deleteBtn)

        self.toggleBtn = ConfigActionButton()
        self.toggleBtn.clicked.connect(self._on_toggle_clicked)
        self.btn_enable_signal.connect(self.toggleBtn.setEnabled)
        layout.addWidget(self.toggleBtn)

        self.update_status("idle", "")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_card.set_current_config(self.config_name)
            event.accept()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_label()

    def _refresh_label(self):
        if (
            getattr(self.main_card, "_ws_initial_scanning_placeholder", False)
            and self.config_name == self.main_card.current_config
        ):
            full_text = tr("app_scanning")
        else:
            full_text = f"{self.config_name}: {get_status_text(self.current_status)}"
        self.statusLabel.set_marquee_text(full_text)
        if self._should_show_task():
            self.taskLabel.set_marquee_text(self.current_task)
        else:
            self.taskLabel.set_marquee_text("")

    def _should_show_task(self):
        return bool(self.current_task and self.main_card.config.get("show_task_name", False))

    def apply_task_display_setting(self):
        self.taskLabel.setVisible(self._should_show_task())
        self._refresh_label()

    def update_status(self, status, task=""):
        status = normalize_status(status)
        delete_enabled = (
            status != "running"
            and len(self.main_card._configs) > 1
            and not self.main_card._use_websocket_comm()
        )
        if self.current_status == status and getattr(self, "current_task", "") == task:
            if self.deleteBtn.isEnabled() != delete_enabled:
                self.deleteBtn.setEnabled(delete_enabled)
            return

        self.current_status = status
        self.current_task = task
        self.statusIndicator.setStatus(self.current_status)
        self.toggleBtn.set_status(self.current_status)
        self.deleteBtn.setEnabled(delete_enabled)
        self.taskLabel.setVisible(self._should_show_task())
        self._refresh_label()

    def _on_delete_clicked(self):
        if len(self.main_card._configs) <= 1:
            show_info(
                self,
                tr("delete_config_title"),
                tr("delete_config_last"),
            )
            return
        if self.current_status == "running":
            show_warning(
                self,
                tr("delete_config_title"),
                tr("delete_config_running", config=self.config_name),
            )
            return

        if ask_confirm(
            self,
            tr("delete_config_title"),
            tr("delete_config_confirm", config=self.config_name),
            tr("delete_config_action"),
            tr("cancel"),
            danger=True,
        ):
            self.main_card.delete_config(self.config_name)

    def _on_toggle_clicked(self):
        self.main_card.set_current_config(self.config_name)
        self.toggleBtn.setEnabled(False)
        action = "stop" if self.current_status == "running" else "start"

        # 捕获必要引用，避免后台线程通过 self 访问已销毁控件
        main_card = self.main_card
        config_name = self.config_name
        btn_enable_signal = self.btn_enable_signal

        def send_req():
            try:
                main_card._post_control_action(config_name, action)
            except Exception as e:
                print(f"[Error] Failed to send control command: {e}")
                main_card.status_all_update_signal.emit(
                    {config_name: "disconnected"},
                    {config_name: ""},
                )
                if main_card.current_config == config_name:
                    main_card.status_update_signal.emit("disconnected", "")
                main_card.control_error_signal.emit(action, tr("control_connect_failed"))
            finally:
                safe_emit_signal(btn_enable_signal, True)

        threading.Thread(target=send_req, daemon=True).start()

def build_websocket_ui_snapshot(snapshot, current_config=""):
    """构造 WebSocket 模式下供 UI 使用的状态快照。"""
    configs = [str(config_name) for config_name in snapshot.get("configs", [])]
    statuses = {
        str(config_name): normalize_status(status)
        for config_name, status in snapshot.get("statuses", {}).items()
    }
    tasks = {
        str(config_name): str(task)
        for config_name, task in snapshot.get("tasks", {}).items()
    }
    state = snapshot.get("connection_state", "")
    scanning_states = {"connecting", "initial_scanning"}
    current_fallback = "scanning" if state in scanning_states else "disconnected"
    if not configs:
        # 无真实配置时返回空列表和扫描/断开状态，不构造伪配置
        current_status = current_fallback
        current_task = ""
        return configs, statuses, tasks, current_status, current_task
    current_status = statuses.get(current_config, current_fallback)
    current_task = tasks.get(current_config, "")
    return configs, statuses, tasks, current_status, current_task


class CardWidget(QFrame):
    """Main card"""
    status_update_signal = Signal(str, str)
    configs_update_signal = Signal(list)
    status_all_update_signal = Signal(dict, dict)
    config_delete_result_signal = Signal(bool, str, str, list, str)
    control_error_signal = Signal(str, str)
    websocket_fallback_notice_signal = Signal()
    poll_interval_update_signal = Signal(int)
    ws_initial_scanning_placeholder_signal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)

        self.config = {
            "ip": "127.0.0.1",
            "port": "22267",
            "auto_start": False,
            "always_on_top": False,
            "api_token": "",
            "mini_click_through": False,
            "show_task_name": False,
            "mini_opacity": 100,
            "lang": get_language(),
            "setup_completed": False,
            "connection_mode": "auto",
            "websocket_poll_interval": 3,
            "websocket_poll_mode": "round_robin",
        }

        self.config_path = config_path()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                self.config.update(loaded_config)
                self.config["connection_mode"] = normalize_connection_mode(self.config)
                if "setup_completed" not in loaded_config:
                    self.config["setup_completed"] = True
            except Exception as e:
                print(f"[Warning] Failed to read {self.config_path}: {e}")

        self._status = "idle" # idle, running, error, disconnected
        self._task = ""
        self._configs = ["alas"]
        self.current_config = self.config.get("current_config", "alas")
        self._configs[0] = self.current_config
        self._configs_fetching = False
        self._configs_last_fetch_at = 0.0
        self._configs_fetch_interval = 15.0
        self._polling_status = False
        self._poll_lock = threading.Lock()
        self._runtime_connection_lock = threading.Lock()
        self._statuses = {}
        self._tasks = {}
        self._ws_initial_scanning_placeholder = False
        self.rows = {}

        self._config_idx = 0
        self._runtime_connection = "websocket" if self._use_websocket_comm() else "overlay"
        self._overlay_recovery_last_check_at = None
        self._overlay_recovery_failure_count = 0
        self._overlay_recovery_backoff_steps = (15, 30, 60, 90, 180)
        self._websocket_shutdown_deadline = None

        self._build_ui()

        self.status_update_signal.connect(self._update_status_ui)
        self.configs_update_signal.connect(self._on_configs_updated)
        self.status_all_update_signal.connect(self._on_status_all_updated)
        self.config_delete_result_signal.connect(self._on_config_delete_result)
        self.control_error_signal.connect(self._on_control_error)
        self.websocket_fallback_notice_signal.connect(self._on_websocket_fallback_notice)
        self.poll_interval_update_signal.connect(self._apply_poll_interval)
        self.ws_initial_scanning_placeholder_signal.connect(
            self._set_ws_initial_scanning_placeholder
        )

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._start_poll_thread)
        self.poll_timer.start(3000)

        from PySide6.QtCore import QTimer as CoreQTimer
        CoreQTimer.singleShot(50, self._start_poll_thread)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.windowCtrlBg = QWidget(self)
        self.windowCtrlBg.setObjectName("compactCtrlBg")
        self.windowCtrlBg.setAttribute(Qt.WA_StyledBackground, True)
        self.windowCtrlBg.setFixedHeight(30)
        install_title_bar_drag(self.window(), self.windowCtrlBg)
        ctrl_layout = QHBoxLayout(self.windowCtrlBg)
        ctrl_layout.setContentsMargins(20, 0, 8, 0)
        ctrl_layout.setSpacing(0)

        self.titleLabel = QLabel("Alas-Gyre", self.windowCtrlBg)
        self.titleLabel.setObjectName("settingsTitle")
        ctrl_layout.addWidget(self.titleLabel)
        ctrl_layout.addStretch()

        self.miniDot = WindowButton("minimize")
        self.miniDot.mousePressEvent = self._minimize_from_top
        self.closeDot = WindowButton("close")
        self.closeDot.mousePressEvent = self._close_from_top
        ctrl_layout.addWidget(self.miniDot, alignment=Qt.AlignVCenter)
        ctrl_layout.addWidget(self.closeDot, alignment=Qt.AlignVCenter)
        main_layout.addWidget(self.windowCtrlBg)

        self.configScroll = QScrollArea(self)
        self.configScroll.setObjectName("configScrollArea")
        self.configScroll.setAttribute(Qt.WA_StyledBackground, True)
        self.configScroll.setWidgetResizable(True)
        self.configScroll.setFrameShape(QFrame.NoFrame)
        self.configScroll.setFocusPolicy(Qt.NoFocus)
        self.configScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.configScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.configListBg = QWidget()
        self.configListBg.setObjectName("configListBg")
        self.configListBg.setAttribute(Qt.WA_StyledBackground, True)
        list_layout = QVBoxLayout(self.configListBg)
        list_layout.setContentsMargins(10, 8, 10, 6)
        list_layout.setSpacing(2)
        self.rows_layout = list_layout
        self.configScroll.setWidget(self.configListBg)
        self.configScroll.setFixedHeight(MAIN_LIST_HEIGHT)
        main_layout.addWidget(self.configScroll)

        self.bottomBg = QWidget(self)
        self.bottomBg.setObjectName("mainBottomBg")
        self.bottomBg.setAttribute(Qt.WA_StyledBackground, True)
        self.bottomBg.setFixedHeight(40)
        bot_layout = QHBoxLayout(self.bottomBg)
        bot_layout.setContentsMargins(24, 0, 24, 0)
        bot_layout.setSpacing(0)

        self.setIcon = BottomIconButton("settings")
        self.homeIcon = BottomIconButton("home")
        self.floatIcon = BottomIconButton("float")
        self.logIcon = BottomIconButton("log")

        self.setIcon.setToolTip(tr("settings_btn_tip"))
        self.homeIcon.setToolTip(tr("home_btn_tip"))
        self.floatIcon.setToolTip(tr("float_btn_tip"))
        self.logIcon.setToolTip(tr("log_btn_tip"))

        bot_layout.addWidget(self.setIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.homeIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.floatIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.logIcon)

        self.setIcon.mousePressEvent = lambda e: self._on_icon_click("settings", self.setIcon)
        self.homeIcon.mousePressEvent = lambda e: self._on_icon_click("home", self.homeIcon)
        self.floatIcon.mousePressEvent = lambda e: self._on_icon_click("minimize", self.floatIcon)
        self.logIcon.mousePressEvent = lambda e: self._on_icon_click("log", self.logIcon)

        main_layout.addWidget(self.bottomBg)
        self._rebuild_rows()

    def retranslate_ui(self):
        self.setIcon.setToolTip(tr("settings_btn_tip"))
        self.homeIcon.setToolTip(tr("home_btn_tip"))
        self.floatIcon.setToolTip(tr("float_btn_tip"))
        self.logIcon.setToolTip(tr("log_btn_tip"))
        self._rebuild_rows()

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[Error] Failed to write {self.config_path}: {e}")
            return False

    def apply_task_display_settings(self):
        for row in self.rows.values():
            row.apply_task_display_setting()

    def _sync_window_size(self, visible_count=None):
        _ = visible_count
        # The main window is deliberately not resized by the number of configs.
        # Config changes now only affect the scroll area's content. This keeps
        # the bottom menu visible after add/delete/status refresh operations.
        self.configScroll.setFixedHeight(MAIN_LIST_HEIGHT)
        self.setFixedSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)
        self.updateGeometry()

        top_window = self.window()
        if top_window and top_window is not self:
            top_window.setMinimumSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)
            top_window.setMaximumSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)
            top_window.resize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)
            top_window.updateGeometry()

            # Re-apply after the current event pass. This protects the compact
            # frameless window from stale fixed-size state on Windows.
            QTimer.singleShot(
                0,
                lambda: isValid(top_window)
                and top_window.setFixedSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT),
            )

    def _rebuild_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.rows.clear()

        visible_configs = list(self._configs)
        if self.current_config and self.current_config not in visible_configs:
            visible_configs.insert(0, self.current_config)

        for config_name in visible_configs:
            row = MainConfigRow(config_name, self)
            self.rows_layout.addWidget(row)
            self.rows[config_name] = row
            if config_name in self._statuses:
                row.update_status(self._statuses[config_name], self._tasks.get(config_name, ""))
        self.rows_layout.addStretch()
        self._sync_window_size(len(visible_configs))

    def set_current_config(self, config_name):
        if not config_name or self.current_config == config_name:
            return
        previous_config = self.current_config
        self.current_config = config_name
        self.config["current_config"] = self.current_config
        self._save_config()
        if self.current_config not in self.rows:
            self._rebuild_rows()
        for row_config in (previous_config, self.current_config):
            row = self.rows.get(row_config)
            if row is not None:
                row._refresh_label()
        if hasattr(self, "log_dialog") and self.log_dialog.isVisible():
            self.log_dialog.set_config(self.current_config)

    def delete_config(self, config_name):
        threading.Thread(target=self._delete_config_task, args=(config_name,), daemon=True).start()

    def _delete_config_task(self, config_name):
        try:
            url = gyre_api_url(self.config, "configs")
            resp = api_request("DELETE",
                url,
                params={"config": config_name},
                headers=api_headers(self.config),
                timeout=5,
            )
            try:
                data = resp.json()
            except Exception:
                data = {}

            if resp.status_code == 200:
                configs = data.get("configs", [])
                default = data.get("default", "")
                self.config_delete_result_signal.emit(True, config_name, "", configs, default)
                return

            message = data.get("message") or data.get("error") or resp.text
            self.config_delete_result_signal.emit(False, config_name, message, [], "")
        except Exception as exc:
            self.config_delete_result_signal.emit(False, config_name, str(exc), [], "")

    def _on_config_delete_result(self, success, config_name, message, configs, default_config):
        if not success:
            show_warning(
                self,
                tr("delete_config_title"),
                tr("delete_config_failed", config=config_name, error=message),
            )
            return

        self._statuses.pop(config_name, None)
        self._tasks.pop(config_name, None)
        self._configs = [str(config) for config in configs if str(config)] or [
            config for config in self._configs if config != config_name
        ]
        if not self._configs:
            self._configs = ["alas"]

        if self.current_config == config_name:
            self.current_config = default_config if default_config in self._configs else self._configs[0]
            self.config["current_config"] = self.current_config
            self._save_config()

        self._rebuild_rows()
        if hasattr(self, "mini_dialog") and self.mini_dialog.isVisible():
            self.mini_dialog.rebuild_rows()
        if hasattr(self, "log_dialog") and self.log_dialog.isVisible():
            self.log_dialog.set_configs(self._configs, self.current_config)
            self.log_dialog.set_config(self.current_config)

        show_info(
            self,
            tr("delete_config_title"),
            tr("delete_config_success", config=config_name),
        )
        self._start_poll_thread()

    def _use_websocket_comm(self):
        """判断是否直接使用 WebSocket 通讯。"""
        return should_use_websocket_directly(self.config)

    def _reset_runtime_connection(self):
        """按当前配置重置运行时连接来源和降级提示状态。"""
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                self._runtime_connection = "websocket" if self._use_websocket_comm() else "overlay"
                self._websocket_fallback_notice_shown = False
                self._overlay_recovery_last_check_at = None
                self._overlay_recovery_failure_count = 0
                self._websocket_shutdown_deadline = None
                is_overlay = (self._runtime_connection == "overlay")
        else:
            self._runtime_connection = "websocket" if self._use_websocket_comm() else "overlay"
            self._websocket_fallback_notice_shown = False
            self._overlay_recovery_last_check_at = None
            self._overlay_recovery_failure_count = 0
            self._websocket_shutdown_deadline = None
            is_overlay = (self._runtime_connection == "overlay")
        if is_overlay and hasattr(self, "poll_timer"):
            self.poll_timer.setInterval(3000)

    def _mark_websocket_fallback(self):
        """标记已降级到 WebSocket，并在当前降级周期只提示一次。"""
        should_notify = False
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                if getattr(self, "_runtime_connection", "overlay") != "websocket_fallback":
                    print("[Log] Overlay API 不可用，已自动切换到 WebSocket 通讯")
                    self._overlay_recovery_last_check_at = None
                    self._overlay_recovery_failure_count = 0
                    self._websocket_shutdown_deadline = None
                self._runtime_connection = "websocket_fallback"
                if not getattr(self, "_websocket_fallback_notice_shown", False):
                    self._websocket_fallback_notice_shown = True
                    should_notify = True
        else:
            if getattr(self, "_runtime_connection", "overlay") != "websocket_fallback":
                print("[Log] Overlay API 不可用，已自动切换到 WebSocket 通讯")
                self._overlay_recovery_last_check_at = None
                self._overlay_recovery_failure_count = 0
                self._websocket_shutdown_deadline = None
            self._runtime_connection = "websocket_fallback"
            if not getattr(self, "_websocket_fallback_notice_shown", False):
                self._websocket_fallback_notice_shown = True
                should_notify = True
        if should_notify:
            safe_emit_signal(self.websocket_fallback_notice_signal)

    def _overlay_recovery_next_interval(self):
        """返回下一次 Overlay 恢复探测间隔秒数。"""
        steps = getattr(self, "_overlay_recovery_backoff_steps", (15, 30, 60, 90, 180))
        failure_count = max(0, int(getattr(self, "_overlay_recovery_failure_count", 0)))
        index = max(0, failure_count - 1)
        index = min(index, len(steps) - 1)
        return steps[index]

    def _overlay_recovery_due(self):
        """判断当前 poll tick 是否应执行 Overlay 恢复探测。"""
        last_check_at = getattr(self, "_overlay_recovery_last_check_at", None)
        if last_check_at is None:
            return True
        return time.monotonic() - last_check_at >= self._overlay_recovery_next_interval()

    def _reset_overlay_recovery_state(self):
        """清空 Overlay 恢复探测状态。"""
        self._overlay_recovery_last_check_at = None
        self._overlay_recovery_failure_count = 0

    def _mark_overlay_recovered(self):
        """切回 Overlay 并启动 WebSocket 延迟关闭窗口。"""
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                self._runtime_connection = "overlay"
                self._reset_overlay_recovery_state()
                self._websocket_shutdown_deadline = time.monotonic() + 30
        else:
            self._runtime_connection = "overlay"
            self._reset_overlay_recovery_state()
            self._websocket_shutdown_deadline = time.monotonic() + 30
        print("[Log] Overlay API 可用，自动切回 Overlay API")

    def _mark_overlay_recovery_failed(self):
        """记录恢复探测失败并推进退避。"""
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                self._overlay_recovery_last_check_at = time.monotonic()
                self._overlay_recovery_failure_count = min(
                    int(getattr(self, "_overlay_recovery_failure_count", 0)) + 1,
                    len(getattr(self, "_overlay_recovery_backoff_steps", (15, 30, 60, 90, 180))),
                )
        else:
            self._overlay_recovery_last_check_at = time.monotonic()
            self._overlay_recovery_failure_count = min(
                int(getattr(self, "_overlay_recovery_failure_count", 0)) + 1,
                len(getattr(self, "_overlay_recovery_backoff_steps", (15, 30, 60, 90, 180))),
            )
        print(f"[Log] Overlay API 不可用，下次查询 {self._overlay_recovery_next_interval()}s")

    def _check_websocket_shutdown_deadline(self):
        """Overlay 恢复稳定后延迟关闭 WebSocket manager。"""
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                deadline = getattr(self, "_websocket_shutdown_deadline", None)
                if deadline is None:
                    return
                if time.monotonic() < deadline:
                    return
                if getattr(self, "_runtime_connection", "overlay") != "overlay":
                    self._websocket_shutdown_deadline = None
                    return
                if self._use_websocket_comm():
                    self._websocket_shutdown_deadline = None
                    return
        else:
            deadline = getattr(self, "_websocket_shutdown_deadline", None)
            if deadline is None:
                return
            if time.monotonic() < deadline:
                return
            if getattr(self, "_runtime_connection", "overlay") != "overlay":
                self._websocket_shutdown_deadline = None
                return
            if self._use_websocket_comm():
                self._websocket_shutdown_deadline = None
                return
        manager = get_persistent_manager()
        snapshot = manager.get_status_all()
        if self._websocket_control_active(snapshot):
            return
        # 异步关闭 manager，避免阻塞 poll 线程
        try:
            threading.Thread(target=manager.stop, daemon=True).start()
        except Exception:
            pass
        if lock is not None:
            with lock:
                self._websocket_shutdown_deadline = None
        else:
            self._websocket_shutdown_deadline = None

    def _websocket_control_active(self, snapshot):
        """判断 WebSocket manager 是否存在控制活动。"""
        if snapshot.get("pending_controls"):
            return True
        active_targets = snapshot.get("active_control_targets", {})
        if active_targets:
            return True
        statuses = snapshot.get("statuses", {}) or {}
        for status in statuses.values():
            if normalize_status(status) == "queued":
                return True
        return False

    def _try_overlay_recovery(self, snapshot):
        """在 WebSocket fallback 轮询后尝试恢复 Overlay。"""
        if should_use_websocket_directly(self.config):
            return
        should_probe = False
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                if getattr(self, "_runtime_connection", "overlay") != "websocket_fallback":
                    return
                if self._websocket_control_active(snapshot):
                    return
                if not self._overlay_recovery_due():
                    return
                should_probe = True
        else:
            if getattr(self, "_runtime_connection", "overlay") != "websocket_fallback":
                return
            if self._websocket_control_active(snapshot):
                return
            if not self._overlay_recovery_due():
                return
            should_probe = True
        if self._probe_overlay_recovery(snapshot):
            self._mark_overlay_recovered()
            return
        self._mark_overlay_recovery_failed()

    def _overlay_probe_config(self, snapshot):
        """选择旧状态接口恢复验证使用的配置名。"""
        current = str(getattr(self, "current_config", "") or "").strip()
        if current:
            return current
        for config_name in snapshot.get("configs", []) or []:
            config_name = str(config_name or "").strip()
            if config_name:
                return config_name
        return ""

    def _probe_overlay_recovery(self, snapshot):
        """双层验证 Overlay API 是否已恢复。"""
        try:
            health = api_request(
                "GET",
                gyre_api_url(self.config, "health"),
                headers=api_headers(self.config),
                timeout=1.0,
            )
            if health.status_code != 200:
                return False

            status_all = api_request(
                "GET",
                gyre_api_url(self.config, "status_all"),
                headers=api_headers(self.config),
                timeout=1.0,
            )
            if status_all.status_code == 200:
                status_all.json()
                return True
            if status_all.status_code != 404:
                return False

            probe_config = self._overlay_probe_config(snapshot)
            if not probe_config:
                return False
            status = api_request(
                "GET",
                gyre_api_url(self.config, "status"),
                params={"config": probe_config},
                headers=api_headers(self.config),
                timeout=1.0,
            )
            if status.status_code != 200:
                return False
            status.json()
            return True
        except Exception:
            return False

    def _is_ws_initial_scanning_placeholder(self, snapshot):
        """判断当前 WebSocket 快照是否应显示初始化扫描占位文案。"""
        return (
            snapshot.get("connection_state") in {"connecting", "initial_scanning"}
            and not snapshot.get("configs")
            and not snapshot.get("statuses")
            and bool(getattr(self, "_configs", None))
        )

    def _set_ws_initial_scanning_placeholder(self, enabled):
        """更新主界面 WebSocket 初始化扫描占位显示状态。"""
        enabled = bool(enabled)
        if getattr(self, "_ws_initial_scanning_placeholder", False) == enabled:
            return
        self._ws_initial_scanning_placeholder = enabled
        row = self.rows.get(self.current_config)
        if row is not None:
            row._refresh_label()

    def _is_websocket_snapshot_usable(self, snapshot):
        """判断 WebSocket 快照是否可用（连接状态有效）。"""
        return snapshot.get("connection_state") in {"connecting", "initial_scanning", "ready", "degraded"}

    def _poll_via_websocket_manager(self, fallback=False):
        """通过 WebSocket 管理器轮询状态。

        Args:
            fallback: 是否为降级模式（设置 _runtime_connection 为 websocket_fallback）

        Returns:
            bool: 快照是否成功获取并可用
        """
        manager = get_persistent_manager()
        manager.update_config(self.config)
        snapshot = manager.get_status_all()
        if snapshot.get("connection_state") == "stopped":
            manager.start()
            snapshot = manager.get_status_all()
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                was_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        else:
            was_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        if fallback and not self._is_websocket_snapshot_usable(snapshot):
            self.ws_initial_scanning_placeholder_signal.emit(False)
            return False
        if fallback:
            self._mark_websocket_fallback()
        self.ws_initial_scanning_placeholder_signal.emit(
            self._is_ws_initial_scanning_placeholder(snapshot)
        )
        configs, statuses, tasks, current_status, current_task = build_websocket_ui_snapshot(
            snapshot,
            self.current_config,
        )
        if configs:
            self.configs_update_signal.emit(configs)
        self.status_all_update_signal.emit(statuses, tasks)
        self.status_update_signal.emit(current_status, current_task)
        # 消费控制错误——通知 UI 控制失败（一次性消费，避免重复触发）
        control_errors = manager.pop_control_errors()
        for config_name, error_msg in control_errors.items():
            if config_name not in statuses or statuses.get(config_name) == "queued":
                self.status_all_update_signal.emit({config_name: "disconnected"}, {config_name: error_msg or ""})
                if config_name == self.current_config:
                    self.status_update_signal.emit("disconnected", error_msg or "")
        if fallback and was_fallback:
            self._try_overlay_recovery(snapshot)
        return True

    def _queue_websocket_control(self, config_name, action):
        """通过 WebSocket 管理器发送控制命令。

        Args:
            config_name: 配置名称
            action: 控制动作，如 start/stop

        Returns:
            dict: post_action 的结果
        """
        manager = get_persistent_manager()
        manager.update_config(self.config)
        snapshot = manager.get_status_all()
        if snapshot.get("connection_state") == "stopped":
            manager.start()
            snapshot = manager.get_status_all()
        result = manager.post_action(config_name, action)
        if result.get("queued"):
            self.status_all_update_signal.emit({config_name: "queued"}, {config_name: ""})
            if self.current_config == config_name:
                self.status_update_signal.emit("queued", "")
        return result

    def _post_control_action(self, config_name, action):
        """发送控制命令，支持 Overlay/WebSocket 自动降级。

        Args:
            config_name: 配置名称
            action: 控制动作，如 start/stop

        Returns:
            dict: 包含 status/error 的结果字典
        """
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        else:
            is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        if self._use_websocket_comm() or is_fallback:
            return self._queue_websocket_control(config_name, action)
        try:
            resp = api_request(
                "POST",
                gyre_api_url(self.config, action),
                params={"config": config_name},
                headers=api_headers(self.config),
                timeout=3,
            )
            if resp.status_code == 200:
                status = normalize_status(resp.json().get("status", "idle"))
                self.status_all_update_signal.emit({config_name: status}, {config_name: ""})
                if self.current_config == config_name:
                    self.status_update_signal.emit(status, "")
                return {"status": status}
            failure = self.format_control_http_error(resp)
        except Exception as exc:
            failure = exc
        if should_fallback_to_websocket(self.config, failure):
            self._mark_websocket_fallback()
            return self._queue_websocket_control(config_name, action)
        self.control_error_signal.emit(action, str(failure) or tr("control_connect_failed"))
        return {"error": str(failure)}

    def format_control_http_error(self, resp):
        try:
            data = resp.json()
        except Exception:
            data = {}
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("message") or data.get("error") or "").strip()
        if not detail:
            detail = str(getattr(resp, "text", "") or "").strip()
        if detail:
            return tr("control_http_failed_with_detail", status=resp.status_code, error=detail[:300])
        return tr("control_http_failed", status=resp.status_code)

    def _on_control_error(self, action, message):
        parent = self.window()
        if hasattr(self, "mini_dialog") and self.mini_dialog.isVisible():
            parent = self.mini_dialog
        show_warning(
            parent or self,
            tr("control_failed_title"),
            message or tr("action_failed", error=action),
        )

    def _on_websocket_fallback_notice(self):
        """提示用户当前已自动切换到 WebSocket 通讯。"""
        parent = self.window()
        if hasattr(self, "mini_dialog") and self.mini_dialog.isVisible():
            parent = self.mini_dialog
        show_warning(
            parent or self,
            tr("websocket_fallback_notice_title"),
            tr("websocket_fallback_notice_message"),
        )

    def _apply_poll_interval(self, interval_ms):
        """在主线程安全地更新 poll timer 间隔，避免后台线程跨线程操作 QTimer。"""
        if hasattr(self, "poll_timer") and self.poll_timer.interval() != interval_ms:
            self.poll_timer.setInterval(interval_ms)

    def _forward_drag_press(self, event):
        if self.window():
            self.window().mousePressEvent(event)

    def _forward_drag_move(self, event):
        if self.window():
            self.window().mouseMoveEvent(event)

    def _forward_drag_release(self, event):
        if self.window():
            self.window().mouseReleaseEvent(event)

    def _minimize_to_taskbar(self):
        if self.window():
            self.window().showMinimized()

    def _minimize_from_top(self, event):
        self._minimize_to_taskbar()
        event.accept()

    def _close_from_top(self, event):
        QApplication.quit()
        event.accept()

    def _update_status_ui(self, status, task=""):
        status = normalize_status(status)
        if self._status == status and getattr(self, "_task", "") == task:
            return
        self._status = status
        self._task = task
        if self.current_config in self.rows:
            self.rows[self.current_config].update_status(status, task)
        print(f"[Log] Status sync -> {status} ({self.current_config})")

    def _start_poll_thread(self):
        start_fetch = False
        start_poll = False
        with self._poll_lock:
            if not hasattr(self, "_configs_fetched") and not self._configs_fetching:
                self._configs_fetching = True
                self._configs_last_fetch_at = time.monotonic()
                start_fetch = True
            if not self._polling_status:
                self._polling_status = True
                start_poll = True

        if start_fetch:
            threading.Thread(target=self._fetch_configs_task, daemon=True).start()
        if start_poll:
            threading.Thread(target=self._poll_status_task_guarded, daemon=True).start()

    def _poll_status_task_guarded(self):
        try:
            self._poll_status_task()
            self._check_websocket_shutdown_deadline()
        finally:
            with self._poll_lock:
                self._polling_status = False

    def _fetch_configs_task(self):
        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        else:
            is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        if self._use_websocket_comm() or is_fallback:
            with self._poll_lock:
                self._configs_fetching = False
            return
        try:
            url = gyre_api_url(self.config, "configs")
            resp = api_request("GET", url, headers=api_headers(self.config), timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                configs = data.get("configs", ["alas"])
                if isinstance(configs, list) and configs:
                    self.configs_update_signal.emit(configs)
        except Exception as exc:
            if should_fallback_to_websocket(self.config, exc):
                self._poll_via_websocket_manager(fallback=True)
        finally:
            with self._poll_lock:
                self._configs_fetching = False

    def _on_configs_updated(self, configs):
        self._configs_fetched = True
        new_configs = [str(config) for config in configs if str(config)]
        if not new_configs:
            new_configs = ["alas"]

        old_current_config = self.current_config
        if self.current_config not in new_configs:
            self.current_config = new_configs[0]
            self.config["current_config"] = self.current_config

        configs_changed = new_configs != self._configs
        current_changed = self.current_config != old_current_config
        self._configs = new_configs
        if not (configs_changed or current_changed):
            return

        self._rebuild_rows()

        old_status = self._status
        self._status = None
        self._task = ""
        self._update_status_ui(old_status or "idle", "")

        if hasattr(self, "mini_dialog") and self.mini_dialog.isVisible():
            self.mini_dialog.rebuild_rows()
        if hasattr(self, "log_dialog") and self.log_dialog.isVisible():
            self.log_dialog.set_configs(self._configs, self.current_config)

    def _on_status_all_updated(self, statuses, tasks):
        tasks = {
            str(config_name): str((tasks or {}).get(config_name, "") or "")
            for config_name in statuses
        }
        changed_statuses = {
            config_name: status
            for config_name, status in statuses.items()
            if self._statuses.get(config_name) != status or self._tasks.get(config_name) != tasks.get(config_name)
        }
        self._statuses.update(statuses)
        self._tasks.update(tasks)
        new_configs = [str(config_name) for config_name in statuses if str(config_name) not in self._configs]
        if new_configs:
            self._configs.extend(new_configs)
            self._configs.sort(key=str.lower)
            self._rebuild_rows()
        for config_name in changed_statuses.keys():
            if config_name in self.rows:
                self.rows[config_name].update_status(self._statuses[config_name], self._tasks.get(config_name, ""))

    def _poll_status_task(self):
        if (
            hasattr(self, "_configs_fetched")
            and time.monotonic() - self._configs_last_fetch_at >= self._configs_fetch_interval
        ):
            delattr(self, "_configs_fetched")

        if self._use_websocket_comm():
            lock = getattr(self, "_runtime_connection_lock", None)
            if lock is not None:
                with lock:
                    self._runtime_connection = "websocket"
            else:
                self._runtime_connection = "websocket"
            self._poll_via_websocket_manager(fallback=False)
            # 根据配置动态更新轮询间隔，通过 signal 转到主线程操作 QTimer
            try:
                interval_ms = max(1, min(60, int(self.config.get("websocket_poll_interval", 3)))) * 1000
            except (ValueError, TypeError):
                interval_ms = 3000
            self.poll_interval_update_signal.emit(interval_ms)
            return

        lock = getattr(self, "_runtime_connection_lock", None)
        if lock is not None:
            with lock:
                is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        else:
            is_fallback = getattr(self, "_runtime_connection", "overlay") == "websocket_fallback"
        if is_fallback:
            self._poll_via_websocket_manager(fallback=True)
            return

        self.poll_interval_update_signal.emit(3000)

        try:
            url = gyre_api_url(self.config, "status_all")
            resp = api_request("GET", url, headers=api_headers(self.config), timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                statuses = {
                    str(config_name): normalize_status(status)
                    for config_name, status in data.get("statuses", {}).items()
                }
                tasks = {
                    str(config_name): str(task)
                    for config_name, task in data.get("tasks", {}).items()
                }
                self.status_all_update_signal.emit(statuses, tasks)
                current_status = statuses.get(self.current_config, "idle")
                current_task = tasks.get(self.current_config, "")
                if normalize_status(current_status) == "disconnected" and should_fallback_to_websocket(self.config, current_status):
                    if self._poll_via_websocket_manager(fallback=True):
                        return
                self.status_update_signal.emit(current_status, current_task)
            elif resp.status_code == 404:
                statuses = {}
                tasks = {}
                for config_name in self._configs:
                    try:
                        url = gyre_api_url(self.config, "status")
                        resp2 = api_request("GET",
                            url,
                            params={"config": config_name},
                            headers=api_headers(self.config),
                            timeout=1.5,
                        )
                        if resp2.status_code == 200:
                            j = resp2.json()
                            statuses[config_name] = normalize_status(j.get("status", "idle"))
                            tasks[config_name] = j.get("task", "")
                        else:
                            statuses[config_name] = "disconnected"
                            tasks[config_name] = ""
                    except Exception:
                        statuses[config_name] = "disconnected"
                        tasks[config_name] = ""
                self.status_all_update_signal.emit(statuses, tasks)
                current_status = statuses.get(self.current_config, "disconnected")
                current_task = tasks.get(self.current_config, "")
                if normalize_status(current_status) == "disconnected" and should_fallback_to_websocket(self.config, current_status):
                    if self._poll_via_websocket_manager(fallback=True):
                        return
                self.status_update_signal.emit(current_status, current_task)
            else:
                exc = Exception(f"HTTP {resp.status_code}")
                if should_fallback_to_websocket(self.config, exc):
                    if self._poll_via_websocket_manager(fallback=True):
                        return
                self.status_update_signal.emit("disconnected", "")
        except Exception as exc:
            if should_fallback_to_websocket(self.config, exc):
                if self._poll_via_websocket_manager(fallback=True):
                    return
            self.status_update_signal.emit("disconnected", "")

    def restore_main_window(self):
        if hasattr(self, "mini_dialog"):
            self.mini_dialog.hide()
        if self.window():
            self.window().showNormal()
            self.window().show()
            self.window().raise_()
            self.window().activateWindow()

    def show_mini_window(self):
        from .mini_window import MiniWindow
        if not hasattr(self, "mini_dialog"):
            self.mini_dialog = MiniWindow(self)

        if self.window():
            geom = self.window().geometry()
            self.mini_dialog.move(geom.x() + geom.width() // 2 - 100, geom.y() + geom.height() // 2 - 22)
            if self.config.get("mini_click_through", False):
                self.window().showMinimized()
            else:
                self.window().hide()
        self.mini_dialog.apply_window_settings()
        self.mini_dialog.show()

    def _on_icon_click(self, name, widget):
        print(f"[Log] Icon clicked -> {name}")
        if name == "close":
            QApplication.quit()
        elif name == "settings":
            from .settings_window import SettingsWindow
            dialog = SettingsWindow(self.window(), self.config, self._configs, self.current_config)
            if dialog.exec():
                try:
                    from .i18n import set_language
                    set_language(self.config.get("lang", "zh"))

                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4, ensure_ascii=False)
                    print(f"[Log] Config successfully persisted to {self.config_path}")

                    self._reset_runtime_connection()

                    self.retranslate_ui()

                    app = QApplication.instance()
                    tray_actions = getattr(app, "_alas_tray_actions", {})
                    if tray_actions:
                        action_texts = {
                            "show_main": tr("show_main"),
                            "show_float": tr("show_float"),
                            "open_webui": tr("open_webui"),
                            "settings": tr("settings_title"),
                            "wizard": tr("wizard"),
                            "quit": tr("quit"),
                        }
                        for action_name, action_text in action_texts.items():
                            action = tray_actions.get(action_name)
                            if action is not None:
                                action.setText(action_text)

                    from .theme import apply_theme
                    apply_theme(app, self.config.get("theme", "dark"))

                    if hasattr(self.window(), "apply_always_on_top"):
                        self.window().apply_always_on_top(self.config.get("always_on_top", False))
                    self.apply_task_display_settings()
                    if hasattr(self, "mini_dialog"):
                        self.mini_dialog.apply_window_settings()
                except Exception as e:
                    print(f"[Error] Failed to write {self.config_path}: {e}")
            dialog.deleteLater()
        elif name == "home":
            import webbrowser
            url = f"http://{self.config['ip']}:{self.config['port']}"
            print(f"[Log] Opening home page -> {url}")
            webbrowser.open(url)
        elif name == "log":
            from .log_window import LogWindow
            dialog = getattr(self, "log_dialog", None)
            if dialog is not None:
                try:
                    dialog.set_configs(self._configs, self.current_config)
                    dialog.set_config(self.current_config)
                    dialog.show()
                    dialog.activateWindow()
                    return
                except RuntimeError:
                    dialog = None
            if dialog is None:
                self.log_dialog = LogWindow(self.window(), self.config, self.current_config, self._configs)
                self.log_dialog.show()
        elif name == "minimize":
            self.show_mini_window()

class AlasConsole(QWidget):
    auto_update_result_signal = Signal(dict, int)

    def __init__(self):
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle("Alas-Gyre")
        self.setFixedSize(MAIN_CARD_WIDTH, MAIN_CARD_HEIGHT)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = CardWidget(self)
        self.apply_always_on_top(self.card.config.get("always_on_top", False), show_after=False)
        main_layout.addWidget(self.card, alignment=Qt.AlignTop)
        self.card._sync_window_size()

        self._auto_update_check_id = 0
        self._update_prompt_shown = False
        self.auto_update_result_signal.connect(self._on_auto_update_result)
        self._center_on_screen()

    def start_auto_update_check(self, current_version):
        if self._update_prompt_shown:
            return
        self._auto_update_check_id += 1
        check_id = self._auto_update_check_id
        threading.Thread(
            target=self._auto_update_check_task,
            args=(current_version, check_id),
            daemon=True,
        ).start()

    def _auto_update_check_task(self, current_version, check_id):
        try:
            from alas_gyre.services.updater import check_for_updates
            result = check_for_updates(current_version)
        except Exception as exc:
            result = {"has_update": False, "error": str(exc)}
        try:
            if isValid(self):
                self.auto_update_result_signal.emit(result, check_id)
        except RuntimeError:
            pass

    def _on_auto_update_result(self, result, check_id):
        if not isValid(self):
            return
        if check_id != self._auto_update_check_id:
            return
        if not result.get("has_update"):
            if result.get("error"):
                print(f"[Update Check] Auto check failed: {result.get('error')}")
            return

        self._update_prompt_shown = True
        from .update_window import UpdatePromptWindow

        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

        self.update_dialog = UpdatePromptWindow(self, result)
        self.update_dialog.show()

    def apply_always_on_top(self, enabled, show_after=True):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(enabled))
        if show_after:
            self.show()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)
        schedule_frameless_stabilize(self, self.card, stable_input_region=False)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)

    def _snap_to_screen_edges(self):
        snap_to_available_screen(self, margins=(10, 10, 10, 10))
