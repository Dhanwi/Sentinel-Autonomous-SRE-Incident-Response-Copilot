import os
from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health_check() -> dict:
    """Liveness check. Used by CI, local smoke tests, and later uptime checks."""
    return{
        "status": "ok",
        "environment": os.getenv("ENV", "development"),
    }

