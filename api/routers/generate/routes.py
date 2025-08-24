from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from api.database import get_async_session
from api.routers.generate import get_veo_service
from api.routers.generate.schema import CallbackOut, GenerateOut, GeneratePhotoIn, GenerateTextIn, KIECallbackIn, StatusOut, VideoReadyIn
from api.security import require_bot_service
from services.veo import VeoCallbackAuthError, VeoService, VeoServiceError
from sqlalchemy.ext.asyncio import AsyncSession
from bot.manager import bot_manager
from aiogram import types

router = APIRouter(prefix="/bot/veo", tags=["bot-veo"], dependencies=[Depends(require_bot_service)])


@router.post("/generate/text", response_model=GenerateOut)
async def generate_text(
    payload: GenerateTextIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
):
    try:
        data = await svc.generate_by_text(chat_id=payload.chat_id, prompt=payload.prompt, session=session)
        return GenerateOut(ok=True, task_id=data["task_id"], raw=data.get("raw"))
    except VeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")

@router.post("/generate/photo", response_model=GenerateOut)
async def generate_photo(
    dto: GeneratePhotoIn,
    session: AsyncSession = Depends(get_async_session),
    svc: VeoService = Depends(get_veo_service),
):
    try:
        data = await svc.generate_by_photo(
            chat_id=dto.chat_id,
            prompt=dto.prompt,
            image_url=dto.image_url,  
            session=session
        )
        return GenerateOut(
            ok=True,
            task_id=data["task_id"],
            input_image_url=data.get("input_image_url"),
            raw=data.get("raw"),
        )
    except VeoServiceError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # 502, как и раньше, сигнализирует об ошибке обращения к KIE
        print(e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")
  
@router.get("/status/{task_id}", response_model=StatusOut)
async def get_status(task_id: str, svc: VeoService = Depends(get_veo_service)):
    try:
        info = await svc.get_status(task_id)
        return StatusOut(ok=True, **info)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="KIE unavailable")


# ===================== КОЛБЭК ОТ KIE =====================

public_router = APIRouter(prefix="/veo", tags=["veo-callback"])

@public_router.post("/complete", response_model=CallbackOut)
async def veo_complete(
    payload: KIECallbackIn,
    svc: VeoService = Depends(get_veo_service),
):
    try:
        res = await svc.handle_callback(payload.model_dump())
        return CallbackOut(ok=True, **res)
    except VeoCallbackAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Callback unauthorized")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    


internal = APIRouter(prefix="/internal", tags=["internal"])




@internal.post("/veo/video-ready")
async def video_ready(payload: VideoReadyIn):
    text = (
        "Видео готово!"
    )
    await bot_manager.bot.send_video(chat_id=payload.chat_id,
                                     video=types.URLInputFile(payload.result_url),
                                     caption=text,
                                     show_caption_above_media=True)
    return {"ok": True}
