from PySide6.QtWidgets import QApplication


def snap_to_available_screen(widget, margins=(0, 0, 0, 0), distance=18):
    """Snap a frameless window to the nearest screen work-area edge."""
    if widget is None:
        return

    screen = QApplication.screenAt(widget.frameGeometry().center())
    if screen is None:
        screen = widget.screen() or QApplication.primaryScreen()
    if screen is None:
        return

    left_margin, top_margin, right_margin, bottom_margin = margins
    window_rect = widget.geometry()
    available = screen.availableGeometry()

    visible_left = window_rect.left() + left_margin
    visible_top = window_rect.top() + top_margin
    visible_right = window_rect.right() - right_margin
    visible_bottom = window_rect.bottom() - bottom_margin

    dx = 0
    dy = 0

    if (
        abs(visible_left - available.left()) <= distance
        or abs(window_rect.left() - available.left()) <= distance
    ):
        dx = available.left() - visible_left
    elif (
        abs(visible_right - available.right()) <= distance
        or abs(window_rect.right() - available.right()) <= distance
    ):
        dx = available.right() - visible_right

    if (
        abs(visible_top - available.top()) <= distance
        or abs(window_rect.top() - available.top()) <= distance
    ):
        dy = available.top() - visible_top
    elif (
        abs(visible_bottom - available.bottom()) <= distance
        or abs(window_rect.bottom() - available.bottom()) <= distance
    ):
        dy = available.bottom() - visible_bottom

    if dx or dy:
        widget.move(window_rect.x() + dx, window_rect.y() + dy)
