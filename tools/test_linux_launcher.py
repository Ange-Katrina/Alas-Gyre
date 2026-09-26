"""Launcher regression tests; Linux cases use temporary dummy services only.

Run: python tools/test_linux_launcher.py
No real ALAS instance, installed service, or saved credentials are used.
"""

import os
from pathlib import Path
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alas_gyre.api.overlay_launcher import generate_portable_overlay_launchers


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for dummy service or launcher")


class LauncherTests(unittest.TestCase):
    def test_config_file_values_survive_repeated_loads(self):
        shell = shutil.which("sh")
        if shell is None and os.name == "nt":
            candidate = Path(r"C:\Program Files\Git\bin\sh.exe")
            if candidate.is_file():
                shell = str(candidate)
        if shell is None:
            self.skipTest("No POSIX shell available")
        with tempfile.TemporaryDirectory(prefix="gyre-config-test-") as directory:
            result = generate_portable_overlay_launchers(directory, api_token="test-only")
            script = Path(result["sh_path"])
            # Load the real functions without dispatching the menu or services.
            text = script.read_text(encoding="utf-8").rsplit('case "${1:-}" in', 1)[0]
            script.write_text(text + '''
load_config
load_config
printf '%s|%s|%s|%s|%s\\n' "$GYRE_UPDATE_HOST" "$GYRE_UPDATE_PORT" "$GYRE_LOG_MAX_BYTES" "$GYRE_LOG_BACKUP_COUNT" "$(basename "$ALAS_ROOT")"
''', encoding="utf-8")
            for name in ("config-host", "env-host"):
                host = Path(directory) / name
                (host / "module/webui").mkdir(parents=True)
                (host / "gui.py").touch()
                (host / "module/webui/app.py").touch()
            (script.parent / ".gyre_runtime.conf").write_text(
                "GYRE_UPDATE_HOST=127.0.0.1\nGYRE_UPDATE_PORT=32109\n"
                "GYRE_LOG_MAX_BYTES=12345\nGYRE_LOG_BACKUP_COUNT=7\n"
                f"ALAS_ROOT={(Path(directory) / 'config-host').as_posix()}\n", encoding="utf-8"
            )
            env = {key: value for key, value in os.environ.items() if not key.startswith(("GYRE_", "ALAS_"))}
            result = subprocess.run([shell, str(script)], env=env, capture_output=True, text=True, check=True, timeout=10)
            self.assertIn("127.0.0.1|32109|12345|7|config-host", result.stdout)
            env["GYRE_UPDATE_PORT"] = "32110"
            env["ALAS_ROOT"] = (Path(directory) / "env-host").as_posix()
            result = subprocess.run([shell, str(script)], env=env, capture_output=True, text=True, check=True, timeout=10)
            self.assertIn("127.0.0.1|32110|12345|7|env-host", result.stdout)

    def test_generated_shell_syntax(self):
        shell = shutil.which("sh")
        if shell is None and os.name == "nt":
            candidate = Path(r"C:\Program Files\Git\bin\sh.exe")
            if candidate.is_file():
                shell = str(candidate)
        if shell is None:
            self.skipTest("No POSIX shell available")
        with tempfile.TemporaryDirectory(prefix="gyre-launcher-") as directory:
            result = generate_portable_overlay_launchers(directory, api_token="test-'quote")
            subprocess.run([shell, "-n", result["sh_path"]], check=True, timeout=10)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Requires Linux process/session semantics")
    def test_services_survive_menu_exit(self):
        # Exercise both detached-start implementations, both menu choices,
        # terminal interrupt/hangup, and normal menu exit.
        for fallback in (False, True):
            for choice, exit_signal in (("1", signal.SIGINT), ("2", signal.SIGINT),
                                        ("1", signal.SIGHUP), ("2", None)):
                with self.subTest(fallback=fallback, choice=choice, signal=exit_signal):
                    self.check_menu_exit(fallback, choice, exit_signal)

    def check_menu_exit(self, fallback, choice, exit_signal):
        with tempfile.TemporaryDirectory(prefix="gyre-launcher-") as directory:
            base = Path(directory)
            result = generate_portable_overlay_launchers(directory, api_token="launcher-test-only")
            runtime = Path(result["output_dir"])
            script = Path(result["sh_path"])
            if fallback:
                # Only disable setsid discovery in this temporary test copy.
                text = script.read_text(encoding="utf-8")
                script.write_text(text.replace("if command -v setsid >/dev/null 2>&1; then",
                                               "if false; then"), encoding="utf-8")
            host = base / "dummy ALAS"
            (host / "module/webui").mkdir(parents=True)
            (host / "module/webui/app.py").touch()
            (host / "gui.py").write_text(
                "import os, subprocess, sys\nfrom http.server import HTTPServer, BaseHTTPRequestHandler\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
                "with open(os.environ['TEST_WORKER_PID_FILE'], 'w') as f: f.write(str(child.pid))\n"
                "class Handler(BaseHTTPRequestHandler):\n"
                "    def do_GET(self):\n"
                "        self.send_response(200)\n        self.end_headers()\n"
                "        self.wfile.write(b'dummy-alas')\n"
                "HTTPServer(('127.0.0.1', int(os.environ['TEST_ALAS_PORT'])), Handler).serve_forever()\n",
                encoding="utf-8",
            )
            (host / "run_alas.sh").write_text(
                "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -u gui.py\n", encoding="utf-8"
            )
            host_alias = base / "linked ALAS"
            host_alias.symlink_to(host, target_is_directory=True)
            alas_port, updater_port = free_port(), free_port()
            while updater_port == alas_port:
                updater_port = free_port()
            (runtime / ".gyre_runtime.conf").write_text(
                f"ALAS_ROOT={host_alias}\nGYRE_LANG=en\nGYRE_UPDATE_HOST=127.0.0.1\n"
                f"GYRE_UPDATE_PORT={updater_port}\nALAS_WEBUI_PORT={alas_port}\n", encoding="utf-8"
            )
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("ALAS_", "GYRE_"))}
            worker_pid_file = runtime / ".test_worker.pid"
            env.update(TEST_ALAS_PORT=str(alas_port), TEST_WORKER_PID_FILE=str(worker_pid_file),
                       GYRE_COLOR="never", PYTHONUNBUFFERED="1")
            opener = build_opener(ProxyHandler({}))

            def reachable(port, path="/"):
                try:
                    request = Request(f"http://127.0.0.1:{port}{path}",
                                      headers={"X-Alas-Gyre-Token": "launcher-test-only"})
                    with opener.open(request, timeout=0.5) as response:
                        return response.status == 200
                except OSError:
                    return False

            output_path = base / "menu.log"
            with output_path.open("wb") as output:
                menu = subprocess.Popen(["/bin/sh", str(script)], stdin=subprocess.PIPE,
                                        stdout=output, stderr=output, env=env, start_new_session=True)
                try:
                    menu.stdin.write((choice + "\n").encode())
                    menu.stdin.flush()
                    marker = "Ctrl+C exits the log viewer" if choice == "1" else "[Alas-Gyre] Started."
                    wait_for(lambda: marker in output_path.read_text(encoding="utf-8", errors="replace"))
                    wait_for(lambda: reachable(alas_port) and reachable(updater_port, "/runtime/info"))
                    for name in (".gyre_alas.pid", ".gyre_updater.pid"):
                        pid = int((runtime / name).read_text().strip())
                        self.assertNotEqual(os.getsid(pid), os.getsid(menu.pid))
                    if exit_signal is None:
                        menu.stdin.write(b"0\n")
                        menu.stdin.flush()
                    else:
                        os.killpg(menu.pid, exit_signal)
                    menu.wait(timeout=10)
                    self.assertEqual(menu.returncode, 0 if exit_signal is None else 128 + exit_signal)
                    self.assertTrue(reachable(alas_port), "ALAS stopped with launcher")
                    self.assertTrue(reachable(updater_port, "/runtime/info"), "Updater stopped with launcher")
                    subprocess.run(["/bin/sh", str(script), "__gyre_service_stop"], env=env,
                                   stdout=output, stderr=output, check=True, timeout=35)
                    self.assertFalse(reachable(alas_port), "Explicit stop did not stop ALAS")
                    self.assertFalse(reachable(updater_port, "/runtime/info"), "Explicit stop did not stop updater")
                    worker_pid = int(worker_pid_file.read_text())
                    stat = Path(f"/proc/{worker_pid}/stat")
                    if stat.exists():
                        self.assertEqual(stat.read_text().rsplit(")", 1)[1].split()[0], "Z",
                                         "ALAS child survived process-group stop")
                finally:
                    # Only signal PIDs from this test's private runtime directory.
                    for name in (".gyre_alas.pid", ".gyre_updater.pid", ".test_worker.pid"):
                        path = runtime / name
                        if path.exists():
                            try:
                                os.kill(int(path.read_text().strip()), signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                    try:
                        os.killpg(menu.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    menu.wait(timeout=5)
                    menu.stdin.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
