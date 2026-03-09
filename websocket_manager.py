"""WebSocket connection manager for real-time broadcasting."""

import asyncio
import json
from typing import Set

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events to all clients."""

    def __init__(self) -> None:
        self._connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        try:
            await websocket.close()
        except Exception:
            pass

    async def broadcast(self, event: str, data: dict) -> None:
        """Broadcast an event with payload to all connected clients."""
        message = json.dumps({"event": event, "data": data})
        async with self._lock:
            dead = set()
            for ws in self._connections:
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.add(ws)
            for ws in dead:
                self._connections.discard(ws)
