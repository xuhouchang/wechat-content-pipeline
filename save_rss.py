#!/usr/bin/env python3
"""
Save step for RSS items after agent filtering.
Merges filter verdicts with raw data via index, downloads content, saves MD files.
"""

import sys
import json
import os
import datetime
import urllib.request
import re
import html as html_mod
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    REPORTS_DIR, TMP_DIR, append_to_url_registry,
    update_daily_summary, get_date_str, slugify
)

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def fetch_full_content(url: str) -> str | None:
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        body = body_match.group(1) if body_match else html
        body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
        body = re.sub(r'</?(?:p|div|h[1-6]|li|br|tr|blockquote|article|section)[^>]*>', '\n', body)
        text = html_mod.unescape(body)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text[:50000].strip() if len(text) > 50000 else text.strip()
    except Exception:
        return None


def merge_with_raw(filtered: list, raw: list) -> list:
    """Merge filter verdicts into raw items by index."""
    raw_by_index = {i: item for i, item in enumerate(raw)}
    merged = []
    for fitem in filtered:
        idx = fitem.get("index", -1)
        if idx < 0 or idx not in raw_by_index:
            continue
        if fitem.get("verdict") != "pass":
            continue
        item = dict(raw_by_index[idx])  # copy
        item["topics"] = fitem.get("topics", [])
        item["verdict"] = "pass"
        item["_filter_reason"] = fitem.get("reason", "")
        merged.append(item)
    return merged


def main():
    date_str = get_date_str()
    today = datetime.date.today()

    raw_dir = TMP_DIR / "rss"
    if not raw_dir.exists():
        print("No rss tmp dir"); sys.exit(0)

    filtered_files = sorted(raw_dir.glob(f"rss_filtered_{date_str}.json"))
    raw_files = sorted(raw_dir.glob(f"rss_raw_{date_str}.json"))

    items = []

    if filtered_files and raw_files:
        with open(filtered_files[-1]) as f:
            filtered = json.load(f)
        with open(raw_files[-1]) as f:
            raw = json.load(f)
        items = merge_with_raw(filtered, raw)
        print(f"Agent-filtered: {len(items)} merged from {len(filtered)} verdicts / {len(raw)} raw")
    elif raw_files:
        with open(raw_files[-1]) as f:
            raw = json.load(f)
        items = [i for i in raw if i.get("_relevance_quick") == "pass"]
        print(f"Quick-pass fallback: {len(items)} items")
    else:
        print("No RSS data"); sys.exit(0)

    if not items:
        print("No items passed filter, nothing to save"); sys.exit(0)

    saved = 0
    new_urls = []

    for item in items:
        url = (item.get("url") or "").strip()
        if not url:
            continue

        source_name = (item.get("source_name") or "unknown").split("(")[0].strip()
        source_slug = slugify(source_name)
        item_slug = slugify((item.get("title") or "untitled")[:40])

        save_dir = REPORTS_DIR / "newsletters" / source_slug / today.strftime("%Y-%m")
        save_dir.mkdir(parents=True, exist_ok=True)

        full_content = fetch_full_content(url)
        # ── Content size guard: skip URLs whose content is too thin ──
        content_text = full_content or item.get("summary") or ""
        if len(content_text.strip()) < 200:
            print(f"  ⏭️  Content too short ({len(content_text.strip())} chars): {url[:60]}")
            continue

        topics = item.get("topics", [])
        topics_str = json.dumps(list(topics))

        md = f"""---
title: "{item.get('title', 'Untitled')}"
source: "{source_name}"
source_type: newsletter
date: {item.get('date', date_str)}
url: {url}
topics: {topics_str}
relevance: high
---

{content_text}

---

*Collected by research-report-collector on {date_str}*
"""
        filepath = save_dir / f"{date_str}_{source_slug}_{item_slug}.md"
        with open(filepath, "w") as f:
            f.write(md)
        saved += 1
        new_urls.append(url)
        print(f"  Saved: {filepath.name}")

    if new_urls:
        append_to_url_registry(new_urls)

    update_daily_summary(date_str, "Part 1: RSS Feeds", {"saved": saved})
    print(f"\n  Done: {saved} RSS items saved")


if __name__ == "__main__":
    main()
