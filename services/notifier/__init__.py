from __future__ import annotations
from typing import Optional
import aiohttp

from config import ENV

class BotNotifier:
    """
    Бэк дергает эндпоинт бота.
    Если URL не задан — тихо пропускаем.
    """
    def __init__(self):
        self.env = ENV()
        self.url = f"{self.env.BASE_URL}/internal/veo/video-ready"

    async def video_ready(
        self,
        *,
        chat_id: str,
        task_id: str,
        result_url: Optional[str] = None,
        source_url: Optional[str] = None,
        fallback: bool = False,
    ) -> None:
        print({
            "chat_id": chat_id,
            "task_id": task_id,
            "result_url": result_url,
            "source_url": source_url,
            "fallback": fallback,
        })
        if not self.url:
            return
        headers = {"Content-Type": "application/json"}
        payload = {
            "chat_id": str(chat_id),
            "task_id": task_id,
            "result_url": result_url,
            "source_url": source_url,
            "fallback": fallback,
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(self.url, json=payload, headers=headers) as r:
                await r.read()
