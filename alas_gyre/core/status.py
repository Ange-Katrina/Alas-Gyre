VALID_STATUSES = {"idle", "running", "error", "update", "disconnected"}


def normalize_status(status):
    return status if isinstance(status, str) and status in VALID_STATUSES else "disconnected"
