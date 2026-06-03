#!/usr/bin/env python3
"""
WeChat Official Account article stats fetcher — v2.

Uses the currently available WeChat API:
  - getarticletotaldetail (works as of May 2026)
  - getarticlesummary (deprecated, errcode 47009)

Workflow:
  1. Get access_token
  2. For each of the past 7 days, call getarticletotaldetail
  3. Merge stats across days
  4. Upsert to Feishu Bitable

Run manually:
  python3 fetch_wechat_stats.py
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

WECHAT_DATACUBE_BASE = "https://api.weixin.qq.com"

BITABLE_APP_TOKEN = "TLI5bITzLawgSQsb1T6cr8F6nFX"
BITABLE_TABLE_ID = "tblOts2XBJb0wrWE"

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

WECHAT_APP_ID = os.environ.get("WECHAT_APP_ID", "")
WECHAT_APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")


class WeChatAPI:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._token = None
        self._token_expires = 0

    def _get_access_token(self) -> str:
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={self.app_id}&secret={self.app_secret}"
        resp = json.loads(urllib.request.urlopen(url, timeout=15).read())
        if "access_token" not in resp:
            raise RuntimeError(f"WeChat token error: {resp}")
        self._token = resp["access_token"]
        self._token_expires = time.time() + resp["expires_in"]
        return self._token

    def _request(self, endpoint: str, body: dict, retry: int = 2) -> dict:
        for attempt in range(retry):
            try:
                token = self._get_access_token()
                url = f"{WECHAT_DATACUBE_BASE}/{endpoint}?access_token={token}"
                req = urllib.request.Request(
                    url,
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                )
                resp = json.loads(urllib.request.urlopen(req, timeout=15).read())
                if resp.get("errcode") not in (None, 0):
                    print(f"  ⚠ WeChat API error ({endpoint}): {resp}")
                return resp
            except urllib.error.HTTPError as e:
                if e.code == 404 and attempt < retry - 1:
                    self._token = None
                    time.sleep(1)
                    continue
                raise
        return {}

    def get_article_detail_single_day(self, date_str: str) -> list[dict]:
        """
        Call getarticletotaldetail for a single day.
        Returns the list of articles with their stats.
        """
        resp = self._request("datacube/getarticletotaldetail", {
            "begin_date": date_str,
            "end_date": date_str,
        })
        return resp.get("list", [])


def merge_article_stats(articles_by_key: dict, day_items: list[dict]):
    """
    Merge a day's articles into the accumulator dict.
    Keyed by msgid for de-duplication.
    """
    for item in day_items:
        msgid = item.get("msgid", "")
        title = item.get("title", "")
        link = item.get("link", "")
        ref_date = item.get("ref_date", "")
        if not msgid:
            continue
        key = msgid

        # Take the latest day's stats (most recent stat_date)
        # detail_list contains one entry per day after publish, up to 10 days
        details = sorted(
            [d for d in item.get("detail_list", []) if d.get("stat_date")],
            key=lambda d: d["stat_date"],
            reverse=True,
        )
        latest = details[0] if details else {}
        total_read_user = latest.get("read_user", 0) or 0
        total_share_user = latest.get("share_user", 0) or 0
        total_collection_user = latest.get("collection_user", 0) or 0

        if key not in articles_by_key:
            articles_by_key[key] = {
                "title": title,
                "msgid": msgid,
                "link": link,
                "ref_date": ref_date,
                "read_user": 0,
                "share_user": 0,
                "collection_user": 0,
            }

        articles_by_key[key]["read_user"] += total_read_user
        articles_by_key[key]["share_user"] += total_share_user
        articles_by_key[key]["collection_user"] += total_collection_user
        if not articles_by_key[key]["link"] and link and link != "?":
            articles_by_key[key]["link"] = link


def feishu_api(method: str, path: str, data: dict = None) -> dict:
    """Call lark-cli api with JSON body and parse response."""
    cmd = ["lark-cli", "api", method, path, "--as", "bot", "--format", "json"]
    input_str = None
    if data:
        input_str = json.dumps(data, ensure_ascii=False)
        cmd.extend(["--data", "-"])

    try:
        result = subprocess.run(cmd, input=input_str, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            stderr = result.stderr.strip()[:400]
            if stderr:
                print(f"  ⚠ lark-cli error: {stderr}")
            return {}
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parse error: {e}")
        return {}


def get_bitable_records() -> dict:
    """Get current records in bitable, keyed by article title."""
    cmd = [
        "lark-cli", "api", "GET",
        f"/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records",
        "--as", "bot", "--format", "json",
        "--page-size", "500",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    try:
        resp = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    records = {}
    for item in resp.get("data", {}).get("items", []):
        fields = item.get("fields", {})
        title = fields.get("文章标题", "") or fields.get("公众号文章数据 - 零一怎么看", "")
        if title:
            records[title.strip()] = item["record_id"]
    return records


def guess_source_from_title(title: str) -> tuple[str, str]:
    """Guess the material source and type from article title."""
    kw_rules = [
        ("McKinsey", "McKinsey 报告", "企业落地"),
        ("KPMG", "KPMG 报告", "企业落地"),
        ("BCG", "BCG 报告", "企业落地"),
        ("Deloitte", "Deloitte 报告", "企业落地"),
        ("Accenture", "Accenture 报告", "企业落地"),
        ("LinkedIn", "LinkedIn 报告", "企业落地"),
        ("Mollick", "Ethan Mollick", "有意思的发现"),
        ("Anthropic", "Anthropic 研究", "有意思的发现"),
        ("Claude", "Anthropic 研究", "有意思的发现"),
        ("ChatGPT", "OpenAI 研究", "有意思的发现"),
        ("Google", "Google AI 研究", "有意思的发现"),
        ("DeepMind", "DeepMind 研究", "有意思的发现"),
        ("微软", "Microsoft 研究", "有意思的发现"),
        ("OpenAI", "OpenAI 研究", "有意思的发现"),
        ("Meta", "Meta AI 研究", "有意思的发现"),
        ("Sam Altman", "Sam Altman 观点", "有意思的发现"),
        ("Wharton", "Wharton 研究", "有意思的发现"),
        ("MIT", "MIT 研究", "有意思的发现"),
        ("哈佛", "哈佛研究", "有意思的发现"),
        ("斯坦福", "Stanford 研究", "有意思的发现"),
        ("Import AI", "Import AI", "有意思的发现"),
        ("同事.Skill", "飞书产品观察", "企业落地"),
    ]
    for kw, label, stype in kw_rules:
        if kw.lower() in title.lower():
            return label, stype
    report_kw = ["调研", "报告", "CIO", "CEO", "高管", "企业", "组织", "流程", "落地", "Tech Trends"]
    interesting_kw = ["AI", "研究", "发现", "能力", "模型", "智能", "算法", "数据"]
    report_score = sum(1 for kw in report_kw if kw.lower() in title.lower())
    interesting_score = sum(1 for kw in interesting_kw if kw.lower() in title.lower())
    if report_score >= interesting_score:
        return "综合报告", "企业落地"
    return "综合研究", "有意思的发现"


def main():
    print(f"📊 WeChat Stats Fetcher v2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if not WECHAT_APP_ID or not WECHAT_APP_SECRET:
        print("❌ WECHAT_APP_ID or WECHAT_APP_SECRET not set")
        sys.exit(1)

    api = WeChatAPI(WECHAT_APP_ID, WECHAT_APP_SECRET)

    today = datetime.now()
    end_date = today - timedelta(days=1)
    start_date = today - timedelta(days=7)
    week_label = f"{start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}"
    print(f"📅 Range: {start_date.strftime('%Y-%m-%d')} -> {end_date.strftime('%Y-%m-%d')}")

    # Fetch detail data for each day, merge by article msgid
    merged = {}

    current = start_date
    while current <= end_date:
        ds = current.strftime("%Y-%m-%d")
        items = api.get_article_detail_single_day(ds)
        if items:
            merge_article_stats(merged, items)
            print(f"  {ds}: {len(items)} articles")
        else:
            print(f"  {ds}: no data")
        current += timedelta(days=1)

    if not merged:
        print("  ℹ️ No data for the period")
        sys.exit(0)

    # Sort by total read_user descending
    sorted_articles = sorted(
        merged.values(),
        key=lambda a: a["read_user"],
        reverse=True,
    )
    print(f"\n  📊 Articles in period: {len(sorted_articles)}")

    # Fetch existing bitable records
    existing = get_bitable_records()
    print(f"  🗂  Existing records in bitable: {len(existing)}")

    created = 0
    updated = 0
    skipped = 0

    for a in sorted_articles:
        title = a["title"]
        link = a.get("link", "")
        total_read = a["read_user"]
        share_count = a["share_user"]
        fav_count = a["collection_user"]
        pub_date = a.get("ref_date", "")

        # Skip articles with 0 reads (might be auto-drafts)
        if total_read == 0:
            skipped += 1
            continue

        source, source_type = guess_source_from_title(title)

        record_id = existing.get(title.strip())
        pub_ts = int(datetime.strptime(pub_date, "%Y-%m-%d").timestamp() * 1000) if pub_date else None

        fields = {
            "文章标题": title,
            "链接": {"link": link, "text": title} if link and link != "?" else None,
            "发布日期": pub_ts,
            "阅读量": total_read,
            "分享数": share_count,
            "收藏数": fav_count,
            "素材来源": source,
            "素材类型": source_type,
            "数据周次": week_label,
        }
        fields = {k: v for k, v in fields.items() if v is not None and v != ""}

        if record_id:
            # Update existing record — only stats change week to week
            patch_body = {
                "fields": {
                    "阅读量": total_read,
                    "分享数": share_count,
                    "收藏数": fav_count,
                    "数据周次": week_label,
                }
            }
            resp = feishu_api(
                "PUT",
                f"/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records/{record_id}",
                patch_body,
            )
            if resp.get("code") == 0:
                updated += 1
        else:
            # Create new record
            fields["公众号文章数据 - 零一怎么看"] = title
            create_body = {"fields": fields}
            resp = feishu_api(
                "POST",
                f"/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records",
                create_body,
            )
            if resp.get("data", {}).get("record"):
                created += 1

    print(f"\n  ✅ Done: {created} created, {updated} updated, {skipped} skipped (0 reads)")


if __name__ == "__main__":
    main()
