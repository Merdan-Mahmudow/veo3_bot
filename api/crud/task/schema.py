from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class TaskCreate(BaseModel):
    task_id: Optional[str]
    chat_id: Optional[str]
    raw: Optional[str]
    is_video: bool = False
    rating: Optional[int] = None
    created_at: Optional[str] = None


class TaskRead(BaseModel):
    id: uuid.UUID
    task_id: str
    chat_id: str
    raw: Optional[str] = None
    is_video: bool
    rating: Optional[int] = None
    created_at: str
