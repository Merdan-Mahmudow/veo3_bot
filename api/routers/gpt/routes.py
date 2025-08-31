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

router = APIRouter()
redis = RedisClient()

@router.post(
        "/suggest", 
        response_model=PromptResponse,
        summary="Сгенерировать промпт на основе краткого описания"
        )
async def suggest_prompt(
    data: PromptRequest,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
    ) -> PromptResponse:
    """
    Генерация промпта на основе краткого описания.
    
    Cтатус запроса:
    - 200 OK - успешная генерация промпта
    - 500 Internal Server Error - ошибка сервера
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `brief: str` - краткое описание желаемого изображения
    - `clarifications: str | None` - уточнения к описанию
    - `attempt: int` - номер попытки (начинается с 1)
    - `previous_prompt: str | None` - предыдущий сгенерированный промпт
    - `image_url: str | None` - URL изображения для контекстуальной генерации

    Выходные данные:
    - `prompt: List[str]` - список сгенерированных промптов (на русском и английском языках)
    """
    try:
        ai = PromptAI()
        ru_text, en_text = await ai.suggest_prompt(
        brief=data.brief,
        clarifications=data.clarifications,
        attempt=data.attempt,
        previous_prompt=data.previous_prompt,
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


@router.patch(
        "/change_system_prompt", 
        summary="Изменить системный промпт для генерации"
        )
async def change_system_prompt(
    prompt: ChangeSystemPromptRequest
    ) -> dict:
    """
    Изменение системного промпта для генерации.
    
    Статус запроса:
    - 200 OK - успешное изменение промпта
    - 500 Internal Server Error - ошибка сервера

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
    
    Входные данные:
    - `system_prompt: str` - новый системный промпт для генерации
    
    Выходные данные:
    - `message: str` - сообщение об успешном изменении промпта
    """
    try:
        await redis.set_prompt("system_prompt", prompt.system_prompt)
        return {"message": "System prompt updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))