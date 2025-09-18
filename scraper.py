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
PAGES = 3               # how many result pages to fetch
SLEEP_SEC = (1.0, 2.0)  # polite delay window between requests (min, max)


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

    # Find only real listing anchors; skip gallery/image-number links
    for a in soup.select('a[href*="/v-"]'):
        href = a.get("href") or ""
        if "imageNumber=" in href:
            continue

        # Get title from aria-label if present, fallback to text
        title = a.get("aria-label") or a.get_text(" ", strip=True)
        if not title:
            continue
        if title.lower().startswith("open the picture"):
            continue

        # Build absolute URL
        url = href
        if url.startswith("/"):
            url = "https://www.kijiji.ca" + url

        # Try to find a nearby price element
        price_text = None
        root = a.find_parent(["div", "li"]) or soup
        for el in root.select('[data-testid="listing-price"], span[data-testid="ad-price"], div.price, span.price, p.price'):
            txt = el.get_text(" ", strip=True)
            if any(sym in txt for sym in ["$", "€", "£", "Free", "free", "FREE"]):
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
        u = c.get("url")
        if u and u not in seen:
            seen.add(u)
            deduped.append(c)
    return deduped


def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-CA,en;q=0.9"}
    r = requests.get(url, headers=headers, timeout=20)
    r.raise_for_status()
    return r.text

def main():
    all_items = []
    for page in range(1, PAGES + 1):
        if "?" in CITY_URL:
            url = f"{CITY_URL}&page={page}"
        else:
            url = f"{CITY_URL}?page={page}"

        print(f"Fetching page {page}: {url}")
        html = fetch(url)
        items = extract_listings(html)
        print(f"  -> {len(items)} items")
        all_items.extend(items)

        time.sleep(random.uniform(*SLEEP_SEC))

    if not all_items:
        print("No listings parsed. The page structure may have changed.")
        return

    print(f"\nFound {len(all_items)} total listings across {PAGES} pages.")
    save_to_db(all_items)
    print("Saved to database: deals.db")

    for i, it in enumerate(all_items[:20], 1):
        print(f"{i}. {it['title']}  —  {it['price_text'] or 'N/A'}  —  {it['url']}")

    # CSV snapshot
    try:
        import csv
        from datetime import datetime
        fname = f"kijiji_ottawa_page1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["title", "price_text", "price", "url"])
            w.writeheader()
            for it in all_items:
                w.writerow(it)
        print(f"\nWrote CSV: {fname}")
    except Exception as e:
        print(f"CSV write failed: {e}")


import sqlite3

def save_to_db(items):
    conn = sqlite3.connect("deals.db")
    cur = conn.cursor()
    for it in items:
        cur.execute("""
            INSERT OR IGNORE INTO listings (title, price_text, price, url)
            VALUES (?, ?, ?, ?)
            """, (it["title"], it["price_text"], it["price"], it["url"]))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
