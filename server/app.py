"""
server/app.py
-------------
FastAPI app that:
  - Serves shiori.html and static assets (JS, model files)
  - Provides a WebSocket endpoint /ws for real-time Python -> browser events
  - Binds to 0.0.0.0:8080 so any device on the LAN can connect

Run standalone (for testing):
    uvicorn server.app:app --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import socket
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from server import ws_bridge

app = FastAPI(title="SHIORI Avatar Server")

_STATIC_DIR = Path(__file__).parent.parent / "static"

# Serve everything under /static/ (JS, model files, etc.)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/")
async def index():
    """Serve the main Live2D viewer page."""
    return FileResponse(str(_STATIC_DIR / "shiori.html"))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint — each browser tab gets one connection."""
    await ws.accept()
    ws_bridge._register(ws)
    try:
        while True:
            # Keep alive — browsers can also send events back if needed
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_bridge._unregister(ws)


def get_local_ip() -> str:
    """Return the machine's LAN IP address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "localhost"
