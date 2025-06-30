import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Endpoint to check the health of the backend

    This endpoint is used by the Web UI to check if the backend is ready
    and operational. It's particularly useful after cold starts.
    """
    logger.info("Received request to /health endpoint")

    return {"status": "ok", "message": "Backend is healthy"}
