"""Tiny HTTP updater for Alas-Gyre gyre_runtime.

This file intentionally uses Python standard library only. It runs outside the
ALAS WebUI process and updates only a small whitelist inside gyre_runtime.
"""

import argparse
import base64
import errno
import hashlib
import json
import os
import secrets
import shutil
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


TOKEN_HEADER = "X-Alas-Gyre-Token"
PROTOCOL = "alas-gyre-runtime-update"
RUNTIME_VERSION = "__RUNTIME_VERSION__"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 22268
MAX_FILE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 8 * 1024 * 1024
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 3
DEFAULT_LOG_CHECK_INTERVAL = 60
LOG_COPY_CHUNK_SIZE = 1024 * 1024
ROTATED_LOG_FILES = (".gyre_alas.log", ".gyre_updater.log")

ALLOWED_FILES = {
    "overlay/sitecustomize.py": {"restart_required": True, "executable": False},
    "overlay/gyre_overlay_runtime.py": {"restart_required": True, "executable": False},
    "gyre_runtime_updater.py": {"restart_required": False, "executable": False},
    "start_gyre_alas.sh": {"restart_required": False, "executable": True},
    "start_gyre_alas.bat": {"restart_required": False, "executable": False},
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 256), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_int(value, default, minimum=None, maximum=None):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def read_token():
    return os.environ.get("ALAS_GYRE_API_TOKEN", "").strip()


def normalize_rel_path(path):
    raw = str(path or "").replace("\\", "/").strip()
    if raw.startswith("/") or raw.startswith("../") or "/../" in raw or raw in {"", ".", ".."}:
        raise ValueError("invalid_path")
    if raw not in ALLOWED_FILES:
        raise ValueError("file_not_allowed")
    return raw


def safe_target(runtime_dir, rel_path):
    rel_path = normalize_rel_path(rel_path)
    runtime_real = os.path.realpath(os.path.abspath(runtime_dir))
    target = os.path.abspath(os.path.join(runtime_real, *rel_path.split("/")))
    parent = os.path.realpath(os.path.dirname(target))
    if os.path.commonpath([runtime_real, parent]) != runtime_real:
        raise ValueError("path_escape")
    if os.path.islink(target):
        raise ValueError("target_is_symlink")
    target_real = os.path.realpath(target) if os.path.exists(target) else target
    if os.path.commonpath([runtime_real, os.path.realpath(os.path.abspath(target_real))]) != runtime_real:
        raise ValueError("path_escape")
    return target


def json_response(handler, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def current_files(runtime_dir):
    files = {}
    for rel_path in ALLOWED_FILES:
        try:
            target = safe_target(runtime_dir, rel_path)
            files[rel_path] = sha256_file(target) if os.path.isfile(target) else ""
        except Exception:
            files[rel_path] = ""
    return files


def write_allowed_file(runtime_dir, rel_path, content):
    info = ALLOWED_FILES[rel_path]
    target = safe_target(runtime_dir, rel_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp_path = target + ".tmp"
    bak_path = target + ".bak"
    with open(tmp_path, "wb") as f:
        f.write(content)
    if sha256_file(tmp_path) != sha256_bytes(content):
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise ValueError("tmp_hash_mismatch")
    if os.path.exists(target):
        shutil.copy2(target, bak_path)
    os.replace(tmp_path, target)
    if info.get("executable"):
        mode = os.stat(target).st_mode
        os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_file_stream(src_path, dst_path):
    tmp_path = dst_path + ".tmp"
    try:
        with open(src_path, "rb") as src, open(tmp_path, "wb") as dst:
            shutil.copyfileobj(src, dst, length=LOG_COPY_CHUNK_SIZE)
        os.replace(tmp_path, dst_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass


def rotate_log_file(log_path, max_bytes, backup_count):
    if max_bytes <= 0:
        return
    if not os.path.isfile(log_path):
        return
    try:
        if os.path.getsize(log_path) < max_bytes:
            return
    except OSError:
        return

    if backup_count <= 0:
        try:
            with open(log_path, "wb"):
                pass
        except OSError as exc:
            print("[Alas-Gyre Updater] log_truncate_failed %s: %r" % (log_path, exc), flush=True)
        return

    for index in range(backup_count, 1, -1):
        src = "%s.%s" % (log_path, index - 1)
        dst = "%s.%s" % (log_path, index)
        if os.path.exists(src):
            try:
                os.replace(src, dst)
            except OSError:
                pass

    try:
        copy_file_stream(log_path, "%s.1" % log_path)
        with open(log_path, "wb"):
            pass
        print("[Alas-Gyre Updater] rotated log: %s" % log_path, flush=True)
    except OSError as exc:
        print("[Alas-Gyre Updater] log_rotate_failed %s: %r" % (log_path, exc), flush=True)


def rotate_runtime_logs(runtime_dir, max_bytes, backup_count):
    for file_name in ROTATED_LOG_FILES:
        rotate_log_file(os.path.join(runtime_dir, file_name), max_bytes, backup_count)


def start_log_maintenance(runtime_dir, max_bytes, backup_count, interval):
    stop_event = threading.Event()

    def loop():
        rotate_runtime_logs(runtime_dir, max_bytes, backup_count)
        while not stop_event.wait(interval):
            rotate_runtime_logs(runtime_dir, max_bytes, backup_count)

    thread = threading.Thread(target=loop, name="gyre-log-maintenance", daemon=True)
    thread.start()
    return stop_event


class RuntimeUpdaterHandler(BaseHTTPRequestHandler):
    server_version = "AlasGyreRuntimeUpdater/1.0"

    def log_message(self, fmt, *args):
        # Keep logs concise and compatible with BusyBox environments.
        print("[Alas-Gyre Updater] " + (fmt % args))

    def do_OPTIONS(self):
        json_response(self, {"ok": True})

    def do_GET(self):
        if self.path != "/runtime/info":
            json_response(self, {"error": "not_found"}, status=404)
            return
        if not self.authorized():
            json_response(self, {"error": "unauthorized"}, status=401)
            return
        payload = {
            "ok": True,
            "protocol": PROTOCOL,
            "runtime_version": RUNTIME_VERSION,
            "runtime_dir": self.server.runtime_dir,
            "update_host": self.server.update_host,
            "update_port": self.server.update_port,
            "files": current_files(self.server.runtime_dir),
        }
        json_response(self, payload)

    def do_POST(self):
        if self.path != "/runtime/update":
            json_response(self, {"error": "not_found"}, status=404)
            return
        if not self.authorized():
            json_response(self, {"error": "unauthorized"}, status=401)
            return
        try:
            data = self.read_json_body()
            result = apply_update(self.server.runtime_dir, data)
            result["ok"] = True
            result["runtime_version"] = RUNTIME_VERSION
            json_response(self, result)
        except ValueError as exc:
            json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            print("[Alas-Gyre Updater] update_failed: %r" % (exc,), flush=True)
            json_response(self, {"error": "update_failed"}, status=500)

    def authorized(self):
        expected = read_token()
        if not expected:
            return False
        provided = self.headers.get(TOKEN_HEADER, "")
        return secrets.compare_digest(provided, expected)

    def read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid_content_length")
        if length <= 0:
            raise ValueError("empty_body")
        if length > MAX_REQUEST_BYTES:
            raise ValueError("request_too_large")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise ValueError("invalid_json")


def apply_update(runtime_dir, data):
    if not isinstance(data, dict):
        raise ValueError("invalid_body")
    files = data.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("no_files")

    operations = []
    unchanged = []
    restart_required = False

    for rel_path, item in files.items():
        rel_path = normalize_rel_path(rel_path)
        if not isinstance(item, dict):
            raise ValueError("invalid_file_item")
        expected_hash = str(item.get("sha256", "")).lower().strip()
        content_b64 = item.get("content_b64", "")
        if len(expected_hash) != 64 or any(c not in "0123456789abcdef" for c in expected_hash):
            raise ValueError("invalid_sha256")
        if not isinstance(content_b64, str) or not content_b64:
            raise ValueError("missing_content")
        try:
            content = base64.b64decode(content_b64.encode("ascii"), validate=True)
        except Exception:
            raise ValueError("invalid_base64")
        if len(content) > MAX_FILE_BYTES:
            raise ValueError("file_too_large")
        actual_hash = sha256_bytes(content)
        if actual_hash != expected_hash:
            raise ValueError("sha256_mismatch")

        target = safe_target(runtime_dir, rel_path)
        current_hash = sha256_file(target) if os.path.isfile(target) else ""
        if current_hash == actual_hash:
            unchanged.append(rel_path)
            continue
        operations.append((rel_path, content))
        restart_required = restart_required or bool(ALLOWED_FILES[rel_path].get("restart_required"))

    updated = []
    for rel_path, content in operations:
        write_allowed_file(runtime_dir, rel_path, content)
        updated.append(rel_path)

    return {
        "updated": updated,
        "unchanged": unchanged,
        "restart_required": restart_required,
        "files": current_files(runtime_dir),
    }


class RuntimeUpdaterHTTPServer(HTTPServer):
    allow_reuse_address = True


def parse_args():
    parser = argparse.ArgumentParser(description="Alas-Gyre Runtime Updater")
    parser.add_argument("--runtime", default=os.path.dirname(os.path.abspath(__file__)))
    parser.add_argument("--host", default=os.environ.get("GYRE_UPDATE_HOST", DEFAULT_HOST))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GYRE_UPDATE_PORT", DEFAULT_PORT)))
    parser.add_argument(
        "--log-max-bytes",
        type=int,
        default=parse_int(os.environ.get("GYRE_LOG_MAX_BYTES"), DEFAULT_LOG_MAX_BYTES, minimum=0),
    )
    parser.add_argument(
        "--log-backup-count",
        type=int,
        default=parse_int(os.environ.get("GYRE_LOG_BACKUP_COUNT"), DEFAULT_LOG_BACKUP_COUNT, minimum=0, maximum=20),
    )
    parser.add_argument(
        "--log-check-interval",
        type=int,
        default=parse_int(os.environ.get("GYRE_LOG_CHECK_INTERVAL"), DEFAULT_LOG_CHECK_INTERVAL, minimum=10),
    )
    return parser.parse_args()


def main():
    args = parse_args()
    runtime_dir = os.path.realpath(os.path.abspath(args.runtime))
    try:
        httpd = RuntimeUpdaterHTTPServer((args.host, args.port), RuntimeUpdaterHandler)
    except OSError as exc:
        if getattr(exc, "errno", None) in (errno.EADDRINUSE, 98, 10048):
            print(
                "[Alas-Gyre Updater] %s:%s is already in use. "
                "If this is an existing gyre_runtime updater, it is safe to ignore."
                % (args.host, args.port),
                flush=True,
            )
            return 98
        raise
    httpd.runtime_dir = runtime_dir
    httpd.update_host = args.host
    httpd.update_port = args.port
    log_stop_event = start_log_maintenance(
        runtime_dir,
        args.log_max_bytes,
        args.log_backup_count,
        args.log_check_interval,
    )
    print("[Alas-Gyre Updater] listening on %s:%s runtime=%s" % (args.host, args.port, runtime_dir), flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        log_stop_event.set()
        httpd.server_close()


if __name__ == "__main__":
    main()
