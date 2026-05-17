from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QLineEdit, QCheckBox,
    QPushButton, QFrame, QGraphicsDropShadowEffect, QSlider
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QColor, QPixmap, QPainter, QPen, QIcon
import requests
import secrets
import threading

from .api_client import api_base_url, api_headers
from updater import check_for_updates, do_update
from main import VERSION
from .main_window import WindowButton
from .i18n import tr

class CheckBox(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isChecked():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor("#d9fff0"), 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        y = (self.height() - 14) // 2
        painter.drawLine(4, y + 8, 7, y + 11)
        painter.drawLine(7, y + 11, 13, y + 4)
        painter.end()

class SettingsWindow(QDialog):
    test_result_signal = Signal(bool, str)

    def __init__(self, parent=None, config=None, configs=None, current_config="alas"):
        super().__init__(parent)
        self.config = config if config is not None else {}
        self.setObjectName("settingsWindow")
        self.setFixedSize(420, 440)  # 高度微调至 440 以完美容纳多一行复选框
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 18)

        # 背景容器卡片
        self.card = QFrame(self)
        self.card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ====== 顶栏 ======
        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("settingsTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)

        title = QLabel(tr("settings_title"))
        title.setObjectName("settingsTitle")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.closeBtn = WindowButton("close", self.topBg)
        self.closeBtn.mousePressEvent = lambda event: self.reject() if event.button() == Qt.LeftButton else None
        top_layout.addWidget(self.closeBtn)

        card_layout.addWidget(self.topBg)

        # ====== 表单区域 ======
        self.formBg = QWidget(self.card)
        self.formBg.setObjectName("settingsFormBg")
        self.formBg.setAttribute(Qt.WA_StyledBackground, True)
        form_layout = QVBoxLayout(self.formBg)
        form_layout.setContentsMargins(24, 18, 24, 16)
        form_layout.setSpacing(12)

        # 开关选项第1行
        option_layout1 = QHBoxLayout()
        option_layout1.setSpacing(28)

        self.autoStartCheck = CheckBox(tr("auto_start"))
        self.autoStartCheck.setCursor(Qt.PointingHandCursor)
        self.autoStartCheck.setChecked(self.config.get("auto_start", False))

        self.alwaysOnTopCheck = CheckBox(tr("always_on_top"))
        self.alwaysOnTopCheck.setCursor(Qt.PointingHandCursor)
        self.alwaysOnTopCheck.setChecked(self.config.get("always_on_top", False))

        option_layout1.addWidget(self.autoStartCheck)
        option_layout1.addWidget(self.alwaysOnTopCheck)
        option_layout1.addStretch()

        # 开关选项第2行
        option_layout2 = QHBoxLayout()
        option_layout2.setSpacing(28)

        self.miniClickThroughCheck = CheckBox(tr("click_through"))
        self.miniClickThroughCheck.setCursor(Qt.PointingHandCursor)
        self.miniClickThroughCheck.setChecked(self.config.get("mini_click_through", False))

        self.lightThemeCheck = CheckBox(tr("light_mode"))
        self.lightThemeCheck.setCursor(Qt.PointingHandCursor)
        self.lightThemeCheck.setChecked(self.config.get("theme", "dark") == "light")

        option_layout2.addWidget(self.miniClickThroughCheck)
        option_layout2.addWidget(self.lightThemeCheck)
        option_layout2.addStretch()

        # 开关选项第3行 (语言设置)
        option_layout3 = QHBoxLayout()
        option_layout3.setSpacing(28)

        self.englishLangCheck = CheckBox(tr("english_mode"))
        self.englishLangCheck.setCursor(Qt.PointingHandCursor)
        self.englishLangCheck.setChecked(self.config.get("lang", "zh") == "en")

        option_layout3.addWidget(self.englishLangCheck)
        option_layout3.addStretch()

        form_layout.addLayout(option_layout1)
        form_layout.addLayout(option_layout2)
        form_layout.addLayout(option_layout3)

        opacity_layout = QHBoxLayout()
        opacity_layout.setSpacing(10)
        opacity_label = QLabel(tr("float_opacity"))
        opacity_label.setObjectName("formLabel")
        opacity_label.setFixedWidth(100)
        self.miniOpacitySlider = QSlider(Qt.Horizontal)
        self.miniOpacitySlider.setObjectName("settingsSlider")
        self.miniOpacitySlider.setRange(35, 100)
        self.miniOpacitySlider.setSingleStep(5)
        self.miniOpacitySlider.setPageStep(10)
        self.miniOpacitySlider.setValue(self._normalize_opacity(self.config.get("mini_opacity", 100)))
        self.miniOpacityValue = QLabel(f"{self.miniOpacitySlider.value()}%")
        self.miniOpacityValue.setObjectName("sliderValueLabel")
        self.miniOpacityValue.setFixedWidth(42)
        self.miniOpacityValue.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.miniOpacitySlider.valueChanged.connect(
            lambda value: self.miniOpacityValue.setText(f"{value}%")
        )
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(self.miniOpacitySlider, stretch=1)
        opacity_layout.addWidget(self.miniOpacityValue)
        form_layout.addLayout(opacity_layout)

        # IP 布局
        ip_layout = QHBoxLayout()
        ip_layout.setSpacing(10)
        ip_label = QLabel(tr("ip_address"))
        ip_label.setObjectName("formLabel")
        ip_label.setFixedWidth(100)
        self.ipInput = QLineEdit()
        self.ipInput.setObjectName("settingsInput")
        self.ipInput.setFixedHeight(30)
        self.ipInput.setText(self.config.get("ip", "127.0.0.1"))
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ipInput, stretch=1)

        # 端口与测试按钮布局
        port_layout = QHBoxLayout()
        port_layout.setSpacing(10)
        
        port_label = QLabel(tr("service_port"))
        port_label.setObjectName("formLabel")
        port_label.setFixedWidth(100)
        self.portInput = QLineEdit()
        self.portInput.setObjectName("settingsInput")
        self.portInput.setFixedSize(90, 30)
        self.portInput.setText(self.config.get("port", "22267"))
        port_layout.addWidget(port_label)
        port_layout.addWidget(self.portInput)
        port_layout.addStretch()

        self.testBtn = QPushButton(tr("test_connection"))
        self.testBtn.setObjectName("testBtn")
        self.testBtn.setCursor(Qt.PointingHandCursor)
        self.testBtn.setFocusPolicy(Qt.NoFocus)
        self.testBtn.setFixedSize(120, 30)
        self.testBtn.clicked.connect(self._run_connection_test)
        port_layout.addWidget(self.testBtn)

        token_layout = QHBoxLayout()
        token_layout.setSpacing(10)
        token_label = QLabel("API Token")
        token_label.setObjectName("formLabel")
        token_label.setFixedWidth(100)
        self.tokenInput = QLineEdit()
        self.tokenInput.setObjectName("settingsInput")
        self.tokenInput.setFixedHeight(30)
        self.tokenInput.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.tokenInput.setText(self.config.get("api_token", ""))
        token_layout.addWidget(token_label)
        token_layout.addWidget(self.tokenInput, stretch=1)

        self.tokenGenerateBtn = QPushButton(tr("generate"))
        self.tokenGenerateBtn.setObjectName("tokenBtn")
        self.tokenGenerateBtn.setCursor(Qt.PointingHandCursor)
        self.tokenGenerateBtn.setFocusPolicy(Qt.NoFocus)
        self.tokenGenerateBtn.setFixedSize(80, 30)
        self.tokenGenerateBtn.clicked.connect(self._generate_token)
        token_layout.addWidget(self.tokenGenerateBtn)

        # 版本更新布局
        update_layout = QHBoxLayout()
        update_layout.setSpacing(10)
        
        update_label = QLabel(tr("version_update"))
        update_label.setObjectName("formLabel")
        update_label.setFixedWidth(100)
        
        self.versionLabel = QLabel(f"{tr('current_version')} {VERSION}")
        self.versionLabel.setStyleSheet("color: #a6abb4; font-size: 13px; font-family: 'Microsoft YaHei', 'Segoe UI';")
        
        self.updateBtn = QPushButton(tr("check_update"))
        self.updateBtn.setObjectName("updateBtn")
        self.updateBtn.setCursor(Qt.PointingHandCursor)
        self.updateBtn.setFocusPolicy(Qt.NoFocus)
        self.updateBtn.setFixedSize(110, 30)
        self.updateBtn.setStyleSheet("""
            QPushButton#updateBtn {
                background-color: transparent;
                border: 1px solid #454852;
                border-radius: 4px;
                color: #a6abb4;
            }
            QPushButton#updateBtn:hover {
                background-color: #454852;
                color: #ffffff;
            }
        """)
        self.updateBtn.clicked.connect(self._check_for_updates)
        
        update_layout.addWidget(update_label)
        update_layout.addWidget(self.versionLabel)
        update_layout.addStretch()
        update_layout.addWidget(self.updateBtn)

        form_layout.addLayout(ip_layout)
        form_layout.addLayout(port_layout)
        form_layout.addLayout(token_layout)
        form_layout.addLayout(update_layout)
        form_layout.addStretch()

        # 绑定测试结果信号
        self.test_result_signal.connect(self._on_test_result)

        # 底部按钮
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 8, 0, 0)
        btn_layout.addStretch()

        self.cancelBtn = QPushButton(tr("cancel"))
        self.cancelBtn.setObjectName("cancelBtn")
        self.cancelBtn.setCursor(Qt.PointingHandCursor)
        self.cancelBtn.setFocusPolicy(Qt.NoFocus)
        self.cancelBtn.setFixedSize(76, 30)
        self.cancelBtn.clicked.connect(self.reject)

        self.saveBtn = QPushButton(tr("save"))
        self.saveBtn.setObjectName("saveBtn")
        self.saveBtn.setCursor(Qt.PointingHandCursor)
        self.saveBtn.setFocusPolicy(Qt.NoFocus)
        self.saveBtn.setFixedSize(76, 30)
        self.saveBtn.clicked.connect(self.accept)

        btn_layout.addWidget(self.cancelBtn)
        btn_layout.addWidget(self.saveBtn)

        form_layout.addLayout(btn_layout)

        card_layout.addWidget(self.formBg)
        main_layout.addWidget(self.card)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.card.setGraphicsEffect(shadow)

        self._center_on_screen()

    def _center_on_screen(self):
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
            self.move(x, y)

    def _check_for_updates(self):
        self.updateBtn.setEnabled(False)
        self.updateBtn.setText(tr("checking"))
        self._checking_active = True
        QTimer.singleShot(4000, self._on_update_timeout)
        threading.Thread(target=self._update_task, daemon=True).start()

    def _update_task(self):
        result = check_for_updates(VERSION)
        QTimer.singleShot(0, lambda: self._handle_update_check_result(result))

    def _handle_update_check_result(self, result):
        if not getattr(self, "_checking_active", False):
            return
        self._checking_active = False
        if result.get("has_update"):
            self.updateBtn.setText(tr("download_update"))
            self.updateBtn.setStyleSheet("""
                QPushButton#updateBtn {
                    background-color: #28e06f;
                    border: none;
                    border-radius: 4px;
                    color: #1a1b26;
                    font-weight: bold;
                }
                QPushButton#updateBtn:hover {
                    background-color: #42d392;
                }
            """)
            self.updateBtn.setEnabled(True)
            try:
                self.updateBtn.clicked.disconnect()
            except Exception:
                pass
            
            download_url = result["url"]
            self.updateBtn.clicked.connect(lambda: self._start_download(download_url))
        elif "error" in result:
            self.updateBtn.setText(tr("check_failed"))
            self.updateBtn.setEnabled(True)
            QTimer.singleShot(2000, self._reset_update_btn)
        else:
            self.updateBtn.setText(tr("new_version"))
            QTimer.singleShot(2000, self._reset_update_btn)

    def _start_download(self, download_url):
        self.updateBtn.setEnabled(False)
        self.updateBtn.setText("0%")
        threading.Thread(target=do_update, args=(download_url, self._on_download_progress, self._on_update_finish), daemon=True).start()

    def _on_download_progress(self, percentage):
        QTimer.singleShot(0, lambda: self.updateBtn.setText(f"{percentage}%"))

    def _on_update_finish(self, success, message):
        def _ui_update():
            self.updateBtn.setText(tr("restart") if success else tr("check_failed"))
            if not success:
                self.updateBtn.setEnabled(True)
                QTimer.singleShot(3000, self._reset_update_btn)
        QTimer.singleShot(0, _ui_update)

    def _on_update_timeout(self):
        if getattr(self, "_checking_active", False):
            self._checking_active = False
            self.updateBtn.setText(tr("timeout"))
            self.updateBtn.setEnabled(True)
            QTimer.singleShot(2000, self._reset_update_btn)

    def _reset_update_btn(self):
        self.updateBtn.setText(tr("check_update"))
        self.updateBtn.setEnabled(True)
        self.updateBtn.setStyleSheet("""
            QPushButton#updateBtn {
                background-color: transparent;
                border: 1px solid #454852;
                border-radius: 4px;
                color: #a6abb4;
            }
            QPushButton#updateBtn:hover {
                background-color: #454852;
                color: #ffffff;
            }
        """)
        try:
            self.updateBtn.clicked.disconnect()
        except Exception:
            pass
        self.updateBtn.clicked.connect(self._check_for_updates)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            import sys
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.ReleaseCapture()
                hwnd = self.winId()
                ctypes.windll.user32.SendMessageW(int(hwnd), 0x0112, 0xF012, 0)
            else:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        import sys
        if sys.platform != "win32":
            if hasattr(self, "_drag_offset") and event.buttons() & Qt.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()

    def accept(self):
        self.config["auto_start"] = self.autoStartCheck.isChecked()
        self.config["always_on_top"] = self.alwaysOnTopCheck.isChecked()
        self.config["theme"] = "light" if self.lightThemeCheck.isChecked() else "dark"
        self.config["lang"] = "en" if self.englishLangCheck.isChecked() else "zh"
        self.config["ip"] = self.ipInput.text()
        self.config["port"] = self.portInput.text()
        self.config["api_token"] = self.tokenInput.text().strip()
        self.config["mini_click_through"] = self.miniClickThroughCheck.isChecked()
        self.config["mini_opacity"] = self._normalize_opacity(self.miniOpacitySlider.value())
        if "api_port" in self.config:
            del self.config["api_port"]
        print(f"[配置保存] 语言: {self.config['lang']}, 自动启动: {self.config['auto_start']}, 主窗口置顶: {self.config['always_on_top']}, 主题: {self.config['theme']}, IP: {self.config['ip']}, Port: {self.config['port']}")
        super().accept()

    def _normalize_opacity(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 100
        return max(35, min(value, 100))

    def _generate_token(self):
        self.tokenInput.setText(secrets.token_urlsafe(32))
        self.tokenInput.setFocus()

    def _run_connection_test(self):
        ip = self.ipInput.text().strip()
        port_str = self.portInput.text().strip()
        
        if not ip or not port_str.isdigit():
            self._on_test_result(False, tr("test_invalid"))
            return
            
        self.testBtn.setText("...")
        self.testBtn.setIcon(QIcon())
        self.testBtn.setEnabled(False)
        self.testBtn.setProperty("state", "testing")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
        
        threading.Thread(
            target=self._test_api,
            args=(ip, port_str, self.tokenInput.text().strip()),
            daemon=True,
        ).start()

    def _test_api(self, ip, port, token):
        success = False
        message = ""
        try:
            test_config = {
                "ip": ip,
                "port": port,
                "api_token": token,
            }
            resp = requests.get(
                f"{api_base_url(test_config)}/api/health",
                headers=api_headers(test_config),
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
        p = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        
        if state == "success":
            pen = QPen(QColor("#42d392"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(5, 12, 10, 17)
            p.drawLine(10, 17, 19, 7)
        elif state == "error":
            pen = QPen(QColor("#ff5c5c"), 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(7, 7, 17, 17)
            p.drawLine(17, 7, 7, 17)
            
        p.end()
        return QIcon(pixmap)

    def _on_test_result(self, success, message=""):
        self.testBtn.setEnabled(True)
        self.testBtn.setText("")
        self.testBtn.setToolTip(message)
        self.testBtn.setIconSize(QSize(20, 20))
        if success:
            self.testBtn.setIcon(self._create_icon("success"))
            self.testBtn.setProperty("state", "success")
        else:
            self.testBtn.setIcon(self._create_icon("error"))
            self.testBtn.setProperty("state", "error")
            
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
        
        QTimer.singleShot(2000, self._reset_test_btn)

    def _reset_test_btn(self):
        self.testBtn.setIcon(QIcon())
        self.testBtn.setText(tr("test_connection"))
        self.testBtn.setToolTip("")
        self.testBtn.setProperty("state", "normal")
        self.testBtn.style().unpolish(self.testBtn)
        self.testBtn.style().polish(self.testBtn)
