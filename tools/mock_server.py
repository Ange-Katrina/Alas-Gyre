"""Small local FastAPI mock server for Alas-Gyre UI development.

Run from the repository root:
    python tools/mock_server.py

It exposes the /api/gyre/* endpoints expected by the desktop client.
"""

import uvicorn
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/gyre/health")
def health():
    return {"ok": True, "overlay": True, "configs": ["alas", "test_config"], "default": "alas"}


@app.get("/api/gyre/status_all")
def status_all():
    return {
        "statuses": {"alas": "running", "test_config": "idle"},
        "tasks": {"alas": "Daily mission 12-4 (75%)", "test_config": ""},
    }


@app.get("/api/gyre/configs")
def configs():
    return {"configs": ["alas", "test_config"], "default": "alas"}


@app.get("/api/gyre/status")
def status(config: str = "alas"):
    if config == "alas":
        return {"status": "running", "task": "Daily mission 12-4 (75%)"}
    return {"status": "idle", "task": ""}


@app.post("/api/gyre/start")
def start(config: str = "alas"):
    return {"config": config, "status": "running", "message": "started"}


@app.post("/api/gyre/stop")
def stop(config: str = "alas"):
    return {"config": config, "status": "idle", "message": "stopped"}


if __name__ == "__main__":
    print("Starting Alas-Gyre mock server on http://127.0.0.1:22267")
    uvicorn.run(app, host="127.0.0.1", port=22267)
