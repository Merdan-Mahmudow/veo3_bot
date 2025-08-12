from fastapi import APIRouter, Depends
from api.crud.user import UserService
from services.kie import GenerateRequests
from services.notifier import BotNotifier
from services.redis import RedisClient
from services.storage import YandexS3Storage
from services.veo import VeoService



def get_user_service() -> UserService: return UserService()
def get_storage() -> YandexS3Storage: return YandexS3Storage()
def get_kie_client() -> GenerateRequests: return GenerateRequests()
def get_redis() -> RedisClient: return RedisClient()
def get_notifier() -> BotNotifier: return BotNotifier()

def get_veo_service(
    users: UserService = Depends(get_user_service),
    gen: GenerateRequests = Depends(get_kie_client),
    storage: YandexS3Storage = Depends(get_storage),
    redis: RedisClient = Depends(get_redis),
    notifier: BotNotifier = Depends(get_notifier),
) -> VeoService:
    return VeoService(users=users, gen=gen, storage=storage, redis=redis, notifier=notifier)