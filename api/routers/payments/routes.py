from fastapi import APIRouter
from .routers.sbp import router as SBPRouter
from .routers.webhook import router as WebhookRouter

router = APIRouter()

router.include_router(SBPRouter, prefix="/sbp", tags=["Система быстрых платежей"])
router.include_router(WebhookRouter, tags=["Платежные вебхуки"])