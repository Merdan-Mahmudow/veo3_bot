from __future__ import annotations
from typing import Optional
import aiohttp

class BotNotifier:
    """
    Бэк дергает эндпоинт бота.
    Если URL не задан — тихо пропускаем.
    """
    def __init__(self):
        self.url = "http://0.0.0.0:8000/internal/veo/video-ready"

    async def video_ready(
        self,
        *,
        chat_id: str,
        task_id: str,
        result_url: str,
        source_url: Optional[str] = None,
        fallback: bool = False,
    ) -> None:
        if not self.url:
            return
        headers = {"Content-Type": "application/json"}
        payload = {
            "chat_id": chat_id,
            "task_id": task_id,
            "result_url": result_url,
            "source_url": source_url,
            "fallback": fallback,
        }
        async with aiohttp.ClientSession() as s:
            async with s.post(self.url, json=payload, headers=headers) as r:
                await r.read()
