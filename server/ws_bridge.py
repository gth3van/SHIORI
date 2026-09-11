"""
server/ws_bridge.py
-------------------
Thin async bridge so main.py can broadcast events to all connected browsers.

Usage (from main.py):
    from server.ws_bridge import broadcast
    await broadcast({"type": "speaking", "duration_ms": 2400})
    await broadcast({"type": "idle"})
    await broadcast({"type": "emotion", "name": "happy"})
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

# Set of active WebSocket connections, managed by server/app.py
_clients: set = set()


def _register(ws) -> None:
    """Called by app.py when a client connects."""
    _clients.add(ws)


def _unregister(ws) -> None:
    """Called by app.py when a client disconnects."""
    _clients.discard(ws)


async def broadcast(event: dict[str, Any]) -> None:
    """Send a JSON event to all connected browser clients.

    Silently drops connections that have already closed.
    """
    if not _clients:
        return
    message = json.dumps(event)
    dead: set = set()
    for ws in _clients:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _clients.discard(ws)
