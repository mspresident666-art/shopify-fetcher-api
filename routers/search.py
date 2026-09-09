import json
import os
import time
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from core.fetcher import fetch_multiple_stores
from core.filters import filter_products, sort_products, get_cheapest_price
from core.formatter import format_product

router = APIRouter()

STORES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")
MAX_CONCURRENT = 50


class SearchRequest(BaseModel):
    keyword: str
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    available_only: bool = False
    on_sale: bool = False
    sort: str = "price-asc"
    limit: int = 50
    per_store_limit: int = 3
    category: Optional[str] = None


@router.get("/search")
async def search_get(
    q: str = Query(..., description="Keyword to search across all stores"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    available: Optional[bool] = Query(None),
    on_sale: Optional[bool] = Query(None),
    sort: str = Query("price-asc"),
    limit: int = Query(50, ge=1, le=500),
    per_store: int = Query(3, ge=1, le=20, description="Max products per store"),
    category: Optional[str] = Query(None),
):
    return await _do_search(
        keyword=q,
        min_price=min_price,
        max_price=max_price,
        available_only=available or False,
        on_sale=on_sale or False,
        sort=sort,
        limit=limit,
        per_store_limit=per_store,
        category=category,
    )


@router.post("/search")
async def search_post(body: SearchRequest):
    return await _do_search(
        keyword=body.keyword,
        min_price=body.min_price,
        max_price=body.max_price,
        available_only=body.available_only,
        on_sale=body.on_sale,
        sort=body.sort,
        limit=body.limit,
        per_store_limit=body.per_store_limit,
        category=body.category,
    )


async def _do_search(
    keyword: str,
    min_price: Optional[float],
    max_price: Optional[float],
    available_only: bool,
    on_sale: bool,
    sort: str,
    limit: int,
    per_store_limit: int,
    category: Optional[str],
):
    if not keyword or not keyword.strip():
        raise HTTPException(status_code=400, detail="keyword is required")

    t_start = time.time()

    # Load stores
    try:
        with open(STORES_PATH, "r", encoding="utf-8") as f:
            all_stores = json.load(f)
    except Exception:
        raise HTTPException(status_code=500, detail="Could not load stores database")

    # Filter by category if given
    if category:
        all_stores = [s for s in all_stores if s.get("category", "").lower() == category.lower()]

    store_urls = [s["url"] for s in all_stores]

    # Batch fetch all stores
    all_results = []
    for i in range(0, len(store_urls), MAX_CONCURRENT):
        batch = store_urls[i: i + MAX_CONCURRENT]
        results = await fetch_multiple_stores(batch, parallel=True)
        all_results.extend(results)

    # Aggregate with per-store limit — so results come from many different stores
    all_products = []
    succeeded_stores = []
    failed_stores = []
    total_raw = 0
    stores_with_results = 0

    for result in all_results:
        if result["error"]:
            failed_stores.append({"url": result["url"], "error": result["error"]})
            continue

        succeeded_stores.append(result["url"])
        total_raw += len(result["products"])

        filtered = filter_products(
            result["products"],
            min_price=min_price,
            max_price=max_price,
            available_only=available_only,
            on_sale=on_sale,
            q=keyword,
        )

        if not filtered:
            continue

        stores_with_results += 1

        # Sort per-store results and cap at per_store_limit
        filtered = sort_products(filtered, sort)
        filtered = filtered[:per_store_limit]

        domain = result["domain"]
        for p in filtered:
            p["_store_url"] = result["url"]
            formatted = format_product(p, domain)
            all_products.append(formatted)

    # Sort globally across all stores
    all_products = sort_products(all_products, sort)

    # Apply final limit
    returned = all_products[:limit]

    elapsed_ms = int((time.time() - t_start) * 1000)
    prices = [get_cheapest_price(p) for p in returned if get_cheapest_price(p) > 0]

    return {
        "success": True,
        "keyword": keyword,
        "meta": {
            "stores_searched": len(store_urls),
            "stores_succeeded": len(succeeded_stores),
            "stores_with_results": stores_with_results,
            "stores_failed": len(failed_stores),
            "total_products_raw": total_raw,
            "returned": len(returned),
            "per_store_limit": per_store_limit,
            "fetch_time_ms": elapsed_ms,
            "cheapest": f"${min(prices):.2f}" if prices else None,
            "most_expensive": f"${max(prices):.2f}" if prices else None,
        },
        "products": returned,
        "failed_stores": failed_stores,
    }
