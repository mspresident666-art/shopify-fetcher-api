"""
Dynamic Shopify store discovery using DuckDuckGo search.
Finds Shopify stores selling products related to a keyword.
"""
import re
import asyncio
from urllib.parse import urlparse


def _extract_shopify_domain(url: str) -> str | None:
    """Extract the store domain from a URL if it's a Shopify store."""
    try:
        parsed = urlparse(url if url.startswith("http") else f"https://{url}")
        host = parsed.netloc or parsed.path.split("/")[0]
        host = host.lower().strip()

        # Remove www.
        if host.startswith("www."):
            host = host[4:]

        # Direct myshopify.com subdomain
        if host.endswith(".myshopify.com"):
            return host

        # Custom domain — we can't tell for sure it's Shopify, but include it
        # Filter out known non-Shopify domains
        excluded = {
            "google.com", "bing.com", "yahoo.com", "amazon.com", "ebay.com",
            "facebook.com", "instagram.com", "twitter.com", "youtube.com",
            "reddit.com", "pinterest.com", "tiktok.com", "shopify.com",
            "etsy.com", "walmart.com", "target.com", "aliexpress.com",
            "dhgate.com", "alibaba.com", "wikipedia.org", "github.com",
        }
        if host in excluded:
            return None
        if any(host.endswith(f".{e}") for e in excluded):
            return None

        # Only return if it has a proper TLD and looks like a real store
        parts = host.split(".")
        if len(parts) >= 2 and len(parts[-1]) >= 2:
            return host
    except Exception:
        pass
    return None


async def discover_stores_for_keyword(keyword: str, max_results: int = 20) -> list[str]:
    """
    Search DuckDuckGo for Shopify stores selling products related to `keyword`.
    Returns a list of discovered store domains (deduplicated).
    """
    discovered = set()

    try:
        from duckduckgo_search import DDGS

        queries = [
            f"{keyword} site:myshopify.com",
            f'buy "{keyword}" shopify store',
            f"{keyword} shop myshopify",
        ]

        def _search_ddg(q: str) -> list[dict]:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(q, max_results=15))
            except Exception:
                return []

        # Run searches in thread pool (DDG client is sync)
        loop = asyncio.get_event_loop()
        tasks = [loop.run_in_executor(None, _search_ddg, q) for q in queries]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for results in results_list:
            if isinstance(results, Exception):
                continue
            for r in results:
                # Check URL and body for myshopify domains
                url = r.get("href", "")
                body = r.get("body", "")

                # Extract from URL
                domain = _extract_shopify_domain(url)
                if domain:
                    discovered.add(domain)

                # Extract myshopify.com mentions from snippet
                myshopify_re = re.findall(r"([\w-]+\.myshopify\.com)", body + " " + url)
                for d in myshopify_re:
                    discovered.add(d.lower())

    except ImportError:
        pass  # duckduckgo_search not installed
    except Exception:
        pass

    return list(discovered)[:max_results]
