import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from api.crud.user import UserService
from api.crud.user.schema import CoinPlus
from api.database import get_async_session
from api.routers.generate import get_redis, get_task_crud, get_veo_service, get_user_service
from api.routers.generate.schema import CallbackOut, GenerateOut, GeneratePhotoIn, GenerateTextIn, KIECallbackIn, StatusOut, VideoReadyIn
from services.redis import RedisClient
from services.veo import VeoCallbackAuthError, VeoService, VeoServiceError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.manager import bot_manager
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from api.crud.task import TaskCRUD
from utils.progress import finish_progress


router = APIRouter()


@router.post(
        "/generate/text", 
        response_model=GenerateOut,
        summary="Генерация видео по текстовому описанию"
        )
async def generate_text(
    payload: GenerateTextIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud)
):
    """
    Генерация видео по текстовому описанию с помощью KIE (Veo 3).

    Cтатус запроса:
    - 200 OK - успешная генерация задачи
    - 400 Bad Request - ошибка валидации входных данных или бизнес-логики
    - 502 Bad Gateway - ошибка связи с KIE (Veo 3)

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `prompt: str` - текстовое описание для генерации видео
    - `aspect_ratio: str | None` - соотношение сторон видео ("16:9", "9:16")
    """
    try:
        data = await svc.generate_by_text(
            chat_id=payload.chat_id,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            session=session
        )
        return GenerateOut(ok=True, task_id=data["task_id"], raw=data.get("raw"))
    except VeoServiceError as e:
        logging.error("VeoServiceError: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        logging.exception("Error generating from text: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


@router.post(
        "/generate/photo", 
        response_model=GenerateOut,
        summary="Генерация видео по изображению и текстовому описанию"
        )
async def generate_photo(
    dto: GeneratePhotoIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud)
):
    """
    Генерация видео по изображению и текстовому описанию с помощью KIE (Veo 3).

    Cтатус запроса:
    - 200 OK - успешная генерация задачи
    - 400 Bad Request - ошибка валидации входных данных или бизнес-логики
    - 502 Bad Gateway - ошибка связи с KIE (Veo 3)
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
    
    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `prompt: str` - текстовое описание для генерации видео
    - `image_url: str | None` - URL изображения для генерации видео
    - `aspect_ratio: str | None` - соотношение сторон видео ("16:9", "9:16")
    """

    try:
        data = await svc.generate_by_photo(
            chat_id=dto.chat_id,
            prompt=dto.prompt,
            image_url=dto.image_url,
            aspect_ratio=dto.aspect_ratio,
            session=session
        )
        return GenerateOut(
            ok=True,
            task_id=data["task_id"],
            input_image_url=data.get("input_image_url"),
            raw=data.get("raw"),
        )
    except VeoServiceError as e:
        logging.error("VeoServiceError: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.exception("Error generating from photo: %s", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


@router.get(
        "/status/{task_id}", 
        response_model=StatusOut,
        summary="Получение статуса задачи генерации"
        )
async def get_status(
    task_id: str,
    svc: VeoService = Depends(get_veo_service)
    ):
    """
    Получение статуса задачи генерации видео по task_id.
    
    Cтатус запроса:
    - 200 OK - успешное получение статуса задачи
    - 502 Bad Gateway - ошибка связи с KIE (Veo 3)
    
    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)
    
    Входные данные:
    - `task_id: str` - уникальный идентификатор задачи генерации
    
    Выходные данные:
    - `ok: bool` - статус успешности запроса
    - `task_id: str` - уникальный идентификатор задачи генерации
    - `status: str | None` - текущий статус задачи ("pending", "completed", "failed")
    - `source_url: str | None` - URL исходного изображения (если применимо)
    - `result_url: str | None` - URL сгенерированного видео (если задача завершена)
    - `raw: dict | None` - сырые данные ответа от KIE
    """
    try:
        info = await svc.get_status(task_id)
        return StatusOut(ok=True, **info)
    except Exception:
        logging.exception("Error fetching status for task %s", task_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


# ===================== КОЛБЭК ОТ KIE =====================

public_router = APIRouter()

@public_router.post(
        "/complete", response_model=CallbackOut,
        summary="Колбэк от KIE о завершении задачи"
        )
async def veo_complete(
    payload: KIECallbackIn,
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud),
    session: AsyncSession = Depends(get_async_session),
    user: UserService = Depends(get_user_service)
):
    """
    Колбэк от KIE (Veo 3) о завершении задачи генерации видео.

    Cтатус запроса:
    - 200 OK - успешная обработка колбэка
    - 401 Unauthorized - ошибка аутентификации колбэка
    - 500 Internal Server Error - внутренняя ошибка сервера при обработке колбэка

    Входные данные:
    - `code: int` - код статуса задачи (0 - успех, иначе - ошибка)
    - `msg: str | None` - сообщение о статусе задачи
    - `data: dict` - данные задачи, включая:
        - `taskId: str` - уникальный идентификатор задачи
        - `info: dict | None` - дополнительная информация о задаче, включая:
            - `resultUrls: list[str] | None` - список URL сгенерированных видео
            - `originUrls: list[str] | None` - список URL исходных изображений
        - `fallbackFlag: bool | None` - флаг использования резервного метода генерации
    
    Выходные данные:
    - `ok: bool` - статус успешности обработки колбэка
    - `task_id: str` - уникальный идентификатор задачи
    - `status: str | None` - итоговый статус задачи ("completed", "failed")
    - `source_url: str | None` - URL исходного изображения (если применимо)
    - `result_url: str | None` - URL сгенерированного видео (если задача завершена)
    - `fallback: bool | None` - флаг использования резервного метода генерации
    """
    chat_id: Optional[str]
    try:
        print(payload)
        if payload.code == 400:
            chat_id = await task.get_chatID_by_taskID(payload.data.taskId, session)
            if chat_id:
                await user.plus_coins(CoinPlus(chat_id=chat_id, count=1))
                await finish_progress(payload.data.taskId, bot_manager.bot)
                await bot_manager.bot.send_message(
                    chat_id=int(chat_id), 
                    text=(
                        "Видео не вернулось 😕\n"
                        "Обычно такое случается, если описание или фото слишком жёсткое или содержит то, что система не может показать."
                        "Попробуйте немного переформулировать — и я сделаю ролик!"
                    ))
        res = await svc.handle_callback(payload.model_dump())
        return CallbackOut(ok=True, **res)
    except VeoCallbackAuthError:
        logging.error("Callback unauthorized")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Callback unauthorized")
    except Exception as e:
        logging.exception("Error handling callback: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


internal = APIRouter()


def rating_kb(task_id: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for score in range(1, 6):
        kb.button(text=str(score), callback_data=f"rate:{task_id}:{score}")
    kb.adjust(5)
    return kb.as_markup()


@internal.post(
        "/veo/video-ready",
        summary="Уведомление о готовности видео"
        )
async def video_ready(
    payload: VideoReadyIn,
    redis: RedisClient = Depends(get_redis)
):
    """
    Уведомление о готовности видео (внутренний эндпоинт).
    Этот эндпоинт вызывается внутренними сервисами для уведомления бота о том, что видео готово к отправке пользователю.

    Cтатус запроса:
    - 200 OK - успешная обработка уведомления
    - 500 Internal Server Error - внутренняя ошибка сервера при обработке уведомления
    
    Входные данные:
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `task_id: str` - уникальный идентификатор задачи генерации
    - `result_url: str | None` - URL сгенерированного видео
    - `source_url: str | None` - URL исходного изображения (если применимо)
    - `fallback: bool | None` - флаг использования резервного метода генерации
    """
    text = ("Видео готово!")
    try:

        await finish_progress(payload.task_id, bot_manager.bot)
        await bot_manager.bot.send_video(chat_id=payload.chat_id,
                                         video=types.URLInputFile(
                                             payload.result_url),
                                         caption=text,
                                         show_caption_above_media=True
                                         )
        rating_message = await bot_manager.bot.send_message(chat_id=payload.chat_id,
                                           text="Пожалуйста, оцените качество видео от 1 до 5:",
                                           reply_markup=rating_kb(payload.task_id),
                                           )
        await redis.set_del_msg(key=f"{payload.chat_id}:{payload.task_id}", value=f"{rating_message.message_id}")
        return {"ok": True}
    except Exception as e:
        logging.exception("Error sending video ready message: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
