"""Merge commoncrawl_stores.json into stores.json (dedup)."""
import json

# Load existing curated
with open("data/stores.json") as f:
    existing = json.load(f)
existing_domains = {s["url"] for s in existing}
print(f"Existing: {len(existing_domains)} stores")

# Load commoncrawl
with open("data/commoncrawl_stores.json") as f:
    cc_domains = json.load(f)
print(f"CommonCrawl: {len(cc_domains)} domains")

# Add new ones
added = 0
for domain in cc_domains:
    if domain not in existing_domains:
        existing.append({
            "name": domain.replace(".myshopify.com", "").replace("-", " ").title(),
            "url": domain,
            "category": "discovered"
        })
        existing_domains.add(domain)
        added += 1

with open("data/stores.json", "w") as f:
    json.dump(existing, f, indent=2)

print(f"Added {added} new stores")
print(f"Total stores: {len(existing)}")
