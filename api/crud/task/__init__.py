from .interface import TaskInterface
from typing import Any, Dict
from sqlalchemy import insert, select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from .schema import TaskCreate, TaskRead
from api.models.tasks import Task

class TaskCRUD(TaskInterface):
    def __init__(self):
        pass

    async def create_task(self, dto: TaskCreate, session: AsyncSession) -> Dict[str, Any]:
        query = insert(Task).values(dto.model_dump())
        await session.execute(query)
        await session.commit()
        return {"ok": True}

    async def get_task(self, task_id: str, session: AsyncSession) -> TaskRead:
        query = select(Task).where(Task.task_id == task_id)
        res = await session.execute(query)
        task = res.scalar_one_or_none()
        if not task:
            raise Exception("Task not found")
        return TaskRead(task)

    async def get_all_tasks(self, session: AsyncSession) -> list[TaskRead]:
        query = select(Task)
        res = await session.execute(query)
        tasks = res.scalars().all()
        return [TaskRead.from_orm(task) for task in tasks]
    
    async def set_rating(self, task_id: str, rating: int, session: AsyncSession) -> None:
        query = (
            update(Task)
            .where(Task.task_id == task_id)
            .values(rating=rating)
        )
        res = await session.execute(query)
        await session.commit()
        if res.rowcount == 0:
            raise Exception("Task not found")