"""Windows launcher helpers tested with temporary dummy commands only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "resources/start_gyre_alas.bat.template"


def powershell_command(line):
    return line.split('-Command "', 1)[1].rsplit('" <nul', 1)[0]


@unittest.skipUnless(sys.platform == "win32", "Windows runner encoding and process identity")
class WindowsLauncherTests(unittest.TestCase):
    def test_utf8_runners_preserve_chinese_paths(self):
        lines = TEMPLATE.read_text(encoding="utf-8").splitlines()
        with tempfile.TemporaryDirectory(prefix="gyre-runner-") as temp:
            base = Path(temp) / "中文目录 space"
            base.mkdir()
            fake_launcher = base / "dummy.bat"
            fake_launcher.write_text("@echo off\necho 中文成功\n", encoding="utf-8", newline="\r\n")
            fake_updater = base / "dummy.py"
            fake_updater.write_text("print('中文成功')\n", encoding="utf-8")
            env = dict(os.environ, SCRIPT_PATH=str(fake_launcher), GYRE_RUNTIME=str(base),
                       ALAS_RUNNER=str(base / "alas_runner.bat"), UPDATER_RUNNER=str(base / "updater_runner.bat"),
                       LOG_FILE=str(base / "alas.log"), UPDATER_LOG_FILE=str(base / "updater.log"),
                       GYRE_PYTHON=sys.executable, UPDATER_SCRIPT=str(fake_updater), ALAS_GYRE_API_TOKEN="test-only",
                       GYRE_UPDATE_HOST="127.0.0.1", GYRE_UPDATE_PORT="1", GYRE_LOG_MAX_BYTES="1000",
                       GYRE_LOG_BACKUP_COUNT="1", PYTHONIOENCODING="utf-8")
            for kind, log in (("ALAS_RUNNER", "LOG_FILE"), ("UPDATER_RUNNER", "UPDATER_LOG_FILE")):
                line = next(line for line in lines if "WriteAllLines($env:" + kind in line)
                subprocess.run(["powershell", "-NoProfile", "-Command", powershell_command(line)],
                               env=env, check=True, capture_output=True, timeout=15,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run(["cmd", "/d", "/c", env[kind]], env=env, check=True,
                               capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertIn("中文成功", Path(env[log]).read_text(encoding="utf-8"))

    def test_pid_identity_rejects_wrong_path_and_invalid_pid(self):
        text = TEMPLATE.read_text(encoding="utf-8").split(":is_owned_pid\n", 1)[1]
        command = powershell_command(next(line for line in text.splitlines() if line.startswith("powershell ")))
        with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                              creationflags=subprocess.CREATE_NO_WINDOW) as process:
            try:
                for pid, path, expected in ((str(process.pid), sys.executable, 0),
                                            (str(process.pid), "not-the-gyre-runner", 1), ("bad", sys.executable, 1)):
                    env = dict(os.environ, CHECK_PID=pid, CHECK_PATH=path, CHECK_ALT_PATH="")
                    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], env=env,
                                            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                    self.assertEqual(result.returncode, expected, result.stderr)
            finally:
                process.terminate()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
