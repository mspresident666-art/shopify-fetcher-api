import json
import os
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter()

# Load stores database once at startup
STORES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")

def load_stores() -> list:
    try:
        with open(STORES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@router.get("/discover")
async def discover_stores(
    q: Optional[str] = Query(None, description="Search keyword for store name"),
    category: Optional[str] = Query(None, description="Filter by category (fashion, beauty, food, accessories, electronics)"),
    limit: int = Query(50, ge=1, le=200, description="Max number of stores to return"),
):
    stores = load_stores()

    # Filter by category
    if category:
        stores = [s for s in stores if s.get("category", "").lower() == category.lower()]

    # Filter by keyword
    if q:
        q_lower = q.lower()
        stores = [
            s for s in stores
            if q_lower in s.get("name", "").lower()
            or q_lower in s.get("url", "").lower()
            or q_lower in s.get("category", "").lower()
        ]

    # Limit results
    stores = stores[:limit]

    # Add fetch_url to each store
    for store in stores:
        store["fetch_url"] = f"/api/v1/fetch?url={store.get('url', '')}"

    return {
        "success": True,
        "total": len(stores),
        "stores": stores,
        "categories": ["fashion", "beauty", "food", "accessories", "electronics"],
    }
