import time
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.fetcher import fetch_store_products
from core.filters import filter_products, sort_products
from core.formatter import format_product

router = APIRouter()


# ── Pydantic model for POST body ──────────────────────────────────────────────
class FetchRequest(BaseModel):
    url: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    available_only: bool = False
    on_sale: bool = False
    q: Optional[str] = None
    sort: str = "default"
    limit: int = 250
    type: Optional[str] = None
    vendor: Optional[str] = None


# ── Shared fetch logic ────────────────────────────────────────────────────────
async def _do_fetch(
    url: str,
    min_price: Optional[float],
    max_price: Optional[float],
    available_only: bool,
    on_sale: bool,
    q: Optional[str],
    sort: str,
    limit: int,
    product_type: Optional[str],
    vendor: Optional[str],
):
    if not url:
        raise HTTPException(status_code=400, detail="'url' parameter is required")

    t_start = time.time()

    # 1. Fetch raw products
    result = await fetch_store_products(url)

    if result["error"]:
        raise HTTPException(status_code=502, detail=f"Failed to fetch store: {result['error']}")

    raw_products = result["products"]
    total_raw = len(raw_products)

    # 2. Filter
    filtered = filter_products(
        raw_products,
        min_price=min_price,
        max_price=max_price,
        available_only=available_only,
        on_sale=on_sale,
        q=q,
        product_type=product_type,
        vendor=vendor,
    )

    # 3. Sort
    filtered = sort_products(filtered, sort)

    # 4. Limit
    filtered = filtered[:limit]

    # 5. Format with _checkout
    store_domain = result["domain"]
    formatted = [format_product(p, store_domain) for p in filtered]

    elapsed_ms = int((time.time() - t_start) * 1000)

    return {
        "success": True,
        "store": url,
        "meta": {
            "total_raw": total_raw,
            "returned": len(formatted),
            "fetch_time_ms": elapsed_ms,
        },
        "products": formatted,
    }


# ── GET endpoint ──────────────────────────────────────────────────────────────
@router.get("/fetch")
async def fetch_get(
    url: str = Query(..., description="Shopify store URL e.g. store.myshopify.com"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    available: Optional[bool] = Query(None, description="Only available products"),
    on_sale: Optional[bool] = Query(None, description="Only on-sale products"),
    q: Optional[str] = Query(None, description="Keyword search"),
    sort: str = Query("default", description="Sort: price-asc, price-desc, title-asc, newest"),
    limit: int = Query(250, ge=1, le=6250),
    type: Optional[str] = Query(None, description="Product type filter"),
    vendor: Optional[str] = Query(None, description="Vendor filter"),
):
    return await _do_fetch(
        url=url,
        min_price=min_price,
        max_price=max_price,
        available_only=available or False,
        on_sale=on_sale or False,
        q=q,
        sort=sort,
        limit=limit,
        product_type=type,
        vendor=vendor,
    )


# ── POST endpoint ─────────────────────────────────────────────────────────────
@router.post("/fetch")
async def fetch_post(body: FetchRequest):
    return await _do_fetch(
        url=body.url,
        min_price=body.min_price,
        max_price=body.max_price,
        available_only=body.available_only,
        on_sale=body.on_sale,
        q=body.q,
        sort=body.sort,
        limit=body.limit,
        product_type=body.type,
        vendor=body.vendor,
    )
