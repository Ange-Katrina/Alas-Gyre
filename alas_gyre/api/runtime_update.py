import base64
import hashlib
import os
import shutil
import tempfile

from alas_gyre.api.client import TOKEN_HEADER, api_request
from alas_gyre.api.overlay_launcher import RUNTIME_UPDATE_FILES, generate_portable_overlay_launchers


DEFAULT_RUNTIME_UPDATE_PORT = "22268"
RUNTIME_INFO_PATH = "/runtime/info"
RUNTIME_UPDATE_PATH = "/runtime/update"


def runtime_update_port(config):
    port = str(config.get("runtime_update_port", DEFAULT_RUNTIME_UPDATE_PORT)).strip()
    return port if port.isdigit() else DEFAULT_RUNTIME_UPDATE_PORT


def runtime_update_base_url(config):
    ip = str(config.get("ip", "127.0.0.1")).strip() or "127.0.0.1"
    return f"http://{ip}:{runtime_update_port(config)}"


def runtime_update_headers(config):
    token = str(config.get("api_token", "")).strip()
    if not token:
        return {}
    return {TOKEN_HEADER: token}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def build_local_runtime_files(api_token):
    temp_dir = tempfile.mkdtemp(prefix="alas_gyre_runtime_")
    try:
        result = generate_portable_overlay_launchers(temp_dir, api_token=api_token)
        runtime_dir = result["output_dir"]
        files = {}
        for rel_path in RUNTIME_UPDATE_FILES:
            path = os.path.join(runtime_dir, *rel_path.split("/"))
            if not os.path.isfile(path):
                continue
            with open(path, "rb") as f:
                content = f.read()
            files[rel_path] = {
                "sha256": sha256_bytes(content),
                "content": content,
            }
        return files
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def check_remote_runtime(config, timeout=4.0):
    resp = api_request(
        "GET",
        runtime_update_base_url(config) + RUNTIME_INFO_PATH,
        headers=runtime_update_headers(config),
        timeout=timeout,
    )
    return resp


def update_remote_runtime(config, current_version, timeout=10.0):
    token = str(config.get("api_token", "")).strip()
    if not token:
        return {"success": False, "message": "missing_token"}

    try:
        info_resp = check_remote_runtime(config, timeout=4.0)
    except Exception as exc:
        return {"success": False, "message": "connect_failed", "detail": str(exc)}

    if info_resp.status_code == 401:
        return {"success": False, "message": "unauthorized"}
    if info_resp.status_code != 200:
        return {"success": False, "message": "info_failed", "detail": f"HTTP {info_resp.status_code}"}

    try:
        info = info_resp.json()
    except Exception as exc:
        return {"success": False, "message": "invalid_info", "detail": str(exc)}

    remote_files = info.get("files") if isinstance(info, dict) else None
    if not isinstance(remote_files, dict):
        return {"success": False, "message": "unsupported"}

    local_files = build_local_runtime_files(token)
    upload_files = {}
    for rel_path, item in local_files.items():
        remote_hash = str(remote_files.get(rel_path, "") or "").lower()
        if remote_hash == item["sha256"]:
            continue
        upload_files[rel_path] = {
            "sha256": item["sha256"],
            "content_b64": base64.b64encode(item["content"]).decode("ascii"),
        }

    if not upload_files:
        return {
            "success": True,
            "message": "latest",
            "updated": [],
            "unchanged": sorted(local_files),
            "restart_required": False,
        }

    try:
        update_resp = api_request(
            "POST",
            runtime_update_base_url(config) + RUNTIME_UPDATE_PATH,
            headers=runtime_update_headers(config),
            json={"runtime_version": current_version, "files": upload_files},
            timeout=timeout,
        )
    except Exception as exc:
        return {"success": False, "message": "connect_failed", "detail": str(exc)}

    if update_resp.status_code == 401:
        return {"success": False, "message": "unauthorized"}
    try:
        data = update_resp.json()
    except Exception:
        data = {}
    if update_resp.status_code != 200 or not data.get("ok"):
        return {
            "success": False,
            "message": "update_failed",
            "detail": data.get("message") or data.get("error") or f"HTTP {update_resp.status_code}",
        }

    return {
        "success": True,
        "message": "updated",
        "updated": data.get("updated", []),
        "unchanged": data.get("unchanged", []),
        "restart_required": bool(data.get("restart_required")),
    }
