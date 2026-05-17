import os
import sys

def resource_path(relative_path):
    """获取程序运行时资源文件的绝对路径，兼容 PyInstaller 打包环境"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path)

def apply_theme(app, theme_name="dark"):
    """动态加载并为应用程序应用 QSS 样式表主题"""
    if theme_name == "light":
        style_path = resource_path(os.path.join("ui", "light.qss"))
    else:
        style_path = resource_path(os.path.join("ui", "style.qss"))
        
    if os.path.exists(style_path):
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            print(f"[主题加载] 已成功应用主题: {theme_name}")
        except Exception as e:
            print(f"[错误] 加载样式表 {style_path} 失败: {e}")
    else:
        print(f"[警告] 未找到主题样式表文件: {style_path}")
