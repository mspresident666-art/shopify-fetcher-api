from core.filters import (
    parse_price,
    get_cheapest_price,
    is_on_sale,
    is_available,
)


def format_price(amount: float) -> str:
    """Format float price to dollar string."""
    return f"${amount:.2f}"


def build_checkout_url(store_domain: str, variant_id, quantity: int = 1) -> str:
    """Build a Shopify direct cart checkout URL."""
    domain = store_domain.rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/cart/{variant_id}:{quantity}"


def build_product_url(store_domain: str, handle: str) -> str:
    """Build a Shopify product page URL."""
    domain = store_domain.rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/products/{handle}"


def format_variant(variant: dict, store_domain: str) -> dict:
    """Format a single product variant with checkout info."""
    price = parse_price(variant.get("price", 0))
    cap = parse_price(variant.get("compare_at_price") or 0)
    has_discount = cap > price > 0
    discount_amount = cap - price if has_discount else 0.0

    return {
        "variant_id": variant.get("id"),
        "title": variant.get("title", ""),
        "sku": variant.get("sku", ""),
        "price": format_price(price),
        "compare_at_price": format_price(cap) if cap > 0 else None,
        "has_discount": has_discount,
        "discount_amount": format_price(discount_amount) if has_discount else None,
        "available": variant.get("available", False),
        "weight": f"{variant.get('weight', 0)}{variant.get('weight_unit', 'g')}",
        "checkout_url": build_checkout_url(store_domain, variant.get("id")),
        "checkout_price": format_price(price),
        "option1": variant.get("option1"),
        "option2": variant.get("option2"),
        "option3": variant.get("option3"),
    }


def format_product(product: dict, store_domain: str) -> dict:
    """
    Add _checkout field to a raw Shopify product.
    Preserves all original Shopify fields.
    """
    variants = product.get("variants", [])
    images = product.get("images", [])

    # Find cheapest available variant, else just cheapest
    available_variants = [v for v in variants if v.get("available", False)]
    target_variants = available_variants if available_variants else variants

    if not target_variants:
        # No variants at all
        product["_checkout"] = {}
        return product

    # Find cheapest
    cheapest_variant = min(
        target_variants,
        key=lambda v: parse_price(v.get("price", 0))
    )

    cheapest_price = parse_price(cheapest_variant.get("price", 0))
    all_prices = [parse_price(v.get("price", 0)) for v in variants if parse_price(v.get("price", 0)) > 0]
    max_price = max(all_prices) if all_prices else 0.0

    # Discount calculation
    on_sale = is_on_sale(product)
    discount_percent = 0
    if on_sale:
        cap = parse_price(cheapest_variant.get("compare_at_price") or 0)
        if cap > cheapest_price > 0:
            discount_percent = round((1 - cheapest_price / cap) * 100)

    # Main image
    main_image = images[0].get("src", "") if images else ""

    # Format all variants
    formatted_variants = [format_variant(v, store_domain) for v in variants]

    product["_checkout"] = {
        "product_url": build_product_url(store_domain, product.get("handle", "")),
        "main_image": main_image,
        "cheapest_checkout_url": build_checkout_url(store_domain, cheapest_variant.get("id")),
        "cheapest_checkout_price": format_price(cheapest_price),
        "cheapest_variant_id": cheapest_variant.get("id"),
        "cheapest_variant_title": cheapest_variant.get("title", ""),
        "price_range": {
            "min": format_price(cheapest_price),
            "max": format_price(max_price),
        },
        "total_variants": len(variants),
        "available_variants": len(available_variants),
        "sold_out": len(available_variants) == 0,
        "on_sale": on_sale,
        "discount_percent": discount_percent,
        "variant_checkouts": formatted_variants,
    }

    return product


def build_price_summary(products: list) -> dict:
    """Build price bucket summary for bulk response meta."""
    buckets = {"under_1": 0, "under_5": 0, "under_10": 0, "under_25": 0, "under_50": 0, "over_100": 0}
    for p in products:
        price = get_cheapest_price(p)
        if price < 1:
            buckets["under_1"] += 1
        if price < 5:
            buckets["under_5"] += 1
        if price < 10:
            buckets["under_10"] += 1
        if price < 25:
            buckets["under_25"] += 1
        if price < 50:
            buckets["under_50"] += 1
        if price > 100:
            buckets["over_100"] += 1
    return buckets
