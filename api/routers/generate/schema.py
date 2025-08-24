from __future__ import annotations
from typing import Optional
from fastapi import Form
from pydantic import BaseModel



class GenerateTextIn(BaseModel):
    chat_id: str
    prompt: str

class GeneratePhotoIn(BaseModel):
    chat_id: str
    prompt: str
    image_url: Optional[str] = None

class GenerateOut(BaseModel):
    ok: bool
    task_id: str
    input_image_url: Optional[str] = None
    raw: Optional[dict] = None

class StatusOut(BaseModel):
    ok: bool
    task_id: str
    status: Optional[str] = None
    source_url: Optional[str] = None
    result_url: Optional[str] = None
    raw: Optional[dict] = None

# Колбэк от KIE в новом формате
class KIECallbackInfo(BaseModel):
    resultUrls: Optional[list[str]] = None
    originUrls: Optional[list[str]] = None

class KIECallbackData(BaseModel):
    taskId: str
    info: Optional[KIECallbackInfo] = None
    fallbackFlag: Optional[bool] = None

class KIECallbackIn(BaseModel):
    code: int
    msg: Optional[str] = None
    data: KIECallbackData

class CallbackOut(BaseModel):
    ok: bool
    task_id: str
    status: Optional[str] = None
    source_url: Optional[str] = None
    result_url: Optional[str] = None
    fallback: Optional[bool] = None

class VideoReadyIn(BaseModel):
    chat_id: str
    task_id: str
    result_url: str | None = None
    source_url: str | None = None
    fallback: bool | None = None