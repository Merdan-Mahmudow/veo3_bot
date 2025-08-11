from __future__ import annotations
from abc import ABC, abstractmethod

class UserInterface(ABC):
    @abstractmethod
    async def register_user():
        pass

    @abstractmethod
    async def get_user():
        pass

    @abstractmethod
    async def delete_user():
        pass

    @abstractmethod
    async def get_coins():
        pass

    @abstractmethod
    async def minus_coin():
        pass

    @abstractmethod
    async def plus_coins():
        pass