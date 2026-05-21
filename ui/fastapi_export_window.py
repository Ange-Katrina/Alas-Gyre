import os
import json
import secrets

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QFileDialog, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)
from .main_window import WindowButton
from .i18n import tr

TOKEN_ASSIGNMENT = 'ALAS_GYRE_API_TOKEN = "__ALAS_GYRE_API_TOKEN__"'
FASTAPI_CUSTOM_DIR_KEY = "fastapi_custom_dir"


def save_config(config, config_path):
    if not config_path:
        return
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def ensure_api_token(config, config_path=""):
    token = str(config.get("api_token", "")).strip()
    if token:
        return token

    token = secrets.token_urlsafe(32)
    config["api_token"] = token
    save_config(config, config_path)
    return token


def render_fastapi_payload(source_path, config, config_path=""):
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"未找到源文件 {source_path}")

    token = ensure_api_token(config, config_path)
    with open(source_path, "r", encoding="utf-8") as f:
        source = f.read()
    if TOKEN_ASSIGNMENT not in source:
        raise RuntimeError("fastapi payload 缺少 Token 占位符")

    rendered = source.replace(
        TOKEN_ASSIGNMENT,
        f"ALAS_GYRE_API_TOKEN = {json.dumps(token)}",
        1,
    )
    return rendered


def write_fastapi_file(output_path, rendered):
    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(rendered)
    return output_path


def export_fastapi_file(source_path, output_path, config, config_path=""):
    rendered = render_fastapi_payload(source_path, config, config_path)
    return write_fastapi_file(output_path, rendered)


def custom_fastapi_output_path(custom_dir):
    custom_dir = str(custom_dir or "").strip().strip('"')
    if not custom_dir:
        return ""
    return os.path.join(os.path.abspath(os.path.expanduser(custom_dir)), "fastapi.py")


def selected_fastapi_output_path(root_output_path, custom_dir=""):
    return custom_fastapi_output_path(custom_dir) or os.path.abspath(root_output_path)


def export_fastapi_to_selected_path(source_path, root_output_path, config, config_path="", custom_dir=""):
    rendered = render_fastapi_payload(source_path, config, config_path)
    return write_fastapi_file(selected_fastapi_output_path(root_output_path, custom_dir), rendered)


class FastapiExportWindow(QDialog):
    def __init__(self, parent=None, source_path="", output_path="", config=None, config_path=""):
        super().__init__(parent)
        self.source_path = source_path
        self.output_path = output_path
        self.config = config if config is not None else {}
        self.config_path = config_path

        self.setObjectName("fastapiExportWindow")
        self.setFixedSize(520, 580)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 18)

        self.card = QFrame(self)
        self.card.setObjectName("fastapiCard")
        self.card.setAttribute(Qt.WA_StyledBackground, True)
        self.card.setFixedSize(484, 548)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("fastapiTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)

        title = QLabel(tr("export_title"))
        title.setObjectName("fastapiTitle")
        top_layout.addWidget(title)
        top_layout.addStretch()

        self.closeBtn = WindowButton("close", self.topBg)
        self.closeBtn.mousePressEvent = lambda event: self.reject() if event.button() == Qt.LeftButton else None
        top_layout.addWidget(self.closeBtn)
        card_layout.addWidget(self.topBg)

        self.bodyBg = QWidget(self.card)
        self.bodyBg.setObjectName("fastapiBodyBg")
        self.bodyBg.setAttribute(Qt.WA_StyledBackground, True)
        self.bodyBg.setFixedSize(484, 518)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(24, 16, 24, 18)
        body_layout.setSpacing(7)

        desc = QLabel(tr("export_desc"))
        desc.setObjectName("fastapiDesc")
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        path_title = QLabel(tr("output_file"))
        path_title.setObjectName("fastapiSectionTitle")
        body_layout.addWidget(path_title)

        self.pathBox = QWidget(self.bodyBg)
        self.pathBox.setObjectName("fastapiPathBox")
        self.pathBox.setAttribute(Qt.WA_StyledBackground, True)
        self.pathBox.setFixedHeight(108)
        path_layout = QVBoxLayout(self.pathBox)
        path_layout.setContentsMargins(12, 8, 12, 10)
        path_layout.setSpacing(7)

        custom_label = QLabel(tr("output_custom_dir"))
        custom_label.setObjectName("fastapiPathTitle")
        path_layout.addWidget(custom_label)

        hint_label = QLabel(tr("output_hint"))
        hint_label.setObjectName("fastapiPathHint")
        hint_label.setWordWrap(True)
        hint_label.setFixedHeight(28)
        path_layout.addWidget(hint_label)

        custom_layout = QHBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(8)
        self.customDirInput = QLineEdit("")
        self.customDirInput.setObjectName("fastapiPathInput")
        self.customDirInput.setFixedHeight(28)
        self.customDirInput.setPlaceholderText(tr("output_default_hint"))
        self.customDirInput.setToolTip(self.output_path)
        self.customDirInput.textChanged.connect(self.customDirInput.setToolTip)
        custom_layout.addWidget(self.customDirInput, stretch=1)

        self.browseBtn = QPushButton(tr("browse"))
        self.browseBtn.setObjectName("tokenBtn")
        self.browseBtn.setCursor(Qt.PointingHandCursor)
        self.browseBtn.setFocusPolicy(Qt.NoFocus)
        self.browseBtn.setFixedSize(76, 28)
        self.browseBtn.clicked.connect(self._choose_custom_dir)
        custom_layout.addWidget(self.browseBtn)
        path_layout.addLayout(custom_layout)
        body_layout.addWidget(self.pathBox)

        steps_title = QLabel(tr("install_steps"))
        steps_title.setObjectName("fastapiSectionTitle")
        body_layout.addWidget(steps_title)

        self.stepsBox = QWidget(self.bodyBg)
        self.stepsBox.setObjectName("fastapiStepsBox")
        self.stepsBox.setAttribute(Qt.WA_StyledBackground, True)
        self.stepsBox.setFixedHeight(154)
        steps_layout = QVBoxLayout(self.stepsBox)
        steps_layout.setContentsMargins(12, 9, 12, 9)
        steps_layout.setSpacing(6)
        steps_layout.addWidget(self._create_step("1", tr("step_1")))
        steps_layout.addWidget(self._create_step("2", tr("step_2")))
        steps_layout.addWidget(self._create_step("3", tr("step_3")))
        steps_layout.addWidget(self._create_step("4", tr("step_4")))
        body_layout.addWidget(self.stepsBox)

        warning = QLabel(tr("export_warning"))
        warning.setObjectName("fastapiWarning")
        warning.setWordWrap(True)
        warning.setFixedHeight(48)
        body_layout.addWidget(warning)

        body_layout.addSpacing(6)

        self.statusLabel = QLabel("")
        self.statusLabel.setObjectName("fastapiStatus")
        self.statusLabel.setWordWrap(True)
        self.statusLabel.setMinimumHeight(18)
        body_layout.addWidget(self.statusLabel)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch()

        self.exportBtn = QPushButton(tr("export_btn"))
        self.exportBtn.setObjectName("fastapiExportBtn")
        self.exportBtn.setCursor(Qt.PointingHandCursor)
        self.exportBtn.setFocusPolicy(Qt.NoFocus)
        self.exportBtn.setFixedSize(180, 32)
        self.exportBtn.clicked.connect(self._export_fastapi)
        btn_layout.addWidget(self.exportBtn)
        body_layout.addLayout(btn_layout)

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
        for widget in (self, self.card, self.bodyBg, self.pathBox, self.stepsBox):
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            widget.updateGeometry()
            widget.update()

    def _create_step(self, number, text):
        row = QWidget(self.bodyBg)
        row.setObjectName("fastapiStepRow")
        row.setMinimumHeight(23)
        row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        badge = QLabel(number)
        badge.setObjectName("fastapiStepBadge")
        badge.setFixedSize(20, 20)
        badge.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(badge, alignment=Qt.AlignTop)

        label = QLabel(text)
        label.setObjectName("fastapiStepText")
        label.setWordWrap(True)
        label.setMinimumHeight(23)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row_layout.addWidget(label, stretch=1)
        return row

    def _center_on_parent(self):
        if not self.parent():
            return
        parent_geom = self.parent().geometry()
        x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
        y = parent_geom.y() + (parent_geom.height() - self.height()) // 2
        self.move(x, y)

    def _set_status(self, text, state):
        self.statusLabel.setText(text)
        self.statusLabel.setProperty("state", state)
        self.statusLabel.style().unpolish(self.statusLabel)
        self.statusLabel.style().polish(self.statusLabel)

    def _ensure_token(self):
        return ensure_api_token(self.config, self.config_path)

    def _choose_custom_dir(self):
        start_dir = (
            self.customDirInput.text().strip()
            or str(self.config.get(FASTAPI_CUSTOM_DIR_KEY, "") or "").strip()
            or os.path.dirname(self.output_path)
        )
        selected_dir = QFileDialog.getExistingDirectory(self, tr("output_custom_dir"), start_dir)
        if selected_dir:
            self.customDirInput.setText(selected_dir)

    def _export_fastapi(self):
        if not os.path.exists(self.source_path):
            self._set_status(tr("export_fail", error=f"Source path not found: {self.source_path}"), "error")
            return

        try:
            custom_dir = self.customDirInput.text().strip()
            self.config[FASTAPI_CUSTOM_DIR_KEY] = custom_dir
            output_path = export_fastapi_to_selected_path(
                self.source_path,
                self.output_path,
                self.config,
                self.config_path,
                custom_dir,
            )
            save_config(self.config, self.config_path)
            self._set_status(tr("export_success", path=output_path), "success")
        except Exception as exc:
            self._set_status(tr("export_fail", error=str(exc)), "error")

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
