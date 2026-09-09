import time
from fastapi import APIRouter

router = APIRouter()
START_TIME = time.time()


@router.get("/health")
async def health_check():
    uptime_seconds = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return {
        "status": "ok",
        "uptime": f"{hours}h {minutes}m {seconds}s",
        "uptime_seconds": uptime_seconds,
        "capabilities": [
            "single-store fetch",
            "bulk multi-store fetch",
            "store discovery",
            "price filtering",
            "sale detection",
            "direct checkout URLs",
        ],
        "rate_limits": {
            "requests_per_minute": 60,
            "max_stores_per_bulk": 20,
            "max_products_per_store": 6250,
        },
        "endpoints": [
            "GET  /api/v1/health",
            "GET  /api/v1/discover",
            "GET  /api/v1/fetch",
            "POST /api/v1/fetch",
            "GET  /api/v1/bulk",
            "POST /api/v1/bulk",
        ],
        "cors": "enabled",
        "version": "1.0.0",
    }
