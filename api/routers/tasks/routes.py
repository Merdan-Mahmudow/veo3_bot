from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.crud.task import TaskCRUD
from api.crud.task.schema import TaskCreate, TaskRead
from api.database import get_async_session
from api.security import require_bot_service    
from typing import List, Dict, Any

router = APIRouter(prefix="/tasks", tags=["tasks"], dependencies=[Depends(require_bot_service)])

@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_task(
    dto: TaskCreate,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    try:
        result = await crud.create_task(dto, session)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    try:
        task = await crud.get_task(task_id, session)
        return task
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.get("/", response_model=List[TaskRead])
async def get_all_tasks(
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    try:
        tasks = await crud.get_all_tasks(session)
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch("/{task_id}/rating", status_code=status.HTTP_204_NO_CONTENT)
async def set_task_rating(
    task_id: str,
    rating: int,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    try:
        await crud.set_rating(task_id, rating, session)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))