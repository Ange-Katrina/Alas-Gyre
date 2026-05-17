import sys
import os
import requests
import subprocess
import threading
from packaging import version

# 请在此修改您的 GitHub 仓库名
GITHUB_REPO = "Ange-Katrina/Alas-Gyre"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

def get_current_exe_path():
    """获取当前可执行文件路径"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return None

def check_for_updates(current_version):
    """检查是否有新版本"""
    try:
        resp = requests.get(API_URL, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            latest_version = data.get("tag_name", "")
            if latest_version.startswith("v"):
                if version.parse(latest_version) > version.parse(current_version):
                    assets = data.get("assets", [])
                    download_url = None
                    for asset in assets:
                        if asset["name"].endswith(".exe"):
                            download_url = asset["browser_download_url"]
                            break
                    if download_url:
                        return {
                            "has_update": True, 
                            "version": latest_version, 
                            "url": download_url, 
                            "changelog": data.get("body", "")
                        }
        return {"has_update": False}
    except Exception as e:
        return {"has_update": False, "error": str(e)}

def do_update(download_url, progress_callback, finish_callback):
    """后台下载并执行自我替换"""
    try:
        exe_path = get_current_exe_path()
        if not exe_path:
            finish_callback(False, "仅支持在打包后的 exe 运行环境中自动更新。")
            return
            
        resp = requests.get(download_url, stream=True, timeout=8)
        resp.raise_for_status()
        
        total_length = resp.headers.get('content-length')
        downloaded = 0
        
        temp_file = exe_path + ".new"
        with open(temp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_length:
                        progress_callback(int(downloaded * 100 / int(total_length)))
                        
        old_file = exe_path + ".old"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except Exception:
                pass
                
        os.rename(exe_path, old_file)
        os.rename(temp_file, exe_path)
        
        finish_callback(True, "更新完成，即将重启应用...")
        
        import time
        time.sleep(1)
        subprocess.Popen([exe_path])
        sys.exit(0)
        
    except Exception as e:
        finish_callback(False, f"更新失败: {e}")

def cleanup_old_exe():
    """在程序启动时清理上次更新留下的 .old 文件"""
    exe_path = get_current_exe_path()
    if exe_path:
        old_file = exe_path + ".old"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except Exception:
                pass
