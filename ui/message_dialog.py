from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .i18n import tr


class MessageIcon(QWidget):
    def __init__(self, kind="info", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(34, 34)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.kind == "warning":
            color = QColor("#f5c542")
            path = QPainterPath()
            path.moveTo(17, 4)
            path.lineTo(31, 29)
            path.lineTo(3, 29)
            path.closeSubpath()
            painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(QColor(245, 197, 66, 40))
            painter.drawPath(path)
            painter.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(17, 12, 17, 21)
            painter.drawPoint(17, 25)
        elif self.kind == "success":
            color = QColor("#42d392")
            painter.setPen(QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(QColor(66, 211, 146, 34))
            painter.drawEllipse(QRectF(4, 4, 26, 26))
            painter.drawLine(10, 17, 15, 22)
            painter.drawLine(15, 22, 25, 11)
        else:
            color = QColor("#8fb7ff")
            painter.setPen(QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.setBrush(QColor(143, 183, 255, 32))
            painter.drawEllipse(QRectF(4, 4, 26, 26))
            painter.drawLine(17, 15, 17, 24)
            painter.drawPoint(17, 10)

        painter.end()


class MessageCloseButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self._hover = True
        self.update()

    def leaveEvent(self, event):
        self._hover = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.window():
            self.window().reject()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._hover:
            painter.fillRect(self.rect(), QColor("#c42b1c"))
            color = QColor("#ffffff")
        else:
            color = QColor("#a6abb4")
        painter.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(10, 10, 20, 20)
        painter.drawLine(20, 10, 10, 20)
        painter.end()


class MessageDialog(QDialog):
    def __init__(
        self,
        parent,
        title,
        message,
        kind="info",
        primary_text=None,
        secondary_text=None,
        primary_role="primary",
    ):
        super().__init__(parent.window() if parent and parent.window() else parent)
        self._drag_pos = None
        self.setObjectName("messageDialog")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)

        self.card = QFrame(self)
        self.card.setObjectName("messageCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        root.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 95))
        self.card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("messageTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(44)
        self.topBg.mousePressEvent = self._mouse_press
        self.topBg.mouseMoveEvent = self._mouse_move
        self.topBg.mouseReleaseEvent = self._mouse_release

        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 6, 0)
        title_label = QLabel(title)
        title_label.setObjectName("messageTitle")
        top_layout.addWidget(title_label)
        top_layout.addStretch()
        top_layout.addWidget(MessageCloseButton(self.topBg))
        layout.addWidget(self.topBg)

        body = QWidget(self.card)
        body.setObjectName("messageBodyBg")
        body.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 18, 20, 18)
        body_layout.setSpacing(18)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        content_layout.addWidget(MessageIcon(kind))

        text_label = QLabel(message)
        text_label.setObjectName("messageText")
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_layout.addWidget(text_label, stretch=1)
        body_layout.addLayout(content_layout)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.addStretch()
        if secondary_text:
            secondary_btn = QPushButton(secondary_text)
            secondary_btn.setObjectName("messageSecondaryBtn")
            secondary_btn.setFixedSize(88, 32)
            secondary_btn.clicked.connect(self.reject)
            button_layout.addWidget(secondary_btn)

        primary_btn = QPushButton(primary_text or tr("ok"))
        primary_btn.setObjectName(
            "messageDangerBtn" if primary_role == "danger" else "messagePrimaryBtn"
        )
        primary_btn.setFixedSize(96, 32)
        primary_btn.clicked.connect(self.accept)
        primary_btn.setDefault(True)
        button_layout.addWidget(primary_btn)
        body_layout.addLayout(button_layout)

        layout.addWidget(body)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            center = parent.frameGeometry().center()
            self.move(center - self.rect().center())

    def _mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _mouse_move(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _mouse_release(self, event):
        self._drag_pos = None
        event.accept()


def show_message(parent, title, message, kind="info"):
    dialog = MessageDialog(parent, title, message, kind=kind)
    return dialog.exec()


def show_info(parent, title, message):
    return show_message(parent, title, message, kind="success")


def show_warning(parent, title, message):
    return show_message(parent, title, message, kind="warning")


def ask_confirm(parent, title, message, accept_text, cancel_text=None, danger=False):
    dialog = MessageDialog(
        parent,
        title,
        message,
        kind="warning",
        primary_text=accept_text,
        secondary_text=cancel_text or tr("cancel"),
        primary_role="danger" if danger else "primary",
    )
    return dialog.exec() == QDialog.Accepted
