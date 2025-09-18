import re
import time
import random
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

CITY_URL = "https://www.kijiji.ca/b-ottawa/l1700185"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

def clean_price(text: str) -> float | None:
    if not text:
        return None
    t = text.strip().lower()
    if "free" in t:
        return 0.0
    m = re.search(r"([\$€£]?\s*[\d,]+(?:\.\d{1,2})?)", t)
    if not m:
        return None
    num = m.group(1)
    num = num.replace("$", "").replace(",", "").strip()
    try:
        return float(num)
    except ValueError:
        return None

def extract_listings(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = []

    # Kijiji changes markup periodically; try a few reliable patterns.
    # 1) New-style result cards often use <a data-testid="listing-link"> or aria-label on the anchor
    for a in soup.select('a[data-testid="listing-link"], a[aria-label][href*="/v-"]'):
        title = a.get("aria-label") or a.get_text(strip=True)
        url = a.get("href") or ""
        if url.startswith("/"):
            url = "https://www.kijiji.ca" + url

        # price sometimes near the anchor; try sibling/ancestor patterns
        price_text = None
        price_candidates = []
        card_root = a.find_parent(["div", "li"]) or soup
        price_candidates += card_root.select('[data-testid="listing-price"], span[data-testid="ad-price"], div.price, span.price, p.price')
        if not price_candidates:
            # fallback: scan nearby text
            price_candidates += a.find_all_next("span", limit=4)

        for el in price_candidates:
            txt = el.get_text(" ", strip=True)
            if any(sym in txt for sym in ["$", "£", "€", "Free", "FREE", "free"]):
                price_text = txt
                break

        cards.append({
            "title": (title or "").strip(),
            "price_text": (price_text or "").strip(),
            "price": clean_price(price_text or ""),
            "url": url
        })

    # De-duplicate by URL
    seen = set()
    deduped = []
    for c in cards:
        if c["url"] and c["url"] not in seen:
            seen.add(c["url"])
            deduped.append(c)

    return deduped

def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-CA,en;q=0.9"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def main():
    html = fetch(CITY_URL)
    items = extract_listings(html)

    if not items:
        print("No listings parsed. The page structure may have changed.")
        return

    print(f"Found {len(items)} listings on first page.")
    for i, it in enumerate(items[:20], 1):
        print(f"{i}. {it['title']}  —  {it['price_text'] or 'N/A'}  —  {it['url']}")

    # Optional: write a CSV snapshot for quick inspection
    try:
        import csv
        from datetime import datetime
        fname = f"kijiji_ottawa_page1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["title", "price_text", "price", "url"])
            w.writeheader()
            for it in items:
                w.writerow(it)
        print(f"\nWrote CSV: {fname}")
    except Exception as e:
        print(f"CSV write failed: {e}")

if __name__ == "__main__":
    main()
