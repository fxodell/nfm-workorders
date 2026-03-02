"""WebSocket endpoint for real-time updates."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.core.observability import WS_CONNECTIONS
from app.core.security import decode_ws_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages active WebSocket connections grouped by org_id."""

    def __init__(self) -> None:
        # org_id -> set of (user_id, websocket)
        self._connections: dict[str, set[tuple[str, WebSocket]]] = defaultdict(set)

    async def connect(
        self, websocket: WebSocket, user_id: str, org_id: str,
    ) -> None:
        """Accept a WebSocket connection and register it."""
        await websocket.accept()
        self._connections[org_id].add((user_id, websocket))
        WS_CONNECTIONS.inc()
        logger.info("WS connected: user=%s org=%s", user_id, org_id)

    def disconnect(self, websocket: WebSocket, user_id: str, org_id: str) -> None:
        """Remove a WebSocket connection."""
        self._connections[org_id].discard((user_id, websocket))
        if not self._connections[org_id]:
            del self._connections[org_id]
        WS_CONNECTIONS.dec()
        logger.info("WS disconnected: user=%s org=%s", user_id, org_id)

    async def broadcast_to_org(self, org_id: str, message: dict[str, Any]) -> None:
        """Broadcast a message to all connections in an org."""
        connections = self._connections.get(org_id, set())
        payload = json.dumps(message, default=str)
        disconnected = []
        for user_id, ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append((user_id, ws))

        for user_id, ws in disconnected:
            self.disconnect(ws, user_id, org_id)

    async def send_to_user(
        self, org_id: str, user_id: str, message: dict[str, Any],
    ) -> None:
        """Send a message to a specific user's connections."""
        connections = self._connections.get(org_id, set())
        payload = json.dumps(message, default=str)
        for uid, ws in connections:
            if uid == user_id:
                try:
                    await ws.send_text(payload)
                except Exception:
                    pass

    @property
    def active_count(self) -> int:
        """Total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())


manager = ConnectionManager()


# ── WS /ws ─────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """WebSocket endpoint. Validate short-lived WS token, then maintain connection."""
    # Validate token
    try:
        payload = decode_ws_token(token)
    except JWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    user_id = payload.get("sub")
    org_id = payload.get("org_id")

    if not user_id or not org_id:
        await websocket.close(code=4001, reason="Invalid token payload")
        return

    await manager.connect(websocket, user_id, org_id)

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=60.0
                )
            except asyncio.TimeoutError:
                # Send ping for heartbeat
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            # Handle client messages
            try:
                message = json.loads(data)
                msg_type = message.get("type")

                if msg_type == "pong":
                    # Heartbeat acknowledged
                    continue
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                else:
                    # Echo acknowledgment for other messages
                    await websocket.send_json({
                        "type": "ack",
                        "original_type": msg_type,
                    })
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket error for user=%s", user_id)
    finally:
        manager.disconnect(websocket, user_id, org_id)
