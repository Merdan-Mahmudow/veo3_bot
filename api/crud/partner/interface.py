from abc import ABC, abstractmethod

class PartnerInterface(ABC):
    @abstractmethod
    async def get_partner_link():
        pass

    @abstractmethod
    async def create_partner_link():
        pass

    @abstractmethod
    async def delete_partner_link():
        pass

    @abstractmethod
    async def list_partner_links():
        pass

    @abstractmethod
    async def get_partner_balance():
        pass

    @abstractmethod
    async def update_partner_balance():
        pass

    @abstractmethod
    async def get_referred_users():
        pass

    @abstractmethod
    async def get_statistics():
        pass
