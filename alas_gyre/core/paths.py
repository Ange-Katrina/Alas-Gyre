import os
import sys


def app_base_dir():
    """Return the directory that contains user config and external resources."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def bundled_base_dir():
    """Return the directory that contains bundled package resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return app_base_dir()


def resource_path(relative_path):
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(app_base_dir(), relative_path)


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
