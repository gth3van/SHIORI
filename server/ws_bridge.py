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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

# Set of active WebSocket connections, managed by server/app.py
_clients: set[WebSocket] = set()
_server_loop: asyncio.AbstractEventLoop | None = None


def set_server_loop(loop: asyncio.AbstractEventLoop | None) -> None:
    """Publish the loop that owns the WebSockets during the server lifespan."""
    global _server_loop
    _server_loop = loop


def _register(ws: WebSocket) -> None:
    """Called by app.py when a client connects."""
    _clients.add(ws)


def _unregister(ws: WebSocket) -> None:
    """Called by app.py when a client disconnects."""
    _clients.discard(ws)


async def broadcast(event: dict[str, Any]) -> None:
    """Send an event on the loop that owns the connected browser clients."""
    loop = _server_loop
    if loop is None or not loop.is_running():
        return
    message = json.dumps(event)
    if asyncio.get_running_loop() is loop:
        await _broadcast(message)
        return

    delivery = _broadcast(message)
    try:
        pending = asyncio.run_coroutine_threadsafe(delivery, loop)
    except RuntimeError:
        # The server may have closed its loop since is_running().
        delivery.close()
        return
    await asyncio.wrap_future(pending)


async def _broadcast(message: str) -> None:
    for ws in tuple(_clients):
        try:
            await ws.send_text(message)
        except Exception:
            _unregister(ws)
