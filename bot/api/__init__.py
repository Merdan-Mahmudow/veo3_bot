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
    retries: int = 2
    backoff_base: float = 0.2
    backoff_factor: float = 2.0
    retry_for_status: tuple[int, ...] = (502, 503, 504)


class BackendAPI:
    """
    Клиент для API.
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
        files: dict | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> httpx.Response:
        client = await self._ensure_client()
        attempt = 0
        while True:
            try:
                if files:
                    resp = await client.request(method, url, data=json, files=files)
                else:
                    resp = await client.request(method, url, json=json)
            except httpx.HTTPError as e:
                if attempt < self.retry.retries:
                    delay = self.retry.backoff_base * (self.retry.backoff_factor ** attempt)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                logging.exception("HTTP error on %s %s: %s", method, url, e)
                raise BackendError(f"Network error: {e}") from e

            if resp.status_code in expected:
                return resp
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

            raise BackendUnexpectedError(f"Unexpected {resp.status_code}: {self._detail_from_response(resp)}")

    # ---------- Public Methods ----------

    async def check_user_exist(self, chat_id: int) -> bool:
        try:
            await self._request("GET", f"/users/{chat_id}", expected=(200,))
            return True
        except BackendNotFound:
            return False

    async def register_user(self, **kwargs) -> RegisterResult:
        """
        Registers a user. Accepts chat_id, nickname, and optional referral fields.
        """
        payload = {k: v for k, v in kwargs.items() if v is not None}
        try:
            # NOTE: Assuming the registration endpoint is at /auth/register based on grep
            await self._request("POST", "/users/register", json=payload, expected=(200, 201))
            return {"created": True}
        except BackendUnexpectedError as e:
            if "exists" in str(e).lower():
                return {"created": False, "reason": "exists"}
            raise

    async def get_coins(self, chat_id: int) -> int:
        resp = await self._request("GET", f"/users/{chat_id}/coins", expected=(200,))
        return int(resp.json().get("coins", 0))
    
    async def get_user_referral_link(self, chat_id: int) -> str:
        """Gets the user's referral link."""
        resp = await self._request("GET", f"/referral/link/{chat_id}", expected=(200,))
        data =  resp.json()
        return data.get("url")

    async def get_user_referral_stats(self, chat_id: int) -> dict:
        """Gets the user's referral stats."""
        resp = await self._request("GET", f"/referral/stats/{chat_id}", expected=(200,))
        return await resp.json()

    async def get_user_bonus_history(self, chat_id: int) -> List[dict]:
        """Gets the user's bonus history."""
        resp = await self._request("GET", f"/referral/bonuses/{chat_id}", expected=(200,))
        return await resp.json()

    async def get_user_roles(self, chat_id: int) -> List[str]:
        """Gets the user's roles from the backend."""
        try:
            # NOTE: Assuming the endpoint is at /auth/{chat_id}/roles based on router structure
            resp = await self._request("GET", f"/users/{chat_id}/roles", expected=(200,))
            data = resp.json()
            return data.get("roles", [])
        except BackendNotFound:
            return [] # If user not found, they have no roles.

    async def get_partner_dashboard(self, chat_id: int) -> dict:
        """Gets the partner's dashboard stats."""
        resp = await self._request("GET", f"/partner/{chat_id}/dashboard", expected=(200,))
        return await resp.json()

    # --- Other methods from original file ---
    async def generate_text(self, chat_id: int, prompt: str, aspect_ratio: str = "16:9") -> dict:
        payload = {"chat_id": chat_id, "prompt": prompt, "aspect_ratio": aspect_ratio}
        resp = await self._request("POST", "/bot/veo/generate/text", json=payload, expected=(200,))
        return resp.json()

    async def generate_photo(
        self, chat_id: int, prompt: str, image_url: str, aspect_ratio: str = "16:9"
    ) -> dict:
        payload = {"chat_id": str(chat_id), "prompt": prompt, "image_url": image_url, "aspect_ratio": aspect_ratio}
        resp = await self._request("POST", "/bot/veo/generate/photo", json=payload, expected=(200,))
        return resp.json()

    async def suggest_prompt(
        self, chat_id: str, brief: str, clarifications: Optional[List[str]],
        attempt: int, previous_prompt: Optional[str], image_url: Optional[str]
    ) -> tuple[str, str]:
        payload = {
            "chat_id": chat_id, "brief": brief, "clarifications": clarifications,
            "attempt": attempt, "previous_prompt": previous_prompt, "image_url": image_url
        }
        resp = await self._request("POST", "/prompt/suggest", json=payload)
        data = resp.json()
        return data.get("ru_text"), data.get("en_text")

    async def rate_task(self, task_id: str, rating: int) -> None:
        await self._request("PATCH", f"/tasks/{task_id}/rating?rating={rating}", expected=(200, 204))

    async def save_task(self, task_id: str, chat_id: str, raw: dict, is_video: bool, rating: int) -> None:
        payload = {
            "task_id": task_id, "chat_id": chat_id, "raw": json.dumps(raw),
            "is_video": is_video, "rating": rating, "created_at": datetime.utcnow().isoformat()
        }
        await self._request("POST", "/tasks/", json=payload, expected=(201,))

    async def get_task(self, task_id: str) -> dict:
        resp = await self._request("GET", f"/tasks/{task_id}", expected=(200,))
        return resp.json()
    
    async def get_user(self, chat_id: int) -> dict:
        resp = await self._request("GET", f"/users/{chat_id}", expected=(200,))
        return resp.json()