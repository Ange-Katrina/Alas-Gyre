import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from ui.main_window import AlasConsole
from ui.settings_window import SettingsWindow
from ui.i18n import set_language

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    with open("ui/style.qss", "r", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
        
    steps = []
    
    def run_next_step():
        if not steps:
            app.quit()
            return
        
        step_func = steps.pop(0)
        step_func()
        
    # Step 1: Capture Chinese Main
    def step_1():
        print("Capturing Chinese main window...")
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
    def step_2():
        print("Capturing Chinese settings window...")
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

    # Step 3: Capture English Main
    def step_3():
        print("Capturing English main window...")
        set_language("en")
        win = AlasConsole()
        win.show()
        
        def do_capture():
            win.grab().save("ui_preview_en.png")
            print("Captured ui_preview_en.png")
            win.close()
            QTimer.singleShot(100, run_next_step)
            
        QTimer.singleShot(500, do_capture)

    # Step 4: Capture English Settings
    def step_4():
        print("Capturing English settings window...")
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

    steps.extend([step_1, step_2, step_3, step_4])
    QTimer.singleShot(100, run_next_step)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
