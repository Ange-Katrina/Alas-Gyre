TOKEN_HEADER = "X-Alas-Gyre-Token"
GYRE_API_PREFIX = "/api/gyre"
CONTROL_REQUEST_TIMEOUT = (3, 20)


def http_base_url(config, port_key="port", default_port="22267"):
    ip = str(config.get("ip", "127.0.0.1")).strip() or "127.0.0.1"
    port = str(config.get(port_key, default_port)).strip() or default_port
    if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
        raise ValueError("invalid_port")
    if any(char in ip for char in "/\\?#@") or any(char.isspace() for char in ip):
        raise ValueError("invalid_host")
    if ":" in ip and not ip.startswith("["):
        ip = "[" + ip + "]"
    return f"http://{ip}:{port}"


def api_base_url(config):
    return http_base_url(config)


def api_headers(config):
    token = str(config.get("api_token", "")).strip()
    if not token:
        return {}
    return {TOKEN_HEADER: token}


def gyre_api_url(config, path):
    path = "/" + str(path or "").lstrip("/")
    return f"{api_base_url(config)}{GYRE_API_PREFIX}{path}"


def api_request(method, url, **kwargs):
    import requests

    session = requests.Session()
    session.trust_env = False
    # A redirect must not forward the custom Gyre token to another host.
    kwargs.setdefault("allow_redirects", False)
    kwargs.setdefault("timeout", (3, 15))
    try:
        return session.request(method, url, **kwargs)
    finally:
        session.close()
