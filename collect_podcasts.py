#!/usr/bin/env python3
"""
Part 5: Podcast Transcript Scanner.
Only runs on Mondays. Generates search specs for agent to process.
"""

import sys
import json
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    TMP_DIR, get_date_str, is_monday, save_raw
)

PODCASTS = [
    {"name": "HBR Podcasts", "search_query": "hbr.org/podcast AI enterprise workforce organization"},
    {"name": "a16z Podcast", "url": "https://podscripts.co/podcasts/a16z-podcast/"},
    {"name": "McKinsey on AI", "url": "https://www.audioscrape.com/podcast/mckinsey-on-ai"},
    {"name": "The AI in Business (Emerj)", "url": "https://podcast.emergj.com/"},
    {"name": "Me, Myself, and AI (MIT SMR+BCG)", "search_query": '"Me Myself and AI" podcast transcript'},
]


def main():
    date_str = get_date_str()
    force = os.environ.get("FORCE", "") == "1"
    
    if not is_monday() and not force:
        print(f"Part 5: Not Monday ({date_str}), skipping podcast scan.")
        print(f"\nSUMMARY:{json.dumps({'date': date_str, 'source': 'podcasts', 'skipped': 'not monday'})}")
        return
    
    print(f"Part 5: Podcast Transcript Scan — {date_str}")
    print(f"  {len(PODCASTS)} podcast sources prepared for agent processing")
    
    podcasts_items = []
    for pod in PODCASTS:
        item = {"name": pod["name"]}
        if "search_query" in pod:
            item["search_query"] = pod["search_query"]
            item["type"] = "search"
        else:
            item["url"] = pod["url"]
            item["type"] = "list_page"
        item["_source"] = "podcast"
        item["_date"] = date_str
        podcasts_items.append(item)
    
    if podcasts_items:
        filename = f"podcast_scan_{date_str}.json"
        path = save_raw("podcasts", filename, podcasts_items)
        print(f"  Saved: {path}")
    
    print(f"\nSUMMARY:{json.dumps({'date': date_str, 'source': 'podcasts', 'podcasts': len(podcasts_items)})}")


if __name__ == "__main__":
    main()
