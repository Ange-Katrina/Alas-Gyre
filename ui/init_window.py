import threading

import requests
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from .api_client import api_base_url, api_headers
from .fastapi_export_window import ensure_api_token, export_fastapi_file, save_config
from .main_window import WindowButton
from .i18n import tr


class InitSetupWindow(QDialog):
    test_result_signal = Signal(bool, str)

    def __init__(
        self,
        parent=None,
        config=None,
        config_path="",
        fastapi_source_path="",
        fastapi_output_path="",
    ):
        super().__init__(parent)
        self.config = config if config is not None else {}
        self.config_path = config_path
        self.fastapi_source_path = fastapi_source_path
        self.fastapi_output_path = fastapi_output_path

        self.setObjectName("initWindow")
        self.setFixedSize(520, 500)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 18)

        self.card = QFrame(self)
        self.card.setObjectName("initCard")
        self.card.setFixedSize(484, 468)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("initTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
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
        self.bodyBg.setFixedSize(484, 438)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(12)

        desc = QLabel(tr("welcome_desc"))
        desc.setObjectName("initDesc")
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        server_panel = QFrame(self.bodyBg)
        server_panel.setObjectName("initPanel")
        server_layout = QVBoxLayout(server_panel)
        server_layout.setContentsMargins(12, 12, 12, 12)
        server_layout.setSpacing(10)

        ip_layout = QHBoxLayout()
        ip_layout.setSpacing(10)
        ip_label = QLabel(tr("ip_address"))
        ip_label.setObjectName("formLabel")
        ip_label.setFixedWidth(68)
        self.ipInput = QLineEdit(self.config.get("ip", "127.0.0.1"))
        self.ipInput.setObjectName("settingsInput")
        self.ipInput.setFixedHeight(30)
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ipInput, stretch=1)
        server_layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.setSpacing(10)
        port_label = QLabel(tr("service_port"))
        port_label.setObjectName("formLabel")
        port_label.setFixedWidth(68)
        self.portInput = QLineEdit(self.config.get("port", "22267"))
        self.portInput.setObjectName("settingsInput")
        self.portInput.setFixedWidth(120)
        self.portInput.setFixedHeight(30)
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.portInput)
        port_layout.addStretch()

        self.testBtn = QPushButton(tr("test_connection"))
        self.testBtn.setObjectName("testBtn")
        self.testBtn.setCursor(Qt.PointingHandCursor)
        self.testBtn.setFocusPolicy(Qt.NoFocus)
        self.testBtn.setFixedSize(78, 30)
        self.testBtn.clicked.connect(self._run_connection_test)
        port_layout.addWidget(self.testBtn)
        server_layout.addLayout(port_layout)

        token_layout = QHBoxLayout()
        token_layout.setSpacing(10)
        token_label = QLabel("API Token")
        token_label.setObjectName("formLabel")
        token_label.setFixedWidth(68)
        self.tokenInput = QLineEdit(self.config.get("api_token", ""))
        self.tokenInput.setObjectName("settingsInput")
        self.tokenInput.setFixedHeight(30)
        self.tokenInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.tokenInput, stretch=1)

        self.generateBtn = QPushButton(tr("generate"))
        self.generateBtn.setObjectName("tokenBtn")
        self.generateBtn.setCursor(Qt.PointingHandCursor)
        self.generateBtn.setFocusPolicy(Qt.NoFocus)
        self.generateBtn.setFixedSize(62, 30)
        self.generateBtn.clicked.connect(self._generate_token)
        token_layout.addWidget(self.generateBtn)
        server_layout.addLayout(token_layout)
        body_layout.addWidget(server_panel)

        install_panel = QFrame(self.bodyBg)
        install_panel.setObjectName("initPanel")
        install_layout = QVBoxLayout(install_panel)
        install_layout.setContentsMargins(12, 10, 12, 10)
        install_layout.setSpacing(8)

        install_title = QLabel(tr("step3_title"))
        install_title.setObjectName("initPanelTitle")
        install_layout.addWidget(install_title)

        install_text = QLabel(tr("step3_desc"))
        install_text.setObjectName("initHint")
        install_text.setWordWrap(True)
        install_layout.addWidget(install_text)

        install_btn_layout = QHBoxLayout()
        install_btn_layout.addStretch()
        self.exportBtn = QPushButton(tr("export_btn"))
        self.exportBtn.setObjectName("fastapiExportBtn")
        self.exportBtn.setCursor(Qt.PointingHandCursor)
        self.exportBtn.setFocusPolicy(Qt.NoFocus)
        self.exportBtn.setFixedSize(128, 32)
        self.exportBtn.clicked.connect(self._export_fastapi)
        install_btn_layout.addWidget(self.exportBtn)
        install_layout.addLayout(install_btn_layout)
        body_layout.addWidget(install_panel)

        self.statusLabel = QLabel("")
        self.statusLabel.setObjectName("initStatus")
        self.statusLabel.setWordWrap(True)
        body_layout.addWidget(self.statusLabel)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.skipBtn = QPushButton(tr("cancel"))
        self.skipBtn.setObjectName("cancelBtn")
        self.skipBtn.setCursor(Qt.PointingHandCursor)
        self.skipBtn.setFocusPolicy(Qt.NoFocus)
        self.skipBtn.setFixedSize(78, 30)
        self.skipBtn.clicked.connect(self.reject)
        btn_layout.addWidget(self.skipBtn)

        self.finishBtn = QPushButton(tr("finish"))
        self.finishBtn.setObjectName("saveBtn")
        self.finishBtn.setCursor(Qt.PointingHandCursor)
        self.finishBtn.setFocusPolicy(Qt.NoFocus)
        self.finishBtn.setFixedSize(92, 30)
        self.finishBtn.clicked.connect(self._finish_setup)
        btn_layout.addWidget(self.finishBtn)
        body_layout.addLayout(btn_layout)

        self.test_result_signal.connect(self._on_test_result)
        card_layout.addWidget(self.bodyBg)
        main_layout.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.card.setGraphicsEffect(shadow)
        self._center_on_parent()
        self._force_layout()
        QTimer.singleShot(0, self._force_layout)

    def showEvent(self, event):
        super().showEvent(event)
        self._force_layout()
        QTimer.singleShot(0, self._force_layout)

    def _force_layout(self):
        for widget in (self, self.card, self.bodyBg):
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            widget.updateGeometry()
            widget.update()

    def _center_on_parent(self):
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
            self.move(x, y)

    def _sync_config_from_ui(self):
        self.config["ip"] = self.ipInput.text().strip() or "127.0.0.1"
        self.config["port"] = self.portInput.text().strip() or "22267"
        self.config["api_token"] = self.tokenInput.text().strip()

    def _set_status(self, text, state="normal"):
        self.statusLabel.setText(text)
        self.statusLabel.setProperty("state", state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def _generate_token(self):
        self._sync_config_from_ui()
        token = ensure_api_token(self.config, self.config_path)
        self.tokenInput.setText(token)
        self.tokenInput.setFocus()
        self._set_status(tr("token_generated"), "success")

    def _export_fastapi(self):
        self._sync_config_from_ui()
        try:
            output_path = export_fastapi_file(
                self.fastapi_source_path,
                self.fastapi_output_path,
                self.config,
                self.config_path,
            )
            self.tokenInput.setText(self.config.get("api_token", ""))
            self._set_status(tr("export_success", path=output_path), "success")
        except Exception as exc:
            self._set_status(tr("export_fail", error=str(exc)), "error")

    def _finish_setup(self):
        self._sync_config_from_ui()
        self.config["setup_completed"] = True
        try:
            save_config(self.config, self.config_path)
            self.accept()
        except Exception as exc:
            self._set_status(tr("export_fail", error=str(exc)), "error")

    def _run_connection_test(self):
        self._sync_config_from_ui()
        if not self.config["ip"] or not self.config["port"].isdigit():
            self._on_test_result(False, tr("test_invalid"))
            return

        self.testBtn.setText("...")
        self.testBtn.setIcon(QIcon())
        self.testBtn.setEnabled(False)
        self.testBtn.setProperty("state", "testing")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
        threading.Thread(target=self._test_api, daemon=True).start()

    def _test_api(self):
        success = False
        message = ""
        try:
            resp = requests.get(
                f"{api_base_url(self.config)}/api/health",
                headers=api_headers(self.config),
                timeout=2.0,
            )
            success = resp.status_code == 200
            if resp.status_code == 401:
                message = tr("test_unauthorized")
            elif not success:
                message = f"HTTP {resp.status_code}"
        except Exception as exc:
            message = str(exc)
        self.test_result_signal.emit(success, message)

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
        self.testBtn.setEnabled(True)
        self.testBtn.setText("")
        self.testBtn.setToolTip(message)
        self.testBtn.setIconSize(QSize(20, 20))
        self.testBtn.setIcon(self._create_icon("success" if success else "error"))
        self.testBtn.setProperty("state", "success" if success else "error")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
        self._set_status(tr("test_success") if success else tr("test_failed", error=message), "success" if success else "error")
        QTimer.singleShot(2000, self._reset_test_btn)

    def _reset_test_btn(self):
        self.testBtn.setIcon(QIcon())
        self.testBtn.setText(tr("test_connection"))
        self.testBtn.setToolTip("")
        self.testBtn.setProperty("state", "normal")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            import sys
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.ReleaseCapture()
                ctypes.windll.user32.SendMessageW(int(self.winId()), 0x0112, 0xF012, 0)
            else:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        import sys
        if sys.platform != "win32" and hasattr(self, "_drag_offset") and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
