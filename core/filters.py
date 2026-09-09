from typing import Optional


def parse_price(price_str) -> float:
    """Convert price string/number to float."""
    try:
        return float(str(price_str).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0


def get_variant_prices(product: dict) -> list[float]:
    """Get all variant prices from a product."""
    prices = []
    for variant in product.get("variants", []):
        price = parse_price(variant.get("price", 0))
        if price > 0:
            prices.append(price)
    return prices


def get_cheapest_price(product: dict) -> float:
    """Return the cheapest variant price."""
    prices = get_variant_prices(product)
    return min(prices) if prices else 0.0


def get_compare_at_prices(product: dict) -> list[float]:
    """Get all compare_at_price values from variants."""
    prices = []
    for variant in product.get("variants", []):
        cap = variant.get("compare_at_price")
        if cap:
            try:
                prices.append(float(str(cap).replace(",", "").strip()))
            except (ValueError, TypeError):
                pass
    return prices


def is_on_sale(product: dict) -> bool:
    """Check if any variant has a compare_at_price higher than price."""
    for variant in product.get("variants", []):
        price = parse_price(variant.get("price", 0))
        cap = parse_price(variant.get("compare_at_price") or 0)
        if cap > price > 0:
            return True
    return False


def is_available(product: dict) -> bool:
    """Check if any variant is available."""
    return any(v.get("available", False) for v in product.get("variants", []))


def filter_products(
    products: list,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    available_only: bool = False,
    on_sale: bool = False,
    q: Optional[str] = None,
    product_type: Optional[str] = None,
    vendor: Optional[str] = None,
) -> list:
    """Apply all filters to a product list."""
    filtered = []

    for p in products:
        cheapest = get_cheapest_price(p)

        # Price filters
        if min_price is not None and cheapest < min_price:
            continue
        if max_price is not None and cheapest > max_price:
            continue

        # Availability filter
        if available_only and not is_available(p):
            continue

        # On sale filter
        if on_sale and not is_on_sale(p):
            continue

        # Keyword search (title, tags, vendor, product_type)
        if q:
            q_lower = q.lower()
            searchable = " ".join([
                p.get("title", ""),
                p.get("vendor", ""),
                p.get("product_type", ""),
                " ".join(p.get("tags", [])),
            ]).lower()
            if q_lower not in searchable:
                continue

        # Product type filter
        if product_type:
            if product_type.lower() not in p.get("product_type", "").lower():
                continue

        # Vendor filter
        if vendor:
            if vendor.lower() not in p.get("vendor", "").lower():
                continue

        filtered.append(p)

    return filtered


def sort_products(products: list, sort: str = "default") -> list:
    """Sort products by given strategy."""
    if sort == "price-asc":
        return sorted(products, key=lambda p: get_cheapest_price(p))
    elif sort == "price-desc":
        return sorted(products, key=lambda p: get_cheapest_price(p), reverse=True)
    elif sort == "title-asc":
        return sorted(products, key=lambda p: p.get("title", "").lower())
    elif sort == "title-desc":
        return sorted(products, key=lambda p: p.get("title", "").lower(), reverse=True)
    elif sort == "newest":
        return sorted(products, key=lambda p: p.get("created_at", ""), reverse=True)
    elif sort == "oldest":
        return sorted(products, key=lambda p: p.get("created_at", ""))
    return products
