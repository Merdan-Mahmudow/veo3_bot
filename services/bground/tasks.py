from __future__ import annotations
from typing import Any, Dict
import asyncio
from celery import states
from celery.exceptions import Ignore

from services.bground import CeleryManager
from services.veo import VeoService
from services.kie import GenerateRequests
from services.storage import YandexS3Storage
from services.redis import RedisClient
from services.notifier import BotNotifier
from api.crud.user import UserService

celery_app = CeleryManager()

def _make_service() -> VeoService:
    # Собираем все зависимости так же, как это делает FastAPI DI
    return VeoService(
        users=UserService(),
        gen=GenerateRequests(),
        storage=YandexS3Storage(),
        redis=RedisClient(),
        notifier=BotNotifier(),
    )

@celery_app.celery_app.task(bind=True, max_retries=3, name="veo.postprocess_callback")
def postprocess_callback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Обрабатывает колбэк от KIE в фоне:
      - парсит результат,
      - скачивает видео,
      - грузит в S3,
      - шлёт нотификацию боту,
      - чистит Redis по task_id.
    """
    svc = _make_service()

    async def _run():
        # Можно давать «реальный» прогресс через update_state
        self.update_state(state=states.STARTED, meta={"step": "parse_payload"})
        result = await svc.handle_callback(payload)

        # Для наглядности обновим финальное состояние
        self.update_state(state=states.SUCCESS, meta={
            "task_id": result.get("task_id"),
            "status": result.get("status"),
            "result_url": result.get("result_url"),
            "source_url": result.get("source_url"),
            "fallback": result.get("fallback"),
        })
        return result

    try:
        return asyncio.run(_run())
    except Exception as e:
        # Обновим мету и пометим как FAIL, без бесконечных ретраев
        self.update_state(state=states.FAILURE, meta={"error": str(e)})
        raise  # пусть воркер логирует трейс
