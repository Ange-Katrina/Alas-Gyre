import os
import re
import shlex
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


def http_get(url, **kwargs):
    session = _requests().Session()
    session.trust_env = False
    try:
        resp = session.get(url, **kwargs)
        resp._alas_session = session
        return resp
    except Exception:
        session.close()
        raise


def close_response(resp):
    if resp is None:
        return
    try:
        resp.close()
    finally:
        session = getattr(resp, "_alas_session", None)
        if session is not None:
            session.close()


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
    normalized = normalize_version_tag(tag).lstrip("v")
    match = re.match(r"^(\d+(?:\.\d+)*)(?:[-_.]?([a-zA-Z]+)(\d*)?)?$", normalized)
    if not match:
        raise ValueError(f"invalid version tag: {tag}")

    release = [int(part) for part in match.group(1).split(".")]
    release = (release + [0, 0, 0, 0])[:4]

    label = (match.group(2) or "").lower()
    number = int(match.group(3) or 0)
    stage_order = {
        "dev": -1,
        "a": 0,
        "alpha": 0,
        "b": 1,
        "beta": 1,
        "rc": 2,
        "pre": 2,
        "preview": 2,
        "": 3,
    }
    return (*release, stage_order.get(label, 3), number)


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
    if data.get("draft"):
        return {"has_update": False, "error": "draft release"}

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
    resp = http_get(API_URL, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    try:
        resp.raise_for_status()
        releases = resp.json()
    finally:
        close_response(resp)
    if not releases or not isinstance(releases, list):
        raise ValueError("No releases found.")

    skipped_errors = []
    newest_seen = ""
    for release in releases:
        result = update_result_from_release(release, current_version)
        if result.get("version") and not newest_seen:
            newest_seen = result["version"]
        if result.get("has_update"):
            return result
        if result.get("error"):
            skipped_errors.append(
                f"{release.get('tag_name', 'unknown')}: {result.get('error')}"
            )

    fallback = {"has_update": False}
    if newest_seen:
        fallback["version"] = newest_seen
    if skipped_errors:
        fallback["error"] = "; ".join(skipped_errors)
    return fallback


def validate_downloaded_exe(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Downloaded file not found: {path}")
    if os.path.getsize(path) < 1024:
        raise RuntimeError("Downloaded file is too small.")
    if sys.platform == "win32" or path.lower().endswith(".exe"):
        with open(path, "rb") as f:
            if f.read(2) != b"MZ":
                raise RuntimeError("Downloaded file is not a valid Windows executable.")


def fetch_latest_tag_by_redirect():
    resp = http_get(
        RELEASE_LATEST_URL,
        headers=REQUEST_HEADERS,
        timeout=CHECK_TIMEOUT,
        allow_redirects=False,
    )
    try:
        if resp.status_code not in (301, 302, 303, 307, 308):
            resp.raise_for_status()
            return ""

        location = resp.headers.get("Location", "")
    finally:
        close_response(resp)
    marker = "/releases/tag/"
    if marker not in location:
        return ""
    return normalize_version_tag(location.rsplit(marker, 1)[-1].strip("/"))


def fetch_release_by_tag(tag, current_version):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{quote(tag, safe='')}"
    resp = http_get(url, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    try:
        resp.raise_for_status()
        data = resp.json()
    finally:
        close_response(resp)
    return update_result_from_release(data, current_version)


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
            resp = http_get(
                download_url,
                headers=REQUEST_HEADERS,
                stream=True,
                timeout=(4, 30),
            )
            resp.raise_for_status()

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
        finally:
            close_response(resp)

        validate_downloaded_exe(temp_file)
        if progress_callback:
            progress_callback(100)

        dir_name = os.path.dirname(exe_path)

        if sys.platform == "win32":
            bat_path = os.path.join(dir_name, "update.bat")
            bat_content = f"""@echo off
set "PID={os.getpid()}"
set "TEMP_FILE={temp_file}"
set "EXE_PATH={exe_path}"

:wait_loop
tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL
if %ERRORLEVEL%==0 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)

:replace
move /Y "%TEMP_FILE%" "%EXE_PATH%" >nul
if not %ERRORLEVEL%==0 (
    timeout /t 1 /nobreak >nul
    goto replace
)

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
TEMP_FILE={shlex.quote(temp_file)}
EXE_PATH={shlex.quote(exe_path)}

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
