import json
import secrets


def save_config(config, config_path):
    if not config_path:
        return
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def ensure_api_token(config, config_path=""):
    token = str(config.get("api_token", "")).strip()
    if token:
        return token

    token = secrets.token_urlsafe(32)
    config["api_token"] = token
    save_config(config, config_path)
    return token
