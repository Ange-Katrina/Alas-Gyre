import os
import subprocess
import sys
from urllib.parse import quote

try:
    from build_info import BUILD_FLAVOR
except Exception:
    BUILD_FLAVOR = "pyinstaller"


GITHUB_REPO = "Ange-Katrina/Alas-Gyre"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases"
RELEASE_LATEST_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
CHECK_TIMEOUT = (4, 12)
REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Alas-Gyre-Updater",
}
VALID_BUILD_FLAVORS = {"pyinstaller", "nuitka"}
PYINSTALLER_ASSET_NAMES = ("alas-gyre-pyinstaller.exe", "alas-gyre.exe")
NUITKA_ASSET_NAMES = ("alas-gyre-nuitka.exe",)


def _requests():
    import requests
    return requests


def get_current_exe_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def normalize_build_flavor(flavor):
    flavor = str(flavor or "").strip().lower()
    return flavor if flavor in VALID_BUILD_FLAVORS else "pyinstaller"


def get_build_flavor():
    configured_flavor = normalize_build_flavor(BUILD_FLAVOR)
    exe_path = get_current_exe_path()
    if exe_path:
        exe_name = os.path.basename(exe_path).lower()
        if "nuitka" in exe_name:
            return "nuitka"
        if "pyinstaller" in exe_name:
            return "pyinstaller"
    return configured_flavor


def normalize_version_tag(tag):
    tag = str(tag or "").strip()
    if not tag:
        return ""
    return tag if tag.lower().startswith("v") else f"v{tag}"


def parse_version_tag(tag):
    from packaging import version

    return version.parse(normalize_version_tag(tag).lstrip("v"))


def is_newer_version(latest_version, current_version):
    try:
        return parse_version_tag(latest_version) > parse_version_tag(current_version)
    except Exception:
        return False


def find_exe_asset(assets, build_flavor=None):
    build_flavor = normalize_build_flavor(build_flavor or get_build_flavor())
    exe_assets = []
    for asset in assets or []:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            exe_assets.append(asset)

    if not exe_assets:
        return None

    preferred_names = (
        NUITKA_ASSET_NAMES if build_flavor == "nuitka" else PYINSTALLER_ASSET_NAMES
    )
    for preferred_name in preferred_names:
        for asset in exe_assets:
            if asset.get("name", "").lower() == preferred_name:
                return asset.get("browser_download_url")

    for asset in exe_assets:
        name = asset.get("name", "").lower()
        if build_flavor == "nuitka" and "nuitka" in name:
            return asset.get("browser_download_url")
        if (
            build_flavor == "pyinstaller"
            and "nuitka" not in name
            and "pyinstaller" not in name
        ):
            return asset.get("browser_download_url")

    return None


def update_result_from_release(data, current_version):
    latest_version = normalize_version_tag(data.get("tag_name", ""))
    if not latest_version:
        return {"has_update": False, "error": "empty latest version"}

    if not is_newer_version(latest_version, current_version):
        return {"has_update": False, "version": latest_version}

    build_flavor = get_build_flavor()
    download_url = find_exe_asset(data.get("assets", []), build_flavor)
    if not download_url:
        return {
            "has_update": False,
            "version": latest_version,
            "error": f"missing {build_flavor} exe asset",
        }

    return {
        "has_update": True,
        "version": latest_version,
        "url": download_url,
        "changelog": data.get("body", ""),
        "build_flavor": build_flavor,
    }


def fetch_latest_release_by_api(current_version):
    resp = _requests().get(API_URL, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    resp.raise_for_status()
    releases = resp.json()
    if not releases or not isinstance(releases, list):
        raise ValueError("No releases found.")
    # The first item is the latest release (including pre-releases)
    return update_result_from_release(releases[0], current_version)


def fetch_latest_tag_by_redirect():
    resp = _requests().get(
        RELEASE_LATEST_URL,
        headers=REQUEST_HEADERS,
        timeout=CHECK_TIMEOUT,
        allow_redirects=False,
    )
    if resp.status_code not in (301, 302, 303, 307, 308):
        resp.raise_for_status()
        return ""

    location = resp.headers.get("Location", "")
    marker = "/releases/tag/"
    if marker not in location:
        return ""
    return normalize_version_tag(location.rsplit(marker, 1)[-1].strip("/"))


def fetch_release_by_tag(tag, current_version):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{quote(tag, safe='')}"
    resp = _requests().get(url, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    resp.raise_for_status()
    return update_result_from_release(resp.json(), current_version)


def check_for_updates(current_version):
    errors = []

    try:
        return fetch_latest_release_by_api(current_version)
    except Exception as exc:
        errors.append(f"api: {exc}")

    try:
        latest_version = fetch_latest_tag_by_redirect()
        if latest_version:
            if not is_newer_version(latest_version, current_version):
                return {"has_update": False, "version": latest_version}
            try:
                return fetch_release_by_tag(latest_version, current_version)
            except Exception as exc:
                errors.append(f"release tag: {exc}")
    except Exception as exc:
        errors.append(f"redirect: {exc}")

    return {"has_update": False, "error": "; ".join(errors) or "unknown error"}


def do_update(download_url, progress_callback, finish_callback):
    try:
        exe_path = get_current_exe_path()
        if not exe_path:
            finish_callback(False, "Auto update is only available in packaged exe builds.")
            return

        resp = None
        try:
            print(f"[update] downloading from GitHub: {download_url}")
            resp = _requests().get(download_url, stream=True, timeout=3.5)
            resp.raise_for_status()
        except Exception as exc:
            if download_url.startswith("https://github.com/"):
                print(f"[update] GitHub download failed ({exc}); trying mirror.")
                try:
                    mirror_url = f"https://mirror.ghproxy.com/{download_url}"
                    resp = _requests().get(mirror_url, stream=True, timeout=15)
                    resp.raise_for_status()
                except Exception as mirror_exc:
                    print(f"[update] primary mirror failed ({mirror_exc}); trying backup mirror.")
                    backup_mirror_url = f"https://ghproxy.net/{download_url}"
                    resp = _requests().get(backup_mirror_url, stream=True, timeout=15)
                    resp.raise_for_status()
            else:
                raise exc

        total_length = resp.headers.get("content-length")
        downloaded = 0

        temp_file = exe_path + ".new"
        with open(temp_file, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_length:
                        progress_callback(int(downloaded * 100 / int(total_length)))

        dir_name = os.path.dirname(exe_path)

        if sys.platform == "win32":
            bat_path = os.path.join(dir_name, "update.bat")
            bat_content = f"""@echo off
set PID={os.getpid()}
set TEMP_FILE={temp_file}
set EXE_PATH={exe_path}

:wait_loop
tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL
if %ERRORLEVEL%==0 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

:replace
copy /Y "%TEMP_FILE%" "%EXE_PATH%" >nul
if not %ERRORLEVEL%==0 (
    timeout /t 1 /nobreak >nul
    goto replace
)

del /Q "%TEMP_FILE%" >nul

start "" "%EXE_PATH%"
del /Q "%~f0" >nul
"""
            with open(bat_path, "w", encoding="ansi") as f:
                f.write(bat_content)

            finish_callback(True, "Update downloaded. Restarting via update helper...")
            import time
            time.sleep(0.5)

            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
            )
        else:
            sh_path = os.path.join(dir_name, "update.sh")
            sh_content = f"""#!/bin/sh
PID={os.getpid()}
TEMP_FILE="{temp_file}"
EXE_PATH="{exe_path}"

while kill -0 $PID 2>/dev/null; do
    sleep 1
done

cp -f "$TEMP_FILE" "$EXE_PATH"
rm -f "$TEMP_FILE"
chmod +x "$EXE_PATH"
"$EXE_PATH" &
rm -f "$0"
"""
            with open(sh_path, "w", encoding="utf-8") as f:
                f.write(sh_content)
            os.chmod(sh_path, 0o755)

            finish_callback(True, "Update downloaded. Restarting via update helper...")
            import time
            time.sleep(0.5)

            subprocess.Popen([sh_path], start_new_session=True)

        os._exit(0)

    except Exception as exc:
        finish_callback(False, f"Update failed: {exc}")


def cleanup_old_exe():
    exe_path = get_current_exe_path()
    if exe_path:
        for ext in (".old", ".new", ".bat", ".sh"):
            file_path = exe_path + ext
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
            flat_path = os.path.join(os.path.dirname(exe_path), "update" + ext)
            if os.path.exists(flat_path):
                try:
                    os.remove(flat_path)
                except Exception:
                    pass
