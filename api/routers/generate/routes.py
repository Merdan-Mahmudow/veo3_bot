from datetime import datetime
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from api.database import get_async_session
from api.routers.generate import get_task_crud, get_veo_service
from api.routers.generate.schema import CallbackOut, GenerateOut, GeneratePhotoIn, GenerateTextIn, KIECallbackIn, StatusOut, VideoReadyIn
from api.security import require_bot_service
from services.veo import VeoCallbackAuthError, VeoService, VeoServiceError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.manager import bot_manager
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from api.crud.task import TaskCRUD
from api.crud.task.schema import TaskCreate


router = APIRouter(prefix="/bot/veo",
                   tags=["bot-veo"], dependencies=[Depends(require_bot_service)])


@router.post("/generate/text", response_model=GenerateOut)
async def generate_text(
    payload: GenerateTextIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud)
):
    try:
        data = await svc.generate_by_text(
            chat_id=payload.chat_id,
            prompt=payload.prompt,
            aspect_ratio=payload.aspect_ratio,
            session=session
        )
        # Сохраняем задачу в БД
        task_dto = TaskCreate(
            task_id=data["task_id"],
            chat_id=payload.chat_id,
            raw=json.dumps(data.get("raw")),
            created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            is_video=True,
            rating=0
        )
        await task.create_task(task_dto, session)
        return GenerateOut(ok=True, task_id=data["task_id"], raw=data.get("raw"))
    except VeoServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


@router.post("/generate/photo", response_model=GenerateOut)
async def generate_photo(
    dto: GeneratePhotoIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud)
):
    try:
        data = await svc.generate_by_photo(
            chat_id=dto.chat_id,
            prompt=dto.prompt,
            image_url=dto.image_url,
            aspect_ratio=dto.aspect_ratio,
            session=session
        )
        # Сохраняем задачу в БД
        task_dto = TaskCreate(
            task_id=data["task_id"],
            chat_id=dto.chat_id,
            raw=json.dumps(data.get("raw")),
            created_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            is_video=False,
            rating=0
        )
        await task.create_task(task_dto, session)
        return GenerateOut(
            ok=True,
            task_id=data["task_id"],
            input_image_url=data.get("input_image_url"),
            raw=data.get("raw"),
        )
    except VeoServiceError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # 502, как и раньше, сигнализирует об ошибке обращения к KIE
        print(e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


@router.get("/status/{task_id}", response_model=StatusOut)
async def get_status(task_id: str, svc: VeoService = Depends(get_veo_service)):
    try:
        info = await svc.get_status(task_id)
        return StatusOut(ok=True, **info)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


# ===================== КОЛБЭК ОТ KIE =====================

public_router = APIRouter(prefix="/veo", tags=["veo-callback"])


@public_router.post("/complete", response_model=CallbackOut)
async def veo_complete(
    payload: KIECallbackIn,
    svc: VeoService = Depends(get_veo_service),
    task: TaskCRUD = Depends(get_task_crud)
):
    try:
        res = await svc.handle_callback(payload.model_dump())
                # Обновляем задачу в БД
        task_dto = TaskCreate(
            raw=json.dumps(payload.model_dump()),
        )
        await task.create_task(task_dto, session=None)
        return CallbackOut(ok=True, **res)
    except VeoCallbackAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Callback unauthorized")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


internal = APIRouter(prefix="/internal", tags=["internal"])


def rating_kb(task_id: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for score in range(1, 6):
        kb.button(text=str(score), callback_data=f"rate:{task_id}:{score}")
    kb.adjust(5)
    return kb.as_markup()


@internal.post("/veo/video-ready")
async def video_ready(
    payload: VideoReadyIn
    ):
    text = (
        "Видео готово!"
    )

    await bot_manager.bot.send_video(chat_id=payload.chat_id,
                                     video=types.URLInputFile(payload.result_url),
                                     caption=text,
                                     show_caption_above_media=True
                                     )
    await bot_manager.bot.send_message(chat_id=payload.chat_id,
                                        text="Пожалуйста, оцените качество видео от 1 до 5:",
                                        reply_markup=rating_kb(payload.task_id)
                                        )
    return {"ok": True}
