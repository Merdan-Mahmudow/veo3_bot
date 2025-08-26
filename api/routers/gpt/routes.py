from datetime import datetime
import json
import aiohttp
from fastapi import APIRouter, Depends, HTTPException, Request
from api.crud.task.schema import TaskCreate
from api.routers.gpt.schemas import ChangeSystemPromptRequest, PromptRequest, PromptResponse
from services.gpt import PromptAI
from services.redis import RedisClient
from api.crud.task import TaskCRUD
from api.database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/prompt", tags=["prompt"])
redis = RedisClient()

@router.post("/suggest", response_model=PromptResponse, include_in_schema=False)
async def suggest_prompt(
    data: PromptRequest,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
    ) -> PromptResponse:
    try:
        # генерируем промпт
        ai = PromptAI()
        ru_text, en_text = await ai.suggest_prompt(
        brief=data.brief,
        clarifications=data.clarifications,
        attempt=data.attempt,
        previous_prompt=data.previous_prompt,
        # aspect_ratio=data.aspect_ratio,
        image_url=data.image_url,
    )
        task = TaskCreate(
                task_id="GPT-" + data.chat_id + "-" + str(data.attempt) + "-" + str(hash(ru_text + en_text)) + "-" + str(datetime.utcnow().strftime("%Y-%m-%d-%H:%M:%S")),
                chat_id=data.chat_id,
                raw="".join(json.dumps(data.model_dump())),
                created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                is_video=False,
                rating=0
            )
        await crud.create_task(dto=task,session=session)
        
        return PromptResponse(prompt=[ru_text, en_text])

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