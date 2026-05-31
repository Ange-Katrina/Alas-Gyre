_current_version = "v1.2.0"


def set_current_version(version):
    global _current_version
    _current_version = str(version or "").strip() or _current_version


def get_current_version():
    return _current_version


