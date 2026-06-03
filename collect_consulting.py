#!/usr/bin/env python3
"""
Part 3: Consulting + Think Tank Scanner.
Only runs on Mondays (unless FORCE=1 env var set).

Fixes:
- consulting now outputs consulting_raw_{date}.json (compatible with filter_items.py)
- Items include actual search URLs for web_search
- Uses sources.yaml for content source configuration
"""

import sys
import json
import os
import datetime
import urllib.request
import urllib.error
import re
import html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    load_url_registry, is_duplicate, save_raw, get_date_str,
    is_monday, quick_relevance_check, guess_relevance_reason,
    load_sources, fetch_url,
)

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Dest": "document",
}


def fetch_page(url: str) -> str | None:
    """Fetch a webpage using unified fetch_url with Jina fallback."""
    return fetch_url(url, timeout=20)


def extract_article_links(html_text: str, base_url: str, source_name: str) -> list[dict]:
    """Extract article links from a list page HTML.

    Returns list of {title, url, source_name}.
    """
    items = []
    # Find all <a> tags with href containing typical article URL patterns
    # This is intentionally broad — filtering happens in Phase 2
    seen_urls = set()

    # Match <a href="...">title</a> patterns
    for m in re.finditer(r'href="([^"]*)"[^>]*>\s*([^<]{15,200}?)\s*<', html_text, re.IGNORECASE):
        href = m.group(1)
        title = html.unescape(m.group(2).strip())

        # Normalize URL
        if href.startswith("/"):
            parsed = urllib.parse.urlparse(base_url)
            href = f"{parsed.scheme}://{parsed.netloc}{href}"
        elif href.startswith("#") or href.startswith("javascript:"):
            continue
        elif href in seen_urls:
            continue

        # Filter out non-article links
        if len(title) < 15 or len(href) < 20:
            continue
        if any(x in href.lower() for x in ["/tag/", "/category/", "/author/", "/page/", "#"]):
            continue

        seen_urls.add(href)
        items.append({"title": title, "url": href, "source_name": source_name})

    return items


def serper_search(queries: list[str], api_key: str, num_days: str = "m") -> list[dict]:
    """Search via Serper.dev Google Search API.

    Args:
        queries: List of search query strings.
        api_key: Serper.dev API key.
        num_days: Time range suffix for tbs param (m=month, w=week, d=day).

    Returns:
        List of {title, link, snippet, date} from organic results.
    """
    import http.client

    payload = [{"q": q, "tbs": f"qdr:{num_days}"} for q in queries]
    body = json.dumps(payload)

    conn = http.client.HTTPSConnection("google.serper.dev")
    conn.request("POST", "/search", body, headers={
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    })
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    results = json.loads(raw)

    items = []
    for r in results:
        for organic in r.get("organic", []):
            items.append({
                "title": organic.get("title", ""),
                "url": organic.get("link", ""),
                "snippet": organic.get("snippet", ""),
                "date": organic.get("date", ""),
            })
    return items


def main():
    date_str = get_date_str()
    registry = load_url_registry()
    sources = load_sources()
    force = os.environ.get("FORCE", "") == "1"

    if not is_monday() and not force:
        print(f"Part 3: Not Monday ({date_str}), skipping consulting/think-tank scans.")
        print(f"\nSUMMARY:{json.dumps({'date': date_str, 'source': 'consulting', 'skipped': 'not monday'})}")
        return

    today = datetime.date.today()
    month_name = MONTH_NAMES[today.month]
    year = str(today.year)

    serper_key = os.environ.get("SERPER_API_KEY", "")
    if not serper_key:
        # Try loading from .env next to collector
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SERPER_API_KEY="):
                        serper_key = line.split("=", 1)[1].strip()
                        break
    if not serper_key:
        print("  [WARN] SERPER_API_KEY not found in env or .env, skipping consulting search.")

    # ── Part 3a: Consulting (via Serper Google Search) ──
    print(f"Part 3a: Consulting Report Search via Google (Serper) — {date_str}")
    consulting_cfg = sources.get("consulting", {})
    consulting_firms = consulting_cfg.get("firms", [])
    query_templates = consulting_cfg.get("search_queries", [])

    consulting_items = []
    search_queries_batch = []
    firm_for_q = []  # parallel list tracking which firm each query belongs to

    for firm in consulting_firms:
        for qtpl in query_templates:
            q = qtpl.replace("{firm}", firm).replace("{month}", month_name).replace("{year}", year)
            search_queries_batch.append(q)
            firm_for_q.append(firm)

    if serper_key and search_queries_batch:
        print(f"  Sending {len(search_queries_batch)} queries to Serper (batched)...")
        serper_results = serper_search(search_queries_batch, serper_key, num_days="m")

        # Re-map firm names — Serper returns results globally, we re-tag by domain heuristic
        # Simple approach: results are returned in query order, but we have to match back
        # Actually Serper returns per-query chunks; we'll process differently:
        # Serper's batch endpoint returns one result per query in order.
        pass  # We'll rebuild the mapping below

    # Better approach: search one firm at a time for clearer attribution
    for firm in consulting_firms:
        queries = [q.replace("{firm}", firm).replace("{month}", month_name).replace("{year}", year)
                   for q in query_templates]

        if not serper_key:
            break

        results = serper_search(queries, serper_key, num_days="m")
        print(f"  Searching: {firm} ({len(results)} results)")

        for r in results:
            url = r["url"]
            title = r["title"]

            if is_duplicate(url, registry):
                continue

            check = quick_relevance_check(title, r.get("snippet", ""))
            if check == "skip":
                continue

            item = {
                "title": title,
                "url": url,
                "snippet": r.get("snippet", ""),
                "firm": firm,
                "source_name": f"Consulting: {firm}",
                "_source": "consulting",
                "_date": date_str,
                "_relevance_quick": check,
            }
            consulting_items.append(item)
            print(f"    [{check}] {firm}: {title[:80]}")

    if consulting_items:
        filename = f"consulting_raw_{date_str}.json"
        path = save_raw("consulting", filename, consulting_items)
        print(f"  Saved: {path} ({len(consulting_items)} items)")
    else:
        print("  No new consulting items found.")

    # ── Part 3b: Think Tank / Journals (list page scan) ──
    print(f"\nPart 3b: Think Tank & Journal Scan — {date_str}")
    think_tank_sources = sources.get("thinktank", [])
    think_tank_items = []

    for src in think_tank_sources:
        name = src["name"]
        url = src["url"]
        print(f"  Scanning: {name} ({url})")

        html_text = fetch_page(url)
        if not html_text:
            continue

        links = extract_article_links(html_text, url, name)
        for link in links:
            if is_duplicate(link["url"], registry):
                continue

            check = quick_relevance_check(link["title"], "")
            if check == "skip":
                continue

            link["_source"] = "thinktank"
            link["_date"] = date_str
            link["_relevance_quick"] = check
            think_tank_items.append(link)
            print(f"    [{check}] {link['title'][:80]}")

    if think_tank_items:
        filename = f"thinktank_raw_{date_str}.json"
        path = save_raw("thinktank", filename, think_tank_items)
        print(f"  Saved: {path} ({len(think_tank_items)} items)")
    else:
        print("  No new think tank items found.")

    print(f"\nSUMMARY:{json.dumps({
        'date': date_str,
        'source': 'consulting+thinktank',
        'consulting_items': len(consulting_items),
        'thinktank_items': len(think_tank_items),
    })}")


if __name__ == "__main__":
    main()
