"""
Crawl management API endpoints.
"""
from fastapi import APIRouter, BackgroundTasks, Query
from core.crawler import crawl_curated_stores, crawl_keyword_discovery, get_crawl_status
from core.database import get_db_stats

router = APIRouter()


@router.get("/crawl/status")
async def crawl_status():
    """Get current crawl status and database statistics."""
    db = await get_db_stats()
    crawl = get_crawl_status()
    return {"db": db, "crawl": crawl}


@router.post("/crawl/start")
async def start_crawl(background_tasks: BackgroundTasks):
    """Start crawling all curated stores and indexing products into the database."""
    status = get_crawl_status()
    if status.get("running"):
        return {"message": "Crawl already running", "status": status}

    background_tasks.add_task(crawl_curated_stores)
    return {"message": "Crawl started in background — products will be indexed into database"}


@router.post("/crawl/discover")
async def discover_and_crawl(
    background_tasks: BackgroundTasks,
    keyword: str = Query(..., description="Keyword to discover stores for"),
    max_stores: int = Query(50, ge=1, le=200),
):
    """Discover new Shopify stores for a keyword via DuckDuckGo and crawl them."""
    background_tasks.add_task(crawl_keyword_discovery, keyword, max_stores)
    return {
        "message": f"Discovering Shopify stores for '{keyword}' via web search...",
        "keyword": keyword,
        "max_stores": max_stores,
    }
