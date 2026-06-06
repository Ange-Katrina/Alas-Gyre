"""Shared behavior for frameless Qt windows.

Stable-first dialogs deliberately avoid ``WA_TranslucentBackground`` and heavy
shadow effects.  The repaint helpers remain centralized here so all frameless
windows get consistent layout activation without full-window mouse handlers
stealing clicks from form controls.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QRegion

try:
    from shiboken6 import isValid
except Exception:  # pragma: no cover - compatibility fallback
    def isValid(widget):
        return widget is not None


def install_title_bar_drag(window, title_bar):
    """Make only the provided title bar drag the frameless window."""
    if title_bar is None:
        return
    title_bar.setCursor(Qt.SizeAllCursor)
    title_bar.mousePressEvent = lambda event: _drag_mouse_press(window, event)
    title_bar.mouseMoveEvent = lambda event: _drag_mouse_move(window, event)
    title_bar.mouseReleaseEvent = lambda event: _drag_mouse_release(window, event)


def schedule_frameless_stabilize(window, *widgets, stable_input_region=True):
    """Schedule a short layout/repaint sequence after a frameless window is shown."""
    QTimer.singleShot(
        0,
        lambda: stabilize_frameless_window(
            window,
            *widgets,
            stable_input_region=stable_input_region,
        ),
    )
    QTimer.singleShot(
        80,
        lambda: stabilize_frameless_window(
            window,
            *widgets,
            stable_input_region=stable_input_region,
        ),
    )
    QTimer.singleShot(
        180,
        lambda: repaint_frameless_window(window, *widgets),
    )


def clamp_window_to_available_screen(window, reference_widget=None, margin=8):
    """Keep a dialog fully reachable inside the current screen work area."""
    if not _is_live_widget(window):
        return

    screen = None
    ref = reference_widget if _is_live_widget(reference_widget) else window
    try:
        point = ref.frameGeometry().center()
        screen = QGuiApplication.screenAt(point)
    except Exception:
        screen = None
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    frame = window.frameGeometry()
    width = max(frame.width(), window.width(), 1)
    height = max(frame.height(), window.height(), 1)

    min_x = available.x() + margin
    min_y = available.y() + margin
    max_x = available.x() + available.width() - width - margin
    max_y = available.y() + available.height() - height - margin
    if max_x < min_x:
        max_x = min_x
    if max_y < min_y:
        max_y = min_y

    x = min(max(frame.x(), min_x), max_x)
    y = min(max(frame.y(), min_y), max_y)
    if x != frame.x() or y != frame.y():
        window.move(QPoint(x, y))


def stabilize_frameless_window(window, *widgets, stable_input_region=True):
    if not _is_live_widget(window) or not window.isVisible():
        return

    window.setAttribute(Qt.WA_TransparentForMouseEvents, False)
    if stable_input_region:
        apply_stable_input_region(window)
    repaint_frameless_window(window, *widgets)


def repaint_frameless_window(window, *widgets):
    if not _is_live_widget(window):
        return

    for widget in _iter_live_widgets(window, widgets):
        layout = widget.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        widget.updateGeometry()
        widget.update()
        widget.repaint()

    try:
        handle = window.windowHandle()
        if handle is not None:
            handle.requestUpdate()
    except RuntimeError:
        pass


def apply_stable_input_region(window):
    """Keep frameless dialogs fully clickable on Windows."""
    if sys.platform != "win32" or not _is_live_widget(window):
        return
    try:
        window.setMask(QRegion(window.rect()))
    except Exception:
        pass


def _drag_mouse_press(window, event):
    if event.button() != Qt.LeftButton:
        return
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.ReleaseCapture()
            ctypes.windll.user32.SendMessageW(int(window.winId()), 0x0112, 0xF012, 0)
        except Exception:
            setattr(
                window,
                "_gyre_drag_offset",
                event.globalPosition().toPoint() - window.frameGeometry().topLeft(),
            )
    else:
        setattr(
            window,
            "_gyre_drag_offset",
            event.globalPosition().toPoint() - window.frameGeometry().topLeft(),
        )
    event.accept()


def _drag_mouse_move(window, event):
    if (
        sys.platform != "win32"
        and hasattr(window, "_gyre_drag_offset")
        and event.buttons() & Qt.LeftButton
    ):
        window.move(event.globalPosition().toPoint() - window._gyre_drag_offset)
        event.accept()


def _drag_mouse_release(window, event):
    if hasattr(window, "_gyre_drag_offset"):
        delattr(window, "_gyre_drag_offset")
    event.accept()


def _iter_live_widgets(window, widgets):
    seen = set()
    for widget in (window, *widgets):
        if not _is_live_widget(widget):
            continue
        key = id(widget)
        if key in seen:
            continue
        seen.add(key)
        yield widget


def _is_live_widget(widget):
    try:
        return widget is not None and isValid(widget)
    except RuntimeError:
        return False
