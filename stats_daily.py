#!/usr/bin/env python3
"""
Daily stats collector — 每天采集完成后统计有效素材数量。

统计维度：
- 有效素材总数（有内容 ≥300 chars 的 collected URL）
- 今日新增有效素材数
- 按来源域名分布
- 素材使用率（used / collected）
- 各 Newsletter/Blog 来源活跃度

用法：
  python3 stats_daily.py              # 默认统计到今天
  python3 stats_daily.py --date 2026-05-24
  python3 stats_daily.py --trend      # 输出近7天趋势
  python3 stats_daily.py --json       # JSON 输出，方便其他程序消费
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

COLLECTOR_DIR = Path(__file__).parent
REPORTS_DIR = (COLLECTOR_DIR / ".." / "reports").resolve()
ALL_URLS_TSV = REPORTS_DIR / "_index" / "all_urls.tsv"
RECENT_TOPICS_JSON = REPORTS_DIR / "_index" / "_recent_topics.json"
DAILY_STATS_DIR = REPORTS_DIR / "_index" / "daily-stats"

STUB_STRINGS = {"No content available", ""}


# ── Read all_urls.tsv ──

def load_url_registry() -> list[dict]:
    """Load all URLs from tsv with status."""
    entries = []
    if not ALL_URLS_TSV.exists():
        return entries
    with open(ALL_URLS_TSV, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            url = parts[0]
            status = parts[1] if len(parts) >= 2 else "collected"
            date = parts[2] if len(parts) >= 3 else "unknown"
            entries.append({"url": url, "status": status, "date": date})
    return entries


def read_file_content(url: str) -> str | None:
    """Find the report markdown file for a URL and return its content."""
    from lib.materials import find_report_file
    f = find_report_file(url)
    if not f:
        return None
    try:
        return f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def is_valid_content(content: str | None) -> bool:
    """Check if content is substantive (≥300 chars, not a stub)."""
    if not content:
        return False
    stripped = content.strip()
    if not stripped:
        return False
    if stripped in STUB_STRINGS:
        return False
    if len(stripped) < 300:
        return False
    return True


# ── Stats ──

def compute_stats(entries: list[dict]) -> dict:
    """Compute statistics from url registry entries."""
    total = len(entries)
    collected = [e for e in entries if e["status"] == "collected"]
    used = [e for e in entries if e["status"] == "used"]
    broken = [e for e in entries if e["status"] == "broken"]

    # Count valid collected (has actual content)
    valid_collected = 0
    content_sizes = []
    domain_counter = Counter()
    domain_valid = Counter()
    domain_invalid = Counter()

    for e in collected:
        content = read_file_content(e["url"])
        if is_valid_content(content):
            valid_collected += 1
            domain = e["url"].split("/")[2]
            domain_valid[domain] += 1
            if content:
                content_sizes.append(len(content.strip()))
        else:
            domain = e["url"].split("/")[2]
            domain_invalid[domain] += 1

    domain_counter.update(e["url"].split("/")[2] for e in collected)

    stats = {
        "total": total,
        "collected": len(collected),
        "valid_collected": valid_collected,
        "used": len(used),
        "broken": len(broken),
        "usage_rate": round(len(used) / max(total, 1) * 100, 1),
        "content_sizes": {
            "min": min(content_sizes) if content_sizes else 0,
            "max": max(content_sizes) if content_sizes else 0,
            "avg": round(sum(content_sizes) / max(len(content_sizes), 1)) if content_sizes else 0,
            "total_chars": sum(content_sizes) if content_sizes else 0,
        },
        "stub_entries": len(collected) - valid_collected,
        "domains": {},
    }

    # Per-domain breakdown
    for domain in sorted(set(list(domain_valid.keys()) + list(domain_invalid.keys()))):
        stats["domains"][domain] = {
            "valid": domain_valid.get(domain, 0),
            "stub": domain_invalid.get(domain, 0),
        }

    return stats


def compute_trend(days: int = 7) -> list[dict]:
    """Compute daily stats for the last N days."""
    from lib.materials import get_all_collected_urls

    today = datetime.date.today()
    trend = []
    for i in range(days):
        d = today - datetime.timedelta(days=i)
        # Load entries and filter by date
        entries = load_url_registry()
        # Mark entries collected on this date
        date_str = d.isoformat()
        stats = compute_stats(entries)
        stats["date"] = date_str
        trend.append(stats)

    trend.reverse()  # oldest first
    return trend


def get_today_new_count(entries: list[dict]) -> int:
    """Count how many entries were added today (based on the collected usage in the pipeline)."""
    today = datetime.date.today().isoformat()
    # Check file modification times of report files
    today_new = 0
    from lib.materials import find_report_file
    for e in entries:
        if e["status"] != "collected":
            continue
        f = find_report_file(e["url"])
        if f:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            if mtime == today:
                content = f.read_text(encoding="utf-8", errors="replace")
                if is_valid_content(content):
                    today_new += 1
    return today_new


# ── Output ──

def print_stats(stats: dict, new_today: int):
    """Print human-readable stats."""
    print(f"📊 素材统计 — {datetime.date.today()}")
    print(f"{'='*50}")
    print(f"  📦 全部条目:     {stats['total']}")
    print(f"  ✅ 有效素材:     {stats['valid_collected']}")
    print(f"     (内容 ≥300 chars, 非 stub)")
    print(f"  📝 已使用:       {stats['used']}")
    print(f"  ❌ 无效标记:     {stats['stub_entries']}")
    print(f"  📈 使用率:       {stats['usage_rate']}%")
    print(f"  ➕ 今日新增:     {new_today}")
    print()
    print(f"📐 内容长度分布 ({stats['content_sizes']['avg']:,} chars 平均 / {stats['content_sizes']['total_chars']:,} 总字符)")
    print(f"   最小: {stats['content_sizes']['min']:,}  char(s)")
    print(f"   最大: {stats['content_sizes']['max']:,}  chars")
    print()
    print(f"🌐 按来源域名 (有效 / 无效):")
    sorted_domains = sorted(stats['domains'].items(), key=lambda x: x[1]['valid'], reverse=True)
    for domain, d in sorted_domains:
        bar = "█" * min(d['valid'], 20)
        stub_mark = f" (+{d['stub']} stub)" if d['stub'] > 0 else ""
        print(f"  {bar} {d['valid']:>3}  {domain}{stub_mark}")


def save_stats_json(stats: dict, new_today: int):
    """Save stats to daily-stats directory for trend tracking."""
    DAILY_STATS_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.date.today().isoformat()
    stats["new_today"] = new_today
    stats["date"] = date_str
    filepath = DAILY_STATS_DIR / f"{date_str}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    return filepath


def print_trend(trend: list[dict]):
    """Print trend stats."""
    print(f"📈 近 {len(trend)} 天趋势:")
    print(f"{'日期':<14} {'有效':>5} {'新增':>5} {'无效':>5} {'已用':>5} {'使用率':>7} {'总字符':>9}")
    print(f"{'-'*50}")
    for t in trend:
        print(f"{t.get('date','?'):<14} {t['valid_collected']:>5} {t.get('new_today',0):>5} {t['stub_entries']:>5} {t['used']:>5} {t['usage_rate']:>6}% {t['content_sizes']['total_chars']:>9,}")


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Daily stats for content collection")
    parser.add_argument("--date", help="Date string (YYYY-MM-DD), defaults to today")
    parser.add_argument("--trend", action="store_true", help="Show 7-day trend")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--save", action="store_true", help="Save stats to daily-stats dir")
    args = parser.parse_args()

    entries = load_url_registry()
    if not entries:
        print("⚠️  all_urls.tsv not found or empty")
        return

    stats = compute_stats(entries)
    new_today = get_today_new_count(entries)

    if args.json:
        stats["new_today"] = new_today
        stats["date"] = datetime.date.today().isoformat()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    if args.trend:
        trend = compute_trend(7)
        print_trend(trend)
        return

    print_stats(stats, new_today)

    if args.save:
        fp = save_stats_json(stats, new_today)
        print(f"\n💾 已保存到: {fp}")


if __name__ == "__main__":
    main()
