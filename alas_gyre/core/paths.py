import os
import sys


def packaged_executable_path():
    """Return the installed executable, not Nuitka's onefile extraction binary."""
    if "__compiled__" in globals():
        return os.path.abspath(sys.argv[0])
    if getattr(sys, "frozen", False):
        return sys.executable
    return None


def app_base_dir():
    """Return the directory that contains user config and external resources."""
    executable = packaged_executable_path()
    if executable:
        return os.path.dirname(executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bundled_base_dir():
    """Return the directory that contains bundled package resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    if getattr(sys, "frozen", False):
        return app_base_dir()
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resource_path(relative_path):
    return os.path.join(bundled_base_dir(), relative_path)


def config_path():
    return os.path.join(app_base_dir(), "config.json")


def overlay_runtime_path():
    """Return the persistent Overlay Runtime directory used by generated launchers."""
    return os.path.join(app_base_dir(), "overlay")


def overlay_bundled_path():
    """Return the bundled Overlay Runtime source directory."""
    return os.path.join(bundled_base_dir(), "overlay")


def asset_path(*parts):
    relative_path = os.path.join("ui", "assets", *parts)
    candidates = [
        os.path.join(app_base_dir(), relative_path),
        os.path.join(bundled_base_dir(), relative_path),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return candidates[0]
