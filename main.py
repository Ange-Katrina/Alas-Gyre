import sys
import os
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
from PySide6.QtGui import QAction, QFont, QIcon

from ui import AlasConsole
from ui.init_window import InitSetupWindow
from ui.main_window import config_path, fastapi_output_path, fastapi_source_path
from updater import cleanup_old_exe

VERSION = "v1.0.0"

def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)

def main():
    cleanup_old_exe()
    
    app = QApplication(sys.argv)
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
            window,
            window.card.config,
            window.card.config_path,
            fastapi_source_path(),
            fastapi_output_path(),
        )
        if not app_icon.isNull():
            setup_dialog.setWindowIcon(app_icon)
        setup_dialog.exec()

    window.show()

    sys.exit(app.exec())


def create_tray(app, app_icon, window):
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None

    tray = QSystemTrayIcon(app_icon, app)
    tray.setToolTip("Alas-Gyre")
    menu = QMenu()

    show_action = QAction("显示主界面", menu)
    show_action.triggered.connect(window.card.restore_main_window)
    menu.addAction(show_action)

    mini_action = QAction("显示悬浮窗", menu)
    mini_action.triggered.connect(window.card.show_mini_window)
    menu.addAction(mini_action)

    home_action = QAction("打开 Alas 主页", menu)
    home_action.triggered.connect(lambda: window.card._on_icon_click("主页", window.card.homeIcon))
    menu.addAction(home_action)

    menu.addSeparator()

    setup_action = QAction("初始化向导", menu)
    setup_action.triggered.connect(lambda: open_init_setup(window, app_icon))
    menu.addAction(setup_action)

    export_action = QAction("导出 fastapi.py", menu)
    export_action.triggered.connect(lambda: window.card._on_icon_click("导出", window.card.exportIcon))
    menu.addAction(export_action)

    menu.addSeparator()

    quit_action = QAction("退出", menu)
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
