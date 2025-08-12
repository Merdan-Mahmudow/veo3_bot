import aiohttp
from config import ENV

import aiohttp

class GenerateRequests:
    def __init__(self):
        self.env = ENV()
        self.token = self.env.KIE_TOKEN
        self.callback_url = "https://api.skyrodev.ru/veo/complete"

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        headers = kwargs.pop("headers", {})
        headers.update({"Authorization": f"Bearer {self.token}"})
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, **kwargs) as r:
                data = await r.json()
                # KIE всегда возвращает HTTP 200, но внутри есть поле code
                if not isinstance(data, dict) or data.get("code") != 200:
                    raise RuntimeError(f"KIE error: {data}")
                return data

    async def generate_video_by_text(self, prompt: str):
        url = "https://api.kie.ai/api/v1/veo/generate"
        payload = {"prompt": prompt, "model": "veo3_fast", "aspectRatio": "16:9",
                   "callBackUrl": self.callback_url, "enableFallback": False}
        headers = {"Content-Type": "application/json"}
        return await self._request("POST", url, json=payload, headers=headers)

    async def get_video_info(self, task_id: str):
        url = "https://api.kie.ai/api/v1/veo/record-info"
        params = {"taskId": task_id}
        return await self._request("GET", url, params=params)

    async def generate_video_by_photo(self, prompt: str, imageUrl: str):
        url = "https://api.kie.ai/api/v1/veo/generate"
        payload = {"prompt": prompt, "imageUrls": [imageUrl], "model": "veo3_fast",
                   "aspectRatio": "16:9", "enableFallback": False}
        headers = {"Content-Type": "application/json"}
        return await self._request("POST", url, json=payload, headers=headers)