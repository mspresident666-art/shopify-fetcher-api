"""
Database connection and product storage for the Shopify product index.
Uses PostgreSQL on Railway, with automatic table creation on startup.
"""
import os
import asyncio
import asyncpg
from typing import Optional
import json

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pool


async def init_db():
    """Create tables if they don't exist."""
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not set — database features disabled")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS stores (
                id SERIAL PRIMARY KEY,
                domain VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                category VARCHAR(100) DEFAULT 'general',
                last_crawled TIMESTAMP,
                status VARCHAR(50) DEFAULT 'pending',
                product_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id BIGINT NOT NULL,
                store_domain VARCHAR(255) NOT NULL,
                title TEXT,
                vendor VARCHAR(255),
                product_type VARCHAR(255),
                price_min DECIMAL(10,2),
                price_max DECIMAL(10,2),
                compare_price DECIMAL(10,2),
                image_url TEXT,
                product_url TEXT,
                checkout_url TEXT,
                variant_id BIGINT,
                available BOOLEAN DEFAULT TRUE,
                on_sale BOOLEAN DEFAULT FALSE,
                discount_percent INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (id, store_domain)
            )
        """)

        # Full-text search index on title
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS products_title_fts
            ON products USING gin(to_tsvector('english', COALESCE(title, '')))
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS products_price_idx ON products(price_min)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS products_store_idx ON products(store_domain)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS products_available_idx ON products(available)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS products_on_sale_idx ON products(on_sale)
        """)

    print(f"✅ Database initialized")


async def upsert_store(domain: str, name: str = "", category: str = "general"):
    """Add or update a store in the database."""
    if not DATABASE_URL:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO stores (domain, name, category)
            VALUES ($1, $2, $3)
            ON CONFLICT (domain) DO UPDATE
            SET name = COALESCE(EXCLUDED.name, stores.name)
        """, domain, name, category)


async def save_products(store_domain: str, products: list[dict]):
    """Save/update products for a store in the database."""
    if not DATABASE_URL or not products:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Update store crawl time and product count
        await conn.execute("""
            UPDATE stores SET last_crawled = NOW(), status = 'active',
            product_count = $2 WHERE domain = $1
        """, store_domain, len(products))

        # Upsert each product
        for p in products:
            try:
                checkout = p.get("_checkout") or {}
                price_str = checkout.get("cheapest_checkout_price", "$0").replace("$", "").replace(",", "")
                compare_str = ""
                for v in (checkout.get("variant_checkouts") or []):
                    if v.get("has_discount"):
                        compare_str = v.get("compare_at_price", "").replace("$", "").replace(",", "")
                        break

                price_min = float(price_str) if price_str else 0.0
                compare_price = float(compare_str) if compare_str else None
                img = checkout.get("main_image") or ""
                product_url = checkout.get("product_url") or ""
                checkout_url = checkout.get("cheapest_checkout_url") or ""
                variant_id = checkout.get("cheapest_variant_id")

                available = not checkout.get("sold_out", False)
                on_sale = bool(checkout.get("on_sale", False))
                discount = checkout.get("discount_percent", 0) or 0

                await conn.execute("""
                    INSERT INTO products
                    (id, store_domain, title, vendor, product_type,
                     price_min, price_max, compare_price,
                     image_url, product_url, checkout_url, variant_id,
                     available, on_sale, discount_percent, last_updated)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,NOW())
                    ON CONFLICT (id, store_domain) DO UPDATE SET
                        title = EXCLUDED.title,
                        price_min = EXCLUDED.price_min,
                        image_url = EXCLUDED.image_url,
                        product_url = EXCLUDED.product_url,
                        checkout_url = EXCLUDED.checkout_url,
                        variant_id = EXCLUDED.variant_id,
                        available = EXCLUDED.available,
                        on_sale = EXCLUDED.on_sale,
                        discount_percent = EXCLUDED.discount_percent,
                        last_updated = NOW()
                """, p["id"], store_domain,
                    p.get("title", ""), p.get("vendor", ""), p.get("product_type", ""),
                    price_min, price_min, compare_price,
                    img, product_url, checkout_url,
                    int(variant_id) if variant_id else None,
                    available, on_sale, int(discount))
            except Exception:
                continue


async def search_products_db(
    keyword: str,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    available_only: bool = False,
    on_sale: bool = False,
    sort: str = "price-asc",
    limit: int = 50,
    per_store_limit: int = 3,
) -> tuple[list[dict], int]:
    """Search products in database using full-text search. Returns (products, total_count)."""
    if not DATABASE_URL:
        return [], 0

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build WHERE clause
        conditions = ["to_tsvector('english', COALESCE(title, '')) @@ plainto_tsquery('english', $1)"]
        params: list = [keyword]
        idx = 2

        if min_price is not None:
            conditions.append(f"price_min >= ${idx}")
            params.append(min_price)
            idx += 1
        if max_price is not None:
            conditions.append(f"price_min <= ${idx}")
            params.append(max_price)
            idx += 1
        if available_only:
            conditions.append("available = TRUE")
        if on_sale:
            conditions.append("on_sale = TRUE")

        where = " AND ".join(conditions)

        # Sort
        order = {
            "price-asc": "price_min ASC",
            "price-desc": "price_min DESC",
            "newest": "last_updated DESC",
            "title-asc": "title ASC",
        }.get(sort, "price_min ASC")

        # Use RANK() to limit per store
        query = f"""
            WITH ranked AS (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY store_domain
                        ORDER BY {order}
                    ) AS rn,
                    ts_rank(to_tsvector('english', COALESCE(title, '')),
                            plainto_tsquery('english', $1)) AS rank
                FROM products
                WHERE {where}
            )
            SELECT * FROM ranked WHERE rn <= $idx_per_store
            ORDER BY {order}
            LIMIT $idx_limit
        """.replace("$idx_per_store", f"${idx}").replace("$idx_limit", f"${idx+1}")

        params.append(per_store_limit)
        params.append(limit)

        try:
            rows = await conn.fetch(query, *params)
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM products WHERE {where}", *params[:-2]
            )
            return [dict(r) for r in rows], total or 0
        except Exception as e:
            print(f"DB search error: {e}")
            return [], 0


async def get_db_stats() -> dict:
    """Get database statistics."""
    if not DATABASE_URL:
        return {"enabled": False}
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            store_count = await conn.fetchval("SELECT COUNT(*) FROM stores WHERE status = 'active'")
            product_count = await conn.fetchval("SELECT COUNT(*) FROM products")
            last_crawl = await conn.fetchval("SELECT MAX(last_crawled) FROM stores")
            return {
                "enabled": True,
                "indexed_stores": store_count or 0,
                "indexed_products": product_count or 0,
                "last_crawl": str(last_crawl) if last_crawl else None,
            }
    except Exception as e:
        return {"enabled": False, "error": str(e)}
