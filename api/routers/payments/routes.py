from fastapi import APIRouter
from .routers.sbp import router as SBPRouter

router = APIRouter()

router.include_router(SBPRouter, prefix="/sbp", tags=["Система быстрых платежей"])