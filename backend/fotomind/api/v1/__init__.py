from fastapi import APIRouter

from fotomind.api.v1 import health, session

router = APIRouter()
router.include_router(health.router)
router.include_router(session.router)
