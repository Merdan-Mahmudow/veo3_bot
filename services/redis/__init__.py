from __future__ import annotations
import json, time
import redis.asyncio as aioredis
from typing import Any, Optional
from config import ENV

class RedisClient:
    def __init__(self):
        self.env = ENV()
        self.url = self.env.redis_url
        self.redis = aioredis.from_url(self.url, decode_responses=True)

    async def set_task(self, task_id: str, chat_id: str, meta: Optional[dict] = None, ttl: int = 172800) -> None:
        payload = {
            "chat_id": chat_id,
            "meta": meta or {},
            "created_at": int(time.time()),
        }
        await self.redis.set(f"veo:task:{task_id}", json.dumps(payload), ex=ttl)

    async def get_task(self, task_id: str) -> Optional[dict[str, Any]]:
        raw = await self.redis.get(f"veo:task:{task_id}")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def del_task(self, task_id: str) -> int:
        return await self.redis.delete(f"veo:task:{task_id}")

    async def set_prompt(self, key: str, value: Any, ttl: int = 3600) -> None:
        await self.redis.set(key, str(value), ex=ttl)

    async def get_prompt(self, key: str) -> Optional[Any]:
        raw = await self.redis.get(key)
        if not raw:
            return None
        try:
            return str(raw)
        except Exception:
            return None
    
    async def set_del_msg(self, key: str, value: Any, ttl: int = 3600) -> None:
        await self.redis.set(key, str(value), ex=ttl)

    async def get_del_msg(self, key: str) -> Optional[Any]:
        raw = await self.redis.get(key)
        if not raw:
            return None
        try:
            await self.redis.delete(key)
            return str(raw)
        except Exception:
            return None
