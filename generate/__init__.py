import aiohttp
from config import ENV
from schemas import VeoResponse

class GenerateRequests():
    def __init__(self):
        self.env = ENV()
        self.token = self.env.KIE_TOKEN

    async def generate_video_by_text(self, prompt: str):
        url = "https://api.kie.ai/api/v1/veo/generate"

        payload = {
            "prompt": prompt,
            "model": "veo3_fast",
            "aspectRatio": "16:9",
            "enableFallback": False
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
        return response_data

    async def get_video_info(self, task_id: str):
        url = "https://api.kie.ai/api/v1/veo/record-info"
        headers = {
            "Authorization": f"Bearer {self.token}"
        }
        params = {
            "taskId": task_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
                return data

    async def generate_video_by_photo(self, prompt: str, imageUrl: str):
        url = "https://api.kie.ai/api/v1/veo/generate"

        payload = {
            "prompt": prompt,
            "model": "veo3_fast",
            "aspectRatio": "16:9",
            "enableFallback": False
        }

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                response_data = await response.json()
        return response_data