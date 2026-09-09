from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import health, discover, fetch, bulk, view, search

# ── Rate limiter setup ────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="SYF — Shopify Product Fetcher API",
    description=(
        "Public Bulk API for fetching products from any Shopify store. "
        "Supports filtering by price, availability, sale status, and more."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Attach rate limiter ───────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS — allow all origins ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(discover.router, prefix="/api/v1", tags=["Discover"])
app.include_router(fetch.router, prefix="/api/v1", tags=["Fetch"])
app.include_router(bulk.router, prefix="/api/v1", tags=["Bulk"])
app.include_router(view.router, prefix="/api/v1", tags=["View"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])


# ── Root redirect ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    return JSONResponse({
        "name": "SYF — Shopify Product Fetcher API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": [
            "GET  /api/v1/health",
            "GET  /api/v1/discover",
            "GET  /api/v1/fetch?url=store.myshopify.com",
            "POST /api/v1/fetch",
            "GET  /api/v1/bulk?category=fashion",
            "POST /api/v1/bulk",
        ]
    })


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
