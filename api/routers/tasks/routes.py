from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from api.crud.task import TaskCRUD
from api.crud.task.schema import TaskCreate, TaskRead
from api.database import get_async_session 
from typing import List, Dict, Any

router = APIRouter()

@router.post(
        "/", 
        response_model=Dict[str, Any], 
        status_code=status.HTTP_201_CREATED,
        summary="Создать новую задачу"
        )
async def create_task(
    dto: TaskCreate,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    """
    Создание новой задачи.

    Cтатус запроса:
    - 201 Created - задача успешно создана
    - 500 Internal Server Error - ошибка сервера

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Входные данные:
    - `task_id: str` - уникальный идентификатор задачи
    - `chat_id: str` - уникальный идентификатор пользователя в Telegram
    - `raw: str` - сырые данные задачи (в формате JSON)
    - `created_at: str` - дата и время создания задачи (формат "YYYY-MM-DD HH:MM:SS")
    - `is_video: bool` - флаг, указывающий, является ли задача видео
    - `rating: int` - рейтинг задачи (по умолчанию 0)
    """
    try:
        result = await crud.create_task(dto, session)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get(
        "/{task_id}", 
        response_model=TaskRead,
        summary="Просмотр задачи"
        )
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    """
    Получить задачу по task_id.

    Cтатус запроса:
    - 200 OK - задача найдена и возвращена
    - 404 Not Found - задача не найдена
    - 500 Internal Server Error - ошибка сервера

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Параметры пути:
    - `task_id: str` - уникальный идентификатор задачи
    """
    try:
        task = await crud.get_task(task_id, session)
        return task
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.get(
        "/", 
        response_model=List[TaskRead],
        summary="Получить список всех задач"
        )
async def get_all_tasks(
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    """
    Получить все задачи.

    Cтатус запроса:
    - 200 OK - список задач успешно получен
    - 500 Internal Server Error - ошибка сервера

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Возвращаемые данные:
    - Список объектов задачи (TaskRead)
    """
    try:
        tasks = await crud.get_all_tasks(session)
        return tasks
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.patch(
        "/{task_id}/rating", 
        status_code=status.HTTP_204_NO_CONTENT, 
        summary="Установить рейтинг задачи")
async def set_task_rating(
    task_id: str,
    rating: int,
    session: AsyncSession = Depends(get_async_session),
    crud: TaskCRUD = Depends(TaskCRUD),
):
    """
    Установить (обновить) рейтинг задачи.

    Cтатус запроса:
    - 204 No Content - рейтинг успешно установлен
    - 400 Bad Request - некорректный рейтинг
    - 404 Not Found - задача с указанным task_id не найдена
    - 500 Internal Server Error - ошибка сервера

    > [!important]
    > Заголовки запроса:
    > - `X-API-KEY: str` - API ключ для аутентификации (обязательный)

    Параметры:
    - `task_id: str` - уникальный идентификатор задачи (путь)
    - `rating: int` - целочисленное значение рейтинга
    """
    try:
        await crud.set_rating(task_id, rating, session)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))