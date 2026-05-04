from fastapi import APIRouter

from app.api.v1 import generations, search, styles

api_router = APIRouter()
api_router.include_router(generations.router, prefix="/generations", tags=["generations"])
api_router.include_router(styles.router, prefix="/styles", tags=["styles"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
