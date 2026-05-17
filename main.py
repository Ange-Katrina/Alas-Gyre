import sys
import os
import json
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QFont, QIcon

from ui import AlasConsole
from ui.init_window import InitSetupWindow
from ui.main_window import config_path, fastapi_output_path, fastapi_source_path
from updater import cleanup_old_exe
from ui.i18n import set_language, tr

VERSION = "v1.0.7"
APP_USER_MODEL_ID = "AngeKatrina.AlasGyre"

def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def configure_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception as exc:
        print(f"[警告] 设置 Windows AppUserModelID 失败: {exc}")

def main():
    cleanup_old_exe()
    
    # 提前载入配置中的语言设置
    lang = "zh"
    try:
        cfg_p = config_path()
        if os.path.exists(cfg_p):
            with open(cfg_p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                lang = cfg.get("lang", "zh")
    except Exception as e:
        print(f"[警告] 提前读取语言失败: {e}")
    set_language(lang)

    configure_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("Alas-Gyre")
    app.setApplicationDisplayName("Alas-Gyre")
    app.setOrganizationName("Ange-Katrina")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei", 9))

    icon_path = resource_path(os.path.join("ui", "assets", "alas.ico"))
    app_icon = QIcon(icon_path)
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    window = AlasConsole()
    from ui.theme import apply_theme
    apply_theme(app, window.card.config.get("theme", "dark"))

    if not app_icon.isNull():
        window.setWindowIcon(app_icon)

    tray = create_tray(app, app_icon, window)
    if tray is not None:
        tray.show()

    if not window.card.config.get("setup_completed", False):
        setup_dialog = InitSetupWindow(
            None,
            window.card.config,
            window.card.config_path,
            fastapi_source_path(),
            fastapi_output_path(),
        )
        if not app_icon.isNull():
            setup_dialog.setWindowIcon(app_icon)
        setup_dialog.exec()

    window.show()
    QTimer.singleShot(1500, lambda: window.start_auto_update_check(VERSION))

    sys.exit(app.exec())


def create_tray(app, app_icon, window):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip("Alas-Gyre")
    menu = QMenu()

    show_action = QAction(tr("show_main"), menu)
    show_action.triggered.connect(window.card.restore_main_window)
    menu.addAction(show_action)

    mini_action = QAction(tr("show_float"), menu)
    mini_action.triggered.connect(window.card.show_mini_window)
    menu.addAction(mini_action)

    home_action = QAction(tr("open_webui"), menu)
    home_action.triggered.connect(lambda: window.card._on_icon_click("主页", window.card.homeIcon))
    menu.addAction(home_action)

    menu.addSeparator()

    setup_action = QAction(tr("wizard"), menu)
    setup_action.triggered.connect(lambda: open_init_setup(window, app_icon))
    menu.addAction(setup_action)

    export_action = QAction(tr("export_btn_tip"), menu)
    export_action.triggered.connect(lambda: window.card._on_icon_click("导出", window.card.exportIcon))
    menu.addAction(export_action)

    menu.addSeparator()

    quit_action = QAction(tr("quit"), menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.card.restore_main_window()
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick
        else None
    )
    app._alas_tray = tray
    return tray


def open_init_setup(window, app_icon):
    window.card.restore_main_window()
    dialog = InitSetupWindow(
        window,
        window.card.config,
        window.card.config_path,
        fastapi_source_path(),
        fastapi_output_path(),
    )
    if not app_icon.isNull():
        dialog.setWindowIcon(app_icon)
    if dialog.exec():
        window.card._save_config()

if __name__ == "__main__":
    main()
