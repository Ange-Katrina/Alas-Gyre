"""Isolated workflow regressions; no real ALAS, credentials, or remote hosts.

Run with the desktop/system Python: python tools/test_api_workflows.py
"""
import asyncio
import base64
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from alas_gyre.api import client, runtime_update
from alas_gyre.services import updater as desktop_updater


def load(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


overlay = load("overlay/gyre_overlay_runtime.py")
updater = load("resources/gyre_runtime_updater.py")


class Manager:
    alive = False

    def __init__(self):
        self.calls = []
        self.renderables = []

    @property
    def state(self):
        return 1 if self.alive else 2

    def start(self, func, ev=None):
        self.calls.append((func, ev))
        self.alive = True

    def stop(self):
        self.alive = False


class OverlayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gyre-api-test-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        (self.base / "config").mkdir()
        for name in ("alas", "second"):
            (self.base / "config" / (name + ".json")).write_text("{}", encoding="utf-8")
        self.managers = {name: Manager() for name in ("alas", "second")}
        self.host_updater = types.SimpleNamespace(state=0, event=threading.Event())
        self.host_utils = types.ModuleType("module.submodule.utils")
        self.host_utils.list_mod_instance = Mock()
        for context in (
            patch.dict(os.environ, ALAS_GYRE_API_TOKEN="test-only"),
            patch.object(overlay, "get_data_dir", lambda name: str(self.base / name)),
            patch.object(overlay, "get_manager", lambda name: self.managers.setdefault(name, Manager())),
            patch.object(overlay, "get_updater", lambda: self.host_updater),
            patch.dict(sys.modules, {"module.submodule.utils": self.host_utils}),
        ):
            context.start()
            self.addCleanup(context.stop)
        overlay._CONFIG_OPERATION_LOCKS.clear()
        overlay._UPDATE_BUSY = False

    async def request(self, route, method="GET", query=b"config=alas", body=b"", headers=None):
        messages = []

        async def receive():
            return {"type": "http.request", "body": body}

        async def send(message):
            messages.append(message)
            await asyncio.sleep(0)  # Exercise a yielding network send.

        await overlay.handle_api({"method": method, "path": "/api/gyre" + route,
                                  "query_string": query,
                                  "headers": headers if headers is not None else [(b"x-alas-gyre-token", b"test-only")]}, receive, send)
        return messages[0]["status"], json.loads(messages[-1]["body"])

    def test_authentication_rejects_missing_duplicate_and_non_ascii_headers(self):
        for headers in ([], [(b"x-alas-gyre-token", b"wrong")],
                        [(b"x-alas-gyre-token", b"\xff")],
                        [(b"x-alas-gyre-token", b"test-only")] * 2):
            self.assertEqual(asyncio.run(self.request("/health", headers=headers))[0], 401)
        self.assertEqual(asyncio.run(self.request("/health"))[0], 200)

    def test_host_update_event_and_start_stop_restart(self):
        for action in ("start", "restart", "stop"):
            status, payload = asyncio.run(self.request("/" + action, "POST"))
            self.assertEqual(status, 200, payload)
        self.assertIs(self.managers["alas"].calls[0][1], self.host_updater.event)
        self.assertEqual(self.host_utils.list_mod_instance.call_count, 2)
        self.assertFalse(self.managers["alas"].alive)

    def test_start_rejected_while_host_update_event_is_set(self):
        self.host_updater.event.set()
        status, payload = asyncio.run(self.request("/start", "POST"))
        self.assertEqual((status, payload["error"]), (409, "update_in_progress"))
        self.assertFalse(self.managers["alas"].calls)

    def test_restart_rejected_before_stopping_when_update_is_active(self):
        manager = self.managers["alas"]
        manager.alive = True
        self.host_updater.state = "wait"
        status, _ = asyncio.run(self.request("/restart", "POST"))
        self.assertEqual(status, 409)
        self.assertTrue(manager.alive)

    def test_update_reservation_does_not_block_event_loop(self):
        held = threading.Event()
        release = threading.Event()

        def hold():
            with overlay._UPDATE_OP_LOCK:
                held.set()
                release.wait(3)

        worker = threading.Thread(target=hold)
        worker.start()
        try:
            self.assertTrue(held.wait(1))
            self.host_updater.check_update = Mock()
            status, _ = asyncio.run(self.request("/update/check", "POST"))
            self.assertEqual(status, 409)
            self.host_updater.check_update.assert_not_called()
        finally:
            release.set()
            worker.join(2)

    def test_save_backup_and_fail_closed_delete(self):
        status, payload = asyncio.run(self.request("/config", "PUT", body=b'{"data":{"x":1}}'))
        self.assertEqual(status, 200, payload)
        self.assertTrue((self.base / "config" / payload["backup"]).exists())
        self.assertEqual(json.loads((self.base / "config/alas.json").read_text()), {"x": 1})
        with patch.object(overlay, "get_status", side_effect=RuntimeError("unavailable")):
            status, _ = asyncio.run(self.request("/configs", "DELETE", b"config=second"))
        self.assertEqual(status, 500)
        self.assertTrue((self.base / "config/second.json").exists())

    def test_parallel_deletes_keep_last_config(self):
        async def run():
            return await asyncio.gather(self.request("/configs", "DELETE", b"config=alas"),
                                        self.request("/configs", "DELETE", b"config=second"))
        results = asyncio.run(run())
        self.assertEqual(sorted(code for code, _ in results), [200, 409])
        self.assertEqual(len(overlay.get_config_names()), 1)

    def test_stop_does_not_block_health_or_race_same_config(self):
        entered = threading.Event()
        release = threading.Event()
        manager = self.managers["alas"]
        manager.alive = True

        def stop():
            entered.set()
            release.wait(3)
            manager.alive = False

        manager.stop = stop

        async def run():
            stopping = asyncio.create_task(self.request("/stop", "POST"))
            try:
                deadline = time.monotonic() + 2
                while not entered.is_set() and time.monotonic() < deadline:
                    await asyncio.sleep(0.01)
                self.assertTrue(entered.is_set())
                self.assertEqual((await asyncio.wait_for(self.request("/health"), 0.5))[0], 200)
                self.assertEqual((await self.request("/start", "POST"))[0], 409)
            finally:
                release.set()
            self.assertEqual((await stopping)[0], 200)
        asyncio.run(run())

    def test_yielding_sends_do_not_hold_mutation_locks(self):
        async def run():
            return await asyncio.wait_for(asyncio.gather(
                self.request("/restart", "POST"), self.request("/restart", "POST")), 3)
        self.assertTrue(all(status in (200, 409) for status, _ in asyncio.run(run())))

    def test_mod_config_resolves_logical_name_and_rejects_ambiguity(self):
        path = self.base / "config/demo.maa.json"
        path.write_text("{}")
        self.assertIn("demo", overlay.get_config_names())
        self.assertNotIn("demo.maa", overlay.get_config_names())
        self.assertEqual(Path(overlay.get_config_path("demo")), path)
        (self.base / "config/demo.json").write_text("{}")
        self.assertEqual(overlay.validate_single_config("demo")[1], "ambiguous_config_name")

    def test_invalid_paths_and_bounded_body_and_logs(self):
        for name in ("../x", "..\\x", "template", "x/y"):
            self.assertEqual(overlay.validate_single_config(name)[2], 400)
        status, _ = asyncio.run(self.request("/config", "PUT", body=b"x" * (overlay.MAX_CONFIG_BODY_BYTES + 1)))
        self.assertEqual(status, 400)
        path = self.base / "long.log"
        path.write_bytes(b"x" * (overlay.MAX_LOG_BYTES * 3))
        self.assertEqual(len(overlay.tail_log_file(path, 1)), overlay.MAX_LOG_BYTES)
        self.managers["alas"].renderables = ["x" * overlay.MAX_LOG_BYTES] * 20
        self.assertLessEqual(len(overlay.get_live_log("alas", 2000).encode()), overlay.MAX_LOG_BYTES)

    def test_slow_body_has_deadline(self):
        async def receive():
            await asyncio.sleep(1)
        with patch.object(overlay, "REQUEST_BODY_TIMEOUT", 0.02):
            with self.assertRaisesRegex(ValueError, "request_timeout"):
                asyncio.run(overlay.read_json_body(receive))

    def test_cancel_only_during_host_wait_phase(self):
        self.host_updater.cancel = Mock()
        for state, expected in (("run update", 409), ("start", 409), ("wait", 200)):
            self.host_updater.state = state
            self.assertEqual(asyncio.run(self.request("/update/cancel", "POST"))[0], expected)
        self.host_updater.cancel.assert_called_once()


class RuntimeTests(unittest.TestCase):
    def test_real_client_incremental_update_against_loopback_server(self):
        with tempfile.TemporaryDirectory(prefix="gyre-client-server-") as temp, \
                patch.dict(os.environ, ALAS_GYRE_API_TOKEN="test-only"):
            server = updater.RuntimeUpdaterHTTPServer(("127.0.0.1", 0), updater.RuntimeUpdaterHandler)
            server.runtime_dir = temp
            server.update_host, server.update_port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                config = {"ip": "127.0.0.1", "runtime_update_port": str(server.update_port), "api_token": "test-only"}
                result = runtime_update.update_remote_runtime(config, "test")
                self.assertTrue(result["success"], result)
                self.assertEqual(len(result["updated"]), 5)
                self.assertTrue(result["restart_required"])
                self.assertTrue(result["updater_restart_required"])
                result = runtime_update.update_remote_runtime(config, "test")
                self.assertEqual(result["message"], "latest")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)

    def test_failed_multi_file_update_rolls_back(self):
        with tempfile.TemporaryDirectory(prefix="gyre-update-test-") as temp:
            base = Path(temp)
            names = ("start_gyre_alas.sh", "start_gyre_alas.bat")
            for name in names:
                (base / name).write_bytes(b"original")
            item = {"sha256": updater.sha256_bytes(b"new"), "content_b64": base64.b64encode(b"new").decode()}
            original_write = updater.write_allowed_file

            def write(directory, name, content):
                if name == names[1]:
                    raise OSError("simulated disk failure")
                original_write(directory, name, content)

            with patch.object(updater, "write_allowed_file", side_effect=write):
                with self.assertRaises(OSError):
                    updater.apply_update(temp, {"files": dict.fromkeys(names, item)})
            for name in names:
                self.assertEqual((base / name).read_bytes(), b"original")
            self.assertFalse(list(base.glob(".gyre-update-*")))

    def test_slow_headers_do_not_block_health_and_expire(self):
        with tempfile.TemporaryDirectory(prefix="gyre-http-test-") as temp, \
                patch.dict(os.environ, ALAS_GYRE_API_TOKEN="test-only"), \
                patch.object(updater, "REQUEST_TIMEOUT", 0.3):
            server = updater.RuntimeUpdaterHTTPServer(("127.0.0.1", 0), updater.RuntimeUpdaterHandler)
            server.runtime_dir = temp
            server.update_host, server.update_port = server.server_address
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with socket.create_connection(server.server_address, timeout=2) as slow:
                    slow.sendall(b"GET /runtime/info HTTP/1.1\r\nHost: localhost\r\n")
                    opener = build_opener(ProxyHandler({}))
                    url = "http://%s:%s/runtime/info" % server.server_address
                    with opener.open(Request(url, headers={"X-Alas-Gyre-Token": "test-only"}), timeout=1) as response:
                        self.assertEqual(response.status, 200)
                    self.assertEqual(slow.recv(100), b"")
                    with self.assertRaises(HTTPError) as error:
                        opener.open(url, timeout=1)
                    self.assertEqual(error.exception.code, 401)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)

    def test_validation_precedes_any_write(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                updater.apply_update(temp, {"files": {"../escape": {}}})
            self.assertEqual(list(Path(temp).iterdir()), [])


class ClientTests(unittest.TestCase):
    def test_ui_poll_clears_all_stale_statuses_on_failure_or_missing_config(self):
        if importlib.util.find_spec("PySide6") is None:
            self.skipTest("PySide6 not installed")
        from ui import main_window
        for code, payload in ((500, {}), (200, []), (200, {"statuses": {"alas": "running"}, "tasks": {}})):
            response = Mock(status_code=code)
            response.json.return_value = payload
            card = types.SimpleNamespace(config={}, _configs=["alas", "second"], current_config="alas",
                                         status_all_update_signal=Mock(), status_update_signal=Mock())
            with patch.object(main_window, "api_request", return_value=response):
                main_window.CardWidget._poll_status_task(card)
            statuses = card.status_all_update_signal.emit.call_args.args[0]
            self.assertEqual(statuses["second"], "disconnected")
            self.assertEqual(statuses["alas"], "running" if code == 200 and isinstance(payload, dict) else "disconnected")

    def test_ipv6_ports_and_no_redirects(self):
        self.assertEqual(client.api_base_url({"ip": "::1"}), "http://[::1]:22267")
        for port in ("0", "65536", "abc", "１２"):
            with self.assertRaises(ValueError):
                runtime_update.runtime_update_base_url({"runtime_update_port": port})
        with patch("requests.Session") as session:
            client.api_request("GET", "http://127.0.0.1:1")
            self.assertFalse(session.return_value.request.call_args.kwargs["allow_redirects"])
            session.return_value.close.assert_called_once()

    def test_update_rejects_non_object_json_and_unverified_hashes(self):
        info = Mock(status_code=200)
        info.json.return_value = {"ok": True, "protocol": "alas-gyre-runtime-update", "files": {}}
        response = Mock(status_code=200)
        for payload in ([], {"ok": True, "files": {}}):
            response.json.return_value = payload
            with patch.object(runtime_update, "check_remote_runtime", return_value=info), \
                    patch.object(runtime_update, "build_local_runtime_files", return_value={"start_gyre_alas.sh": {"sha256": "a" * 64, "content": b"x"}}), \
                    patch.object(runtime_update, "api_request", return_value=response):
                self.assertFalse(runtime_update.update_remote_runtime({"api_token": "test-only"}, "test")["success"])


class DesktopUpdaterTests(unittest.TestCase):
    def test_helper_launch_failure_does_not_report_success_or_exit(self):
        with tempfile.TemporaryDirectory(prefix="gyre-desktop-update-") as temp:
            exe = Path(temp) / "中文 app.exe"
            exe.write_bytes(b"old executable")
            content = b"MZ" + b"x" * 2048
            response = Mock(headers={"content-length": str(len(content))})
            response.iter_content.return_value = [content]
            finish = Mock()
            with patch.object(desktop_updater, "get_current_exe_path", return_value=str(exe)), \
                    patch.object(desktop_updater, "http_get", return_value=response), \
                    patch.object(desktop_updater.subprocess, "Popen", side_effect=OSError("helper blocked")), \
                    patch.object(desktop_updater.os, "_exit") as exit_process:
                desktop_updater.do_update("https://example.invalid/update.exe", None, finish,
                                          expected_sha256=updater.sha256_bytes(content))
            finish.assert_called_once()
            self.assertFalse(finish.call_args.args[0])
            exit_process.assert_not_called()
            self.assertEqual(exe.read_bytes(), b"old executable")

    def test_hash_failure_never_launches_helper(self):
        with tempfile.TemporaryDirectory(prefix="gyre-desktop-update-") as temp:
            exe = Path(temp) / "app.exe"
            exe.write_bytes(b"old executable")
            response = Mock(headers={})
            response.iter_content.return_value = [b"MZ" + b"x" * 2048]
            finish = Mock()
            with patch.object(desktop_updater, "get_current_exe_path", return_value=str(exe)), \
                    patch.object(desktop_updater, "http_get", return_value=response), \
                    patch.object(desktop_updater.subprocess, "Popen") as launch, \
                    patch.object(desktop_updater.os, "_exit") as exit_process:
                desktop_updater.do_update("https://example.invalid/update.exe", None, finish, expected_sha256="0" * 64)
            launch.assert_not_called()
            exit_process.assert_not_called()
            self.assertFalse(finish.call_args.args[0])
            self.assertEqual(exe.read_bytes(), b"old executable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
