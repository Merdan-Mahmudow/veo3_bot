from __future__ import annotations
from datetime import datetime
import json
from typing import List, Optional, TypedDict
import asyncio
import httpx
import logging
from dataclasses import dataclass

from config import ENV


# --- Типы результатов ---

class RegisterResult(TypedDict, total=False):
    created: bool
    reason: str  # "exists" и т.п.

class BackendError(Exception): ...
class BackendAuthError(BackendError): ...
class BackendNotFound(BackendError): ...
class BackendServerError(BackendError): ...
class BackendUnexpectedError(BackendError): ...


# --- Конфиг ретраев ---

@dataclass
class RetryConfig:
    retries: int = 2  # повторов помимо первой попытки
    backoff_base: float = 0.2  # секунды
    backoff_factor: float = 2.0
    retry_for_status: tuple[int, ...] = (502, 503, 504)  # временные ошибки


class BackendAPI:
    """
    Клиент для api.skyrodev.ru (бот-интерфейс).
    Авторизация: заголовок X-Api-Key (service-to-service).
    """
    env = ENV()
    def __init__(
        self,
        api_key: str,
        base_url: str = env.BASE_URL,
        timeout: float = 120.0,
        retry: RetryConfig | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.retry = retry or RetryConfig()
        self._client: Optional[httpx.AsyncClient] = None

    # ---------- infra ----------

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"X-Api-Key": self.api_key},
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "BackendAPI":
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    # ---------- helpers ----------

    @staticmethod
    def _detail_from_response(resp: httpx.Response) -> str:
        try:
            data = resp.json()
            return data.get("detail") or data.get("error") or ""
        except Exception:
            return resp.text or ""

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> httpx.Response:
        client = await self._ensure_client()
        attempt = 0
        while True:
            try:
                resp = await client.request(method, url, json=json)
            except httpx.HTTPError as e:
                # сетевые ошибки ретраим
                if attempt < self.retry.retries:
                    delay = self.retry.backoff_base * (self.retry.backoff_factor ** attempt)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                logging.exception("HTTP error on %s %s: %s", method, url, e)
                raise BackendError(f"Network error: {e}") from e

            # успешные коды
            if resp.status_code in expected:
                return resp

            # мэппинг ошибок
            if resp.status_code == 401:
                raise BackendAuthError("Invalid X-Api-Key for backend")
            if resp.status_code == 404:
                raise BackendNotFound("Resource not found")

            if resp.status_code in self.retry.retry_for_status and attempt < self.retry.retries:
                delay = self.retry.backoff_base * (self.retry.backoff_factor ** attempt)
                await asyncio.sleep(delay)
                attempt += 1
                continue

            if 500 <= resp.status_code < 600:
                raise BackendServerError(f"Server error {resp.status_code}: {self._detail_from_response(resp)}")

            # всё остальное — unexpected/biz
            raise BackendUnexpectedError(
                f"Unexpected {resp.status_code}: {self._detail_from_response(resp)}"
            )

    # ---------- публичные методы для бота ----------

    async def check_user_exist(self, chat_id: int) -> bool:
        """
        True — пользователь есть, False — нет.
        """
        try:
            await self._request("GET", f"/users/{chat_id}", expected=(200,))
            return True
        except BackendNotFound:
            return False

    async def register_user(self, chat_id: int, nickname: Optional[str] = None, referral_code: Optional[str] = None) -> RegisterResult:
        """
        Регистрирует пользователя.
        Возвращает {"created": True} или {"created": False, "reason": "exists"}.
        """
        payload = {"chat_id": str(chat_id), "nickname": (nickname or f"user_{chat_id}")[:64]}
        if referral_code:
            payload["referral_code"] = referral_code

        try:
            await self._request("POST", "/users/register", json=payload, expected=(200, 201))
            return {"created": True}
        except BackendUnexpectedError as e:
            msg = str(e).lower()
            if "exists" in msg or "already exists" in msg:
                return {"created": False, "reason": "exists"}
            raise
        except BackendServerError:
            # на случай, если бэкенд отвечает 409 при дубле — считаем exists
            return {"created": False, "reason": "exists"}

    async def create_user_referral_link(self, chat_id: int) -> dict:
        """
        Создает персональную реферальную ссылку для пользователя.
        """
        payload = {"chat_id": str(chat_id)}
        resp = await self._request("POST", "/referrals/create-user-link", json=payload, expected=(200, 201))
        return resp.json()

    async def create_partner_link(self, user_id: str, percent: int, comment: str) -> dict:
        """
        Создает партнерскую ссылку для указанного пользователя.
        """
        payload = {
            "owner_id": user_id,
            "percent": percent,
            "comment": comment
        }
        resp = await self._request("POST", "/referrals/create-partner-link", json=payload, expected=(200, 201))
        return resp.json()

    async def get_payout_requests(self, status: str) -> list[dict]:
        """
        Получает список заявок на выплату по статусу.
        """
        resp = await self._request("GET", f"/payouts?status={status}", expected=(200,))
        return resp.json()

    async def approve_payout_request(self, request_id: str) -> None:
        """
        Одобряет заявку на выплату.
        """
        await self._request("PATCH", f"/payouts/{request_id}/approve", expected=(200, 204))

    async def reject_payout_request(self, request_id: str) -> None:
        """
        Отклоняет заявку на выплату.
        """
        await self._request("PATCH", f"/payouts/{request_id}/reject", expected=(200, 204))

    async def get_partner_dashboard(self, chat_id: int) -> dict:
        """
        Получает данные для дашборда партнера.
        """
        resp = await self._request("GET", f"/partners/dashboard/{chat_id}", expected=(200,))
        return resp.json()

    async def get_partner_links(self, chat_id: int) -> list[dict]:
        """
        Получает список партнерских ссылок для пользователя.
        """
        resp = await self._request("GET", f"/partners/links/{chat_id}", expected=(200,))
        return resp.json()

    async def get_payout_history(self, chat_id: int) -> list[dict]:
        """
        Получает историю заявок на выплату для партнера.
        """
        resp = await self._request("GET", f"/payouts/history/{chat_id}", expected=(200,))
        return resp.json()

    async def request_payout(self, chat_id: int, amount_minor: int, requisites: dict) -> dict:
        """
        Создает заявку на выплату от имени партнера.
        """
        payload = {
            "chat_id": str(chat_id),
            "amount_minor": amount_minor,
            "requisites_json": requisites
        }
        resp = await self._request("POST", "/payouts/request", json=payload, expected=(201,))
        return resp.json()

    async def get_my_referral_info(self, chat_id: int) -> dict:
        """
        Получает информацию о реферальной ссылке и статистике пользователя.
        """
        resp = await self._request("GET", f"/users/my-referral-info/{chat_id}", expected=(200,))
        return resp.json()

    async def ensure_user(self, chat_id: int, nickname: Optional[str] = None) -> RegisterResult:
        """
        Сначала проверит, если нет — зарегистрирует.
        """
        if await self.check_user_exist(chat_id):
            return {"created": False, "reason": "exists"}
        return await self.register_user(chat_id, nickname)

    async def get_user(self, chat_id: int) -> dict:
        """
        Возвращает UserRead как dict (id, nickname, chat_id, coins, token?).
        """
        resp = await self._request("GET", f"/users/{chat_id}", expected=(200,))
        return resp.json()

    async def find_user(self, identifier: str) -> Optional[dict]:
        """
        Ищет пользователя по chat_id или nickname.
        """
        try:
            resp = await self._request("GET", f"/users/find/{identifier}", expected=(200,))
            return resp.json()
        except BackendNotFound:
            return None

    async def get_user_by_id(self, user_id: str) -> Optional[dict]:
        """
        Получает пользователя по его UUID.
        """
        try:
            resp = await self._request("GET", f"/users/id/{user_id}", expected=(200,))
            return resp.json()
        except BackendNotFound:
            return None

    async def set_user_role(self, user_id: str, role: str) -> None:
        """
        Устанавливает роль для пользователя.
        """
        payload = {"role": role}
        await self._request("PATCH", f"/users/{user_id}/role", json=payload, expected=(200, 204))

    async def get_coins(self, chat_id: int) -> int:
        """
        Возвращает текущие coins.
        """
        resp = await self._request("GET", f"/users/{chat_id}/coins", expected=(200,))
        data = resp.json()
        return int(data.get("coins", 0))

    async def minus_coin(self, chat_id: int) -> int:
        """
        Декремент монет на 1. Возвращает новое значение coins.
        Может бросить BackendUnexpectedError при бизнес-ошибке (например, coins < 0).
        """
        payload = {"chat_id": str(chat_id)}
        resp = await self._request("POST", "/users/coins/minus", json=payload, expected=(200,))
        return int(resp.json().get("coins", 0))

    async def plus_coins(self, chat_id: int, count: int) -> int:
        """
        Инкремент монет на count. Возвращает новое значение coins.
        """
        if count <= 0:
            raise ValueError("count must be > 0")
        payload = {"chat_id": str(chat_id), "count": int(count)}
        resp = await self._request("POST", "/users/coins/plus", json=payload, expected=(200,))
        return int(resp.json().get("coins", 0))
    

    async def generate_text(self, chat_id: int, prompt: str, aspect_ratio: str = "16:9") -> dict:
        payload = {"chat_id": chat_id, "prompt": prompt, "aspect_ratio": aspect_ratio}
        resp = await self._request("POST", "/bot/veo/generate/text", json=payload, expected=(200,))
        return resp.json()


    async def generate_photo(
        self,
        chat_id: int,
        prompt: str,
        file_bytes: bytes | None = None,
        image_url: str | None = None,
        filename: str = "image.jpg",
        aspect_ratio: str = "16:9",
    ) -> dict:
        client = await self._ensure_client()

        if image_url:
            # если URL уже есть, отправляем JSON без файлов
            payload = {"chat_id": str(chat_id), "prompt": prompt, "image_url": image_url, "aspect_ratio": aspect_ratio}
            print(payload)
            resp = await self._request("POST", "/bot/veo/generate/photo", json=payload, expected=(200, 400, 401))
        else:
            # иначе отправляем multipart с байтами изображения
            files = {"image": (filename, file_bytes)}
            data = {"chat_id": str(chat_id), "prompt": prompt, "aspect_ratio": aspect_ratio}
            resp = await self._request("POST", "/bot/veo/generate/photo", json=data, files=files, expected=(200, 400, 401))

        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 400:
            raise RuntimeError(resp.json().get("detail", "bad request"))
        if resp.status_code == 401:
            raise PermissionError("Invalid X-Api-Key for backend")
        raise RuntimeError(f"Unexpected {resp.status_code}: {resp.text}")

    async def suggest_prompt(
        self,
        chat_id: str,
        brief: str,
        clarifications: Optional[List[str]] = None,
        attempt: int = 1,
        previous_prompt: Optional[str] = None,
        # aspect_ratio: str = "16:9",
        image_url: Optional[str] = None,
    ) -> str:
        payload = {
            "chat_id": chat_id,
            "brief": brief,
            "clarifications": clarifications,
            "attempt": attempt,
            "previous_prompt": previous_prompt,
            # "aspect_ratio": aspect_ratio,
            "image_url": image_url,
        }
        resp = await self._request("POST", f"{self.base_url}/prompt/suggest", json=payload)
        data = resp.json()
        data_prompt = data["prompt"]
        print(data_prompt)
        return data["prompt"]

    async def rate_task(self, task_id: str, rating: int) -> None:
        await self._request("PATCH", f"/tasks/{task_id}/rating?rating={rating}", expected=(200,204))

    async def save_task(
        self,
        task_id: str,
        chat_id: str,
        raw: dict,
        *,
        is_video: bool = False,
        rating: int | None = 0,
    ) -> None:
        """
        Сохраняет запись о задаче в БД бэкенда. Словарь raw будет сериализован в JSON.
        """
        payload = {
            "task_id": task_id,
            "chat_id": chat_id,
            "raw": json.dumps(raw),
            "is_video": is_video,
            "rating": rating,
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        # POST /tasks вернёт 201 Created, тело нам не нужно
        await self._request("POST", "/tasks/", json=payload, expected=(201,))

    async def get_task(self, task_id: str) -> dict:
        """
        Получает запись о задаче из БД по её task_id. Возвращает словарь вида:
        {
           "id": "...",
           "task_id": "...",
           "chat_id": "...",
           "raw": "<json string>",
           "is_video": true,
           "rating": 0,
           "created_at": "YYYY‑MM‑DD HH:MM:SS"
        }
        """
        resp = await self._request("GET", f"/tasks/{task_id}", expected=(200,))
        return resp.json()
    
    async def get_sbp_url(self, amount: str, desc: str) -> Optional[str]:
        payload = {
            "amount": amount,
            "desc": desc
        }
        resp = await self._request("POST", "/pay/sbp/create", json=payload, expected=(200,))

        return resp.text