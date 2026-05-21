import json
import os
import re
import subprocess
import sys
import time

from .fastapi_export_window import render_fastapi_payload, write_fastapi_file


ALAS_PATH_MARKERS = (
    os.path.join("module", "webui", "fastapi.py"),
    os.path.join("module", "webui"),
    "AzurLaneAutoScript",
)
PROCESS_QUERY = r"""
$items = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match 'AzurLaneAutoScript|module\\webui|alas|Alas|pywebio'
    } |
    Select-Object ProcessId, Name, ExecutablePath, CommandLine
$items | ConvertTo-Json -Compress
"""
QUOTED_PATH_RE = re.compile(r'"([A-Za-z]:\\[^"]+)"')
UNQUOTED_PATH_RE = re.compile(r"([A-Za-z]:\\[^\s\"']+)")


def _run_powershell_json(script, timeout=8):
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "").strip())
    output = completed.stdout.strip()
    if not output:
        return []
    data = json.loads(output)
    return data if isinstance(data, list) else [data]


def list_candidate_processes():
    processes = []
    for item in _run_powershell_json(PROCESS_QUERY):
        command_line = str(item.get("CommandLine") or "")
        name = str(item.get("Name") or "")
        if not command_line:
            continue
        lower = command_line.lower()
        if "alas-gyre" in lower:
            continue
        processes.append(
            {
                "pid": int(item.get("ProcessId") or 0),
                "name": name,
                "executable": str(item.get("ExecutablePath") or ""),
                "command_line": command_line,
            }
        )
    return processes


def extract_paths(command_line):
    paths = []
    for match in QUOTED_PATH_RE.finditer(command_line or ""):
        paths.append(match.group(1))
    for match in UNQUOTED_PATH_RE.finditer(command_line or ""):
        paths.append(match.group(1).rstrip(",;"))
    return paths


def find_alas_root_from_path(path):
    path = os.path.abspath(path.strip().strip('"'))
    if os.path.isfile(path):
        current = os.path.dirname(path)
    else:
        current = path

    while True:
        fastapi_path = os.path.join(current, "module", "webui", "fastapi.py")
        module_dir = os.path.join(current, "module")
        config_dir = os.path.join(current, "config")
        if os.path.isfile(fastapi_path) and os.path.isdir(module_dir):
            return current
        if os.path.isdir(module_dir) and os.path.isdir(config_dir):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return ""
        current = parent


def find_running_alas():
    matches = []
    seen_roots = set()
    for process in list_candidate_processes():
        candidate_paths = extract_paths(process.get("command_line", ""))
        if process.get("executable"):
            candidate_paths.append(process["executable"])
        for path in candidate_paths:
            root = find_alas_root_from_path(path)
            if not root:
                continue
            key = os.path.normcase(os.path.normpath(root))
            if key in seen_roots:
                continue
            seen_roots.add(key)
            fastapi_path = os.path.join(root, "module", "webui", "fastapi.py")
            matches.append(
                {
                    "pid": process["pid"],
                    "name": process["name"],
                    "command_line": process["command_line"],
                    "root": root,
                    "fastapi_path": fastapi_path,
                }
            )
            break
    return matches


def install_fastapi_to_alas(alas_root, source_path, config, config_path=""):
    fastapi_path = os.path.join(alas_root, "module", "webui", "fastapi.py")
    if not os.path.isfile(fastapi_path):
        raise FileNotFoundError(f"未找到 ALAS fastapi.py: {fastapi_path}")
    rendered = render_fastapi_payload(source_path, config, config_path)
    backup_path = fastapi_path + ".bak"
    if os.path.exists(fastapi_path):
        with open(fastapi_path, "rb") as src, open(backup_path, "wb") as dst:
            dst.write(src.read())
    return write_fastapi_file(fastapi_path, rendered)


def restart_alas_process(match):
    pid = int(match.get("pid") or 0)
    command_line = str(match.get("command_line") or "").strip()
    root = str(match.get("root") or "").strip()
    if not pid or not command_line:
        raise RuntimeError("无法获取 ALAS 进程启动命令")

    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        capture_output=True,
        text=True,
        timeout=8,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    time.sleep(0.8)

    kwargs = {"cwd": root or None, "shell": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command_line, **kwargs)


def install_to_first_running_alas(source_path, config, config_path=""):
    matches = find_running_alas()
    if not matches:
        raise RuntimeError("未发现正在运行的本地 ALAS")
    match = matches[0]
    target_path = install_fastapi_to_alas(match["root"], source_path, config, config_path)
    restart_alas_process(match)
    return {
        "root": match["root"],
        "path": target_path,
        "pid": match["pid"],
        "count": len(matches),
    }
