from typing import Optional, Sequence
from pydantic import BaseModel, Field

class PromptRequest(BaseModel):
    chat_id: str = Field(..., description="Идентификатор пользователя в Telegram")
    brief: str = Field(..., description="Краткое описание пользователя")
    clarifications: Optional[Sequence[str]] = None
    attempt: int = 1
    previous_prompt: Optional[str] = None
    aspect_ratio: str = "16:9"

class PromptResponse(BaseModel):
    prompt: str

class ChangeSystemPromptRequest(BaseModel):
    system_prompt: str = Field(..., description="Новый системный промпт для генерации")