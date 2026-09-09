import json
import os
import time
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional

from core.fetcher import fetch_multiple_stores
from core.filters import filter_products, sort_products, get_cheapest_price
from core.formatter import format_product, build_price_summary

router = APIRouter()

STORES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")
MAX_STORES = 20


def load_stores_by_category(category: str) -> list[str]:
    try:
        with open(STORES_PATH, "r", encoding="utf-8") as f:
            all_stores = json.load(f)
        return [s["url"] for s in all_stores if s.get("category", "").lower() == category.lower()]
    except Exception:
        return []


# ── Pydantic model for POST ───────────────────────────────────────────────────
class BulkFilters(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    available_only: bool = False
    on_sale: bool = False
    q: Optional[str] = None
    sort: str = "default"
    type: Optional[str] = None
    vendor: Optional[str] = None


class BulkRequest(BaseModel):
    stores: Optional[list[str]] = None
    category: Optional[str] = None
    filters: BulkFilters = BulkFilters()
    global_limit: int = 250
    parallel: bool = True

    @field_validator("stores")
    @classmethod
    def check_store_limit(cls, v):
        if v and len(v) > MAX_STORES:
            raise ValueError(f"Maximum {MAX_STORES} stores per bulk request")
        return v


# ── Shared bulk logic ─────────────────────────────────────────────────────────
async def _do_bulk(
    stores: list[str],
    filters: BulkFilters,
    global_limit: int,
    parallel: bool,
):
    if not stores:
        raise HTTPException(status_code=400, detail="No stores provided")
    if len(stores) > MAX_STORES:
        raise HTTPException(status_code=400, detail=f"Max {MAX_STORES} stores per request")

    t_start = time.time()

    # Fetch all stores
    results = await fetch_multiple_stores(stores, parallel=parallel)

    all_products = []
    succeeded = []
    failed = []
    total_raw = 0

    for result in results:
        if result["error"]:
            failed.append({"url": result["url"], "error": result["error"]})
            continue

        succeeded.append(result["url"])
        total_raw += len(result["products"])

        # Filter each store's products
        store_filtered = filter_products(
            result["products"],
            min_price=filters.min_price,
            max_price=filters.max_price,
            available_only=filters.available_only,
            on_sale=filters.on_sale,
            q=filters.q,
            product_type=filters.type,
            vendor=filters.vendor,
        )

        # Format with _checkout
        domain = result["domain"]
        for p in store_filtered:
            p["_store_url"] = result["url"]
            all_products.append(format_product(p, domain))

    # Sort combined products
    all_products = sort_products(all_products, filters.sort)

    # Global limit
    returned_products = all_products[:global_limit]

    elapsed_ms = int((time.time() - t_start) * 1000)

    # Price summary
    price_summary = build_price_summary(returned_products)
    all_prices = [get_cheapest_price(p) for p in returned_products if get_cheapest_price(p) > 0]

    return {
        "success": True,
        "meta": {
            "stores_requested": len(stores),
            "stores_succeeded": len(succeeded),
            "stores_failed": len(failed),
            "total_products_raw": total_raw,
            "returned_products": len(returned_products),
            "fetch_time_ms": elapsed_ms,
            "cheapest_product": f"${min(all_prices):.2f}" if all_prices else None,
            "most_expensive_product": f"${max(all_prices):.2f}" if all_prices else None,
            "price_summary": price_summary,
        },
        "stores": succeeded,
        "products": returned_products,
        "failed_stores": failed,
    }


# ── GET endpoint ──────────────────────────────────────────────────────────────
@router.get("/bulk")
async def bulk_get(
    stores: Optional[str] = Query(None, description="Comma-separated list of store URLs"),
    category: Optional[str] = Query(None, description="Fetch all stores in a category"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    available: Optional[bool] = Query(None),
    on_sale: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    sort: str = Query("default"),
    global_limit: int = Query(250, ge=1, le=5000),
    parallel: bool = Query(True),
):
    # Resolve store list
    store_list = []
    if stores:
        store_list = [s.strip() for s in stores.split(",") if s.strip()]
    elif category:
        store_list = load_stores_by_category(category)

    filters = BulkFilters(
        min_price=min_price,
        max_price=max_price,
        available_only=available or False,
        on_sale=on_sale or False,
        q=q,
        sort=sort,
    )

    return await _do_bulk(store_list, filters, global_limit, parallel)


# ── POST endpoint ─────────────────────────────────────────────────────────────
@router.post("/bulk")
async def bulk_post(body: BulkRequest):
    # Resolve store list
    store_list = body.stores or []
    if not store_list and body.category:
        store_list = load_stores_by_category(body.category)

    return await _do_bulk(store_list, body.filters, body.global_limit, body.parallel)
