#!/usr/bin/env python3
"""
Part 1: RSS Feed Processor.
Fetches RSS feeds → saves raw items as JSON → ready for agent filtering.
"""

import sys
import json
import os
import datetime
import feedparser
import urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    load_url_registry, is_duplicate, save_raw, get_date_str,
    quick_relevance_check, guess_relevance_reason, TOPIC_KW_MAP,
    get_sources,
)

# RSS Feeds config — now loaded from sources.yaml
RSS_FEEDS = get_sources("rss")


def fetch_rss(url: str, max_items: int = 20):
    """Fetch and parse an RSS feed."""
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            item = {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "date": entry.get("published", entry.get("updated", "")),
                "summary": entry.get("summary", "")[:2000],
                "source_name": feed.feed.get("title", url),
                "source_url": url,
            }
            items.append(item)
        return items
    except Exception as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return []


def main():
    date_str = get_date_str()
    registry = load_url_registry()
    today_year_month = datetime.date.today().strftime("%Y-%m")

    all_raw_items = []
    skipped_dupes = 0
    skipped_filter = 0
    maybe_count = 0

    print(f"Part 1: RSS Feed Processing — {date_str}")

    for feed in RSS_FEEDS:
        name = feed["name"]
        url = feed["url"]
        priority = feed.get("priority", "medium")

        print(f"  Fetching: {name} ({url})")
        items = fetch_rss(url)

        for item in items:
            item_url = item["url"].strip()

            # Dedup check
            if is_duplicate(item_url, registry):
                skipped_dupes += 1
                continue

            # Quick relevance check
            check = quick_relevance_check(item["title"], item["summary"])
            if check == "skip":
                skipped_filter += 1
                continue

            item["_relevance_quick"] = check
            item["_relevance_reason"] = guess_relevance_reason(item["title"], item["summary"])
            item["_source"] = "rss"

            if check == "maybe":
                maybe_count += 1
            all_raw_items.append(item)

    print(f"\n  Results: {len(all_raw_items)} new items (pass/maybe)")
    print(f"  Filtered out: {skipped_dupes} dupes, {skipped_filter} by filter")
    print(f"  Needs agent review: {maybe_count}")

    if all_raw_items:
        filename = f"rss_raw_{date_str}.json"
        path = save_raw("rss", filename, all_raw_items)
        print(f"  Saved: {path}")
    else:
        print("  No new items to process.")

    # Summary output (consumed by save step)
    summary = {
        "date": date_str,
        "source": "rss",
        "total_new": len(all_raw_items),
        "skipped_dupes": skipped_dupes,
        "skipped_filter": skipped_filter,
        "needs_agent": maybe_count,
    }
    print(f"\nSUMMARY:{json.dumps(summary)}")


if __name__ == "__main__":
    main()
