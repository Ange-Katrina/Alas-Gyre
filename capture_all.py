import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.main_window import AlasConsole
from ui.settings_window import SettingsWindow
from ui.log_window import LogWindow
from ui.mini_window import MiniWindow
from ui.i18n import set_language

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    with open("ui/style.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
        
    steps = []
    
    def run_next_step():
        if not steps:
            print("All captures completed successfully!")
            app.quit()
            return
        
        step_func = steps.pop(0)
        step_func()

    # ==================== CHINESE CAPTURES ====================

    # Step 1: Capture Chinese Single Main
    def step_zh_single():
        print("Capturing Chinese single config main...")
        set_language("zh")
        win = AlasConsole()
        win.show()
        
        def do_capture():
            win.grab().save("ui_preview.png")
            print("Captured ui_preview.png")
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 2: Capture Chinese Settings
    def step_zh_settings():
        print("Capturing Chinese settings...")
        set_language("zh")
        win = AlasConsole()
        win.show()
        dialog = SettingsWindow(win)
        dialog.show()
        dialog._on_test_result(False, "连接失败：端口冲突")
        
        def do_capture():
            dialog.grab().save("settings_preview.png")
            print("Captured settings_preview.png")
            dialog.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 3: Capture Chinese Multi Main
    def step_zh_multi():
        print("Capturing Chinese multi config main...")
        set_language("zh")
        win = AlasConsole()
        win.card._configs = ["alas", "alas2"]
        win.card._statuses = {"alas": "running", "alas2": "idle"}
        win.card._rebuild_rows()
        win.show()
        
        def do_capture():
            win.grab().save("multi_preview.png")
            print("Captured multi_preview.png")
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 4: Capture Chinese Logs
    def step_zh_logs():
        print("Capturing Chinese logs...")
        set_language("zh")
        win = AlasConsole()
        win.show()
        dialog = LogWindow(parent=win, config=win.card.config, current_config="alas", configs=["alas", "alas2"])
        dialog.show()
        dialog._on_log_updated(
            "2026-05-17 20:58:30.123 | INFO | ALAS 初始化成功。\n"
            "2026-05-17 20:58:31.456 | SUCCESS | 登录验证成功。 (当前等级 125, 第一舰队)\n"
            "2026-05-17 20:58:32.789 | WARNING | 任务队列为空，开始执行日常任务...\n"
            "2026-05-17 20:58:33.012 | INFO | 正在运行任务: 委托任务 (进行中)"
        )
        
        def do_capture():
            dialog.grab().save("log_preview.png")
            print("Captured log_preview.png")
            dialog.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 5: Capture Chinese Floating Widget
    def step_zh_float():
        print("Capturing Chinese floating widget...")
        set_language("zh")
        win = AlasConsole()
        win.card._configs = ["alas", "alas2"]
        win.card._statuses = {"alas": "running", "alas2": "idle"}
        mini = MiniWindow(win.card)
        for name, row in mini.rows.items():
            if name in win.card._statuses:
                row.update_status(win.card._statuses[name])
        mini.show()
        
        def do_capture():
            mini.grab().save("float_preview.png")
            print("Captured float_preview.png")
            mini.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # ==================== ENGLISH CAPTURES ====================

    # Step 6: Capture English Single Main
    def step_en_single():
        print("Capturing English single config main...")
        set_language("en")
        win = AlasConsole()
        win.show()
        
        def do_capture():
            win.grab().save("ui_preview_en.png")
            print("Captured ui_preview_en.png")
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 7: Capture English Settings
    def step_en_settings():
        print("Capturing English settings...")
        set_language("en")
        win = AlasConsole()
        win.show()
        dialog = SettingsWindow(win)
        dialog.show()
        dialog._on_test_result(False, "Connection failed: Port conflict")
        
        def do_capture():
            dialog.grab().save("settings_preview_en.png")
            print("Captured settings_preview_en.png")
            dialog.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 8: Capture English Multi Main
    def step_en_multi():
        print("Capturing English multi config main...")
        set_language("en")
        win = AlasConsole()
        win.card._configs = ["alas", "alas2"]
        win.card._statuses = {"alas": "running", "alas2": "idle"}
        win.card._rebuild_rows()
        win.show()
        
        def do_capture():
            win.grab().save("multi_preview_en.png")
            print("Captured multi_preview_en.png")
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 9: Capture English Logs
    def step_en_logs():
        print("Capturing English logs...")
        set_language("en")
        win = AlasConsole()
        win.show()
        dialog = LogWindow(parent=win, config=win.card.config, current_config="alas", configs=["alas", "alas2"])
        dialog.show()
        dialog._on_log_updated(
            "2026-05-17 20:58:30.123 | INFO | ALAS initialized successfully.\n"
            "2026-05-17 20:58:31.456 | SUCCESS | Login verification successful. (Level 125, Fleet 1)\n"
            "2026-05-17 20:58:32.789 | WARNING | Task queue is empty. Searching for daily tasks...\n"
            "2026-05-17 20:58:33.012 | INFO | Running commission task in progress..."
        )
        
        def do_capture():
            dialog.grab().save("log_preview_en.png")
            print("Captured log_preview_en.png")
            dialog.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 10: Capture English Floating Widget
    def step_en_float():
        print("Capturing English floating widget...")
        set_language("en")
        win = AlasConsole()
        win.card._configs = ["alas", "alas2"]
        win.card._statuses = {"alas": "running", "alas2": "idle"}
        mini = MiniWindow(win.card)
        for name, row in mini.rows.items():
            if name in win.card._statuses:
                row.update_status(win.card._statuses[name])
        mini.show()
        
        def do_capture():
            mini.grab().save("float_preview_en.png")
            print("Captured float_preview_en.png")
            mini.close()
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    steps.extend([
        step_zh_single, step_zh_settings, step_zh_multi, step_zh_logs, step_zh_float,
        step_en_single, step_en_settings, step_en_multi, step_en_logs, step_en_float
    ])
    QTimer.singleShot(100, run_next_step)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
