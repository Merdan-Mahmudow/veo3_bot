from __future__ import annotations
from typing import Optional, TypedDict
import asyncio
import httpx
import logging
from dataclasses import dataclass


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
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://0.0.0.0:8000",
        timeout: float = 5.0,
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

    async def register_user(self, chat_id: int, nickname: Optional[str] = None) -> RegisterResult:
        """
        Регистрирует пользователя.
        Возвращает {"created": True} или {"created": False, "reason": "exists"}.
        """
        payload = {"chat_id": str(chat_id), "nickname": (nickname or f"user_{chat_id}")[:64]}
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
    

    async def generate_text(self, chat_id: int, prompt: str) -> dict:
        payload = {"chat_id": chat_id, "prompt": prompt}
        resp = await self._request("POST", "/bot/veo/generate/text", json=payload, expected=(200,))
        return resp.json()


    async def generate_photo(self, chat_id: int, prompt: str, file_bytes: bytes, filename: str = "image.jpg") -> dict:
        client = await self._ensure_client()
        files = {"image": (filename, file_bytes)}
        data = {"chat_id": str(chat_id), "prompt": prompt}  # Form-поля
        resp = await client.post("/bot/veo/generate/photo", data=data, files=files)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 400:
            raise RuntimeError(resp.json().get("detail", "bad request"))
        if resp.status_code == 401:
            raise PermissionError("Invalid X-Api-Key for backend")
        raise RuntimeError(f"Unexpected {resp.status_code}: {resp.text}")