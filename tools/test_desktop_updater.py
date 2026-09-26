"""Desktop update regressions using temporary files, without launching the app."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alas_gyre.core import paths
from alas_gyre.services import updater


class PackagedPathsTests(unittest.TestCase):
    def test_nuitka_onefile_updates_outer_executable_and_keeps_config(self):
        outer = os.path.abspath("installed/renamed.exe")
        extracted = os.path.abspath("temporary/main.exe")
        module = os.path.abspath("temporary/alas_gyre/core/paths.py")
        with patch.object(paths, "__compiled__", object(), create=True), \
                patch.object(sys, "frozen", False, create=True), \
                patch.object(sys, "argv", [outer]), \
                patch.object(sys, "executable", extracted), \
                patch.object(paths, "__file__", module):
            self.assertEqual(updater.get_current_exe_path(), outer)
            self.assertEqual(paths.config_path(), os.path.join(os.path.dirname(outer), "config.json"))
            self.assertEqual(paths.bundled_base_dir(), os.path.dirname(extracted))
            self.assertEqual(paths.resource_path("ui/style.qss"),
                             os.path.join(os.path.dirname(extracted), "ui/style.qss"))

    def test_pyinstaller_paths(self):
        exe = os.path.abspath("installed/app.exe")
        bundle = os.path.abspath("temporary/_MEI123")
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", exe), \
                patch.object(sys, "_MEIPASS", bundle, create=True):
            self.assertEqual(updater.get_current_exe_path(), exe)
            self.assertEqual(paths.app_base_dir(), os.path.dirname(exe))
            self.assertEqual(paths.bundled_base_dir(), bundle)

    def test_source_cannot_replace_python_interpreter(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertIsNone(updater.get_current_exe_path())


@unittest.skipUnless(sys.platform == "win32", "Windows helper integration")
class WindowsHelperTests(unittest.TestCase):
    def test_background_wait_replace_retry_and_restart_in_unicode_directory(self):
        with tempfile.TemporaryDirectory(prefix="gyre-update-") as temp:
            base = Path(temp) / "中文 空格 %PATH% !"
            base.mkdir()
            target = base / "client.exe"
            target.write_bytes(b"old file")
            # A Windows utility that exits without arguments stands in for the app.
            content = (Path(os.environ["SystemRoot"]) / "System32/where.exe").read_bytes()
            response = Mock(headers={})
            response.iter_content.return_value = [content]
            finish = Mock()
            parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            helper = None
            try:
                with patch.object(updater, "get_current_exe_path", return_value=str(target)), \
                        patch.object(updater, "http_get", return_value=response), \
                        patch.object(updater.os, "getpid", return_value=parent.pid), \
                        patch.object(updater.subprocess, "Popen") as launch, \
                        patch.object(updater.os, "_exit") as exit_process:
                    updater.do_update("https://example.invalid/client.exe", None, finish,
                                      expected_sha256=hashlib.sha256(content).hexdigest())
                    launch_args, launch_kwargs = launch.call_args
                    self.assertTrue(finish.call_args.args[0])
                    exit_process.assert_called_once_with(0)
                launch_kwargs["stdout"] = subprocess.PIPE
                launch_kwargs["stderr"] = subprocess.STDOUT
                helper = subprocess.Popen(*launch_args, **launch_kwargs)
                time.sleep(1.5)
                self.assertIsNone(helper.poll(), "helper must wait for the old process")
                self.assertEqual(target.read_bytes(), b"old file")
                # The running onefile bootstrap or antivirus may keep the file locked.
                with target.open("rb"):
                    parent.terminate()
                    parent.wait(timeout=5)
                    time.sleep(2.5)
                    self.assertIsNone(helper.poll(), "helper must retry while target is locked")
                    self.assertEqual(target.read_bytes(), b"old file")
                result = helper.wait(timeout=20)
                output = helper.communicate(timeout=5)[0].decode("utf-8", errors="replace")
                time.sleep(2)  # Allow the harmless restarted utility to release its image.
                self.assertEqual(result, 0, output)
                self.assertEqual(target.read_bytes(), content)
                # The next application startup owns helper cleanup.
                with patch.object(updater, "get_current_exe_path", return_value=str(target)):
                    updater.cleanup_old_exe()
                self.assertFalse((base / "update.bat").exists())
            finally:
                for process in (helper, parent):
                    if process is not None and process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
