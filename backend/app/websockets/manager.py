"""WebSocket connection manager for real-time fan-out."""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """In-process WebSocket registry.

    Tracks connections by area_id so broadcast_to_area() only sends
    to clients subscribed to that area. Each Uvicorn worker has its
    own ConnectionManager instance. Redis pub/sub bridges across workers.
    """

    def __init__(self) -> None:
        # area_id -> set of WebSocket connections
        self._area_connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        # ws -> (user_id, org_id, set of area_ids)
        self._ws_meta: dict[WebSocket, tuple[uuid.UUID, uuid.UUID, set[uuid.UUID]]] = {}

    async def connect(
        self, ws: WebSocket, user_id: uuid.UUID, org_id: uuid.UUID, area_ids: list[uuid.UUID]
    ) -> None:
        await ws.accept()
        area_set = set(area_ids)
        self._ws_meta[ws] = (user_id, org_id, area_set)
        for area_id in area_set:
            self._area_connections[area_id].add(ws)
        logger.info("WS connected: user=%s areas=%s", user_id, [str(a) for a in area_ids])

    async def disconnect(self, ws: WebSocket) -> None:
        meta = self._ws_meta.pop(ws, None)
        if meta:
            user_id, org_id, area_ids = meta
            for area_id in area_ids:
                self._area_connections[area_id].discard(ws)
                if not self._area_connections[area_id]:
                    del self._area_connections[area_id]
            logger.info("WS disconnected: user=%s", user_id)

    async def broadcast_to_area(self, area_id: uuid.UUID, payload: dict) -> None:
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        for ws in self._area_connections.get(area_id, set()):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def send_personal(self, user_id: uuid.UUID, payload: dict) -> None:
        message = json.dumps(payload, default=str)
        for ws, (uid, _, _) in list(self._ws_meta.items()):
            if uid == user_id:
                try:
                    if ws.client_state == WebSocketState.CONNECTED:
                        await ws.send_text(message)
                except Exception:
                    await self.disconnect(ws)

    @property
    def active_connections_count(self) -> int:
        return len(self._ws_meta)


manager = ConnectionManager()
