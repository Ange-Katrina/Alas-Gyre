import os
import secrets
import threading

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QGridLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from alas_gyre.api.client import alas_gui_url, api_headers, api_request, gyre_api_url

try:
    from shiboken6 import isValid
except Exception:
    def isValid(widget):
        return widget is not None

from alas_gyre.api.connection_policy import normalize_connection_mode, test_connection_with_fallback
from alas_gyre.api.overlay_launcher import RUNTIME_DIR_NAME, generate_portable_overlay_launchers
from alas_gyre.core.config import ensure_api_token, save_config
from alas_gyre.core.paths import app_base_dir
from .message_dialog import ask_confirm
from .widgets import WindowButton
from .i18n import tr
from .window_behavior import install_title_bar_drag, schedule_frameless_stabilize


class InitSetupWindow(QDialog):
    test_result_signal = Signal(bool, str)

    def __init__(
        self,
        parent=None,
        config=None,
        config_path="",
    ):
        super().__init__(parent)
        self.config = config if config is not None else {}
        self.config_path = config_path
        self.runtime_output_dir = os.path.join(app_base_dir(), RUNTIME_DIR_NAME)
        self.runtime_generated = os.path.isdir(self.runtime_output_dir)
        self.current_step = 0

        self.setObjectName("initWindow")
        self.setFixedSize(680, 420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.card = QFrame(self)
        self.card.setObjectName("initCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("initTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        install_title_bar_drag(self, self.topBg)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)

        title = QLabel(tr("wizard_title"))
        title.setObjectName("initTitle")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.closeBtn = WindowButton("close", self.topBg)
        self.closeBtn.mousePressEvent = lambda event: self.reject() if event.button() == Qt.LeftButton else None
        top_layout.addWidget(self.closeBtn)
        card_layout.addWidget(self.topBg)

        self.bodyBg = QWidget(self.card)
        self.bodyBg.setObjectName("initBodyBg")
        self.bodyBg.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(22, 16, 22, 16)
        body_layout.setSpacing(10)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

        self.stepRail = QFrame(self.bodyBg)
        self.stepRail.setObjectName("initStepRail")
        self.stepRail.setFixedWidth(156)
        rail_layout = QVBoxLayout(self.stepRail)
        rail_layout.setContentsMargins(14, 14, 14, 14)
        rail_layout.setSpacing(8)

        self.stepNavLayout = rail_layout

        self.stepProgressLabel = QLabel(self.stepRail)
        self.stepProgressLabel.setObjectName("initStepProgress")
        rail_layout.addWidget(self.stepProgressLabel)
        rail_layout.addSpacing(4)

        self.stepNavItems = []
        rail_layout.addStretch()
        content_layout.addWidget(self.stepRail)

        right_panel = QWidget(self.bodyBg)
        right_panel.setObjectName("initStepContent")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(9)

        self.stepTitleLabel = QLabel(right_panel)
        self.stepTitleLabel.setObjectName("initStepTitle")
        self.stepTitleLabel.setWordWrap(True)
        right_layout.addWidget(self.stepTitleLabel)

        self.stepDescLabel = QLabel(right_panel)
        self.stepDescLabel.setObjectName("initStepDesc")
        self.stepDescLabel.setWordWrap(True)
        right_layout.addWidget(self.stepDescLabel)

        self.stack = QStackedWidget(right_panel)
        self.stack.setObjectName("initStepStack")
        self.stack.addWidget(self._build_mode_page())      # index 0: mode
        self.stack.addWidget(self._build_runtime_page())    # index 1: runtime
        self.stack.addWidget(self._build_start_page())      # index 2: start
        self.stack.addWidget(self._build_test_page())       # index 3: test
        self.stack.addWidget(self._build_websocket_page())  # index 4: websocket
        right_layout.addWidget(self.stack, stretch=1)
        content_layout.addWidget(right_panel, stretch=1)
        body_layout.addLayout(content_layout, stretch=1)

        self.statusLabel = QLabel("")
        self.statusLabel.setObjectName("initStatus")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setFixedHeight(34)
        self.statusLabel.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        body_layout.addWidget(self.statusLabel)

        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        self.backBtn = QPushButton(tr("prev"))
        self.backBtn.setObjectName("cancelBtn")
        self.backBtn.setCursor(Qt.PointingHandCursor)
        self.backBtn.setFocusPolicy(Qt.NoFocus)
        self.backBtn.setFixedSize(84, 30)
        self.backBtn.clicked.connect(self._go_back)
        nav_layout.addWidget(self.backBtn)

        self.cancelBtn = QPushButton(tr("cancel"))
        self.cancelBtn.setObjectName("cancelBtn")
        self.cancelBtn.setCursor(Qt.PointingHandCursor)
        self.cancelBtn.setFocusPolicy(Qt.NoFocus)
        self.cancelBtn.setFixedSize(84, 30)
        self.cancelBtn.clicked.connect(self.reject)
        nav_layout.addWidget(self.cancelBtn)

        self.nextBtn = QPushButton(tr("next"))
        self.nextBtn.setObjectName("tokenBtn")
        self.nextBtn.setCursor(Qt.PointingHandCursor)
        self.nextBtn.setFocusPolicy(Qt.NoFocus)
        self.nextBtn.setFixedSize(92, 30)
        self.nextBtn.clicked.connect(self._go_next)
        nav_layout.addWidget(self.nextBtn)

        self.finishBtn = QPushButton(tr("finish"))
        self.finishBtn.setObjectName("saveBtn")
        self.finishBtn.setCursor(Qt.PointingHandCursor)
        self.finishBtn.setFocusPolicy(Qt.NoFocus)
        self.finishBtn.setFixedSize(120, 30)
        self.finishBtn.clicked.connect(self._finish_setup)
        nav_layout.addWidget(self.finishBtn)
        body_layout.addLayout(nav_layout)

        self.test_result_signal.connect(self._on_test_result)
        card_layout.addWidget(self.bodyBg)
        main_layout.addWidget(self.card)

        self._center_on_parent()
        self._set_step(0)
        self._force_layout()
        QTimer.singleShot(0, self._force_layout)

    def _build_step_nav_item_triple(self, number, text_key):
        """构建步骤导航项，返回 (row, badge, label) 三元组。"""
        row = QFrame(self.stepRail)
        row.setObjectName("initStepNavItem")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(8)

        badge = QLabel(str(number), row)
        badge.setObjectName("initStepBadge")
        badge.setFixedSize(22, 22)
        badge.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(badge)

        label = QLabel(tr(text_key), row)
        label.setObjectName("initStepNavLabel")
        label.setWordWrap(True)
        row_layout.addWidget(label, stretch=1)

        self.stepNavItems.append((row, badge, label))
        return row, badge, label


    def _build_step_nav_item(self, number, text_key):
        """构建步骤导航项，返回 row 供旧代码兼容。"""
        row, _, _ = self._build_step_nav_item_triple(number, text_key)
        return row

    def _build_runtime_page(self):
        page = QWidget(self.bodyBg)
        page.setObjectName("initStepPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        panel = QFrame(page)
        panel.setObjectName("initPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)

        token_layout = QHBoxLayout()
        token_layout.setSpacing(10)
        token_label = QLabel("API Token")
        token_label.setObjectName("formLabel")
        token_label.setFixedWidth(82)
        self.tokenInput = QLineEdit(self.config.get("api_token", ""))
        self.tokenInput.setObjectName("settingsInput")
        self.tokenInput.setFixedHeight(30)
        self.tokenInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.tokenInput.setPlaceholderText(tr("token_auto_placeholder"))
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.tokenInput, stretch=1)

        self.generateBtn = QPushButton(tr("regenerate_token"))
        self.generateBtn.setObjectName("tokenBtn")
        self.generateBtn.setCursor(Qt.PointingHandCursor)
        self.generateBtn.setFocusPolicy(Qt.NoFocus)
        self.generateBtn.setFixedSize(104, 30)
        self.generateBtn.clicked.connect(self._generate_token)
        token_layout.addWidget(self.generateBtn)
        panel_layout.addLayout(token_layout)

        token_hint = QLabel(tr("token_auto_hint"))
        token_hint.setObjectName("initSubtle")
        token_hint.setWordWrap(True)
        panel_layout.addWidget(token_hint)

        runtime_btn_layout = QHBoxLayout()
        runtime_btn_layout.addStretch()
        self.openRuntimeDirBtn = QPushButton(tr("open_runtime_dir"))
        self.openRuntimeDirBtn.setObjectName("tokenBtn")
        self.openRuntimeDirBtn.setCursor(Qt.PointingHandCursor)
        self.openRuntimeDirBtn.setFocusPolicy(Qt.NoFocus)
        self.openRuntimeDirBtn.setFixedSize(96, 32)
        self.openRuntimeDirBtn.setEnabled(self.runtime_generated)
        self.openRuntimeDirBtn.clicked.connect(self._open_runtime_dir)
        runtime_btn_layout.addWidget(self.openRuntimeDirBtn)

        self.runtimeBtn = QPushButton(tr("generate_runtime"))
        self.runtimeBtn.setObjectName("runtimePrimaryBtn")
        self.runtimeBtn.setCursor(Qt.PointingHandCursor)
        self.runtimeBtn.setFocusPolicy(Qt.NoFocus)
        self.runtimeBtn.setFixedSize(176, 32)
        self.runtimeBtn.clicked.connect(self._generate_overlay_launcher)
        runtime_btn_layout.addWidget(self.runtimeBtn)
        panel_layout.addLayout(runtime_btn_layout)
        layout.addWidget(panel)

        hint = QLabel(tr("runtime_next_hint"), page)
        hint.setObjectName("initSubtle")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()
        return page

    def _build_start_page(self):
        page = QWidget(self.bodyBg)
        page.setObjectName("initStepPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        panel = QFrame(page)
        panel.setObjectName("initPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)
        for key in ("start_step_windows", "start_step_linux", "start_step_note"):
            label = QLabel(tr(key), panel)
            label.setObjectName("initHint")
            label.setWordWrap(True)
            panel_layout.addWidget(label)

        open_layout = QHBoxLayout()
        open_layout.addStretch()
        self.openRuntimeDirBtn2 = QPushButton(tr("open_runtime_dir"))
        self.openRuntimeDirBtn2.setObjectName("tokenBtn")
        self.openRuntimeDirBtn2.setCursor(Qt.PointingHandCursor)
        self.openRuntimeDirBtn2.setFocusPolicy(Qt.NoFocus)
        self.openRuntimeDirBtn2.setFixedSize(110, 32)
        self.openRuntimeDirBtn2.setEnabled(self.runtime_generated)
        self.openRuntimeDirBtn2.clicked.connect(self._open_runtime_dir)
        open_layout.addWidget(self.openRuntimeDirBtn2)
        panel_layout.addLayout(open_layout)
        layout.addWidget(panel)
        layout.addStretch()
        return page

    def _build_test_page(self):
        page = QWidget(self.bodyBg)
        page.setObjectName("initStepPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        test_panel = QFrame(page)
        test_panel.setObjectName("initPanel")
        test_layout = QVBoxLayout(test_panel)
        test_layout.setContentsMargins(14, 14, 14, 14)
        test_layout.setSpacing(10)

        test_hint = QLabel(tr("optional_connection_desc"), test_panel)
        test_hint.setObjectName("initSubtle")
        test_hint.setWordWrap(True)
        test_layout.addWidget(test_hint)

        connection_layout = QGridLayout()
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(10)
        ip_label = QLabel(tr("ip_address"))
        ip_label.setObjectName("formLabel")
        ip_label.setFixedWidth(62)
        self.ipInput = QLineEdit(self.config.get("ip", "127.0.0.1"))
        self.ipInput.setObjectName("settingsInput")
        self.ipInput.setFixedHeight(30)
        self.ipInput.setMinimumWidth(260)
        connection_layout.addWidget(ip_label, 0, 0)
        connection_layout.addWidget(self.ipInput, 0, 1, 1, 3)

        port_label = QLabel(tr("service_port"))
        port_label.setObjectName("formLabel")
        port_label.setFixedWidth(64)
        self.portInput = QLineEdit(str(self.config.get("port", "22267")))
        self.portInput.setObjectName("settingsInput")
        self.portInput.setFixedSize(86, 30)
        connection_layout.addWidget(port_label, 1, 0)
        connection_layout.addWidget(self.portInput, 1, 1)

        self.testBtn = QPushButton(tr("test_connection_optional"))
        self.testBtn.setObjectName("testBtn")
        self.testBtn.setCursor(Qt.PointingHandCursor)
        self.testBtn.setFocusPolicy(Qt.NoFocus)
        self.testBtn.setFixedSize(132, 30)
        self.testBtn.clicked.connect(self._run_connection_test)
        connection_layout.addWidget(self.testBtn, 1, 3)
        connection_layout.setColumnStretch(2, 1)
        test_layout.addLayout(connection_layout)

        websocket_hint = QLabel(tr("init_websocket_hint"))
        websocket_hint.setWordWrap(True)
        websocket_hint.setStyleSheet("color: #8f96a3; font-size: 12px;")
        test_layout.addWidget(websocket_hint)

        layout.addWidget(test_panel)

        layout.addStretch()
        return page

    def _normalized_mode(self):
        """获取标准化后的连接模式。"""
        return normalize_connection_mode(self.config)


    def _is_auto_mode(self):
        """判断当前是否为自动模式。"""
        return self.modeCombo.currentData() == "auto"


    def _current_step_keys(self):
        """返回当前模式下的步骤键列表。"""
        if self._is_auto_mode():
            return ["mode", "runtime", "start", "test"]
        return ["mode", "websocket"]


    def _build_mode_page(self):
        page = QWidget(self.bodyBg)
        page.setObjectName("initStepPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        desc = QLabel(tr("init_mode_select_desc"), page)
        desc.setObjectName("initSubtle")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.modeCombo = QComboBox(page)
        self.modeCombo.setObjectName("settingsInput")
        self.modeCombo.setCursor(Qt.PointingHandCursor)
        self.modeCombo.setFocusPolicy(Qt.NoFocus)
        self.modeCombo.setFixedHeight(30)
        self.modeCombo.setFixedWidth(280)
        self.modeCombo.addItem(tr("connection_mode_auto"), "auto")
        self.modeCombo.addItem(tr("connection_mode_websocket"), "websocket")
        idx = self.modeCombo.findData(self._normalized_mode())
        self.modeCombo.setCurrentIndex(max(0, idx))

        mode_desc_label = QLabel(
            tr("connection_mode_auto_desc") if self._normalized_mode() == "auto" else tr("connection_mode_websocket_desc"),
            page,
        )
        mode_desc_label.setObjectName("initSubtle")
        mode_desc_label.setWordWrap(True)
        layout.addWidget(mode_desc_label)
        layout.addWidget(self.modeCombo)

        self.modeCombo.currentIndexChanged.connect(lambda: (
            self._set_step(0),
            mode_desc_label.setText(
                tr("connection_mode_auto_desc") if self._is_auto_mode() else tr("connection_mode_websocket_desc")
            ),
        ))
        layout.addStretch()
        return page

    def _build_websocket_page(self):
        page = QWidget(self.bodyBg)
        page.setObjectName("initStepPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        panel = QFrame(page)
        panel.setObjectName("initPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 14, 14, 14)
        panel_layout.setSpacing(10)

        connection_layout = QGridLayout()
        connection_layout.setHorizontalSpacing(10)
        connection_layout.setVerticalSpacing(10)

        ip_label = QLabel(tr("ip_address"))
        ip_label.setObjectName("formLabel")
        ip_label.setFixedWidth(62)
        self.wsIpInput = QLineEdit(self.config.get("ip", "127.0.0.1"))
        self.wsIpInput.setObjectName("settingsInput")
        self.wsIpInput.setFixedHeight(30)
        self.wsIpInput.setMinimumWidth(260)
        connection_layout.addWidget(ip_label, 0, 0)
        connection_layout.addWidget(self.wsIpInput, 0, 1, 1, 3)

        port_label = QLabel(tr("service_port"))
        port_label.setObjectName("formLabel")
        port_label.setFixedWidth(64)
        self.wsPortInput = QLineEdit(str(self.config.get("port", "22267")))
        self.wsPortInput.setObjectName("settingsInput")
        self.wsPortInput.setFixedSize(86, 30)
        connection_layout.addWidget(port_label, 1, 0)
        connection_layout.addWidget(self.wsPortInput, 1, 1)

        self.wsTestBtn = QPushButton(tr("test_connection_optional"))
        self.wsTestBtn.setObjectName("testBtn")
        self.wsTestBtn.setCursor(Qt.PointingHandCursor)
        self.wsTestBtn.setFocusPolicy(Qt.NoFocus)
        self.wsTestBtn.setFixedSize(132, 30)
        self.wsTestBtn.clicked.connect(self._run_ws_connection_test)
        connection_layout.addWidget(self.wsTestBtn, 1, 3)
        connection_layout.setColumnStretch(2, 1)
        panel_layout.addLayout(connection_layout)

        hint = QLabel(tr("init_websocket_hint"), panel)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8f96a3; font-size: 12px;")
        panel_layout.addWidget(hint)

        layout.addWidget(panel)
        layout.addStretch()
        return page

    def _run_ws_connection_test(self):
        if not self.wsIpInput.text().strip() or not self.wsPortInput.text().strip().isdigit():
            self._active_test_btn = self.wsTestBtn
            self._on_test_result(False, tr("test_invalid"))
            return
        self.config["ip"] = self.wsIpInput.text().strip()
        self.config["port"] = self.wsPortInput.text().strip()
        self.config["connection_mode"] = "websocket"

        self._active_test_btn = self.wsTestBtn
        self.wsTestBtn.setText("...")
        self.wsTestBtn.setIcon(QIcon())
        self.wsTestBtn.setEnabled(False)
        self.wsTestBtn.setProperty("state", "testing")
        self.wsTestBtn.style().unpolish(self.wsTestBtn)
        self.wsTestBtn.style().polish(self.wsTestBtn)
        threading.Thread(target=self._ws_test_api, daemon=True).start()

    def _emit_test_result(self, success, message):
        """安全发射测试结果信号，忽略已删除信号源异常。"""
        try:
            if isValid(self):
                self.test_result_signal.emit(success, message)
        except RuntimeError:
            pass

    def _ws_test_api(self):
        btn = self.wsTestBtn
        try:
            result = test_connection_with_fallback(self.config)
            if getattr(self, "_active_test_btn", None) is not btn:
                return
            if result.success:
                message = tr(result.message_key)
                self._emit_test_result(True, message)
            else:
                detail = result.websocket_error or result.overlay_error
                self._emit_test_result(False, detail or tr("test_failed_short"))
        except Exception as exc:
            if getattr(self, "_active_test_btn", None) is not btn:
                return
            self._emit_test_result(False, str(exc))


    def _rebuild_step_nav(self):
        """根据当前模式重建步骤导航栏。"""
        for idx in range(self.stepNavLayout.count() - 1, -1, -1):
            item = self.stepNavLayout.takeAt(idx)
            widget = item.widget()
            if widget is self.stepProgressLabel:
                self.stepNavLayout.insertWidget(0, widget)
                continue
            if widget:
                widget.deleteLater()
        self.stepNavItems = []
        labels = {
            "mode": "init_nav_mode",
            "runtime": "init_nav_runtime",
            "start": "init_nav_start",
            "test": "init_nav_test",
            "websocket": "init_nav_websocket",
        }
        for number, key in enumerate(self._current_step_keys(), start=1):
            row, badge, label = self._build_step_nav_item_triple(number, labels[key])
            self.stepNavLayout.addWidget(row)
        self.stepNavLayout.addStretch()


    def showEvent(self, event):
        super().showEvent(event)
        self._force_layout()
        QTimer.singleShot(0, self._force_layout)
        schedule_frameless_stabilize(self, self.card, self.topBg, self.bodyBg)

    def _force_layout(self):
        for widget in (self, self.card, self.bodyBg, self.stack):
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            widget.updateGeometry()
            widget.update()

    def _set_step(self, index):
        steps = self._current_step_keys()
        if len(steps) != len(self.stepNavItems):
            self._rebuild_step_nav()
        self.current_step = max(0, min(index, len(steps) - 1))
        step_key = steps[self.current_step]
        stack_indexes = {
            "mode": 0,
            "runtime": 1,
            "start": 2,
            "test": 3,
            "websocket": 4,
        }
        self.stack.setCurrentIndex(stack_indexes[step_key])

        titles = {
            "mode": tr("init_mode_select_title"),
            "runtime": tr("init_step_runtime_title"),
            "start": tr("init_step_start_title"),
            "test": tr("init_step_test_title"),
            "websocket": tr("init_websocket_connect_title"),
        }
        descs = {
            "mode": "",
            "runtime": tr("init_step_runtime_desc"),
            "start": tr("init_step_start_desc"),
            "test": tr("init_step_test_desc"),
            "websocket": "",
        }
        self.stepTitleLabel.setText(titles.get(step_key, ""))
        self.stepDescLabel.setText(descs.get(step_key, ""))

        self.stepProgressLabel.setText(tr("wizard_step_progress", current=self.current_step + 1, total=len(steps)))
        self.backBtn.setEnabled(self.current_step > 0)
        self.nextBtn.setVisible(self.current_step < len(steps) - 1)
        self.finishBtn.setVisible(self.current_step == len(steps) - 1)

        for idx, (row, badge, label) in enumerate(getattr(self, "stepNavItems", [])):
            active = idx == self.current_step
            done = idx < self.current_step
            badge.setText("✓" if done else str(idx + 1))
            for widget in (row, badge, label):
                widget.setProperty("active", active)
                widget.setProperty("done", done)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
        self._refresh_runtime_buttons()
        self._force_layout()

    def _go_back(self):
        self._set_step(self.current_step - 1)

    def _go_next(self):
        self._set_step(self.current_step + 1)

    def _refresh_runtime_buttons(self):
        enabled = bool(self.runtime_generated and os.path.isdir(self.runtime_output_dir))
        if hasattr(self, "openRuntimeDirBtn"):
            self.openRuntimeDirBtn.setEnabled(enabled)
        if hasattr(self, "openRuntimeDirBtn2"):
            self.openRuntimeDirBtn2.setEnabled(enabled)

    def _center_on_parent(self):
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
            self.move(x, y)

    def _sync_config_from_ui(self):
        self.config["connection_mode"] = self.modeCombo.currentData() or "auto"
        if self._is_auto_mode():
            self.config["ip"] = self.ipInput.text().strip() or "127.0.0.1"
            self.config["port"] = self.portInput.text().strip() or "22267"
            self.config["api_token"] = self.tokenInput.text().strip()
        else:
            self.config["ip"] = self.wsIpInput.text().strip() or "127.0.0.1"
            self.config["port"] = self.wsPortInput.text().strip() or "22267"

    def _set_status(self, text, state="normal", tooltip=None):
        self.statusLabel.setText(text)
        self.statusLabel.setToolTip(tooltip if tooltip is not None else text)
        self.statusLabel.setProperty("state", state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def _short_display_path(self, path, max_len=44):
        text = os.path.abspath(str(path or "")).replace("/", "\\")
        if len(text) <= max_len:
            return text
        stripped = text.rstrip("\\")
        name = os.path.basename(stripped)
        parent = os.path.basename(os.path.dirname(stripped))
        short = f"...\\{parent}\\{name}" if parent else f"...\\{name}"
        if len(short) <= max_len:
            return short
        return "..." + text[-(max_len - 3):]

    def _open_runtime_dir(self):
        if not self.runtime_output_dir or not os.path.isdir(self.runtime_output_dir):
            self._set_status(tr("open_runtime_dir_failed"), "error")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.runtime_output_dir))

    def _ensure_token(self):
        self._sync_config_from_ui()
        token = ensure_api_token(self.config, self.config_path)
        self.tokenInput.setText(token)
        return token

    def _generate_token(self):
        self._sync_config_from_ui()
        token = secrets.token_urlsafe(32)
        self.config["api_token"] = token
        self.tokenInput.setText(token)
        try:
            save_config(self.config, self.config_path)
            self._set_status(tr("token_generated"), "success")
        except Exception as exc:
            self._set_status(tr("action_failed", error=str(exc)), "error")
        self.tokenInput.setFocus()

    def _generate_overlay_launcher(self):
        self.runtimeBtn.setEnabled(False)
        self.runtimeBtn.setText(tr("generating_runtime"))
        self._refresh_runtime_buttons()
        token = self._ensure_token()
        try:
            save_config(self.config, self.config_path)
        except Exception as exc:
            self._set_status(tr("action_failed", error=str(exc)), "error")
            self.runtimeBtn.setEnabled(True)
            self.runtimeBtn.setText(tr("generate_runtime"))
            self._refresh_runtime_buttons()
            return

        try:
            result = generate_portable_overlay_launchers(api_token=token)
            output_dir = result["output_dir"]
            self.runtime_output_dir = output_dir
            self.runtime_generated = True
            self._refresh_runtime_buttons()
            display_dir = self._short_display_path(output_dir)
            self._set_status(
                tr("overlay_launcher_success", dir=display_dir),
                "success",
                tooltip=output_dir,
            )
        except Exception as exc:
            self._set_status(tr("overlay_launcher_failed", error=str(exc)), "error")
            self._refresh_runtime_buttons()
        finally:
            self.runtimeBtn.setEnabled(True)
            self.runtimeBtn.setText(tr("generate_runtime"))

    def _finish_setup(self):
        self._sync_config_from_ui()
        if self._is_auto_mode() and not self.runtime_generated:
            if not ask_confirm(
                self,
                tr("runtime_missing_confirm_title"),
                tr("runtime_missing_confirm_desc"),
                tr("finish_anyway"),
                tr("cancel"),
            ):
                return
        if self._is_auto_mode():
            self._ensure_token()
        self.config["setup_completed"] = True
        try:
            save_config(self.config, self.config_path)
            self.accept()
        except Exception as exc:
            self._set_status(tr("action_failed", error=str(exc)), "error")

    def _run_connection_test(self):
        self._ensure_token()
        if not self.config["ip"] or not self.config["port"].isdigit():
            self._active_test_btn = self.testBtn
            self._on_test_result(False, tr("test_invalid"))
            return

        self._active_test_btn = self.testBtn
        self.testBtn.setText("...")
        self.testBtn.setIcon(QIcon())
        self.testBtn.setEnabled(False)
        self.testBtn.setProperty("state", "testing")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
        threading.Thread(target=self._test_api, daemon=True).start()

    def _test_api(self):
        """使用统一连接测试接口，支持自动降级。"""
        btn = self.testBtn
        try:
            result = test_connection_with_fallback(self.config)
            if getattr(self, "_active_test_btn", None) is not btn:
                return
            if result.success:
                message = tr(result.message_key)
                if result.source == "websocket_fallback" and result.overlay_error:
                    message = f"{message}\nOverlay: {result.overlay_error}"
                self._emit_test_result(True, message)
            else:
                detail = result.websocket_error or result.overlay_error
                self._emit_test_result(False, detail or tr("test_failed_short"))
        except Exception as exc:
            if getattr(self, "_active_test_btn", None) is not btn:
                return
            self._emit_test_result(False, str(exc))

    def _create_icon(self, state):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        if state == "success":
            pen = QPen(QColor("#42d392"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(5, 12, 10, 17)
            painter.drawLine(10, 17, 19, 7)
        else:
            pen = QPen(QColor("#ff5c5c"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(7, 7, 17, 17)
            painter.drawLine(17, 7, 7, 17)
        painter.end()
        return QIcon(pixmap)

    def _on_test_result(self, success, message=""):
        btn = getattr(self, "_active_test_btn", None)
        if btn is None or not isValid(btn):
            return
        btn.setEnabled(True)
        btn.setText("")
        btn.setToolTip(message)
        btn.setIconSize(QSize(20, 20))
        btn.setIcon(self._create_icon("success" if success else "error"))
        btn.setProperty("state", "success" if success else "error")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        self._set_status(tr("test_success") if success else tr("test_failed_short"), "success" if success else "error")
        if message and not success:
            print(f"[InitSetup] Connection test failed: {message}")
        QTimer.singleShot(2000, self._reset_test_btn)

    def _reset_test_btn(self):
        btn = getattr(self, "_active_test_btn", None)
        if btn is None or not isValid(btn):
            return
        btn.setIcon(QIcon())
        btn.setText(tr("test_connection_optional"))
        btn.setToolTip("")
        btn.setProperty("state", "normal")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
