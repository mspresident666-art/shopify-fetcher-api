import httpx
import asyncio
from typing import Optional

# Shopify limits 250 products per page
PAGE_LIMIT = 250
MAX_PRODUCTS = 6250  # 25 pages max


def normalize_url(url: str) -> str:
    """Normalize store URL to a clean domain."""
    url = url.strip().lower()
    url = url.replace("https://", "").replace("http://", "").rstrip("/")
    return url


async def fetch_page(client: httpx.AsyncClient, base_url: str, page: int) -> list:
    """Fetch a single page of products from Shopify products.json."""
    try:
        resp = await client.get(
            f"https://{base_url}/products.json",
            params={"limit": PAGE_LIMIT, "page": page},
            timeout=15.0,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data.get("products", [])
    except Exception:
        return []


async def fetch_store_products(url: str) -> dict:
    """
    Fetch all products from a Shopify store.
    Returns dict with 'products' list and 'error' if any.
    """
    domain = normalize_url(url)

    all_products = []
    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ShopifyFetcher/1.0)"
            }
        ) as client:
            page = 1
            while len(all_products) < MAX_PRODUCTS:
                products = await fetch_page(client, domain, page)
                if not products:
                    break
                all_products.extend(products)
                if len(products) < PAGE_LIMIT:
                    # Last page
                    break
                page += 1

        return {
            "url": url,
            "domain": domain,
            "products": all_products[:MAX_PRODUCTS],
            "error": None,
        }

    except httpx.ConnectError:
        return {"url": url, "domain": domain, "products": [], "error": "Cannot connect to store"}
    except httpx.TimeoutException:
        return {"url": url, "domain": domain, "products": [], "error": "Request timed out"}
    except Exception as e:
        return {"url": url, "domain": domain, "products": [], "error": str(e)}


async def fetch_multiple_stores(stores: list[str], parallel: bool = True) -> list[dict]:
    """
    Fetch products from multiple stores.
    If parallel=True, fetches all stores concurrently.
    """
    if parallel:
        tasks = [fetch_store_products(url) for url in stores]
        results = await asyncio.gather(*tasks)
        return list(results)
    else:
        results = []
        for url in stores:
            result = await fetch_store_products(url)
            results.append(result)
        return results
