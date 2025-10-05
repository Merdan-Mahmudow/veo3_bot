from fastapi import Depends, FastAPI
import uvicorn
from api.routers.system import routes as SystemRoutes
from api.routers.generate import routes as GenerateRoutes
from api.routers.auth import routes as AuthRoutes
from api.routers.gpt import routes as GptRoutes
from api.routers.tasks import routes as TaskRoutes
from api.routers.payments import routes as PaymentRoutes
from api.routers.referral import routes as ReferralRoutes
from api.security import require_bot_service


class FastAPIManager:
    def __init__(self):
        # формат версии: версия.подверсия:месяц.год.число:stable (beta, stable)
        self.api = FastAPI(
            version="1.0:08.25.31:beta",
            title="Документация для ObjectiVEO 3", 
            description=(
                "Сервис для автоматической генерации коротких видео по текстовым описаниям и фотографиям с использованием нейросетей. "
                "Предоставляет HTTP API и интеграцию с Telegram-ботом: создание и управление задачами генерации, формирование промптов, "
                "отслеживание статуса и уведомления пользователям. Включает публичные и защищённые маршруты. "
                "Для защищённых эндпойнтов требуется авторизация; поддерживаются асинхронные задачи и механизмы rate-limiting."
            ),
        )
        self.add_routers()

    def add_routers(self):
        self.api.include_router(
            SystemRoutes.router
        )
        self.api.include_router(
            GenerateRoutes.router,
            prefix="/bot/veo",
            tags=["Генерация видео"],
            dependencies=[Depends(require_bot_service)]
        )
        self.api.include_router(
            GenerateRoutes.public_router,
            prefix="/veo",
            tags=["Внешние роуты"]
        )
        self.api.include_router(
            GenerateRoutes.internal,
            prefix="/internal",
            dependencies=[Depends(require_bot_service)],
            tags=["Внутренние роуты"]
        )
        self.api.include_router(
            AuthRoutes.router,
            prefix="/users",
            dependencies=[Depends(require_bot_service)],
            tags=["Авторизация"]
        )
        self.api.include_router(
            GptRoutes.router,
            prefix="/prompt",
            dependencies=[Depends(require_bot_service)],
            tags=["Работа с промптами"]
        )
        self.api.include_router(
            TaskRoutes.router,
            prefix="/tasks",
            dependencies=[Depends(require_bot_service)],
            tags=["Задачи и RATE"]
        )
        self.api.include_router(
            PaymentRoutes.router,
            prefix="/pay",
            dependencies=[Depends(require_bot_service)],
            tags=["Платежи"]
        )
        self.api.include_router(
            ReferralRoutes.router,
            prefix="/referral",
            dependencies=[Depends(require_bot_service)],
            tags=["Реферальная система"]
        )

    def start_server(self):
        uvicorn.run(self.api, host="0.0.0.0", port=8000)

    def get_app(self) -> FastAPI:
        return self.api
