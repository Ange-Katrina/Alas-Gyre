TOKEN_HEADER = "X-Alas-Gyre-Token"


def api_base_url(config):
    ip = str(config.get("ip", "127.0.0.1")).strip() or "127.0.0.1"
    port = str(config.get("port", "22267")).strip() or "22267"
    return f"http://{ip}:{port}"


def api_headers(config):
    token = str(config.get("api_token", "")).strip()
    if not token:
        return {}
    return {TOKEN_HEADER: token}
