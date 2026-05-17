import os
import json
import secrets

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget
)
from .main_window import WindowButton

TOKEN_ASSIGNMENT = 'ALAS_GYRE_API_TOKEN = "__ALAS_GYRE_API_TOKEN__"'


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


def export_fastapi_file(source_path, output_path, config, config_path=""):
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
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(rendered)
    return output_path


class FastapiExportWindow(QDialog):
    def __init__(self, parent=None, source_path="", output_path="", config=None, config_path=""):
        super().__init__(parent)
        self.source_path = source_path
        self.output_path = output_path
        self.config = config if config is not None else {}
        self.config_path = config_path

        self.setObjectName("fastapiExportWindow")
        self.setFixedSize(520, 520)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 14, 18, 18)

        self.card = QFrame(self)
        self.card.setObjectName("fastapiCard")
        self.card.setFixedSize(484, 488)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.topBg = QWidget(self.card)
        self.topBg.setObjectName("fastapiTopBg")
        self.topBg.setAttribute(Qt.WA_StyledBackground, True)
        self.topBg.setFixedHeight(30)
        top_layout = QHBoxLayout(self.topBg)
        top_layout.setContentsMargins(20, 0, 8, 0)

        title = QLabel("FastAPI 文件导出")
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
        self.bodyBg.setFixedSize(484, 458)
        body_layout = QVBoxLayout(self.bodyBg)
        body_layout.setContentsMargins(24, 16, 24, 18)
        body_layout.setSpacing(7)

        desc = QLabel(
            "生成适配 AzurLaneAutoScript WebUI 的 fastapi.py。"
            "覆盖后，本工具可远程读取配置、同步状态、启停任务和查看实时日志。"
        )
        desc.setObjectName("fastapiDesc")
        desc.setWordWrap(True)
        body_layout.addWidget(desc)

        path_title = QLabel("输出文件")
        path_title.setObjectName("fastapiSectionTitle")
        body_layout.addWidget(path_title)

        self.pathBox = QWidget(self.bodyBg)
        self.pathBox.setObjectName("fastapiPathBox")
        self.pathBox.setAttribute(Qt.WA_StyledBackground, True)
        self.pathBox.setFixedHeight(70)
        path_layout = QVBoxLayout(self.pathBox)
        path_layout.setContentsMargins(12, 8, 12, 10)
        path_layout.setSpacing(7)

        file_label = QLabel("fastapi.py")
        file_label.setObjectName("fastapiPathTitle")
        path_layout.addWidget(file_label)

        self.outputPathInput = QLineEdit(self.output_path)
        self.outputPathInput.setObjectName("fastapiPathInput")
        self.outputPathInput.setReadOnly(True)
        self.outputPathInput.setFocusPolicy(Qt.ClickFocus)
        self.outputPathInput.setCursorPosition(0)
        self.outputPathInput.setFixedHeight(28)
        self.outputPathInput.setToolTip(self.output_path)
        path_layout.addWidget(self.outputPathInput)
        body_layout.addWidget(self.pathBox)

        steps_title = QLabel("安装步骤")
        steps_title.setObjectName("fastapiSectionTitle")
        body_layout.addWidget(steps_title)

        self.stepsBox = QWidget(self.bodyBg)
        self.stepsBox.setObjectName("fastapiStepsBox")
        self.stepsBox.setAttribute(Qt.WA_StyledBackground, True)
        self.stepsBox.setFixedHeight(124)
        steps_layout = QVBoxLayout(self.stepsBox)
        steps_layout.setContentsMargins(12, 9, 12, 9)
        steps_layout.setSpacing(6)
        steps_layout.addWidget(self._create_step("1", "点击“导出 fastapi.py”生成文件。"))
        steps_layout.addWidget(self._create_step("2", "上传并覆盖 AzurLaneAutoScript 的 module/webui/fastapi.py。"))
        steps_layout.addWidget(self._create_step("3", "重启 AzurLaneAutoScript 或 WebUI 服务，让新接口生效。"))
        steps_layout.addWidget(self._create_step("4", "回到设置页点击“测试连接”，确认 Token 和接口可用。"))
        body_layout.addWidget(self.stepsBox)

        warning = QLabel("安全提示：导出的 fastapi.py 内含 Token，请勿公开上传 config.json 或 output/fastapi.py。")
        warning.setObjectName("fastapiWarning")
        warning.setWordWrap(True)
        warning.setFixedHeight(44)
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

        self.exportBtn = QPushButton("导出 fastapi.py")
        self.exportBtn.setObjectName("fastapiExportBtn")
        self.exportBtn.setCursor(Qt.PointingHandCursor)
        self.exportBtn.setFocusPolicy(Qt.NoFocus)
        self.exportBtn.setFixedSize(128, 32)
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
        for widget in (self, self.card, self.bodyBg, self.stepsBox):
            layout = widget.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            widget.updateGeometry()
            widget.update()

    def _create_step(self, number, text):
        row = QWidget(self.bodyBg)
        row.setObjectName("fastapiStepRow")
        row.setFixedHeight(23)
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
        label.setWordWrap(False)
        label.setFixedHeight(23)
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

    def _export_fastapi(self):
        if not os.path.exists(self.source_path):
            self._set_status(f"导出失败：未找到源文件 {self.source_path}", "error")
            return

        try:
            export_fastapi_file(
                self.source_path,
                self.output_path,
                self.config,
                self.config_path,
            )
            self._set_status(f"已导出：{self.output_path}", "success")
        except Exception as exc:
            self._set_status(f"导出失败：{exc}", "error")

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
