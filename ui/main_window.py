import sys
import os
import json
import math
import weakref
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QVBoxLayout, QHBoxLayout, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, QRectF, QTimer, Signal, QPointF, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QFontMetrics, QPainterPath, QIcon, QPixmap
import threading
import time

from .api_client import api_headers
from .window_snap import snap_to_available_screen
from .i18n import tr
from .message_dialog import ask_confirm, show_info, show_warning

VALID_STATUSES = {"idle", "running", "error", "update", "disconnected"}
ANIMATED_STATUSES = {"running", "error", "update", "disconnected"}
_BOTTOM_ICON_CACHE = {}


def _requests():
    import requests
    return requests

def normalize_status(status):
    return status if status in VALID_STATUSES else "idle"

def get_status_text(status):
    return tr(normalize_status(status))

def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def config_path():
    return os.path.join(app_base_dir(), "config.json")

def fastapi_source_path():
    relative_path = os.path.join("resources", "fastapi_payload.txt")
    candidates = [
        os.path.join(app_base_dir(), relative_path),
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, relative_path))
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]

def fastapi_output_path():
    return os.path.join(app_base_dir(), "output", "fastapi.py")

def asset_path(*parts):
    relative_path = os.path.join("ui", "assets", *parts)
    candidates = [
        os.path.join(app_base_dir(), relative_path),
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, relative_path))
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]

class StatusIndicator(QWidget):
    """带行动效的状态指示器"""
    _sync_started_at = time.monotonic()
    _active_widgets = weakref.WeakSet()
    _animation_timer = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)  # 加大尺寸
        self._state = "idle"  # idle, running, error
        self_ref = weakref.ref(self)
        cls = type(self)
        self.destroyed.connect(lambda: cls._active_widgets.discard(self_ref()))

    @classmethod
    def _ensure_animation_timer(cls):
        if cls._animation_timer is not None:
            return cls._animation_timer
        cls._animation_timer = QTimer(QApplication.instance())
        cls._animation_timer.setInterval(50)
        cls._animation_timer.timeout.connect(cls._update_active_animations)
        return cls._animation_timer

    @classmethod
    def _update_active_animations(cls):
        for widget in list(cls._active_widgets):
            try:
                if widget.isVisible():
                    widget.update()
            except RuntimeError:
                cls._active_widgets.discard(widget)
        if not cls._active_widgets and cls._animation_timer:
            cls._animation_timer.stop()

    @classmethod
    def _synced_angle(cls, degrees_per_second):
        elapsed = time.monotonic() - cls._sync_started_at
        return (elapsed * degrees_per_second) % 360

    def setStatus(self, state):
        state = normalize_status(state)
        if self._state == state:
            return
        self._state = state
        try:
            if state in ANIMATED_STATUSES:
                self._active_widgets.add(self)
                timer = self._ensure_animation_timer()
                if not timer.isActive():
                    timer.start()
            else:
                self._active_widgets.discard(self)
                if not self._active_widgets and self._animation_timer:
                    self._animation_timer.stop()
            self.update()
        except RuntimeError:
            pass  # 忽略退出时 C++ 对象已销毁的错误

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        
        if self._state == "idle":
            # 闲置：灰色静止空心圆环，尺寸和线宽与运行中完全统一
            pen = QPen(QColor("#6b707a"), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(2, 2, 12, 12)
            
        elif self._state == "running":
            # 运行中：绿色旋转圆弧
            pen = QPen(QColor(66, 211, 146), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # drawArc: x, y, w, h, startAngle, spanAngle (以 1/16 度为单位)
            angle = self._synced_angle(-320)
            p.drawArc(2, 2, 12, 12, int(angle * 16), 270 * 16)

        elif self._state == "update":
            # 更新中：蓝色旋转圆弧
            pen = QPen(QColor(96, 165, 250), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            angle = self._synced_angle(-320)
            p.drawArc(2, 2, 12, 12, int(angle * 16), 270 * 16)
            
        elif self._state == "error":
            # 错误：亮金黄色球从小到大，最小透明到最大亮黄色
            scale = self._synced_angle(600) / 360.0
            size = 4 + 10 * scale # 4 ~ 14 之间变化
            offset = (16 - size) / 2
            
            alpha = int(255 * scale)
            color = QColor(255, 193, 7, alpha) # 亮金黄色 (FFC107)
            
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QRectF(offset, offset, size, size))
            
        elif self._state == "disconnected":
            # 断开：红色呼吸动效
            angle = self._synced_angle(160)
            scale = (math.sin(math.radians(angle)) + 1) / 2 # 0.0 ~ 1.0
            size = 8 + 4 * scale # 8 ~ 12 之间变化
            offset = (16 - size) / 2
            
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(245, 108, 108)) # 红色
            p.drawEllipse(QRectF(offset, offset, size, size))
            
        p.end()

class WindowButton(QWidget):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # 获取主题
        theme = "dark"
        curr = self
        while curr:
            if hasattr(curr, "config"):
                theme = curr.config.get("theme", "dark")
                break
            curr = curr.parent()

        if self._hover:
            if self.kind == "close":
                fill_color = QColor("#e11d48") if theme == "light" else QColor("#c42b1c")
                p.fillRect(self.rect(), fill_color)
                color = QColor("#ffffff")
            else:
                fill_color = QColor("#cbd5e1") if theme == "light" else QColor("#2a2e36")
                p.fillRect(self.rect(), fill_color)
                color = QColor("#0f172a") if theme == "light" else QColor("#f0f0f0")
        else:
            color = QColor("#64748b") if theme == "light" else QColor("#a6abb4")

        pen = QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        if self.kind == "minimize":
            p.drawLine(9, 18, 21, 18)
        else:
            p.drawLine(10, 10, 20, 20)
            p.drawLine(20, 10, 10, 20)
        p.end()


def build_bottom_icon(kind, color):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.setBrush(Qt.NoBrush)

    cx = 12.0
    top = 3.0

    if kind == "settings":
        painter.drawEllipse(QRectF(cx - 3.0, top + 6.0, 6.0, 6.0))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            inner = QPointF(cx + math.cos(rad) * 6.3, top + 9.0 + math.sin(rad) * 6.3)
            outer = QPointF(cx + math.cos(rad) * 8.3, top + 9.0 + math.sin(rad) * 8.3)
            painter.drawLine(inner, outer)
    elif kind == "home":
        roof = QPainterPath()
        roof.moveTo(QPointF(cx - 8.0, top + 10.0))
        roof.lineTo(QPointF(cx, top + 3.0))
        roof.lineTo(QPointF(cx + 8.0, top + 10.0))
        painter.drawPath(roof)
        painter.drawRoundedRect(QRectF(cx - 6.2, top + 9.5, 12.4, 9.0), 1.5, 1.5)
    elif kind == "float":
        painter.drawRoundedRect(QRectF(cx - 8.0, top + 5.0, 10.0, 10.0), 1.0, 1.0)
        painter.drawRoundedRect(QRectF(cx - 2.0, top + 11.0, 10.0, 10.0), 1.0, 1.0)
    elif kind == "log":
        painter.drawRoundedRect(QRectF(cx - 6.5, top + 1.0, 13.0, 16.0), 1.5, 1.5)
        painter.drawLine(QPointF(cx - 3.5, top + 6.0), QPointF(cx + 3.5, top + 6.0))
        painter.drawLine(QPointF(cx - 3.5, top + 10.0), QPointF(cx + 3.5, top + 10.0))
        painter.drawLine(QPointF(cx - 3.5, top + 14.0), QPointF(cx + 2.0, top + 14.0))
    elif kind == "export":
        painter.drawRoundedRect(QRectF(cx - 7.0, top + 9.0, 14.0, 9.0), 1.5, 1.5)
        painter.drawLine(QPointF(cx, top + 12.0), QPointF(cx, top + 3.0))
        painter.drawLine(QPointF(cx, top + 3.0), QPointF(cx - 4.0, top + 7.0))
        painter.drawLine(QPointF(cx, top + 3.0), QPointF(cx + 4.0, top + 7.0))
    elif kind == "screenshot":
        painter.drawRoundedRect(QRectF(cx - 8.0, top + 4.0, 16.0, 13.0), 2.0, 2.0)
        painter.drawEllipse(QRectF(cx + 2.5, top + 6.0, 2.5, 2.5))
        image_path = QPainterPath()
        image_path.moveTo(QPointF(cx - 6.0, top + 15.0))
        image_path.lineTo(QPointF(cx - 1.5, top + 10.5))
        image_path.lineTo(QPointF(cx + 1.5, top + 13.0))
        image_path.lineTo(QPointF(cx + 5.5, top + 9.0))
        image_path.lineTo(QPointF(cx + 8.0, top + 11.5))
        painter.drawPath(image_path)
    painter.end()
    return QIcon(pixmap)


def load_bottom_icon(kind, hover=False):
    cache_key = (kind, hover)
    if cache_key in _BOTTOM_ICON_CACHE:
        return _BOTTOM_ICON_CACHE[cache_key]

    # 底部导航栏的原版普通态 PNG 本身就带有完美的透明通道，且非常美观。
    # 悬浮态图片（_hover.png）被错误填充了黑底，因此我们对于导航栏图标，在悬浮时同样加载带透明的原版 PNG，
    # 悬浮底色高亮完全由 QSS 样式表透明承载，从而完美保持原版图标质感并彻底消除黑底。
    if kind in {"settings", "home", "float", "log", "export", "screenshot"}:
        icon_path = asset_path("bottom_icons", f"{kind}.png")
    else:
        suffix = "_hover" if hover else ""
        icon_path = asset_path("bottom_icons", f"{kind}{suffix}.png")
        
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
    else:
        icon = build_bottom_icon(kind, "#d4d8df" if hover else "#a6abb4")
    _BOTTOM_ICON_CACHE[cache_key] = icon
    return icon


class BottomIconButton(QPushButton):
    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._normal_icon = load_bottom_icon(kind)
        self._hover_icon = load_bottom_icon(kind, hover=True)
        self.setFixedSize(36, 40)
        self.setIconSize(QSize(22, 22))
        self.setIcon(self._normal_icon)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("lineIconBtn")

    def enterEvent(self, event):
        self.setIcon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self._normal_icon)
        super().leaveEvent(event)


class ConfigActionButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = "idle"
        self.setFixedSize(72, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("configActionBtn")

    def set_status(self, status):
        status = normalize_status(status)
        if self._status == status:
            return
        self._status = status
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._status == "running":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ff4d4f"))
            painter.drawRect(33, 11, 12, 12)
        else:
            path = QPainterPath()
            path.moveTo(QPointF(31, 9))
            path.lineTo(QPointF(31, 23))
            path.lineTo(QPointF(44, 16))
            path.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#28e06f"))
            painter.drawPath(path)
        painter.end()


class ConfigDeleteButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._normal_icon = load_bottom_icon("delete")
        self._hover_icon = load_bottom_icon("delete", hover=True)
        disabled_path = asset_path("bottom_icons", "delete_disabled.png")
        self._disabled_icon = QIcon(disabled_path) if os.path.exists(disabled_path) else self._normal_icon
        self.setFixedSize(24, 32)
        self.setIconSize(QSize(17, 17))
        self.setIcon(self._normal_icon)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("configDeleteBtn")
        self.setToolTip(tr("delete_config_tip"))

    def enterEvent(self, event):
        if self.isEnabled():
            self.setIcon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self._normal_icon if self.isEnabled() else self._disabled_icon)
        super().leaveEvent(event)

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.setIcon(self._normal_icon if enabled else self._disabled_icon)


class MainConfigRow(QWidget):
    btn_enable_signal = Signal(bool)

    def __init__(self, config_name, main_card, parent=None):
        super().__init__(parent)
        self.config_name = config_name
        self.main_card = main_card
        self.current_status = None
        self.setFixedHeight(36)
        self.setCursor(Qt.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 2, 6, 2)
        layout.setSpacing(10)

        self.statusIndicator = StatusIndicator()
        layout.addWidget(self.statusIndicator, alignment=Qt.AlignVCenter)

        self.statusLabel = QLabel()
        self.statusLabel.setObjectName("rowStatusLabel")
        self.statusLabel.setMinimumWidth(0)
        self.statusLabel.setAlignment(Qt.AlignVCenter)
        self.statusLabel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self.statusLabel, stretch=1, alignment=Qt.AlignVCenter)

        self.deleteBtn = ConfigDeleteButton()
        self.deleteBtn.clicked.connect(self._on_delete_clicked)
        layout.addWidget(self.deleteBtn)

        self.toggleBtn = ConfigActionButton()
        self.toggleBtn.clicked.connect(self._on_toggle_clicked)
        self.btn_enable_signal.connect(self.toggleBtn.setEnabled)
        layout.addWidget(self.toggleBtn)

        self.update_status("idle")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_card.set_current_config(self.config_name)
            if self.main_card.window():
                self.main_card.window().mousePressEvent(event)
            event.accept()

    def mouseMoveEvent(self, event):
        if self.main_card.window():
            self.main_card.window().mouseMoveEvent(event)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.main_card.window():
            self.main_card.window().mouseReleaseEvent(event)
            event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_label()

    def _refresh_label(self):
        full_text = f"{self.config_name}: {get_status_text(self.current_status)}"
        metrics = QFontMetrics(self.statusLabel.font())
        width = max(self.statusLabel.width() - 2, 20)
        self.statusLabel.setText(metrics.elidedText(full_text, Qt.ElideRight, width))

    def update_status(self, status):
        status = normalize_status(status)
        delete_enabled = status != "running" and len(self.main_card._configs) > 1
        if self.current_status == status:
            if self.deleteBtn.isEnabled() != delete_enabled:
                self.deleteBtn.setEnabled(delete_enabled)
            return

        self.current_status = status
        self.statusIndicator.setStatus(self.current_status)
        self.toggleBtn.set_status(self.current_status)
        self.deleteBtn.setEnabled(delete_enabled)
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

        def send_req():
            ip = self.main_card.config.get("ip", "127.0.0.1")
            port = self.main_card.config.get("port", "22267")
            try:
                url = f"http://{ip}:{port}/api/{action}"
                resp = _requests().post(
                    url,
                    params={"config": self.config_name},
                    headers=api_headers(self.main_card.config),
                    timeout=3,
                )
                if resp.status_code == 200:
                    status = normalize_status(resp.json().get("status", "idle"))
                    self.main_card.status_all_update_signal.emit({self.config_name: status})
                    if self.main_card.current_config == self.config_name:
                        self.main_card.status_update_signal.emit(status)
                else:
                    print(f"[错误] {action} 请求失败，HTTP 状态码: {resp.status_code}")
                time.sleep(0.5)
                self.main_card._start_poll_thread()
            except Exception as e:
                print(f"[错误] 发送控制命令失败: {e}")
            finally:
                self.btn_enable_signal.emit(True)

        threading.Thread(target=send_req, daemon=True).start()

class CardWidget(QFrame):
    """主卡片"""
    status_update_signal = Signal(str)
    configs_update_signal = Signal(list)
    status_all_update_signal = Signal(dict)
    config_delete_result_signal = Signal(bool, str, str, list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setFixedSize(294, 166)
        
        self.config = {
            "ip": "127.0.0.1",
            "port": "22267",
            "auto_start": False,
            "always_on_top": False,
            "api_token": "",
            "mini_click_through": False,
            "mini_opacity": 100,
            "setup_completed": False,
        }
        
        self.config_path = config_path()
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)
                self.config.update(loaded_config)
                if "setup_completed" not in loaded_config:
                    self.config["setup_completed"] = True
            except Exception as e:
                print(f"[警告] 读取 {self.config_path} 失败: {e}")

        self._status = "idle" # idle, running, error, disconnected
        self._configs = ["alas"] # 默认配置，稍后会动态刷新
        self.current_config = self.config.get("current_config", "alas")
        self._configs[0] = self.current_config
        self._configs_fetching = False
        self._configs_last_fetch_at = 0.0
        self._configs_fetch_interval = 15.0
        self._polling_status = False
        self._poll_lock = threading.Lock()
        self._statuses = {}
        self.rows = {}
        
        self._config_idx = 0

        self._build_ui()
        
        self.status_update_signal.connect(self._update_status_ui)
        self.configs_update_signal.connect(self._on_configs_updated)
        self.status_all_update_signal.connect(self._on_status_all_updated)
        self.config_delete_result_signal.connect(self._on_config_delete_result)
        
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._start_poll_thread)
        self.poll_timer.start(3000) # 每3秒心跳一次
        
        # 启动时立刻执行一次，避免3秒钟的假死等待感
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
        self.windowCtrlBg.setCursor(Qt.SizeAllCursor)
        self.windowCtrlBg.mousePressEvent = self._forward_drag_press
        self.windowCtrlBg.mouseMoveEvent = self._forward_drag_move
        self.windowCtrlBg.mouseReleaseEvent = self._forward_drag_release
        ctrl_layout = QHBoxLayout(self.windowCtrlBg)
        ctrl_layout.setContentsMargins(8, 0, 8, 0)
        ctrl_layout.setSpacing(0)

        self.dragHint = QWidget(self.windowCtrlBg)
        self.dragHint.setCursor(Qt.SizeAllCursor)
        self.dragHint.mousePressEvent = self._forward_drag_press
        self.dragHint.mouseMoveEvent = self._forward_drag_move
        self.dragHint.mouseReleaseEvent = self._forward_drag_release
        ctrl_layout.addWidget(self.dragHint, stretch=1)

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
        self.configListBg.setCursor(Qt.SizeAllCursor)
        self.configListBg.mousePressEvent = self._forward_drag_press
        self.configListBg.mouseMoveEvent = self._forward_drag_move
        self.configListBg.mouseReleaseEvent = self._forward_drag_release
        list_layout = QVBoxLayout(self.configListBg)
        list_layout.setContentsMargins(10, 8, 10, 6)
        list_layout.setSpacing(2)
        self.rows_layout = list_layout
        self.configScroll.setWidget(self.configListBg)
        main_layout.addWidget(self.configScroll, stretch=1)

        self._rebuild_rows()

        self.bottomBg = QWidget(self)
        self.bottomBg.setObjectName("mainBottomBg")
        self.bottomBg.setAttribute(Qt.WA_StyledBackground, True)
        self.bottomBg.setFixedHeight(40)
        bot_layout = QHBoxLayout(self.bottomBg)
        bot_layout.setContentsMargins(24, 0, 24, 0)
        bot_layout.setSpacing(0)
        
        self.setIcon = BottomIconButton("settings") # 设置
        self.homeIcon = BottomIconButton("home") # 主页
        self.floatIcon = BottomIconButton("float") # 悬浮窗
        self.logIcon = BottomIconButton("log") # 日志
        self.exportIcon = BottomIconButton("export") # 导出
        self.screenshotIcon = BottomIconButton("screenshot") # 错误截图

        self.setIcon.setToolTip(tr("settings_btn_tip"))
        self.homeIcon.setToolTip(tr("home_btn_tip"))
        self.floatIcon.setToolTip(tr("float_btn_tip"))
        self.logIcon.setToolTip(tr("log_btn_tip"))
        self.exportIcon.setToolTip(tr("export_btn_tip"))
        self.screenshotIcon.setToolTip(tr("screenshot_btn_tip"))
            
        bot_layout.addWidget(self.setIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.homeIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.floatIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.logIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.exportIcon)
        bot_layout.addStretch()
        bot_layout.addWidget(self.screenshotIcon)

        # 事件绑定
        self.setIcon.mousePressEvent = lambda e: self._on_icon_click("设置", self.setIcon)
        self.homeIcon.mousePressEvent = lambda e: self._on_icon_click("主页", self.homeIcon)
        self.floatIcon.mousePressEvent = lambda e: self._on_icon_click("最小化", self.floatIcon)
        self.logIcon.mousePressEvent = lambda e: self._on_icon_click("日志", self.logIcon)
        self.exportIcon.mousePressEvent = lambda e: self._on_icon_click("导出", self.exportIcon)
        self.screenshotIcon.mousePressEvent = lambda e: self._on_icon_click("错误截图", self.screenshotIcon)

        main_layout.addWidget(self.bottomBg)

    def retranslate_ui(self):
        self.setIcon.setToolTip(tr("settings_btn_tip"))
        self.homeIcon.setToolTip(tr("home_btn_tip"))
        self.floatIcon.setToolTip(tr("float_btn_tip"))
        self.logIcon.setToolTip(tr("log_btn_tip"))
        self.exportIcon.setToolTip(tr("export_btn_tip"))
        self.screenshotIcon.setToolTip(tr("screenshot_btn_tip"))
        self._rebuild_rows()

    def _save_config(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[错误] 写入 {self.config_path} 失败: {e}")
            return False

    def _sync_window_size(self):
        row_count = min(max(len(self._configs), 2), 5)
        list_height = 8 + 6 + row_count * 36 + max(row_count - 1, 0) * 2 + 8
        card_height = 30 + list_height + 40
        self.setFixedSize(294, card_height)
        if self.window() and self.window() is not self:
            self.window().setFixedSize(314, card_height + 20)

    def _rebuild_rows(self):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
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
                row.update_status(self._statuses[config_name])
        self.rows_layout.addStretch()
        self._sync_window_size()

    def set_current_config(self, config_name):
        if not config_name or self.current_config == config_name:
            return
        self.current_config = config_name
        self.config["current_config"] = self.current_config
        self._save_config()
        if self.current_config not in self.rows:
            self._rebuild_rows()
        if hasattr(self, "log_dialog") and self.log_dialog.isVisible():
            self.log_dialog.set_config(self.current_config)

    def delete_config(self, config_name):
        threading.Thread(target=self._delete_config_task, args=(config_name,), daemon=True).start()

    def _delete_config_task(self, config_name):
        ip = self.config.get("ip", "127.0.0.1")
        port = self.config.get("port", "22267")
        try:
            url = f"http://{ip}:{port}/api/configs"
            resp = _requests().delete(
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

    def _update_status_ui(self, status):
        status = normalize_status(status)
        if self._status == status:
            return
        self._status = status
        if self.current_config in self.rows:
            self.rows[self.current_config].update_status(status)
        print(f"[日志] 状态同步 → {status} ({self.current_config})")

    def _start_poll_thread(self):
        # 避免心跳慢或网络卡顿时不断堆积轮询线程。
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
        finally:
            with self._poll_lock:
                self._polling_status = False

    def _fetch_configs_task(self):
        ip = self.config.get("ip", "127.0.0.1")
        port = self.config.get("port", "22267")
        try:
            url = f"http://{ip}:{port}/api/configs"
            resp = _requests().get(url, headers=api_headers(self.config), timeout=2.0)
            if resp.status_code == 200:
                data = resp.json()
                configs = data.get("configs", ["alas"])
                if isinstance(configs, list) and configs:
                    self.configs_update_signal.emit(configs)
        except Exception:
            pass
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

        # 强制下一次 update_status 能够生效，以便更新文字前缀。
        old_status = self._status
        self._status = None
        self._update_status_ui(old_status or "idle")

        # 广播给迷你悬浮窗和日志窗口。
        if hasattr(self, "mini_dialog") and self.mini_dialog.isVisible():
            self.mini_dialog.rebuild_rows()
        if hasattr(self, "log_dialog") and self.log_dialog.isVisible():
            self.log_dialog.set_configs(self._configs, self.current_config)

    def _on_status_all_updated(self, statuses):
        changed_statuses = {
            config_name: status
            for config_name, status in statuses.items()
            if self._statuses.get(config_name) != status
        }
        self._statuses.update(statuses)
        new_configs = [str(config_name) for config_name in statuses if str(config_name) not in self._configs]
        if new_configs:
            self._configs.extend(new_configs)
            self._configs.sort(key=str.lower)
            self._rebuild_rows()
        for config_name, status in changed_statuses.items():
            if config_name in self.rows:
                self.rows[config_name].update_status(status)

    def _poll_status_task(self):
        if (
            hasattr(self, "_configs_fetched")
            and time.monotonic() - self._configs_last_fetch_at >= self._configs_fetch_interval
        ):
            delattr(self, "_configs_fetched")

        ip = self.config.get("ip", "127.0.0.1")
        port = self.config.get("port", "22267")
        try:
            url = f"http://{ip}:{port}/api/status_all"
            resp = _requests().get(url, headers=api_headers(self.config), timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                statuses = {
                    str(config_name): normalize_status(status)
                    for config_name, status in data.get("statuses", {}).items()
                }
                self.status_all_update_signal.emit(statuses)
                current_status = statuses.get(self.current_config, "idle")
                self.status_update_signal.emit(current_status)
            elif resp.status_code == 404:
                # 兼容没有 /api/status_all 的服务端：逐个配置读取状态。
                statuses = {}
                for config_name in self._configs:
                    try:
                        url = f"http://{ip}:{port}/api/status"
                        resp2 = _requests().get(
                            url,
                            params={"config": config_name},
                            headers=api_headers(self.config),
                            timeout=1.5,
                        )
                        if resp2.status_code == 200:
                            statuses[config_name] = normalize_status(resp2.json().get("status", "idle"))
                        else:
                            statuses[config_name] = "disconnected"
                    except Exception:
                        statuses[config_name] = "disconnected"
                self.status_all_update_signal.emit(statuses)
                self.status_update_signal.emit(statuses.get(self.current_config, "disconnected"))
            else:
                self.status_update_signal.emit("disconnected")
        except Exception:
            self.status_update_signal.emit("disconnected")

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
        print(f"[日志] 点击图标 → {name}")
        if name == "关闭":
            QApplication.quit()
        elif name == "设置":
            from .settings_window import SettingsWindow
            # 传入 self.config 以便在设置窗口中读取和保存
            dialog = SettingsWindow(self.window(), self.config, self._configs, self.current_config)
            if dialog.exec():
                try:
                    from .i18n import set_language
                    set_language(self.config.get("lang", "zh"))

                    with open(self.config_path, "w", encoding="utf-8") as f:
                        json.dump(self.config, f, indent=4, ensure_ascii=False)
                    print(f"[日志] 配置已成功持久化到 {self.config_path}")

                    # 动态更新主界面翻译
                    self.retranslate_ui()

                    # 动态更新系统托盘菜单翻译
                    app = QApplication.instance()
                    if hasattr(app, "_alas_tray"):
                        tray = app._alas_tray
                        actions = tray.contextMenu().actions()
                        if len(actions) >= 7:
                            actions[0].setText(tr("show_main"))
                            actions[1].setText(tr("show_float"))
                            actions[2].setText(tr("open_webui"))
                            actions[4].setText(tr("wizard"))
                            actions[5].setText(tr("export_btn_tip"))
                            actions[7].setText(tr("quit"))

                    # 动态应用主题
                    from .theme import apply_theme
                    apply_theme(app, self.config.get("theme", "dark"))
                    
                    if hasattr(self.window(), "apply_always_on_top"):
                        self.window().apply_always_on_top(self.config.get("always_on_top", False))
                    if hasattr(self, "mini_dialog"):
                        self.mini_dialog.apply_window_settings()
                except Exception as e:
                    print(f"[错误] 写入 {self.config_path} 失败: {e}")
            dialog.deleteLater()
        elif name == "主页":
            import webbrowser
            # 根据设置中的 IP 和端口组合 URL 并打开默认浏览器
            url = f"http://{self.config['ip']}:{self.config['port']}"
            print(f"[日志] 打开主页 → {url}")
            webbrowser.open(url)
        elif name == "日志":
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
        elif name == "导出":
            from .fastapi_export_window import FastapiExportWindow
            dialog = getattr(self, "fastapi_dialog", None)
            if dialog is not None:
                try:
                    dialog.show()
                    dialog.activateWindow()
                    return
                except RuntimeError:
                    dialog = None
            if dialog is None:
                self.fastapi_dialog = FastapiExportWindow(
                    self.window(),
                    fastapi_source_path(),
                    fastapi_output_path(),
                    self.config,
                    self.config_path,
                )
                self.fastapi_dialog.show()
        elif name == "错误截图":
            from .error_screenshot_window import ErrorScreenshotWindow
            dialog = getattr(self, "screenshot_dialog", None)
            if dialog is not None:
                try:
                    dialog.show()
                    dialog.activateWindow()
                    dialog.fetch_groups()
                    return
                except RuntimeError:
                    dialog = None
            if dialog is None:
                self.screenshot_dialog = ErrorScreenshotWindow(self.window(), self.config)
                self.screenshot_dialog.show()
        elif name == "最小化":
            self.show_mini_window()

class AlasConsole(QWidget):
    auto_update_result_signal = Signal(dict, int)

    def __init__(self):
        super().__init__()
        self.setObjectName("mainWindow")
        self.setFixedSize(314, 186)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 核心卡片区域
        self.card = CardWidget(self)
        self.apply_always_on_top(self.card.config.get("always_on_top", False), show_after=False)
        main_layout.addWidget(self.card, alignment=Qt.AlignTop)
        
        # 阴影
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.card.setGraphicsEffect(shadow)

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
            from updater import check_for_updates
            result = check_for_updates(current_version)
        except Exception as exc:
            result = {"has_update": False, "error": str(exc)}
        self.auto_update_result_signal.emit(result, check_id)

    def _on_auto_update_result(self, result, check_id):
        if check_id != self._auto_update_check_id:
            return
        if not result.get("has_update"):
            if result.get("error"):
                print(f"[更新检查] 自动检查失败: {result.get('error')}")
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

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if hasattr(self, "_drag_offset") and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._snap_to_screen_edges()
            if hasattr(self, "_drag_offset"):
                del self._drag_offset
            event.accept()

    def _snap_to_screen_edges(self):
        snap_to_available_screen(self, margins=(10, 10, 10, 10))
