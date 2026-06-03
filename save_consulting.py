#!/usr/bin/env python3
"""
Save step for consulting/thinktank results.
Reads agent-produced results from tmp, indexes URLs.
"""

import sys
import json
import os
import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import (
    REPORTS_DIR, TMP_DIR, append_to_url_registry,
    update_daily_summary, get_date_str, is_monday
)


def main():
    date_str = get_date_str()
    new_urls = []
    saved_count = 0
    
    # Check for consulting results
    consulting_dir = TMP_DIR / "consulting"
    if consulting_dir.exists():
        result_files = sorted(consulting_dir.glob(f"consulting_results_{date_str}.json"))
        if result_files:
            with open(result_files[-1]) as f:
                results = json.load(f)
            # Results should contain the saved URLs
            urls = results if isinstance(results, list) else results.get("urls", [])
            if urls:
                new_urls.extend(urls)
                saved_count += len(urls)
            print(f"  Consulting: {len(urls)} new items")
    
    # Check for thinktank results
    thinktank_dir = TMP_DIR / "thinktank"
    if thinktank_dir.exists():
        result_files = sorted(thinktank_dir.glob(f"thinktank_results_{date_str}.json"))
        if result_files:
            with open(result_files[-1]) as f:
                results = json.load(f)
            urls = results if isinstance(results, list) else results.get("urls", [])
            if urls:
                new_urls.extend(urls)
                saved_count += len(urls)
            print(f"  Think Tank: {len(urls)} new items")
    
    if new_urls:
        append_to_url_registry(new_urls)
        print(f"  Appended {len(new_urls)} URLs to registry")
    
    update_daily_summary(date_str, "Part 3+4: Consulting & Think Tanks", {
        "saved": saved_count,
    })
    
    print(f"\nSUMMARY:{json.dumps({'date': date_str, 'source': 'consulting_save', 'saved': saved_count})}")


if __name__ == "__main__":
    main()
