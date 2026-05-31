from PySide6.QtCore import QTimer
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import QLabel, QSizePolicy


class MarqueeLabel(QLabel):
    """Single-line label that scrolls only when text exceeds available width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_text = ""
        self._offset = 0
        self._gap = 32
        self._hold_frames = 24
        self._hold = self._hold_frames
        self._timer = QTimer(self)
        self._timer.setInterval(35)
        self._timer.timeout.connect(self._tick)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def set_marquee_text(self, text):
        text = str(text or "")
        if text != self._full_text:
            self._full_text = text
            self._offset = 0
            self._hold = self._hold_frames
        self._update_scroll_state()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scroll_state()

    def _text_width(self):
        return QFontMetrics(self.font()).horizontalAdvance(self._full_text)

    def _needs_scroll(self):
        return self._text_width() > max(0, self.width())

    def _update_scroll_state(self):
        if self._needs_scroll():
            if not self._timer.isActive():
                self._timer.start()
        else:
            self._timer.stop()
            self._offset = 0

    def _tick(self):
        if not self._needs_scroll():
            self._update_scroll_state()
            self.update()
            return
        if self._hold > 0:
            self._hold -= 1
            return

        self._offset += 1
        cycle_width = self._text_width() + self._gap
        if self._offset > cycle_width:
            self._offset = 0
            self._hold = self._hold_frames
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.setFont(self.font())
        painter.setClipRect(self.rect())
        painter.setPen(self.palette().color(self.foregroundRole()))

        metrics = QFontMetrics(self.font())
        baseline = (self.height() + metrics.ascent() - metrics.descent()) // 2

        if not self._needs_scroll():
            painter.drawText(0, baseline, self._full_text)
            painter.end()
            return

        text_width = self._text_width()
        x = -self._offset
        painter.drawText(x, baseline, self._full_text)
        painter.drawText(x + text_width + self._gap, baseline, self._full_text)
        painter.end()
