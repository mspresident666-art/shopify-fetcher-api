"""Fetch Shopify store domains from multiple CommonCrawl indexes."""
import json, ssl, urllib.request
from urllib.parse import urlparse

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

all_new = set()

sources = [
    "https://index.commoncrawl.org/CC-MAIN-2024-10-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2023-50-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2023-40-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2023-23-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2022-49-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2022-27-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2021-49-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2021-31-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
    "https://index.commoncrawl.org/CC-MAIN-2020-50-index?url=*.myshopify.com&output=text&fl=url&limit=5000",
]

for src in sources:
    try:
        req = urllib.request.urlopen(src, timeout=25, context=ctx)
        text = req.read().decode("utf-8", errors="ignore")
        before = len(all_new)
        for line in text.split("\n"):
            if "myshopify.com" in line:
                parsed = urlparse(line.strip())
                host = parsed.netloc.lower()
                if host.endswith(".myshopify.com") and len(host) > 15:
                    all_new.add(host)
        added = len(all_new) - before
        label = src.split("?")[0].split("/")[-1]
        print(f"+{added:4d} from {label} -> total {len(all_new)}")
    except Exception as e:
        label = src.split("?")[0].split("/")[-1]
        print(f"FAIL {label}: {str(e)[:60]}")

print(f"NEW domains found: {len(all_new)}")

# Merge with previous
try:
    with open("data/commoncrawl_stores.json") as f:
        prev = set(json.load(f))
    all_new |= prev
except:
    pass

with open("data/commoncrawl_stores.json", "w") as f:
    json.dump(sorted(list(all_new)), f)
print(f"Total saved: {len(all_new)}")
