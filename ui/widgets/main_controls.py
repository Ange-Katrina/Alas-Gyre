import math
import os
import time
import weakref

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from alas_gyre.core.paths import asset_path
from alas_gyre.core.status import normalize_status
from ..i18n import tr


ANIMATED_STATUSES = {"running", "error", "update", "disconnected", "scanning"}
_BOTTOM_ICON_CACHE = {}


class StatusIndicator(QWidget):
    """Animated status indicator"""
    _sync_started_at = time.monotonic()
    _active_widgets = weakref.WeakSet()
    _animation_timer = None

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._state = "idle"  # idle, running, error
        self_ref = weakref.ref(self)
        cls = type(self)
        self.destroyed.connect(lambda: (widget := self_ref()) is not None and cls._active_widgets.discard(widget))

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
            pass

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._state == "idle":
            pen = QPen(QColor("#6b707a"), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(2, 2, 12, 12)

        elif self._state == "running":
            pen = QPen(QColor(66, 211, 146), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            # drawArc: x, y, w, h, startAngle, spanAngle (in 1/16ths of a degree)
            angle = self._synced_angle(-320)
            p.drawArc(2, 2, 12, 12, int(angle * 16), 270 * 16)

        elif self._state in {"update", "scanning"}:
            pen = QPen(QColor(96, 165, 250), 2.5, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            angle = self._synced_angle(-320)
            p.drawArc(2, 2, 12, 12, int(angle * 16), 270 * 16)

        elif self._state == "error":
            scale = self._synced_angle(600) / 360.0
            size = 4 + 10 * scale # Scales between 4 and 14
            offset = (16 - size) / 2

            alpha = int(255 * scale)
            color = QColor(255, 193, 7, alpha)

            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawEllipse(QRectF(offset, offset, size, size))

        elif self._state == "disconnected":
            angle = self._synced_angle(160)
            scale = (math.sin(math.radians(angle)) + 1) / 2 # 0.0 ~ 1.0
            size = 8 + 4 * scale # Scales between 8 and 12
            offset = (16 - size) / 2

            p.setPen(Qt.NoPen)
            p.setBrush(QColor(245, 108, 108)) # Red
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

    # The original normal state PNGs have perfect alpha channels.
    # The _hover.png assets have defective black backgrounds. We use the normal PNG for hover as well.
    # Hover highlighting is fully handled by QSS/opacity to eliminate the black background issue.
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
        self.setFixedSize(36, 40)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setObjectName("lineIconBtn")
        self._hover = False

        icon_path = asset_path("bottom_icons", f"{kind}.png")
        if os.path.exists(icon_path):
            self.icon = QIcon(icon_path)
        else:
            self.icon = build_bottom_icon(kind, "#a6abb4")

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.update()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        theme = "dark"
        curr = self
        while curr:
            if hasattr(curr, "config"):
                theme = curr.config.get("theme", "dark")
                break
            curr = curr.parent()

        if self.underMouse() or self._hover:
            if self.isDown():
                bg_color = QColor("#343a46") if theme == "dark" else QColor("#b8c5d6")
            else:
                bg_color = QColor("#2a2e36") if theme == "dark" else QColor("#cbd5e1")
            painter.fillRect(self.rect(), bg_color)

        opacity = 1.0 if self._hover else 0.8
        painter.setOpacity(opacity)

        if self._hover:
            icon_w, icon_h = 23, 23
            y_offset = -1.0
        else:
            icon_w, icon_h = 22, 22
            y_offset = 0.0

        x = (self.width() - icon_w) / 2
        y = (self.height() - icon_h) / 2 + y_offset

        target_rect = QRectF(x, y, icon_w, icon_h).toRect()
        self.icon.paint(painter, target_rect, Qt.AlignCenter)
        painter.end()


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
