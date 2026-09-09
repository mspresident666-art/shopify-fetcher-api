"""
Background crawler — discovers and indexes Shopify stores into PostgreSQL.
Triggered via API or runs automatically on startup.
"""
import asyncio
import json
import os
from typing import Optional

from core.fetcher import fetch_multiple_stores
from core.formatter import format_product
from core.database import upsert_store, save_products, get_pool, DATABASE_URL
from core.discovery import discover_stores_for_keyword

STORES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")

_crawl_running = False
_crawl_status = {
    "running": False,
    "stores_crawled": 0,
    "products_indexed": 0,
    "current_store": "",
    "errors": 0,
}


def get_crawl_status() -> dict:
    return dict(_crawl_status)


async def crawl_store_list(store_urls: list[str], batch_size: int = 20) -> dict:
    """Crawl a list of stores and index their products into the database."""
    global _crawl_status
    total_products = 0
    errors = 0

    for i in range(0, len(store_urls), batch_size):
        batch = store_urls[i: i + batch_size]
        _crawl_status["current_store"] = batch[0] if batch else ""

        results = await fetch_multiple_stores(batch, parallel=True)

        for result in results:
            if result["error"]:
                errors += 1
                continue

            domain = result["domain"]
            products_raw = result["products"]

            if not products_raw:
                continue

            # Format products
            formatted = []
            for p in products_raw:
                try:
                    fp = format_product(p, domain)
                    fp["_store_url"] = result["url"]
                    formatted.append(fp)
                except Exception:
                    continue

            # Save to database
            try:
                await upsert_store(domain)
                await save_products(domain, formatted)
                total_products += len(formatted)
                _crawl_status["stores_crawled"] += 1
                _crawl_status["products_indexed"] += len(formatted)
            except Exception as e:
                errors += 1

        # Small delay between batches to be respectful
        await asyncio.sleep(0.5)

    _crawl_status["errors"] += errors
    return {"stores_crawled": _crawl_status["stores_crawled"], "products_indexed": total_products, "errors": errors}


async def crawl_curated_stores():
    """Crawl all stores from stores.json and index them. Skips already-indexed stores first."""
    global _crawl_running, _crawl_status

    if _crawl_running:
        return {"message": "Crawl already running"}

    _crawl_running = True
    _crawl_status = {
        "running": True,
        "stores_crawled": 0,
        "products_indexed": 0,
        "current_store": "",
        "errors": 0,
    }

    try:
        with open(STORES_PATH, "r", encoding="utf-8") as f:
            stores = json.load(f)
        store_urls = [s["url"] for s in stores]

        # Get already-indexed domains from DB to skip them on first pass
        already_indexed = set()
        if DATABASE_URL:
            try:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch("SELECT domain FROM stores WHERE status = 'active'")
                    already_indexed = {r["domain"] for r in rows}
            except Exception:
                pass

        # Prioritize: NEW stores first, already-indexed stores last
        new_stores = [u for u in store_urls if u not in already_indexed]
        old_stores = [u for u in store_urls if u in already_indexed]
        ordered_urls = new_stores + old_stores

        print(f"Crawl order: {len(new_stores)} new stores first, then {len(old_stores)} already-indexed")

        # Register all stores as pending
        for s in stores:
            await upsert_store(s["url"], s.get("name", ""), s.get("category", "general"))

        result = await crawl_store_list(ordered_urls, batch_size=20)
        return result
    finally:
        _crawl_running = False
        _crawl_status["running"] = False


async def crawl_keyword_discovery(keyword: str, max_stores: int = 50):
    """Discover new stores for a keyword and crawl them."""
    global _crawl_status

    # Discover stores via DDG
    discovered = await discover_stores_for_keyword(keyword, max_results=max_stores)

    if not discovered:
        return {"discovered": 0, "crawled": 0}

    # Save to DB as pending stores
    for domain in discovered:
        await upsert_store(domain)

    # Crawl them
    result = await crawl_store_list(discovered, batch_size=10)
    return {"keyword": keyword, "discovered": len(discovered), **result}


async def auto_crawl_on_startup():
    """Run initial crawl of curated stores on startup (background)."""
    if not DATABASE_URL:
        return

    await asyncio.sleep(5)  # Wait for server to be ready
    print("🕷️  Starting initial crawl of curated stores...")
    await crawl_curated_stores()
    print("✅ Initial crawl complete")
