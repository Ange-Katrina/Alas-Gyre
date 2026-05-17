import os
import subprocess
import sys
from urllib.parse import quote

import requests
from packaging import version


GITHUB_REPO = "Ange-Katrina/Alas-Gyre"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASE_LATEST_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
CHECK_TIMEOUT = (4, 12)
REQUEST_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Alas-Gyre-Updater",
}


def get_current_exe_path():
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def normalize_version_tag(tag):
    tag = str(tag or "").strip()
    if not tag:
        return ""
    return tag if tag.lower().startswith("v") else f"v{tag}"


def parse_version_tag(tag):
    return version.parse(normalize_version_tag(tag).lstrip("v"))


def is_newer_version(latest_version, current_version):
    try:
        return parse_version_tag(latest_version) > parse_version_tag(current_version)
    except Exception:
        return False


def find_exe_asset(assets):
    for asset in assets or []:
        name = asset.get("name", "")
        if name.lower().endswith(".exe"):
            return asset.get("browser_download_url")
    return None


def update_result_from_release(data, current_version):
    latest_version = normalize_version_tag(data.get("tag_name", ""))
    if not latest_version:
        return {"has_update": False, "error": "empty latest version"}

    if not is_newer_version(latest_version, current_version):
        return {"has_update": False, "version": latest_version}

    download_url = find_exe_asset(data.get("assets", []))
    if not download_url:
        return {
            "has_update": False,
            "version": latest_version,
            "error": "missing exe asset",
        }

    return {
        "has_update": True,
        "version": latest_version,
        "url": download_url,
        "changelog": data.get("body", ""),
    }


def fetch_latest_release_by_api(current_version):
    resp = requests.get(API_URL, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
    resp.raise_for_status()
    return update_result_from_release(resp.json(), current_version)


def fetch_latest_tag_by_redirect():
    resp = requests.get(
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
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=CHECK_TIMEOUT)
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
            resp = requests.get(download_url, stream=True, timeout=3.5)
            resp.raise_for_status()
        except Exception as exc:
            if download_url.startswith("https://github.com/"):
                print(f"[update] GitHub download failed ({exc}); trying mirror.")
                try:
                    mirror_url = f"https://mirror.ghproxy.com/{download_url}"
                    resp = requests.get(mirror_url, stream=True, timeout=15)
                    resp.raise_for_status()
                except Exception as mirror_exc:
                    print(f"[update] primary mirror failed ({mirror_exc}); trying backup mirror.")
                    backup_mirror_url = f"https://ghproxy.net/{download_url}"
                    resp = requests.get(backup_mirror_url, stream=True, timeout=15)
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

        old_file = exe_path + ".old"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except Exception:
                pass

        os.rename(exe_path, old_file)
        os.rename(temp_file, exe_path)

        finish_callback(True, "Update complete. Restarting...")

        import time

        time.sleep(1)
        subprocess.Popen([exe_path])
        sys.exit(0)

    except Exception as exc:
        finish_callback(False, f"Update failed: {exc}")


def cleanup_old_exe():
    exe_path = get_current_exe_path()
    if exe_path:
        old_file = exe_path + ".old"
        if os.path.exists(old_file):
            try:
                os.remove(old_file)
            except Exception:
                pass
