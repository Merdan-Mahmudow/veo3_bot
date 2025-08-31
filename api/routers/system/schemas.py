from pydantic import BaseModel


class BotMessage(BaseModel):
    text: str
    chat_id: str | None = None
    img_url: str | None = None
    video_url: str | None = None