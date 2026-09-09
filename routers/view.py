from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from typing import Optional

from core.fetcher import fetch_store_products
from core.filters import filter_products, sort_products
from core.formatter import format_product
from core.filters import get_cheapest_price

router = APIRouter()


def render_html(products: list, store: str, filters_info: str) -> str:
    total = len(products)

    cards_html = ""
    for p in products:
        c = p.get("_checkout", {})
        title = p.get("title", "No title")
        vendor = p.get("vendor", "")
        product_type = p.get("product_type", "")
        image = c.get("main_image", "")
        price = c.get("cheapest_checkout_price", "N/A")
        checkout_url = c.get("cheapest_checkout_url", "#")
        product_url = c.get("product_url", "#")
        on_sale = c.get("on_sale", False)
        discount = c.get("discount_percent", 0)
        sold_out = c.get("sold_out", False)
        available_v = c.get("available_variants", 0)
        total_v = c.get("total_variants", 0)
        price_range = c.get("price_range", {})
        price_min = price_range.get("min", price)
        price_max = price_range.get("max", price)

        # Badge
        badge = ""
        if sold_out:
            badge = '<span class="badge sold-out">SOLD OUT</span>'
        elif on_sale and discount:
            badge = f'<span class="badge sale">-{discount}%</span>'
        elif on_sale:
            badge = '<span class="badge sale">SALE</span>'

        # Price display
        price_html = f'<span class="price">{price}</span>'
        if price_min != price_max:
            price_html = f'<span class="price">{price_min} – {price_max}</span>'

        # Image
        img_html = f'<img src="{image}" alt="{title}" loading="lazy" onerror="this.src=\'https://placehold.co/300x300/1a1a2e/ffffff?text=No+Image\'">' if image else '<div class="no-img">No Image</div>'

        # Checkout button
        btn_class = "btn-disabled" if sold_out else "btn-checkout"
        btn_text = "Sold Out" if sold_out else "🛒 Checkout"
        btn_href = "#" if sold_out else checkout_url

        cards_html += f"""
        <div class="card {'sold-out-card' if sold_out else ''}">
            <a href="{product_url}" target="_blank" class="card-img-link">
                {img_html}
                {badge}
            </a>
            <div class="card-body">
                <div class="vendor">{vendor}</div>
                <a href="{product_url}" target="_blank" class="card-title">{title}</a>
                <div class="type">{product_type}</div>
                <div class="price-row">
                    {price_html}
                    <span class="stock">{'✅' if not sold_out else '❌'} {available_v}/{total_v} variant</span>
                </div>
                <a href="{btn_href}" target="_blank" class="btn {btn_class}">{btn_text}</a>
            </div>
        </div>"""

    if not cards_html:
        cards_html = '<div class="no-results">😔 Tidak ada produk yang ditemukan dengan filter ini.</div>'

    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SYF — {store}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            min-height: 100vh;
        }}
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-bottom: 1px solid #2a2a4a;
            padding: 20px 30px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .logo {{
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(90deg, #7c3aed, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: 1px;
        }}
        .store-name {{
            font-size: 14px;
            color: #94a3b8;
        }}
        .store-name span {{
            color: #7c3aed;
            font-weight: 600;
        }}
        .stats {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .stat {{
            background: #1e1e3a;
            border: 1px solid #2a2a4a;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            text-align: center;
        }}
        .stat strong {{
            display: block;
            font-size: 20px;
            color: #7c3aed;
        }}
        .filters-bar {{
            background: #12122a;
            padding: 14px 30px;
            border-bottom: 1px solid #2a2a4a;
            font-size: 13px;
            color: #64748b;
        }}
        .filters-bar span {{
            color: #94a3b8;
            margin-left: 8px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 20px;
            padding: 28px 30px;
            max-width: 1600px;
            margin: 0 auto;
        }}
        .card {{
            background: #1a1a2e;
            border: 1px solid #2a2a4a;
            border-radius: 14px;
            overflow: hidden;
            transition: transform 0.2s, border-color 0.2s;
            display: flex;
            flex-direction: column;
        }}
        .card:hover {{
            transform: translateY(-4px);
            border-color: #7c3aed;
        }}
        .sold-out-card {{
            opacity: 0.6;
        }}
        .card-img-link {{
            display: block;
            position: relative;
            background: #0f0f1a;
            aspect-ratio: 1;
            overflow: hidden;
        }}
        .card-img-link img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s;
        }}
        .card:hover .card-img-link img {{
            transform: scale(1.05);
        }}
        .no-img {{
            width: 100%;
            height: 100%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #4a4a6a;
            font-size: 13px;
        }}
        .badge {{
            position: absolute;
            top: 10px;
            left: 10px;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .badge.sale {{
            background: #7c3aed;
            color: white;
        }}
        .badge.sold-out {{
            background: #475569;
            color: white;
        }}
        .card-body {{
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            flex: 1;
        }}
        .vendor {{
            font-size: 11px;
            color: #7c3aed;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            color: #e2e8f0;
            text-decoration: none;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }}
        .card-title:hover {{
            color: #7c3aed;
        }}
        .type {{
            font-size: 11px;
            color: #475569;
        }}
        .price-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 4px;
        }}
        .price {{
            font-size: 18px;
            font-weight: 700;
            color: #06b6d4;
        }}
        .stock {{
            font-size: 11px;
            color: #64748b;
        }}
        .btn {{
            display: block;
            text-align: center;
            padding: 10px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            text-decoration: none;
            margin-top: 8px;
            transition: opacity 0.2s;
        }}
        .btn-checkout {{
            background: linear-gradient(135deg, #7c3aed, #06b6d4);
            color: white;
        }}
        .btn-checkout:hover {{
            opacity: 0.85;
        }}
        .btn-disabled {{
            background: #2a2a4a;
            color: #475569;
            cursor: not-allowed;
        }}
        .no-results {{
            grid-column: 1 / -1;
            text-align: center;
            padding: 60px;
            color: #475569;
            font-size: 18px;
        }}
        footer {{
            text-align: center;
            padding: 24px;
            color: #2a2a4a;
            font-size: 12px;
            border-top: 1px solid #1a1a2e;
        }}
        @media (max-width: 600px) {{
            .grid {{ padding: 16px; gap: 14px; }}
            header {{ padding: 16px; }}
        }}
    </style>
</head>
<body>
    <header>
        <div>
            <div class="logo">⚡ SYF — Shopify Fetcher</div>
            <div class="store-name">Store: <span>{store}</span></div>
        </div>
        <div class="stats">
            <div class="stat"><strong>{total}</strong>Produk</div>
            <div class="stat"><strong>{len([p for p in products if p.get('_checkout', {}).get('on_sale')])}</strong>Diskon</div>
            <div class="stat"><strong>{len([p for p in products if not p.get('_checkout', {}).get('sold_out')])}</strong>Tersedia</div>
        </div>
    </header>
    <div class="filters-bar">
        🔍 Filter aktif: <span>{filters_info}</span>
        &nbsp;|&nbsp;
        <a href="/docs" target="_blank" style="color:#7c3aed">📖 API Docs</a>
    </div>
    <div class="grid">
        {cards_html}
    </div>
    <footer>SYF — Shopify Product Fetcher API v1.0 &nbsp;|&nbsp; {total} produk ditampilkan</footer>
</body>
</html>"""


@router.get("/view", response_class=HTMLResponse)
async def view_products(
    url: str = Query(..., description="Shopify store URL"),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    available: Optional[bool] = Query(None),
    on_sale: Optional[bool] = Query(None),
    q: Optional[str] = Query(None),
    sort: str = Query("price-asc"),
    limit: int = Query(250, ge=1, le=6250),
    type: Optional[str] = Query(None),
    vendor: Optional[str] = Query(None),
):
    # Fetch
    result = await fetch_store_products(url)
    raw = result.get("products", [])
    domain = result.get("domain", url)
    error = result.get("error")

    if error:
        return HTMLResponse(f"""
        <html><body style="background:#0f0f1a;color:#e0e0e0;font-family:sans-serif;padding:40px;text-align:center">
        <h2 style="color:#ef4444">❌ Gagal fetch toko</h2>
        <p>{error}</p>
        <p><a href="javascript:history.back()" style="color:#7c3aed">← Kembali</a></p>
        </body></html>
        """, status_code=502)

    # Filter
    filtered = filter_products(
        raw,
        min_price=min_price,
        max_price=max_price,
        available_only=available or False,
        on_sale=on_sale or False,
        q=q,
        product_type=type,
        vendor=vendor,
    )

    # Sort & limit
    filtered = sort_products(filtered, sort)[:limit]

    # Format
    products = [format_product(p, domain) for p in filtered]

    # Build filter description
    parts = []
    if min_price is not None:
        parts.append(f"min ${min_price}")
    if max_price is not None:
        parts.append(f"max ${max_price}")
    if available:
        parts.append("tersedia")
    if on_sale:
        parts.append("diskon")
    if q:
        parts.append(f'keyword "{q}"')
    if sort != "default":
        parts.append(f"sort: {sort}")
    filters_info = ", ".join(parts) if parts else "tidak ada filter"

    return HTMLResponse(render_html(products, url, filters_info))
