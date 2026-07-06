"""Pure ASGI API layer for Alas-Gyre Overlay Runtime V1."""

from collections import deque
from datetime import datetime
import gc
import json
import mimetypes
import os
import threading
import time
from urllib.parse import parse_qs
import secrets

try:
    from rich.console import Console
except Exception:  # pragma: no cover - optional host dependency
    Console = None


API_PREFIX = "/api/gyre"
TOKEN_HEADER = "X-Alas-Gyre-Token"
DEFAULT_CONFIG = "alas"
CONFIG_DIR = "config"
LOG_DIR = "log"
ERROR_LOG_DIR = "error"
LOG_TAIL_CHUNK_SIZE = 64 * 1024
FILE_RESPONSE_CHUNK_SIZE = 64 * 1024
DEFAULT_LOG_LINES = 200
MAX_LOG_LINES = 2000
MAX_LIVE_RENDERABLES = MAX_LOG_LINES * 2
DEFAULT_ERROR_SCREENSHOT_LIMIT = 20
MAX_ERROR_SCREENSHOT_LIMIT = 100
OVERLAY_VERSION = 1
DEFAULT_MEMORY_WATCHDOG_INTERVAL = 60
DEFAULT_MEMORY_LOW_MB = 256
DEFAULT_MEMORY_LOW_PERCENT = 5.0

STATE_MAP = {
    1: "running",
    2: "idle",
    3: "error",
    4: "update",
}
VALID_STATUSES = {"idle", "running", "error", "update", "disconnected"}
INVALID_CONFIG_NAME_CHARS = set('/\\:*?"<>|')
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

_RICH_CONSOLE = None
_TOKEN_CACHE = {
    "path": "",
    "mtime_ns": None,
    "size": None,
    "value": "",
}
_I18N_CACHE = {}
_MEMORY_WATCHDOG_STARTED = False
_MEMORY_WATCHDOG_LOCK = threading.Lock()
_MEMORY_CLEANUP_STATS = {
    "count": 0,
    "last_at": "",
    "last_reason": "",
    "last_collected": 0,
    "last_malloc_trim": False,
}


def log_internal_error(context, exc):
    print("[Alas-Gyre Overlay] %s: %r" % (context, exc), flush=True)


def create_overlay_app(original_app):
    ensure_memory_watchdog()

    async def overlay_app(scope, receive, send):
        scope_type = scope.get("type")
        if scope_type != "http":
            await original_app(scope, receive, send)
            return

        path = scope.get("path", "") or ""
        if path == API_PREFIX or path.startswith(API_PREFIX + "/"):
            await handle_api(scope, receive, send)
            return

        await original_app(scope, receive, send)

    return overlay_app


def env_bool(name, default=True):
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", "disable", "disabled"}


def env_int(name, default, minimum=None, maximum=None):
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def env_float(name, default, minimum=None, maximum=None):
    try:
        value = float(os.environ.get(name, ""))
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def get_system_memory():
    cgroup_memory = get_cgroup_memory()
    if cgroup_memory:
        return cgroup_memory
    if os.name == "nt":
        return get_windows_memory()
    if os.path.exists("/proc/meminfo"):
        return get_linux_memory()
    return None


def read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def parse_memory_limit(value):
    value = str(value or "").strip()
    if not value or value == "max":
        return None
    try:
        limit = int(value)
    except ValueError:
        return None
    if limit <= 0 or limit >= (1 << 60):
        return None
    return limit


def get_cgroup_memory():
    if os.name != "posix" or not os.path.exists("/proc/self/cgroup"):
        return None
    return get_cgroup_v2_memory() or get_cgroup_v1_memory()


def get_cgroup_v2_memory():
    cgroup_path = ""
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":", 2)
                if len(parts) == 3 and parts[0] == "0":
                    cgroup_path = parts[2].lstrip("/")
                    break
    except Exception:
        return None

    if cgroup_path == "":
        base = "/sys/fs/cgroup"
    else:
        base = os.path.join("/sys/fs/cgroup", cgroup_path)
    limit = parse_memory_limit(read_text_file(os.path.join(base, "memory.max")))
    if limit is None:
        return None
    try:
        current = int(read_text_file(os.path.join(base, "memory.current")) or "0")
    except ValueError:
        return None
    available = max(0, limit - current)
    return limit, available


def get_cgroup_v1_memory():
    cgroup_path = ""
    try:
        with open("/proc/self/cgroup", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":", 2)
                if len(parts) != 3:
                    continue
                controllers = set(parts[1].split(","))
                if "memory" in controllers:
                    cgroup_path = parts[2].lstrip("/")
                    break
    except Exception:
        return None

    candidates = [
        os.path.join("/sys/fs/cgroup/memory", cgroup_path),
        os.path.join("/sys/fs/cgroup", cgroup_path),
    ]
    for base in candidates:
        limit = parse_memory_limit(read_text_file(os.path.join(base, "memory.limit_in_bytes")))
        if limit is None:
            continue
        try:
            current = int(read_text_file(os.path.join(base, "memory.usage_in_bytes")) or "0")
        except ValueError:
            continue
        available = max(0, limit - current)
        return limit, available
    return None


def get_windows_memory():
    try:
        import ctypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.ullTotalPhys), int(status.ullAvailPhys)
    except Exception:
        return None


def get_linux_memory():
    values = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                key, _, rest = line.partition(":")
                if not key:
                    continue
                parts = rest.strip().split()
                if not parts:
                    continue
                try:
                    values[key] = int(parts[0]) * 1024
                except ValueError:
                    continue
    except Exception:
        return None

    total = values.get("MemTotal")
    available = values.get("MemAvailable")
    if available is None:
        available = values.get("MemFree", 0) + values.get("Buffers", 0) + values.get("Cached", 0)
    if not total or available is None:
        return None
    return int(total), int(available)


def try_malloc_trim():
    if os.name != "posix":
        return False
    try:
        import ctypes

        libc = None
        for name in ("libc.so.6", None):
            try:
                libc = ctypes.CDLL(name) if name else ctypes.CDLL(None)
                break
            except Exception:
                continue
        if libc is None or not hasattr(libc, "malloc_trim"):
            return False
        libc.malloc_trim(0)
        return True
    except Exception:
        return False


def perform_memory_cleanup(reason):
    global _RICH_CONSOLE

    _I18N_CACHE.clear()
    _RICH_CONSOLE = None
    collected = gc.collect()
    malloc_trimmed = try_malloc_trim()

    _MEMORY_CLEANUP_STATS.update(
        {
            "count": int(_MEMORY_CLEANUP_STATS.get("count", 0)) + 1,
            "last_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "last_reason": reason,
            "last_collected": int(collected),
            "last_malloc_trim": bool(malloc_trimmed),
        }
    )
    print(
        "[Alas-Gyre Overlay] memory cleanup: reason=%s collected=%s malloc_trim=%s"
        % (reason, collected, malloc_trimmed),
        flush=True,
    )


def memory_watchdog_loop():
    interval = env_int("ALAS_GYRE_MEMORY_CHECK_INTERVAL", DEFAULT_MEMORY_WATCHDOG_INTERVAL, minimum=30)
    low_mb = env_int("ALAS_GYRE_MEMORY_LOW_MB", DEFAULT_MEMORY_LOW_MB, minimum=32)
    low_percent = env_float("ALAS_GYRE_MEMORY_LOW_PERCENT", DEFAULT_MEMORY_LOW_PERCENT, minimum=1.0, maximum=50.0)
    low_bytes = low_mb * 1024 * 1024

    while True:
        time.sleep(interval)
        memory = get_system_memory()
        if not memory:
            continue
        total, available = memory
        if total <= 0:
            continue
        available_percent = (available / float(total)) * 100.0
        if available <= low_bytes or available_percent <= low_percent:
            perform_memory_cleanup(
                "available=%dMB %.1f%% threshold=%dMB %.1f%%"
                % (available // (1024 * 1024), available_percent, low_mb, low_percent)
            )


def ensure_memory_watchdog():
    global _MEMORY_WATCHDOG_STARTED
    if not env_bool("ALAS_GYRE_MEMORY_WATCHDOG", True):
        return
    with _MEMORY_WATCHDOG_LOCK:
        if _MEMORY_WATCHDOG_STARTED:
            return
        _MEMORY_WATCHDOG_STARTED = True
        thread = threading.Thread(target=memory_watchdog_loop, name="gyre-memory-watchdog", daemon=True)
        thread.start()
        print("[Alas-Gyre Overlay] Memory watchdog enabled.", flush=True)


async def handle_api(scope, receive, send):
    method = (scope.get("method") or "GET").upper()
    path = scope.get("path", "") or ""
    route = path[len(API_PREFIX):] or "/"
    if route != "/" and route.endswith("/"):
        route = route.rstrip("/")
    query = parse_query(scope.get("query_string", b""))

    if method == "OPTIONS":
        await send_json(send, {"ok": True})
        return

    if not is_api_authorized(scope):
        await send_json(send, {"error": "unauthorized"}, status=401)
        return

    try:
        if route == "/health" and method == "GET":
            await api_health(send)
        elif route == "/configs" and method == "GET":
            await api_get_configs(send)
        elif route == "/configs" and method == "DELETE":
            await api_delete_config(send, query)
        elif route == "/status_all" and method == "GET":
            await api_get_status_all(send)
        elif route == "/status" and method == "GET":
            await api_get_status(send, query)
        elif route == "/start" and method == "POST":
            await api_post_start(send, query)
        elif route == "/stop" and method == "POST":
            await api_post_stop(send, query)
        elif route == "/log" and method == "GET":
            await api_get_log(send, query)
        elif route == "/error_screenshots" and method == "GET":
            await api_get_error_screenshots(send, query)
        elif route == "/error_screenshots/image" and method == "GET":
            await api_get_error_screenshot_image(send, query)
        else:
            await send_json(send, {"error": "not_found", "path": route}, status=404)
    except Exception as exc:
        log_internal_error("internal_error", exc)
        await send_json(send, {"error": "internal_error"}, status=500)


def parse_query(raw_query):
    if isinstance(raw_query, bytes):
        raw_query = raw_query.decode("utf-8", errors="replace")
    parsed = parse_qs(raw_query or "", keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


def headers_from_scope(scope):
    return {
        key.decode("latin1").lower(): value.decode("latin1")
        for key, value in scope.get("headers", [])
    }


def get_config_path_env():
    return os.environ.get("ALAS_GYRE_CONFIG", "").strip()


def read_expected_token():
    env_token = os.environ.get("ALAS_GYRE_API_TOKEN", "").strip()
    if env_token:
        return env_token

    config_path = get_config_path_env()
    if not config_path:
        overlay_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(overlay_dir), "config.json")

    try:
        real_path = os.path.realpath(os.path.abspath(config_path))
        stat_result = os.stat(real_path)
        mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1000000000))
        size = stat_result.st_size
        if (
            _TOKEN_CACHE.get("path") == real_path
            and _TOKEN_CACHE.get("mtime_ns") == mtime_ns
            and _TOKEN_CACHE.get("size") == size
        ):
            return _TOKEN_CACHE.get("value", "")

        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = str(data.get("api_token", "")).strip()
        _TOKEN_CACHE.update(
            {
                "path": real_path,
                "mtime_ns": mtime_ns,
                "size": size,
                "value": token,
            }
        )
        return token
    except Exception:
        _TOKEN_CACHE.update({"path": "", "mtime_ns": None, "size": None, "value": ""})
        return ""


def is_api_authorized(scope):
    expected_token = read_expected_token()
    if not expected_token:
        return False
    headers = headers_from_scope(scope)
    provided_token = headers.get(TOKEN_HEADER.lower(), "")
    return secrets.compare_digest(provided_token, expected_token)


def response_headers(content_type="application/json; charset=utf-8", extra=None):
    headers = [
        (b"content-type", content_type.encode("latin1")),
        (b"cache-control", b"no-cache"),
    ]
    if extra:
        headers.extend(extra)
    return headers


async def send_json(send, payload, status=200):
    body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": response_headers(extra=[(b"content-length", str(len(body)).encode("ascii"))]),
        }
    )
    await send({"type": "http.response.body", "body": body})


async def send_file(send, path):
    media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
    file_size = os.path.getsize(path)
    headers = response_headers(
        media_type,
        [
            (b"content-length", str(file_size).encode("ascii")),
            (b"content-disposition", f'inline; filename="{os.path.basename(path)}"'.encode("utf-8")),
        ],
    )
    await send({"type": "http.response.start", "status": 200, "headers": headers})
    with open(path, "rb") as f:
        while True:
            chunk = f.read(FILE_RESPONSE_CHUNK_SIZE)
            if not chunk:
                break
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


def get_alas_root():
    return os.path.abspath(os.environ.get("ALAS_ROOT", "") or os.getcwd())


def get_data_dir(dirname):
    candidates = [
        os.path.abspath(dirname),
        os.path.join(get_alas_root(), dirname),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return candidates[0]


def normalize_status(status):
    if isinstance(status, str) and status in VALID_STATUSES:
        return status
    return STATE_MAP.get(status, "idle")


def get_config_names():
    configs = []
    config_dir = get_data_dir(CONFIG_DIR)
    if os.path.isdir(config_dir):
        for entry in os.scandir(config_dir):
            if not entry.is_file():
                continue
            file_name = entry.name
            if not file_name.endswith(".json") or file_name.startswith("template"):
                continue
            configs.append(file_name[:-5])
    configs.sort(key=str.lower)
    return configs or [DEFAULT_CONFIG]


def get_default_config():
    configs = get_config_names()
    if DEFAULT_CONFIG in configs:
        return DEFAULT_CONFIG
    return configs[0] if configs else DEFAULT_CONFIG


def get_requested_config(query):
    config_name = query.get("config")
    if config_name is None:
        return get_default_config()
    return str(config_name).strip() or get_default_config()


def validate_requested_config(config_name):
    configs = get_config_names()
    if config_name not in configs:
        return {
            "error": "unknown_config",
            "config": config_name,
            "configs": configs,
        }
    return None


def normalize_config_name(config_name):
    name = str(config_name or "").strip()
    if name.endswith(".json"):
        name = name[:-5]
    if (
        not name
        or name in {".", ".."}
        or os.path.basename(name) != name
        or any(char in INVALID_CONFIG_NAME_CHARS for char in name)
        or any(ord(char) < 32 for char in name)
        or name.startswith("template")
        or len(name) > 120
    ):
        raise ValueError("invalid_config_name")
    return name


def get_config_path(config_name):
    config_name = normalize_config_name(config_name)
    config_dir = os.path.abspath(get_data_dir(CONFIG_DIR))
    config_path = os.path.abspath(os.path.join(config_dir, f"{config_name}.json"))
    if os.path.commonpath([config_dir, config_path]) != config_dir:
        raise ValueError("invalid config path")
    return config_path


def get_manager(config_name):
    from module.webui.process_manager import ProcessManager

    return ProcessManager.get_manager(config_name)


def get_status(config_name):
    manager = get_manager(config_name)
    return normalize_status(getattr(manager, "state", None))


def get_log_line_limit(query):
    try:
        value = int(query.get("lines", str(DEFAULT_LOG_LINES)))
    except (TypeError, ValueError):
        value = DEFAULT_LOG_LINES
    return max(1, min(value, MAX_LOG_LINES))


def get_error_screenshot_limit(query):
    try:
        value = int(query.get("limit", str(DEFAULT_ERROR_SCREENSHOT_LIMIT)))
    except (TypeError, ValueError):
        value = DEFAULT_ERROR_SCREENSHOT_LIMIT
    return max(1, min(value, MAX_ERROR_SCREENSHOT_LIMIT))


def get_latest_log_file(config_name):
    log_dir = get_data_dir(LOG_DIR)
    if not os.path.isdir(log_dir):
        return None

    suffix = f"_{config_name}.txt"
    best_path = None
    best_key = None
    for entry in os.scandir(log_dir):
        if entry.is_file() and entry.name.endswith(suffix):
            try:
                stat_result = entry.stat()
            except OSError:
                continue
            key = (stat_result.st_mtime, entry.name)
            if best_key is None or key > best_key:
                best_key = key
                best_path = entry.path
    return best_path


def get_error_dir():
    return os.path.join(get_data_dir(LOG_DIR), ERROR_LOG_DIR)


def parse_error_folder_time(folder_name, fallback_path):
    try:
        timestamp = int(folder_name) / 1000
    except (TypeError, ValueError):
        timestamp = os.path.getmtime(fallback_path)
    return timestamp


def format_error_time(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def list_error_images(folder_path):
    images = []
    for entry in os.scandir(folder_path):
        if not entry.is_file(follow_symlinks=False):
            continue
        ext = os.path.splitext(entry.name)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            continue
        stat = entry.stat()
        images.append(
            {
                "name": entry.name,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "display_time": format_error_time(stat.st_mtime),
            }
        )
    images.sort(key=lambda item: item["name"])
    return images


def list_error_screenshot_groups(limit):
    error_dir = get_error_dir()
    if not os.path.isdir(error_dir):
        return []

    groups = []
    for entry in os.scandir(error_dir):
        if entry.is_dir(follow_symlinks=False):
            try:
                images = list_error_images(entry.path)
            except OSError:
                continue
            if not images:
                continue
            timestamp = parse_error_folder_time(entry.name, entry.path)
            groups.append(
                {
                    "folder": entry.name,
                    "timestamp": timestamp,
                    "display_time": format_error_time(timestamp),
                    "image_count": len(images),
                    "images": images,
                }
            )
        elif entry.is_file(follow_symlinks=False):
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                stat = entry.stat()
                timestamp = stat.st_mtime
                groups.append(
                    {
                        "folder": ".",
                        "timestamp": timestamp,
                        "display_time": format_error_time(timestamp),
                        "image_count": 1,
                        "images": [
                            {
                                "name": entry.name,
                                "size": stat.st_size,
                                "modified": timestamp,
                                "display_time": format_error_time(timestamp),
                            }
                        ],
                    }
                )

    groups.sort(key=lambda item: item["timestamp"], reverse=True)
    return groups[:limit]


def resolve_error_folder(folder):
    folder = str(folder or "").strip()
    if folder == ".":
        return os.path.abspath(get_error_dir())
    if (
        not folder
        or folder == ".."
        or os.path.basename(folder) != folder
        or any(char in INVALID_CONFIG_NAME_CHARS for char in folder)
        or any(ord(char) < 32 for char in folder)
    ):
        raise ValueError("invalid_error_folder")

    error_dir = os.path.realpath(os.path.abspath(get_error_dir()))
    folder_path = os.path.realpath(os.path.abspath(os.path.join(error_dir, folder)))
    if os.path.commonpath([error_dir, folder_path]) != error_dir:
        raise ValueError("invalid_error_folder")
    if not os.path.isdir(folder_path):
        raise FileNotFoundError("error_folder_not_found")
    return folder_path


def resolve_error_image(folder, file_name):
    folder_path = resolve_error_folder(folder)
    file_name = str(file_name or "").strip()
    if (
        not file_name
        or file_name in {".", ".."}
        or os.path.basename(file_name) != file_name
        or any(char in INVALID_CONFIG_NAME_CHARS for char in file_name)
        or any(ord(char) < 32 for char in file_name)
    ):
        raise ValueError("invalid_error_image")
    if os.path.splitext(file_name)[1].lower() not in IMAGE_EXTENSIONS:
        raise ValueError("invalid_error_image_type")

    real_folder_path = os.path.realpath(folder_path)
    image_path = os.path.realpath(os.path.abspath(os.path.join(folder_path, file_name)))
    if os.path.commonpath([real_folder_path, image_path]) != real_folder_path:
        raise ValueError("invalid_error_image")
    if not os.path.isfile(image_path):
        raise FileNotFoundError("error_image_not_found")
    return image_path


def tail_log_file(log_file, line_limit):
    file_size = os.path.getsize(log_file)
    if file_size <= 0:
        return ""

    chunks = []
    newline_count = 0
    position = file_size

    with open(log_file, "rb") as f:
        while position > 0 and newline_count <= line_limit:
            read_size = min(LOG_TAIL_CHUNK_SIZE, position)
            position -= read_size
            f.seek(position)
            chunk = f.read(read_size)
            chunks.append(chunk)
            newline_count += chunk.count(b"\n")

    data = b"".join(reversed(chunks))
    lines = data.splitlines(keepends=True)
    return b"".join(lines[-line_limit:]).decode("utf-8", errors="replace")


def render_log_item(renderable):
    global _RICH_CONSOLE
    if isinstance(renderable, str):
        return renderable if renderable.endswith("\n") else renderable + "\n"
    if Console is None:
        return str(renderable) + "\n"

    if _RICH_CONSOLE is None:
        _RICH_CONSOLE = Console(no_color=True, highlight=False, width=119)
    with _RICH_CONSOLE.capture() as capture:
        _RICH_CONSOLE.print(renderable)
    return capture.get()


def get_live_log(config_name, line_limit):
    manager = get_manager(config_name)
    renderables = getattr(manager, "renderables", None)
    if not renderables:
        return ""

    lines = deque(maxlen=line_limit)
    recent_renderables = deque(maxlen=min(MAX_LIVE_RENDERABLES, max(line_limit * 2, line_limit)))
    for renderable in renderables:
        recent_renderables.append(renderable)
    for renderable in recent_renderables:
        lines.extend(render_log_item(renderable).splitlines(True))
    return "".join(lines)


def extract_running_task(config_name):
    def load_i18n_json(paths):
        for path in paths:
            if not os.path.exists(path):
                continue
            try:
                real_path = os.path.realpath(os.path.abspath(path))
                stat_result = os.stat(real_path)
                mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1000000000))
                size = stat_result.st_size
                cached = _I18N_CACHE.get(real_path)
                if (
                    cached
                    and cached.get("mtime_ns") == mtime_ns
                    and cached.get("size") == size
                ):
                    return cached.get("data", {})

                with open(real_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if len(_I18N_CACHE) > 8:
                    _I18N_CACHE.clear()
                _I18N_CACHE[real_path] = {
                    "mtime_ns": mtime_ns,
                    "size": size,
                    "data": data if isinstance(data, dict) else {},
                }
                return _I18N_CACHE[real_path]["data"]
            except Exception:
                continue
        return {}

    def extract_translation_value(value):
        if isinstance(value, str):
            return value
        if not isinstance(value, dict):
            return None
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            return name
        info = value.get("_info")
        if isinstance(info, dict):
            info_name = info.get("name")
            if isinstance(info_name, str) and info_name.strip():
                return info_name
        return None

    def find_translation(data, key):
        if not isinstance(data, dict):
            return None
        # ALAS official i18n stores task display names mostly under:
        #   Task.Restart.name -> 重启设置
        # A direct recursive lookup would miss this because "Restart" maps to a
        # dict, not a string.  Prefer the Task section over Menu to avoid
        # returning generic menu names for task keys such as "Alas".
        for section in ("Task", "Menu"):
            section_data = data.get(section)
            if isinstance(section_data, dict) and key in section_data:
                translated = extract_translation_value(section_data[key])
                if translated:
                    return translated
        if key in data:
            translated = extract_translation_value(data[key])
            if translated:
                return translated
        for child_key, value in data.items():
            if child_key in {"Task", "Menu"}:
                continue
            if isinstance(value, dict):
                res = find_translation(value, key)
                if res:
                    return res
        return None

    def translate_task(task_name):
        if not task_name:
            return ""
        clean_name = task_name.replace("`", "").strip()
        if not clean_name:
            return ""
        paths = [
            "module/config/i18n/zh-CN.json",
            "module/config/i18n/zh_CN.json",
            "gui/i18n/zh-CN.json",
            "config/i18n/zh-CN.json",
        ]
        i18n_dict = load_i18n_json(paths)
        translated = find_translation(i18n_dict, clean_name)
        return translated if translated else clean_name

    try:
        import re

        manager = get_manager(config_name)
        task_value = getattr(manager, "task", None)
        if not task_value:
            for attr in ("current_task", "running_task", "active_task", "scheduler"):
                value = getattr(manager, attr, None)
                if value:
                    if attr == "scheduler":
                        task_value = getattr(value, "task", None) or getattr(value, "current_task", None)
                    else:
                        task_value = value
                    if task_value:
                        break

        task_str = ""
        if task_value:
            task_str = re.sub(r"\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$", "", str(task_value)).strip()

        if not task_str:
            log_file = get_latest_log_file(config_name)
            if log_file and os.path.exists(log_file):
                lines = tail_log_file(log_file, 1000).splitlines()
                for line in reversed(lines):
                    if "Scheduler: Start task" in line:
                        match = re.search(r"Scheduler:\s+Start\s+task\s+(\S+)", line)
                        if match:
                            raw_task = match.group(1).strip().strip("'\"")
                            task_str = re.sub(
                                r"\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$",
                                "",
                                raw_task,
                            ).strip()
                            break
                    elif "Scheduler: End task" in line:
                        break

        if task_str:
            return translate_task(task_str)
    except Exception:
        pass
    return ""


async def api_health(send):
    configs = get_config_names()
    await send_json(
        send,
        {
            "ok": True,
            "overlay": True,
            "gyre_overlay_version": OVERLAY_VERSION,
            "api_prefix": API_PREFIX,
            "memory_watchdog": dict(_MEMORY_CLEANUP_STATS),
            "configs": configs,
            "default": get_default_config(),
        },
    )


async def api_get_configs(send):
    await send_json(send, {"configs": get_config_names(), "default": get_default_config()})


async def api_delete_config(send, query):
    config_name = get_requested_config(query)
    configs = get_config_names()
    if config_name not in configs:
        await send_json(send, {"error": "unknown_config", "config": config_name, "configs": configs}, status=404)
        return
    if len(configs) <= 1:
        await send_json(
            send,
            {"error": "cannot_delete_last_config", "config": config_name, "configs": configs},
            status=409,
        )
        return

    try:
        try:
            status = get_status(config_name)
        except Exception:
            status = "idle"
        if status == "running":
            await send_json(
                send,
                {"error": "cannot_delete_running_config", "config": config_name, "status": "running"},
                status=409,
            )
            return

        config_path = get_config_path(config_name)
        if not os.path.exists(config_path):
            await send_json(
                send,
                {"error": "config_file_not_found", "config": config_name, "configs": configs},
                status=404,
            )
            return
        os.remove(config_path)
        configs = get_config_names()
        await send_json(
            send,
            {
                "config": config_name,
                "message": "deleted",
                "configs": configs,
                "default": get_default_config(),
            },
        )
    except Exception as exc:
        log_internal_error("delete_failed", exc)
        await send_json(send, {"error": "delete_failed", "config": config_name}, status=500)


async def api_get_status_all(send):
    statuses = {}
    errors = {}
    tasks = {}
    for config_name in get_config_names():
        try:
            status = get_status(config_name)
            statuses[config_name] = status
            tasks[config_name] = extract_running_task(config_name) if status == "running" else ""
        except Exception as exc:
            statuses[config_name] = "error"
            tasks[config_name] = ""
            log_internal_error("status_all_failed:%s" % config_name, exc)
            errors[config_name] = "status_failed"

    payload = {"statuses": statuses, "tasks": tasks}
    if errors:
        payload["errors"] = errors
    await send_json(send, payload)


async def api_get_status(send, query):
    config_name = get_requested_config(query)
    error_payload = validate_requested_config(config_name)
    if error_payload is not None:
        await send_json(send, error_payload, status=404)
        return

    try:
        status = get_status(config_name)
        task = extract_running_task(config_name) if status == "running" else ""
        await send_json(send, {"config": config_name, "status": status, "task": task})
    except Exception as exc:
        log_internal_error("status_failed:%s" % config_name, exc)
        await send_json(send, {"config": config_name, "status": "error", "error": "status_failed"}, status=500)


async def api_post_start(send, query):
    config_name = get_requested_config(query)
    error_payload = validate_requested_config(config_name)
    if error_payload is not None:
        await send_json(send, error_payload, status=404)
        return

    try:
        manager = get_manager(config_name)
        already_running = bool(getattr(manager, "alive", False))
        if not already_running:
            manager.start(None)
        await send_json(
            send,
            {
                "config": config_name,
                "message": "already_running" if already_running else "started",
                "status": get_status(config_name),
            },
        )
    except Exception as exc:
        log_internal_error("start_failed:%s" % config_name, exc)
        await send_json(
            send,
            {"config": config_name, "message": "start_failed", "status": "error", "error": "start_failed"},
            status=500,
        )


async def api_post_stop(send, query):
    config_name = get_requested_config(query)
    error_payload = validate_requested_config(config_name)
    if error_payload is not None:
        await send_json(send, error_payload, status=404)
        return

    try:
        manager = get_manager(config_name)
        was_running = bool(getattr(manager, "alive", False))
        if was_running:
            manager.stop()
        await send_json(
            send,
            {
                "config": config_name,
                "message": "stopped" if was_running else "already_stopped",
                "status": get_status(config_name),
            },
        )
    except Exception as exc:
        log_internal_error("stop_failed:%s" % config_name, exc)
        await send_json(
            send,
            {"config": config_name, "message": "stop_failed", "status": "error", "error": "stop_failed"},
            status=500,
        )


async def api_get_log(send, query):
    config_name = get_requested_config(query)
    error_payload = validate_requested_config(config_name)
    if error_payload is not None:
        await send_json(send, error_payload, status=404)
        return

    line_limit = get_log_line_limit(query)
    live_error = None
    try:
        live_log = get_live_log(config_name, line_limit)
    except Exception as exc:
        live_log = ""
        log_internal_error("live_log_failed:%s" % config_name, exc)
        live_error = "live_log_unavailable"

    if live_log:
        await send_json(send, {"config": config_name, "exists": True, "source": "live", "lines": line_limit, "log": live_log})
        return

    log_file = get_latest_log_file(config_name)
    if not log_file or not os.path.exists(log_file):
        payload = {"config": config_name, "exists": False, "source": "none", "lines": line_limit, "log": ""}
        if live_error:
            payload["live_error"] = live_error
        await send_json(send, payload)
        return

    try:
        payload = {
            "config": config_name,
            "exists": True,
            "source": "file",
            "file": os.path.basename(log_file),
            "lines": line_limit,
            "log": tail_log_file(log_file, line_limit),
        }
        if live_error:
            payload["live_error"] = live_error
        await send_json(send, payload)
    except Exception as exc:
        log_internal_error("log_file_failed:%s" % config_name, exc)
        await send_json(
            send,
            {
                "config": config_name,
                "exists": True,
                "source": "file",
                "file": os.path.basename(log_file),
                "lines": line_limit,
                "log": "",
                "error": "log_read_failed",
            },
            status=500,
        )


async def api_get_error_screenshots(send, query):
    limit = get_error_screenshot_limit(query)
    try:
        groups = list_error_screenshot_groups(limit)
        await send_json(
            send,
            {
                "exists": bool(groups),
                "directory": os.path.relpath(get_error_dir(), get_alas_root()),
                "groups": groups,
            },
        )
    except Exception as exc:
        log_internal_error("error_screenshots_failed", exc)
        await send_json(send, {"exists": False, "groups": [], "error": "list_failed"}, status=500)


async def api_get_error_screenshot_image(send, query):
    folder = query.get("folder")
    file_name = query.get("file")
    try:
        image_path = resolve_error_image(folder, file_name)
        await send_file(send, image_path)
    except FileNotFoundError as exc:
        await send_json(send, {"error": str(exc), "folder": folder, "file": file_name}, status=404)
    except ValueError as exc:
        await send_json(send, {"error": str(exc), "folder": folder, "file": file_name}, status=400)
    except Exception as exc:
        log_internal_error("error_screenshot_image_failed", exc)
        await send_json(send, {"error": "image_read_failed", "folder": folder, "file": file_name}, status=500)
