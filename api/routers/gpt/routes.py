import aiohttp
from fastapi import APIRouter, HTTPException, Request
from api.routers.gpt.schemas import ChangeSystemPromptRequest, PromptRequest, PromptResponse
from services.gpt import PromptAI
from services.redis import RedisClient

router = APIRouter(prefix="/prompt", tags=["prompt"])
redis = RedisClient()

@router.post("/suggest", response_model=PromptResponse, include_in_schema=False)
async def suggest_prompt(data: PromptRequest) -> PromptResponse:
    try:
        # генерируем промпт
        ai = PromptAI()
        prompt_text = await ai.suggest_prompt(
        brief=data.brief,
        clarifications=data.clarifications,
        attempt=data.attempt,
        previous_prompt=data.previous_prompt,
        # aspect_ratio=data.aspect_ratio,
        image_url=data.image_url,
    )
        return PromptResponse(prompt=prompt_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/change_system_prompt", include_in_schema=False)
async def change_system_prompt(prompt: ChangeSystemPromptRequest):
    try:
        # сохраняем новый системный промпт в Redis
        await redis.set_prompt("system_prompt", prompt.system_prompt)
        return {"message": "System prompt updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))