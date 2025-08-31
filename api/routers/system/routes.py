from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from api.crud.user import UserService
from api.database import get_async_session
from api.routers.system import SystemRoutesManager
from api.routers.system.schemas import BotMessage
from api.security import require_bot_service
from bot.manager import bot_manager
from sqlalchemy.ext.asyncio import AsyncSession
from scalar_fastapi import get_scalar_api_reference

router = APIRouter()

SRM = SystemRoutesManager()
user = UserService()


@router.post("/bot", include_in_schema=False)
async def webhook_handler(request: Request):
    await SRM.webhook_updates(request=request)


@router.on_event("startup")
async def startup():
    await bot_manager.bot_start()


@router.on_event("shutdown")
async def startup():
    await bot_manager.bot_stop()


@router.get("/check-health", include_in_schema=False)
def check_health():
    return {"ok": True}


@router.get("/scalar", include_in_schema=False)
def get_scalar():
    app = SRM.get_app()
    
    return get_scalar_api_reference(
        title=app.title,
        openapi_url=app.openapi_url,
    )


@router.post(
    "/post-message",
    summary="Рассылка и личное сообщение",
    dependencies=[Depends(require_bot_service)]
)
async def post_message(
        dto: BotMessage,
        session: AsyncSession = Depends(get_async_session)
):
    """
    Отправка сообщения пользователям (рассылка или личное сообщение).

    Статус запроса:
    - 200 OK - сообщения успешно отправлены (или поставлены в очередь)
    - 400 Bad Request - некорректные входные данные
    - 500 Internal Server Error - ошибка при отправке сообщений

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные (BotMessage):
    - `chat_id: Optional[str]` - если указан, сообщение отправляется только указанному чату
    - `text: str` - текст сообщения
    - `img_url: Optional[str]` - URL изображения для отправки (photo)
    - `video_url: Optional[str]` - URL видео для отправки (video)

    Поведение:
    - Если указан chat_id — отправка только этому чату.
    - Если chat_id не указан — рассылка всем пользователям (list_user_chat_ids).
    - Поддерживаются отправка photo, video, media_group или простого текста в зависимости от полей.
    """
    users = await user.list_user_chat_ids(session)
    if dto.chat_id:
        users = [dto.chat_id]
    for chat in users:
        if dto.img_url and not dto.video_url:
            await bot_manager.bot.send_photo(chat_id=int(chat), photo=dto.img_url, caption=dto.text)
        elif dto.video_url and not dto.img_url:
            await bot_manager.bot.send_video(chat_id=int(chat), video=dto.video_url, caption=dto.text)
        elif dto.img_url and dto.video_url:
            await bot_manager.bot.send_media_group(
                chat_id=int(chat),
                media=[
                    {"type": 'photo', "media": dto.img_url, },
                    {"type": 'video', "media": dto.video_url, "caption": dto.text},
                ],
            )
        else:
            await bot_manager.bot.send_message(chat_id=int(chat), text=dto.text,)
