from __future__ import annotations
from abc import ABC, abstractmethod  

class TaskInterface(ABC):
    @abstractmethod
    async def create_task():
        pass

    @abstractmethod
    async def get_task():
        pass

    @abstractmethod
    async def get_all_tasks():
        pass

    @abstractmethod
    async def set_rating():
        pass