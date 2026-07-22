VALID_STATUSES = {"idle", "running", "error", "update", "disconnected", "queued", "scanning"}


def normalize_status(status):
    """归一化状态字符串，未知或无效值返回 idle。

    对输入做 strip + lower 处理，兼容大小写和空白差异。
    """
    if status is None:
        return "idle"
    normalized = str(status).strip().lower()
    return normalized if normalized in VALID_STATUSES else "idle"

