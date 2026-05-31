import os
import shutil
import stat

from alas_gyre.core.paths import app_base_dir, config_path, overlay_bundled_path, overlay_runtime_path, resource_path
from alas_gyre.core.version import get_current_version


BAT_NAME = "start_gyre_alas.bat"
SH_NAME = "start_gyre_alas.sh"
RUNTIME_DIR_NAME = "gyre_runtime"
RUNTIME_UPDATER_NAME = "gyre_runtime_updater.py"
OVERLAY_REQUIRED_FILES = ("sitecustomize.py", "gyre_overlay_runtime.py")
RUNTIME_UPDATE_FILES = (
    os.path.join("overlay", "sitecustomize.py").replace("\\", "/"),
    os.path.join("overlay", "gyre_overlay_runtime.py").replace("\\", "/"),
    RUNTIME_UPDATER_NAME,
    SH_NAME,
    BAT_NAME,
)


def validate_alas_root(alas_root):
    root = os.path.abspath(os.path.expanduser(str(alas_root or "").strip()))
    if not root:
        raise ValueError("ALAS root is empty")
    gui_path = os.path.join(root, "gui.py")
    app_path = os.path.join(root, "module", "webui", "app.py")
    if not os.path.isfile(gui_path) or not os.path.isfile(app_path):
        raise FileNotFoundError(f"Invalid ALAS root: {root}")
    return root


def _copy_file_if_needed(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        try:
            if os.path.getsize(src) == os.path.getsize(dst):
                with open(src, "rb") as src_f, open(dst, "rb") as dst_f:
                    if src_f.read() == dst_f.read():
                        return False
        except OSError:
            pass
    shutil.copy2(src, dst)
    return True


def ensure_overlay_runtime(target_dir=None):
    """Ensure the persistent overlay directory exists and is up to date."""
    source_dir = overlay_bundled_path()
    target_dir = os.path.abspath(target_dir or overlay_runtime_path())
    if not os.path.isdir(source_dir):
        source_dir = target_dir
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Overlay runtime source not found: {source_dir}")

    changed = False
    for file_name in OVERLAY_REQUIRED_FILES:
        src = os.path.join(source_dir, file_name)
        if not os.path.isfile(src):
            raise FileNotFoundError(f"Overlay runtime file missing: {src}")
        dst = os.path.join(target_dir, file_name)
        if os.path.abspath(src) == os.path.abspath(dst):
            continue
        changed = _copy_file_if_needed(src, dst) or changed
    return target_dir, changed


def _windows_path(path):
    return os.path.abspath(path).replace("/", "\\")


def _sh_quote(path):
    return "'" + str(path).replace("'", "'\"'\"'") + "'"


def _bat_value(value):
    return str(value or "").replace("%", "%%").replace('"', "")


def render_windows_launcher(alas_root, overlay_dir, gyre_config_path):
    overlay_dir = _windows_path(overlay_dir)
    gyre_config_path = _windows_path(gyre_config_path)
    return f"""@echo off
setlocal
set "ALAS_ROOT=%~dp0"
if "%ALAS_ROOT:~-1%"=="\\" set "ALAS_ROOT=%ALAS_ROOT:~0,-1%"
set "ALAS_GYRE_OVERLAY={overlay_dir}"
set "ALAS_GYRE_CONFIG={gyre_config_path}"
set "PYTHONPATH=%ALAS_GYRE_OVERLAY%;%PYTHONPATH%"
cd /d "%ALAS_ROOT%"
if exist "%ALAS_ROOT%\\run_alas.bat" (
    call "%ALAS_ROOT%\\run_alas.bat" %*
) else if exist "%ALAS_ROOT%\\toolkit\\python.exe" (
    "%ALAS_ROOT%\\toolkit\\python.exe" gui.py %*
) else (
    python gui.py %*
)
endlocal
"""


def render_posix_launcher(alas_root, overlay_dir, gyre_config_path):
    overlay_dir_q = _sh_quote(os.path.abspath(overlay_dir))
    gyre_config_path_q = _sh_quote(os.path.abspath(gyre_config_path))
    return f"""#!/bin/sh
set -eu
ALAS_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
ALAS_GYRE_OVERLAY={overlay_dir_q}
ALAS_GYRE_CONFIG={gyre_config_path_q}
export ALAS_ROOT ALAS_GYRE_OVERLAY ALAS_GYRE_CONFIG
if [ "${{PYTHONPATH:-}}" ]; then
    export PYTHONPATH="$ALAS_GYRE_OVERLAY:$PYTHONPATH"
else
    export PYTHONPATH="$ALAS_GYRE_OVERLAY"
fi
cd "$ALAS_ROOT"
if [ -f "./run_alas.sh" ]; then
    if [ -x "./run_alas.sh" ]; then
        exec ./run_alas.sh "$@"
    else
        exec sh ./run_alas.sh "$@"
    fi
elif command -v pixi >/dev/null 2>&1 && [ -f "./pixi.toml" ]; then
    exec pixi run python gui.py "$@"
elif [ -x "./.pixi/envs/default/bin/python" ]; then
    exec ./.pixi/envs/default/bin/python gui.py "$@"
elif [ -x "./.venv/bin/python" ]; then
    exec ./.venv/bin/python gui.py "$@"
elif [ -x "./venv/bin/python" ]; then
    exec ./venv/bin/python gui.py "$@"
elif [ -x "./toolkit/python" ]; then
    exec ./toolkit/python gui.py "$@"
elif [ -x "./toolkit/python.exe" ]; then
    exec ./toolkit/python.exe gui.py "$@"
else
    echo "ALAS Python environment not found; falling back to python3." >&2
    exec python3 gui.py "$@"
fi
"""


def render_portable_windows_launcher(api_token):
    api_token = _bat_value(api_token)
    template_path = resource_path(os.path.join("resources", "start_gyre_alas.bat.template"))
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("__API_TOKEN__", api_token)


def render_portable_posix_launcher(api_token):
    api_token_q = _sh_quote(api_token)
    template_path = resource_path(os.path.join("resources", "start_gyre_alas.sh.template"))
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("__API_TOKEN__", api_token_q)


def render_runtime_updater():
    updater_path = resource_path(os.path.join("resources", RUNTIME_UPDATER_NAME))
    with open(updater_path, "r", encoding="utf-8") as f:
        template = f.read()
    return template.replace("__RUNTIME_VERSION__", get_current_version())


def write_text(path, content, executable=False):
    newline = "\r\n" if str(path).lower().endswith(".bat") else "\n"
    with open(path, "w", encoding="utf-8", newline=newline) as f:
        f.write(content)
    if executable:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def generate_overlay_launchers(alas_root, gyre_config_path=None):
    alas_root = validate_alas_root(alas_root)
    overlay_dir, overlay_changed = ensure_overlay_runtime()
    gyre_config_path = os.path.abspath(gyre_config_path or config_path())

    bat_path = os.path.join(alas_root, BAT_NAME)
    sh_path = os.path.join(alas_root, SH_NAME)
    write_text(bat_path, render_windows_launcher(alas_root, overlay_dir, gyre_config_path))
    write_text(sh_path, render_posix_launcher(alas_root, overlay_dir, gyre_config_path), executable=True)
    return {
        "alas_root": alas_root,
        "overlay_dir": overlay_dir,
        "overlay_changed": overlay_changed,
        "bat_path": bat_path,
        "sh_path": sh_path,
    }


def generate_portable_overlay_launchers(output_dir=None, api_token=""):
    """Generate movable runtime files outside the ALAS root.

    The generated gyre_runtime directory is intended to live outside the ALAS
    root. Edit ALAS_ROOT in the launcher after upload; ALAS updates can then
    replace/clean the official directory without deleting the overlay runtime.
    """
    base_output_dir = os.path.abspath(output_dir or app_base_dir())
    runtime_dir = os.path.join(base_output_dir, RUNTIME_DIR_NAME)
    overlay_dir = os.path.join(runtime_dir, "overlay")
    overlay_dir, overlay_changed = ensure_overlay_runtime(overlay_dir)

    bat_path = os.path.join(runtime_dir, BAT_NAME)
    sh_path = os.path.join(runtime_dir, SH_NAME)
    updater_path = os.path.join(runtime_dir, RUNTIME_UPDATER_NAME)
    write_text(bat_path, render_portable_windows_launcher(api_token))
    write_text(sh_path, render_portable_posix_launcher(api_token), executable=True)
    write_text(updater_path, render_runtime_updater())
    return {
        "output_dir": runtime_dir,
        "overlay_dir": overlay_dir,
        "overlay_changed": overlay_changed,
        "bat_path": bat_path,
        "sh_path": sh_path,
        "updater_path": updater_path,
    }
