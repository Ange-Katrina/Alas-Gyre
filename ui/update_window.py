import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QVBoxLayout, QWidget
)

from updater import do_update

from .i18n import tr
from .main_window import WindowButton

try:
    from shiboken6 import isValid
except Exception:
    def isValid(widget):
        return widget is not None


CHANGELOG_PHRASE_MAP = {
    "feat: improve update flow and config display": "功能：改进更新流程和配置显示",
    "fix: improve startup taskbar integration": "修复：改进启动任务栏集成",
    "fix: allow floating widget buttons during click-through": "修复：允许悬浮窗穿透时按钮仍可点击",
}

CHANGELOG_PREFIX_MAP = {
    "feat": "功能",
    "fix": "修复",
    "docs": "文档",
    "style": "样式",
    "refactor": "重构",
    "perf": "性能",
    "test": "测试",
    "build": "构建",
    "ci": "持续集成",
    "chore": "维护",
    "revert": "回滚",
}


def format_changelog_for_display(text):
    lines = []
    translated_hashes = set()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue

        if line.startswith("## What's Changed"):
            lines.append("## What's Changed / 发生了哪些变化？")
            continue
        if line.startswith("**Full Changelog**"):
            lines.append(line.replace("**Full Changelog**", "**Full Changelog / 完整更新记录**", 1))
            continue

        commit_hash, message = split_commit_line(line)
        if commit_hash and commit_hash in translated_hashes:
            continue

        lines.append(line)
        chinese = translate_changelog_line(line)
        if chinese:
            lines.append(chinese)
            translated_hashes.add(commit_hash)
    return "\n".join(lines).strip()


def translate_changelog_line(line):
    commit_hash, message = split_commit_line(line)
    if not commit_hash or not message or contains_cjk(message):
        return ""

    mapped = CHANGELOG_PHRASE_MAP.get(message)
    if mapped:
        return f"{commit_hash} {mapped}"

    message_lower = message.lower()
    for prefix, translated_prefix in CHANGELOG_PREFIX_MAP.items():
        marker = f"{prefix}:"
        if message_lower.startswith(marker):
            return f"{commit_hash} {translated_prefix}：{message[len(marker):].strip()}"
    return ""


def split_commit_line(line):
    normalized = line.lstrip("-* ").strip()
    parts = normalized.split(" ", 1)
    if len(parts) != 2 or not is_short_hash(parts[0]):
        return "", ""
    return parts[0], parts[1]


def contains_cjk(text):
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def is_short_hash(value):
    return 6 <= len(value) <= 12 and all(char in "0123456789abcdefABCDEF" for char in value)


class UpdatePromptWindow(QDialog):
    progress_signal = Signal(int)
    finish_signal = Signal(bool, str)

    def __init__(self, parent=None, update_info=None):
        super().__init__(parent)
        self.update_info = update_info or {}
        self.download_url = self.update_info.get("url", "")

        self.setObjectName("updateWindow")
        self.setFixedSize(520, 440)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 18)

        self.card = QFrame(self)
        self.card.setObjectName("updateCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("updateTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)

        title = QLabel(tr("update_available_title"))
        title.setObjectName("updateTitle")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.closeBtn = WindowButton("close", self.topBg)
        self.closeBtn.mousePressEvent = lambda event: self.reject() if event.button() == Qt.LeftButton else None
        top_layout.addWidget(self.closeBtn)
        card_layout.addWidget(self.topBg)

        self.bodyBg = QWidget(self.card)
        self.bodyBg.setObjectName("updateBodyBg")
        self.bodyBg.setAttribute(Qt.WA_StyledBackground, True)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(24, 18, 24, 18)
        body_layout.setSpacing(10)

        latest_version = self.update_info.get("version", "")
        desc = QLabel(tr("update_available_desc", version=latest_version))
        desc.setObjectName("updateDesc")
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        changelog_title = QLabel(tr("update_changelog"))
        changelog_title.setObjectName("updateSectionTitle")
        body_layout.addWidget(changelog_title)

        self.changelogText = QTextEdit(self.bodyBg)
        self.changelogText.setObjectName("updateChangelog")
        self.changelogText.setReadOnly(True)
        changelog = format_changelog_for_display(self.update_info.get("changelog"))
        self.changelogText.setPlainText(changelog or tr("update_no_changelog"))
        body_layout.addWidget(self.changelogText, stretch=1)

        self.statusLabel = QLabel("")
        self.statusLabel.setObjectName("updateStatus")
        self.statusLabel.setMinimumHeight(18)
        body_layout.addWidget(self.statusLabel)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.laterBtn = QPushButton(tr("update_later"))
        self.laterBtn.setObjectName("updateLaterBtn")
        self.laterBtn.setCursor(Qt.PointingHandCursor)
        self.laterBtn.setFocusPolicy(Qt.NoFocus)
        self.laterBtn.setFixedSize(88, 32)
        self.laterBtn.clicked.connect(self.reject)
        btn_layout.addWidget(self.laterBtn)

        self.downloadBtn = QPushButton(tr("download_update"))
        self.downloadBtn.setObjectName("updatePrimaryBtn")
        self.downloadBtn.setCursor(Qt.PointingHandCursor)
        self.downloadBtn.setFocusPolicy(Qt.NoFocus)
        self.downloadBtn.setFixedSize(116, 32)
        self.downloadBtn.clicked.connect(self._start_download)
        btn_layout.addWidget(self.downloadBtn)

        body_layout.addLayout(btn_layout)
        card_layout.addWidget(self.bodyBg)
        main_layout.addWidget(self.card)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.card.setGraphicsEffect(shadow)

        self.progress_signal.connect(self._on_progress)
        self.finish_signal.connect(self._on_finish)
        self._center_on_parent()

    def _center_on_parent(self):
        if not self.parent():
            return
        parent_geom = self.parent().geometry()
        x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
        self.move(x, y)

    def _start_download(self):
        if not self.download_url:
            self._set_status(tr("update_download_missing"), "error")
            return

        self.downloadBtn.setEnabled(False)
        self.laterBtn.setEnabled(False)
        self.downloadBtn.setText("0%")
        self._set_status(tr("downloading"), "info")
        threading.Thread(
            target=do_update,
            args=(self.download_url, self._emit_progress, self._emit_finish),
            daemon=True,
        ).start()

    def _emit_progress(self, percentage):
        try:
            if isValid(self):
                self.progress_signal.emit(percentage)
        except RuntimeError:
            pass

    def _emit_finish(self, success, message):
        try:
            if isValid(self):
                self.finish_signal.emit(success, message)
        except RuntimeError:
            pass

    def _on_progress(self, percentage):
        if not isValid(self):
            return
        self.downloadBtn.setText(f"{percentage}%")

    def _on_finish(self, success, message):
        if not isValid(self):
            return
        self._set_status(message or "", "success" if success else "error")
        self.downloadBtn.setText(tr("restart") if success else tr("download_update"))
        if not success:
            self.downloadBtn.setEnabled(True)
            self.laterBtn.setEnabled(True)

    def _set_status(self, text, state):
        if not isValid(self):
            return
        self.statusLabel.setText(text)
        self.statusLabel.setProperty("state", state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

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
        if sys.platform != "win32":
            if hasattr(self, "_drag_offset") and event.buttons() & Qt.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()
