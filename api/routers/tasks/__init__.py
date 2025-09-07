from api.crud.task import TaskCRUD

def get_task_crud() -> TaskCRUD:
    return TaskCRUD()