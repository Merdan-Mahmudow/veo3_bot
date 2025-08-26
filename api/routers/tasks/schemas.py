from pydantic import BaseModel

class TaskRatingIn(BaseModel):
    task_id: str
    rating: int