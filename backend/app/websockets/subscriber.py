"""Redis pub/sub subscriber for cross-worker WebSocket fan-out.

Started as an async task during FastAPI app lifespan (startup).
Pattern-subscribes to "org:*:area:*" channels. When a message arrives,
parses the area_id from the channel name and calls broadcast_to_area().
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import redis.asyncio as aioredis

from app.core.config import settings
from app.websockets.manager import manager

logger = logging.getLogger(__name__)


async def redis_subscriber_task() -> None:
    """Long-running task that subscribes to Redis and fans out messages."""
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.psubscribe("org:*:area:*")
    logger.info("Redis subscriber started, pattern: org:*:area:*")

    try:
        async for message in pubsub.listen():
            if message["type"] != "pmessage":
                continue
            try:
                channel = message["channel"]
                # channel format: "org:{org_id}:area:{area_id}"
                parts = channel.split(":")
                if len(parts) >= 4:
                    area_id = uuid.UUID(parts[3])
                    payload = json.loads(message["data"])
                    await manager.broadcast_to_area(area_id, payload)
            except Exception:
                logger.exception("Error processing Redis message")
    except asyncio.CancelledError:
        logger.info("Redis subscriber shutting down")
    finally:
        await pubsub.punsubscribe("org:*:area:*")
        await pubsub.close()
        await r.close()
