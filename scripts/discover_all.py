"""
Aggressive Shopify store discovery script.
Searches DuckDuckGo with hundreds of keywords to find thousands of Shopify stores,
validates them, and adds to stores.json + database.

Run: python scripts/discover_all.py
"""
import asyncio
import json
import os
import re
import sys
import httpx
from urllib.parse import urlparse

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STORES_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "stores.json")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "discovered_stores.json")
API_BASE = "https://shopify-fetcher-api-production.up.railway.app"

# Hundreds of search keywords to maximize store discovery
SEARCH_KEYWORDS = [
    # Footwear / Sneakers
    "sneakers", "shoes", "footwear", "boots", "sandals", "running shoes",
    "basketball shoes", "nike shoes", "adidas shoes", "jordan shoes",
    "converse shoes", "vans shoes", "new balance", "hoka shoes",
    "sneaker boutique", "limited sneakers", "rare sneakers", "deadstock shoes",

    # Fashion / Clothing
    "streetwear", "fashion", "clothing", "apparel", "t-shirt", "hoodie",
    "jacket", "denim", "jeans", "dress", "skirt", "shorts", "joggers",
    "activewear", "athleisure", "sportswear", "swimwear", "lingerie",
    "luxury fashion", "vintage clothing", "thrift store", "designer clothing",
    "streetstyle", "urban fashion", "hypebeast", "skate clothing",

    # Accessories
    "sunglasses", "watch", "jewelry", "necklace", "bracelet", "rings",
    "earrings", "handbag", "backpack", "wallet", "belt", "hat", "cap",
    "beanie", "scarf", "socks", "underwear", "hair accessories",

    # Beauty / Skincare
    "skincare", "makeup", "cosmetics", "serum", "moisturizer", "lip gloss",
    "foundation", "perfume", "fragrance", "nail polish", "eyeliner",
    "hair care", "shampoo", "conditioner", "beard care", "men grooming",
    "organic beauty", "natural skincare", "vegan cosmetics",

    # Food / Drinks
    "coffee beans", "tea", "protein powder", "supplements", "vitamins",
    "snacks", "candy", "chocolate", "hot sauce", "olive oil", "wine",
    "beer", "kombucha", "energy drink", "protein bar", "vegan food",

    # Electronics / Gadgets
    "phone case", "laptop bag", "earbuds", "headphones", "smartwatch",
    "camera accessories", "gaming accessories", "usb hub", "portable charger",
    "led lights", "smart home", "drone accessories",

    # Home / Lifestyle
    "candle", "poster", "art print", "home decor", "plant pot",
    "pillow", "blanket", "mug", "water bottle", "tote bag", "sticker",
    "notebook", "journal", "stationery", "desk accessories",

    # Sports / Outdoor
    "yoga mat", "gym equipment", "fitness gear", "cycling accessories",
    "hiking gear", "camping gear", "surf accessories", "skateboard",
    "gym bag", "sports bottle", "resistance bands",

    # Kids / Pets
    "kids clothing", "baby products", "pet accessories", "dog collar",
    "cat toys", "pet food", "baby shoes", "children toys",
]

# Search query templates
QUERY_TEMPLATES = [
    "{kw} site:myshopify.com",
    'buy "{kw}" myshopify',
    "{kw} shopify store",
    "{kw} online shop myshopify",
]


def extract_shopify_domains(text: str) -> set[str]:
    """Extract myshopify.com domains from text."""
    found = set()

    # Direct myshopify.com pattern
    pattern = r'([\w-]+\.myshopify\.com)'
    matches = re.findall(pattern, text, re.IGNORECASE)
    for m in matches:
        found.add(m.lower().strip())

    return found


async def search_ddg_for_stores(keywords: list[str], max_per_query: int = 20) -> set[str]:
    """Search DuckDuckGo for Shopify stores using many keywords."""
    discovered = set()

    try:
        from duckduckgo_search import DDGS

        def _search(query: str) -> list[dict]:
            try:
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_per_query))
            except Exception as e:
                print(f"  DDG error for '{query}': {e}")
                return []

        loop = asyncio.get_event_loop()
        total_queries = 0

        for kw in keywords:
            for template in QUERY_TEMPLATES[:2]:  # Use 2 templates per keyword
                query = template.format(kw=kw)
                results = await loop.run_in_executor(None, _search, query)
                total_queries += 1

                for r in results:
                    url = r.get("href", "")
                    body = r.get("body", "")
                    combined = url + " " + body

                    domains = extract_shopify_domains(combined)
                    discovered.update(domains)

                    # Also check URL itself
                    try:
                        parsed = urlparse(url)
                        host = parsed.netloc.lower()
                        if host.endswith(".myshopify.com"):
                            discovered.add(host)
                    except Exception:
                        pass

                await asyncio.sleep(0.3)  # Be respectful

                if total_queries % 20 == 0:
                    print(f"  [{total_queries} queries done] Found {len(discovered)} unique stores so far...")

    except ImportError:
        print("duckduckgo-search not installed")

    return discovered


async def validate_shopify_store(domain: str, client: httpx.AsyncClient) -> bool:
    """Check if a domain actually has Shopify products.json."""
    urls_to_try = [
        f"https://{domain}/products.json?limit=1",
    ]
    for url in urls_to_try:
        try:
            r = await client.get(url, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if "products" in data:
                    return True
        except Exception:
            pass
    return False


async def validate_stores_batch(domains: list[str]) -> list[str]:
    """Validate a batch of domains concurrently."""
    valid = []
    async with httpx.AsyncClient(
        headers={"User-Agent": "ShopifyProductFetcher/1.0"},
        follow_redirects=True,
    ) as client:
        tasks = [(d, validate_shopify_store(d, client)) for d in domains]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        for (domain, _), result in zip(tasks, results):
            if result is True:
                valid.append(domain)
    return valid


async def post_stores_to_api(domains: list[str]):
    """Send discovered stores to Railway API for crawling."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # Trigger crawl via discover endpoint for each keyword batch
            for domain in domains[:10]:  # Just print, actual crawl is via API
                print(f"  ✅ Valid: {domain}")
    except Exception as e:
        print(f"API error: {e}")


async def main():
    print("🔍 Starting aggressive Shopify store discovery...")
    print(f"   Keywords: {len(SEARCH_KEYWORDS)}")
    print(f"   Templates: {len(QUERY_TEMPLATES[:2])} per keyword")
    print(f"   Total queries: ~{len(SEARCH_KEYWORDS) * 2}")
    print()

    # Load existing stores
    try:
        with open(STORES_PATH) as f:
            existing = json.load(f)
        existing_domains = {s["url"] for s in existing}
        print(f"📦 Existing curated stores: {len(existing_domains)}")
    except Exception:
        existing = []
        existing_domains = set()

    # Load previously discovered
    try:
        with open(OUTPUT_PATH) as f:
            prev_discovered = set(json.load(f))
        print(f"📦 Previously discovered: {len(prev_discovered)}")
    except Exception:
        prev_discovered = set()

    already_known = existing_domains | prev_discovered

    # Discover new stores
    print("\n🌐 Searching DuckDuckGo for Shopify stores...")
    found_domains = await search_ddg_for_stores(SEARCH_KEYWORDS, max_per_query=15)
    new_domains = found_domains - already_known

    print(f"\n✨ Found {len(found_domains)} total, {len(new_domains)} NEW domains")

    if not new_domains:
        print("No new stores found.")
        return

    # Validate in batches of 30
    print(f"\n🔍 Validating {len(new_domains)} domains (checking products.json)...")
    new_list = list(new_domains)
    valid_domains = []
    batch_size = 30

    for i in range(0, len(new_list), batch_size):
        batch = new_list[i:i+batch_size]
        print(f"  Validating batch {i//batch_size + 1}/{(len(new_list)-1)//batch_size + 1}...")
        valid = await validate_stores_batch(batch)
        valid_domains.extend(valid)
        print(f"  → {len(valid)} valid out of {len(batch)}")

    print(f"\n✅ {len(valid_domains)} valid Shopify stores found!")

    # Save to discovered file
    all_discovered = list(prev_discovered | set(valid_domains))
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_discovered, f, indent=2)
    print(f"💾 Saved {len(all_discovered)} total discovered stores to discovered_stores.json")

    # Also add to stores.json
    new_store_entries = []
    for domain in valid_domains:
        if domain not in existing_domains:
            new_store_entries.append({
                "name": domain.replace(".myshopify.com", "").replace("-", " ").title(),
                "url": domain,
                "category": "discovered"
            })

    if new_store_entries:
        existing.extend(new_store_entries)
        with open(STORES_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"✅ Added {len(new_store_entries)} new stores to stores.json")
        print(f"   Total stores now: {len(existing)}")
    else:
        print("No new stores to add to stores.json")

    # Trigger API crawl
    if valid_domains:
        print(f"\n🕷️  Triggering crawl of {len(valid_domains)} new stores via API...")
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(f"{API_BASE}/api/v1/crawl/start")
                print(f"   Crawl response: {r.status_code}")
        except Exception as e:
            print(f"   Crawl trigger error: {e}")

    print("\n🎉 Discovery complete!")
    print(f"   Total stores in database: {len(existing)}")


if __name__ == "__main__":
    asyncio.run(main())
