from __future__ import annotations
from typing import Optional, Dict, Any
import aiohttp
from sqlalchemy.ext.asyncio import AsyncSession
from api.crud.user.schema import CoinMinus, CoinPlus
from api.crud.user import UserService, UserNotFound, BusinessRuleError
from services.notifier import BotNotifier
from services.redis import RedisClient
from services.storage import YandexS3Storage
from services.kie import GenerateRequests


class VeoServiceError(Exception): ...
class VeoCallbackAuthError(VeoServiceError): ...

class VeoService:
    def __init__(
        self,
        users: UserService,
        gen: GenerateRequests,
        storage: YandexS3Storage,
        redis: RedisClient,
        notifier: BotNotifier,
    ):
        self.users = users
        self.gen = gen
        self.storage = storage
        self.redis = redis
        self.notifier = notifier

    async def generate_by_text(self, chat_id: str, prompt: str, session: AsyncSession) -> dict:
        await self._charge_one_coin(chat_id, session)
        try:
            resp = await self.gen.generate_video_by_text(prompt=prompt)
            task_id = self._parse_task_id(resp)
            if not task_id:
                raise VeoServiceError(f"KIE response has no taskId: {resp}")
            await self.redis.set_task(task_id, chat_id, meta={"mode": "text", "prompt": prompt})
            return {"task_id": task_id, "raw": resp}
        except Exception:
            await self._refund_one_coin(chat_id, session)
            raise

    async def generate_by_photo(self, chat_id: str, prompt: str, image_bytes: bytes, image_ext: str, session: AsyncSession) -> dict:
        input_url = self.storage.save(image_bytes, image_ext, prefix="inputs/")
        await self._charge_one_coin(chat_id, session)
        try:
            resp = await self.gen.generate_video_by_photo(prompt=prompt, imageUrl=input_url)
            task_id = self._parse_task_id(resp)
            if not task_id:
                raise VeoServiceError(f"KIE response has no taskId: {resp}")
            await self.redis.set_task(task_id, chat_id, meta={"mode": "photo", "prompt": prompt, "input_image_url": input_url})
            return {"task_id": task_id, "raw": resp, "input_image_url": input_url}
        except Exception:
            await self._refund_one_coin(chat_id, session)
            raise

    async def get_status(self, task_id: str) -> dict:
        raw = await self.gen.get_video_info(task_id=task_id)
        data = (raw or {}).get("data") or {}
        status = self._status_from_record_info(data)
        result_url = self._first_url(data.get("response", {}))
        return {"task_id": task_id, "status": status, "source_url": result_url, "raw": raw}

    # ---------- колбэк ----------

    async def handle_callback(self, payload: dict) -> dict:

        data = (payload or {}).get("data") or {}
        task_id = data.get("taskId")
        info = data.get("info") or {}

        src_url = self._first_url(info)
        result: Dict[str, Any] = {
            "task_id": task_id,
            "status": "success" if src_url else "processing",
            "fallback": bool(data.get("fallbackFlag", False)),
        }

        # достанем владельца задачи
        owner = await self.redis.get_task(task_id) if task_id else None
        chat_id = int(owner["chat_id"]) if owner and "chat_id" in owner else None

        if src_url:
            video_bytes = await self._download(src_url)
            s3_url = self.storage.save(video_bytes, ".mp4", prefix="videos/")
            result["result_url"] = s3_url
            result["source_url"] = src_url

            # нотификация боту (если знаем chat_id)
            if chat_id:
                await self.notifier.video_ready(
                    chat_id=chat_id, task_id=task_id, result_url=s3_url, source_url=src_url, fallback=result["fallback"]
                )
                # ключ можно удалить — задача завершена
                await self.redis.del_task(task_id)

        return result

    # ---------- helpers ----------
    @staticmethod
    def _parse_task_id(resp: dict) -> Optional[str]:
        data = resp.get("data") or {}
        return data.get("taskId")

    @staticmethod
    def _status_from_record_info(data: dict) -> str:
        if data.get("successFlag") == 1:
            return "success"
        if (data.get("errorMessage") or "").strip():
            return "failed"
        return "processing"

    @staticmethod
    def _first_url(container: dict) -> Optional[str]:
        if not isinstance(container, dict):
            return None
        for key in ("resultUrls", "originUrls"):
            vals = container.get(key)
            if isinstance(vals, list) and vals:
                return vals[0]
        return None

    async def _download(self, url: str) -> bytes:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url) as r:
                r.raise_for_status()
                return await r.read()

    async def _charge_one_coin(self, chat_id: str, session: AsyncSession) -> None:
        try:
            await self.users.minus_coin(CoinMinus(chat_id=chat_id), session)
        except UserNotFound:
            raise VeoServiceError("User not found")
        except BusinessRuleError as e:
            raise VeoServiceError(str(e))

    async def _refund_one_coin(self, chat_id: str, session: AsyncSession) -> None:
        try:
            await self.users.plus_coins(CoinPlus(chat_id=chat_id, count=1), session)
        except Exception:
            pass