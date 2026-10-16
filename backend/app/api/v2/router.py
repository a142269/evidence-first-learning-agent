from fastapi import APIRouter

from backend.app.api.v2.learning_runs import router as learning_runs_router

api_v2_router = APIRouter()
api_v2_router.include_router(learning_runs_router)
