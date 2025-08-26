from typing import List, Optional, Sequence
from pydantic import BaseModel, Field

class PromptRequest(BaseModel):
    chat_id: str
    brief: Optional[str] = None
    clarifications: Optional[Sequence[str]] = None
    attempt: int = 1
    previous_prompt: Optional[str] = None
    aspect_ratio: str = "16:9"
    image_url: Optional[str] = None
    
class PromptResponse(BaseModel):
    prompt: List[str]

class ChangeSystemPromptRequest(BaseModel):
    system_prompt: str = Field(..., description="Новый системный промпт для генерации")