from fastapi import APIRouter

from fotomind.api.v1 import health, library, session, storage, worker

router = APIRouter()
router.include_router(health.router)
router.include_router(session.router)
router.include_router(library.router)
router.include_router(storage.router)
router.include_router(worker.router)
