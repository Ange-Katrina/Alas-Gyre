from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPixmap
import requests
import threading

from .api_client import api_headers
from .i18n import tr
from .main_window import WindowButton


MAX_SCREENSHOT_PIXMAP_SIZE = QSize(1600, 1200)


class ErrorScreenshotWindow(QDialog):
    groups_update_signal = Signal(object)
    image_update_signal = Signal(object, str, str, str)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config if config is not None else {}
        self.groups = []
        self.current_group = None
        self.current_images = []
        self.current_pixmap = QPixmap()
        self._fetching_groups = False
        self._fetching_image_key = None
        self._loaded_image_key = None

        self.setObjectName("screenshotWindow")
        self.resize(760, 520)
        self.setMinimumSize(620, 420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(30, 20, 30, 30)

        self.card = QFrame(self)
        self.card.setObjectName("screenshotCard")
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("screenshotTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)
        top_layout.setSpacing(8)

        self.titleLabel = QLabel(tr("screenshot_title"))
        self.titleLabel.setObjectName("screenshotTitle")
        top_layout.addWidget(self.titleLabel)
        top_layout.addStretch()

        self.refreshBtn = QPushButton(tr("screenshot_refresh"), self.topBg)
        self.refreshBtn.setObjectName("screenshotRefreshBtn")
        self.refreshBtn.setCursor(Qt.PointingHandCursor)
        self.refreshBtn.setFocusPolicy(Qt.NoFocus)
        self.refreshBtn.setFixedSize(72, 24)
        self.refreshBtn.clicked.connect(self.fetch_groups)
        top_layout.addWidget(self.refreshBtn, alignment=Qt.AlignVCenter)

        self.closeBtn = WindowButton("close", self.topBg)
        self.closeBtn.mousePressEvent = lambda event: self.reject() if event.button() == Qt.LeftButton else None
        top_layout.addWidget(self.closeBtn)
        card_layout.addWidget(self.topBg)

        self.bodyBg = QWidget(self.card)
        self.bodyBg.setObjectName("screenshotBodyBg")
        self.bodyBg.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(14, 12, 14, 14)
        body_layout.setSpacing(10)

        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        group_label = QLabel(tr("screenshot_error_group"), self.bodyBg)
        group_label.setObjectName("screenshotFieldLabel")
        control_layout.addWidget(group_label)

        self.groupCombo = QComboBox(self.bodyBg)
        self.groupCombo.setObjectName("screenshotCombo")
        self.groupCombo.setFocusPolicy(Qt.NoFocus)
        self.groupCombo.setCursor(Qt.PointingHandCursor)
        self.groupCombo.currentIndexChanged.connect(self._on_group_selected)
        control_layout.addWidget(self.groupCombo, stretch=1)

        image_label = QLabel(tr("screenshot_image"), self.bodyBg)
        image_label.setObjectName("screenshotFieldLabel")
        control_layout.addWidget(image_label)

        self.imageCombo = QComboBox(self.bodyBg)
        self.imageCombo.setObjectName("screenshotCombo")
        self.imageCombo.setFocusPolicy(Qt.NoFocus)
        self.imageCombo.setCursor(Qt.PointingHandCursor)
        self.imageCombo.currentIndexChanged.connect(self._on_image_selected)
        control_layout.addWidget(self.imageCombo, stretch=1)

        body_layout.addLayout(control_layout)

        self.statusLabel = QLabel("", self.bodyBg)
        self.statusLabel.setObjectName("screenshotStatusLabel")
        body_layout.addWidget(self.statusLabel)

        self.imagePanel = QFrame(self.bodyBg)
        self.imagePanel.setObjectName("screenshotImagePanel")
        image_layout = QVBoxLayout(self.imagePanel)
        image_layout.setContentsMargins(12, 12, 12, 12)
        self.imageLabel = QLabel(tr("screenshot_loading"), self.imagePanel)
        self.imageLabel.setObjectName("screenshotImageLabel")
        self.imageLabel.setAlignment(Qt.AlignCenter)
        self.imageLabel.setMinimumSize(420, 280)
        self.imageLabel.setWordWrap(True)
        image_layout.addWidget(self.imageLabel)
        body_layout.addWidget(self.imagePanel, stretch=1)

        card_layout.addWidget(self.bodyBg, stretch=1)
        main_layout.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.card.setGraphicsEffect(shadow)

        self.sizeGrip = QSizeGrip(self.card)
        self.sizeGrip.setFixedSize(18, 18)
        self.sizeGrip.setStyleSheet("background: transparent;")
        self.sizeGrip.raise_()

        self.groups_update_signal.connect(self._on_groups_updated)
        self.image_update_signal.connect(self._on_image_updated)

        self._center_on_screen()
        self.fetch_groups()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sizeGrip"):
            self.sizeGrip.move(
                self.card.width() - self.sizeGrip.width() - 3,
                self.card.height() - self.sizeGrip.height() - 3,
            )
        self._update_image_view()

    def _center_on_screen(self):
        if self.parent():
            parent_geom = self.parent().geometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
            self.move(x, y)

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

    def fetch_groups(self):
        if self._fetching_groups:
            return
        self._fetching_groups = True
        self.refreshBtn.setEnabled(False)
        self._set_placeholder(tr("screenshot_loading"))
        self.statusLabel.setText(tr("screenshot_loading"))
        threading.Thread(target=self._fetch_groups_thread, daemon=True).start()

    def _fetch_groups_thread(self):
        ip = self.config.get("ip", "127.0.0.1")
        port = self.config.get("port", "22267")
        try:
            resp = requests.get(
                f"http://{ip}:{port}/api/error_screenshots",
                params={"limit": 30},
                headers=api_headers(self.config),
                timeout=3,
            )
            if resp.status_code == 200:
                payload = resp.json()
                payload["_ok"] = True
            else:
                try:
                    data = resp.json()
                    message = data.get("error") or data.get("message") or resp.text
                except Exception:
                    message = resp.text
                payload = {"_ok": False, "error": f"HTTP {resp.status_code}: {message}"}
        except Exception as exc:
            payload = {"_ok": False, "error": str(exc)}
        self.groups_update_signal.emit(payload)

    def _on_groups_updated(self, payload):
        self._fetching_groups = False
        self.refreshBtn.setEnabled(True)

        if not payload.get("_ok"):
            message = tr("screenshot_fetch_failed", error=payload.get("error", "unknown"))
            self.statusLabel.setText(message)
            self._set_placeholder(message)
            return

        self.groups = payload.get("groups") or []
        self.groupCombo.blockSignals(True)
        self.groupCombo.clear()
        for group in self.groups:
            title = group.get("display_time") or group.get("folder", "")
            count = group.get("image_count", len(group.get("images") or []))
            self.groupCombo.addItem(f"{title}  ·  {count}", group.get("folder"))
        if self.groups:
            self.groupCombo.setCurrentIndex(0)
        self.groupCombo.blockSignals(False)

        if not self.groups:
            self.current_group = None
            self.current_images = []
            self.imageCombo.clear()
            self.statusLabel.setText(tr("screenshot_empty"))
            self._set_placeholder(tr("screenshot_empty"))
            return

        self._set_group(0)

    def _on_group_selected(self, index):
        self._set_group(index)

    def _set_group(self, index):
        if index < 0 or index >= len(self.groups):
            return

        self.current_group = self.groups[index]
        self.current_images = self.current_group.get("images") or []
        self.imageCombo.blockSignals(True)
        self.imageCombo.clear()
        for image in self.current_images:
            self.imageCombo.addItem(image.get("name", ""), image.get("name", ""))
        if self.current_images:
            self.imageCombo.setCurrentIndex(len(self.current_images) - 1)
        self.imageCombo.blockSignals(False)

        if not self.current_images:
            self.statusLabel.setText(tr("screenshot_empty"))
            self._set_placeholder(tr("screenshot_empty"))
            return

        self._set_image(len(self.current_images) - 1)

    def _on_image_selected(self, index):
        self._set_image(index)

    def _set_image(self, index):
        if self.current_group is None or index < 0 or index >= len(self.current_images):
            return

        folder = self.current_group.get("folder", "")
        file_name = self.current_images[index].get("name", "")
        if not folder or not file_name:
            return
        image_key = (folder, file_name)
        if self._loaded_image_key == image_key and not self.current_pixmap.isNull():
            self._update_image_view()
            return
        if self._fetching_image_key == image_key:
            return

        self._fetching_image_key = image_key
        self.statusLabel.setText(tr("screenshot_loading_image", file=file_name))
        self._set_placeholder(tr("screenshot_loading_image", file=file_name))
        threading.Thread(target=self._fetch_image_thread, args=(folder, file_name), daemon=True).start()

    def _fetch_image_thread(self, folder, file_name):
        ip = self.config.get("ip", "127.0.0.1")
        port = self.config.get("port", "22267")
        error = ""
        data = b""
        try:
            resp = requests.get(
                f"http://{ip}:{port}/api/error_screenshots/image",
                params={"folder": folder, "file": file_name},
                headers=api_headers(self.config),
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.content
            else:
                try:
                    payload = resp.json()
                    message = payload.get("error") or payload.get("message") or resp.text
                except Exception:
                    message = resp.text
                error = f"HTTP {resp.status_code}: {message}"
        except Exception as exc:
            error = str(exc)
        self.image_update_signal.emit(data, folder, file_name, error)

    def _on_image_updated(self, data, folder, file_name, error):
        if self._fetching_image_key != (folder, file_name):
            return

        if error:
            message = tr("screenshot_image_failed", error=error)
            self.statusLabel.setText(message)
            self._set_placeholder(message)
            return

        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            message = tr("screenshot_image_failed", error="invalid image data")
            self.statusLabel.setText(message)
            self._set_placeholder(message)
            return

        if (
            pixmap.width() > MAX_SCREENSHOT_PIXMAP_SIZE.width()
            or pixmap.height() > MAX_SCREENSHOT_PIXMAP_SIZE.height()
        ):
            pixmap = pixmap.scaled(
                MAX_SCREENSHOT_PIXMAP_SIZE,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )

        self.current_pixmap = pixmap
        self._loaded_image_key = (folder, file_name)
        self.statusLabel.setText(tr("screenshot_loaded", folder=folder, file=file_name))
        self._update_image_view()

    def _set_placeholder(self, text):
        self.current_pixmap = QPixmap()
        self._loaded_image_key = None
        self.imageLabel.clear()
        self.imageLabel.setText(text)

    def _update_image_view(self):
        if self.current_pixmap.isNull() or not hasattr(self, "imageLabel"):
            return
        target_size = self.imageLabel.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return
        scaled = self.current_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.imageLabel.setText("")
        self.imageLabel.setPixmap(scaled)

    def reject(self):
        self.current_pixmap = QPixmap()
        self._fetching_image_key = None
        self._loaded_image_key = None
        self.imageLabel.clear()
        super().reject()
