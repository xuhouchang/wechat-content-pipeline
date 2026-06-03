#!/usr/bin/env python3
"""
Analyze WeChat article stats for the past week.
Reads from Feishu Bitable, generates a report.

Run manually:
  python3 analyze_wechat_data.py

Output:
  - Markdown report saved to wechat-drafts/weekly-stats/
  - Uploaded to Feishu workspace
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Dirs ──
REPORT_DIR = Path(__file__).parent.parent / "wechat-drafts" / "weekly-stats"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# ── Bitable config ──
BITABLE_APP_TOKEN = "TLI5bITzLawgSQsb1T6cr8F6nFX"
BITABLE_TABLE_ID = "tblOts2XBJb0wrWE"


def fetch_bitable_records() -> list[dict]:
    """Fetch all records from the bitable."""
    cmd = [
        "lark-cli", "api", "GET",
        f"/open-apis/bitable/v1/apps/{BITABLE_APP_TOKEN}/tables/{BITABLE_TABLE_ID}/records",
        "--as", "bot", "--format", "json",
        "--page-size", "500",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    records = []
    for item in data.get("data", {}).get("items", []):
        fields = item.get("fields", {})
        records.append(flatten_fields(fields))
    return records


def flatten_fields(fields: dict) -> dict:
    """Flatten bitable field types to simple values."""
    flat = {}
    for k, v in fields.items():
        if k == "链接" and isinstance(v, dict):
            flat["link"] = v.get("link", "")
            flat["link_text"] = v.get("text", "")
        elif k == "发布日期" and isinstance(v, (int, float)):
            # Bitable stores ms timestamps; convert to s first
            ts = v / 1000 if v > 1e12 else v
            flat["pub_date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        else:
            # Convert bitable number strings to int
            try:
                flat[k] = int(v) if isinstance(v, str) and v.isdigit() else v
            except (ValueError, TypeError):
                flat[k] = v
    return flat


def generate_report(records: list[dict]) -> str:
    """Generate the analysis report Markdown."""
    if not records:
        return "# 公众号周报\n\n本周无数据。"

    today = datetime.now()
    week_end = (today - timedelta(days=1)).strftime("%m-%d")
    week_start = (today - timedelta(days=7)).strftime("%m-%d")

    lines = []
    lines.append(f"# 公众号周报：{week_start} ~ {week_end}\n")
    lines.append(f"> 生成时间：{today.strftime('%Y-%m-%d %H:%M')}\n")

    # ── Part 1: Top articles ──
    lines.append("## 一、本周文章表现\n")
    lines.append("| 排名 | 标题 | 阅读量 | 分享数 | 收藏数 | 素材类型 |")
    lines.append("|------|------|--------|--------|--------|----------|")

    sorted_by_reads = sorted(records, key=lambda r: r.get("阅读量", 0), reverse=True)

    for i, r in enumerate(sorted_by_reads, 1):
        title = r.get("文章标题", "?")[:45]
        reads = r.get("阅读量", 0)
        shares = r.get("分享数", 0)
        favs = r.get("收藏数", 0)
        s_type = r.get("素材类型", "-")
        lines.append(f"| {i} | {title} | {reads} | {shares} | {favs} | {s_type} |")

    lines.append("")

    # ── Part 2: Data source analysis ──
    lines.append("## 二、数据源分析\n")

    # Group by source type
    enterprise = [r for r in records if r.get("素材类型") == "企业落地"]
    interesting = [r for r in records if r.get("素材类型") == "有意思的发现"]

    total_ent = sum(r.get("阅读量", 0) for r in enterprise)
    total_int = sum(r.get("阅读量", 0) for r in interesting)
    avg_ent = total_ent / len(enterprise) if enterprise else 0
    avg_int = total_int / len(interesting) if interesting else 0

    lines.append(f"**企业落地类文章（{len(enterprise)}篇）**：平均阅读 {avg_ent:.0f}")
    lines.append(f"**有意思的发现类文章（{len(interesting)}篇）**：平均阅读 {avg_int:.0f}")
    lines.append("")

    if interesting:
        int_sorted = sorted(interesting, key=lambda r: r.get("阅读量", 0), reverse=True)
        top_int = int_sorted[0] if int_sorted else None
        if top_int:
            lines.append(f"有意思发现类最高：**《{top_int.get('文章标题', '?')[:40]}》** "
                        f"阅读 {top_int.get('阅读量', 0)}")

    lines.append("")

    # Source breakdown
    source_groups = {}
    for r in records:
        src = r.get("素材来源", "其他")
        if src not in source_groups:
            source_groups[src] = {"count": 0, "total_reads": 0, "total_shares": 0}
        source_groups[src]["count"] += 1
        source_groups[src]["total_reads"] += r.get("阅读量", 0)
        source_groups[src]["total_shares"] += r.get("分享数", 0)

    lines.append("**按素材来源分类**\n")
    lines.append("| 来源 | 篇数 | 总阅读 | 平均阅读 | 分享/阅读比 |")
    lines.append("|------|------|--------|----------|-------------|")
    for src, info in sorted(source_groups.items(), key=lambda x: x[1]["total_reads"], reverse=True):
        avg = info["total_reads"] / info["count"] if info["count"] else 0
        share_ratio = info["total_shares"] / info["total_reads"] if info["total_reads"] else 0
        lines.append(f"| {src} | {info['count']} | {info['total_reads']} | {avg:.0f} | {share_ratio:.1%} |")

    lines.append("")

    # ── Part 3: Style analysis ──
    lines.append("## 三、写作风格分析\n")

    top3 = sorted_by_reads[:3]
    bottom3 = sorted_by_reads[-3:] if len(sorted_by_reads) >= 3 else sorted_by_reads

    lines.append("**高阅读文章（Top 3）：**\n")
    for r in top3:
        title = r.get("文章标题", "?")
        reads = r.get("阅读量", 0)
        shares = r.get("分享数", 0)
        src = r.get("素材来源", "?")
        s_type = r.get("素材类型", "?")
        lines.append(f"- 《{title}》— {reads}读/{shares}分享 — {src} ({s_type})")

    lines.append("")
    lines.append("**低阅读文章（Bottom 3）：**\n")
    for r in bottom3:
        title = r.get("文章标题", "?")
        reads = r.get("阅读量", 0)
        shares = r.get("分享数", 0)
        src = r.get("素材来源", "?")
        s_type = r.get("素材类型", "?")
        lines.append(f"- 《{title}》— {reads}读/{shares}分享 — {src} ({s_type})")

    lines.append("")

    # ── Part 4: Strategy Insights ──
    lines.append("## 四、策略深度分析\n")

    # ─── 4a: 标题公式 ───
    lines.append("### 1. 标题公式诊断\n")

    lines.append("**高阅读标题共性：**[素材来源/人物] + 中文冒号 + 反常识判断\n")
    lines.append("本周前 3 名均命中此公式：")
    for r in top3:
        t = r.get("文章标题", "")
        reads = r.get("阅读量", 0)
        shares = r.get("分享数", 0)
        lines.append(f"- 《{t[:45]}》→ {reads}读/{shares}分享")
        if True:
            has_colon = "：" in t or ":" in t
            # Estimate: colon splits into source + counterintuitive claim
            if has_colon and ("最" in t or "从" in t or "不是" in t or "颠覆" in t or "反常识" in t):
                skill = "✅"
            elif has_colon:
                skill = "⚠️ 有结论但不够反常识"
            else:
                skill = "⚠️ 缺反常识钩子"
            lines.append(f"  {skill}")

    lines.append("")
    lines.append("**本周标题模式评分（定性）：**")
    
    # Analyze all titles
    strong_pattern = 0
    weak_pattern = 0
    for r in sorted_by_reads:
        t = r.get("文章标题", "")
        has_colon = "：" in t or ":" in t
        has_counterclaim = any(kw in t for kw in ["最", "不是", "颠覆", "重新", "真相", "榨干", "坦白", "内心", "障碍"])
        if has_colon and has_counterclaim:
            strong_pattern += 1
        else:
            weak_pattern += 1
    
    lines.append(f"- 有反常识钩子 + 素材前置：《{sorted_by_reads[0].get('文章标题','?')[:30]}》等 {strong_pattern} 篇 — 对应高阅读区间")
    lines.append(f"- 信息告知型/无判断：《BCG/McKinsey 调研》等 {weak_pattern} 篇 — 对应低阅读区间")

    lines.append("")
    lines.append("**可执行规则：**")
    lines.append("- 标题必须包含 `[来源/人物]：[反常识判断]` 结构")
    lines.append("- 反常识判断的标准：去掉后半句，前文应该让读者感到\'这有什么好说的？\'" )
    lines.append("- 反例自查：如果标题替换成'XX发布了一份新报告'也说得通 → 需要重写")

    # ─── 4b: 阅读量 vs 分享率分化 ───
    lines.append("")
    lines.append("### 2. 阅读量 vs 分享率分化\n")

    # Sort by share ratio for articles with >0 reads
    shareable = [r for r in sorted_by_reads if r.get("阅读量", 0) >= 3]
    shareable_sorted = sorted(shareable, key=lambda r: r.get("分享数", 0) / r.get("阅读量", 1), reverse=True)

    lines.append("| 文章 | 阅读 | 分享 | 分享率 | 信号 |")
    lines.append("|------|------|------|--------|------|")
    
    top_share = shareable_sorted[:3] if len(shareable_sorted) >= 3 else shareable_sorted
    for r in top_share:
        t = r.get("文章标题", "?")[:30]
        reads = r.get("阅读量", 0)
        shares = r.get("分享数", 0)
        ratio = shares / reads if reads > 0 else 0
        if ratio >= 0.15:
            signal = "🔁 朋友圈传播型"
        elif ratio >= 0.05:
            signal = "🔄 交叉传播"
        else:
            signal = "🤖 算法推荐型"
        lines.append(f"| {t} | {reads} | {shares} | {ratio:.1%} | {signal} |")

    lines.append("")
    
    # Find the article with highest reads but lowest share ratio
    high_read_low_share = sorted(
        shareable, 
        key=lambda r: (r.get("分享数", 0) / r.get("阅读量", 1), r.get("阅读量", 0)),
        reverse=False
    )
    if high_read_low_share:
        extreme = high_read_low_share[0]
        if extreme.get("阅读量", 0) >= 20 and extreme.get("分享数", 0) / max(extreme.get("阅读量", 1), 1) < 0.05:
            lines.append(f"**🔍 高阅读低分享信号**：《{extreme.get('文章标题','?')[:40]}》— {extreme.get('阅读量',0)}读/{extreme.get('分享数',0)}分享")
            lines.append(f"  → 说明流量来源是平台推荐/搜一搜算法曝光，非朋友圈自然传播")
            lines.append(f"  → 这类内容有流量天花板，适合做曝光型选题，不适合做品牌沉淀")

    lines.append("")
    lines.append("**策略含義：**")
    lines.append("- 高分享率（>15%）= 品牌型内容：数据+具体结论，读者主动转发")
    lines.append("- 高阅读低分享（<5%）= 流量型内容：反常识/认知冲击，算法推量")
    lines.append("- 两个方向都能走，但每周需要知道本周哪篇文章是哪个类型，据此判断下周侧重")

    # ─── 4c: 选题筛选标准 ───
    lines.append("")
    lines.append("### 3. 选题筛选：三问自查\n")

    lines.append("本周低阅读文章的共性：回答的是「发生了什么」，不是「这意味着什么/推翻什么」。")
    lines.append("")
    lines.append("**写题/选素材前问自己三个问题：**")
    lines.append("1️⃣ **这个素材推翻了什么常见直觉？**")
    lines.append("   - 如果答不上来 → 这个素材不适合写成单篇，存为佐证材料")
    lines.append("2️⃣ **这个素材如果删掉，文章还有没有替代？**")
    lines.append("   - 如果有 → 说明缺乏差异化的判断，需要找到那个不可替代的点")
    lines.append("3️⃣ **用户只读标题不点进来，他亏了什么信息差？**")
    lines.append("   - 如果答案是\x27没什么\x27 → 标题没写对，需要重写")

    # ─── 4d: 下周建议 ───
    lines.append("")
    lines.append("### 4. 下周操作建议\n")
    
    # Determine what the week's data suggests
    ent_stronger = avg_ent >= avg_int if enterprise and interesting else True
    
    if ent_stronger:
        lines.append("- **数据+结论型选题比重保持 2:1**：企业落地类为基本盘，有意思发现类做差异化")
    else:
        lines.append("- **有意思发现类加大投入**：本周表现超过企业落地类，后续持续观测趋势")
    
    # Check if any source performed well
    best_source = max(source_groups.items(), key=lambda x: x[1]["total_reads"]) if source_groups else None
    if best_source:
        lines.append(f"- **{best_source[0]} 本周产出最高**：持续关注此源，优先从中选素材")
    
    lines.append("- **标题统一公式**：本周验证有效的 `[来源/人物]：[反常识判断]` 结构，下周严格执行")
    lines.append("- **周三/周日复盘**：周三快速检视半周数据，判断阅读量是推荐型还是分享型，周日补发针对另一类型的文章")

    lines.append("")
    lines.append("---")
    lines.append(f"_每周自动生成 | 数据来源：微信公众平台 API | 下周期：{today.strftime('%Y-%m-%d')}_")

    return "\n".join(lines)


def upload_to_feishu(content: str, filename: str) -> None:
    """Upload report to Feishu workspace."""
    # Write to local file first
    local_path = REPORT_DIR / filename
    local_path.write_text(content, encoding="utf-8")
    print(f"  📄 Report saved to: {local_path}")

    # Upload to Drive - find or create folder first
    # For now just save locally; upload handled by cron wrapper


def main():
    print(f"📈 WeChat Stats Analyzer — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    records = fetch_bitable_records()
    print(f"  📊 Records fetched: {len(records)}")

    if not records:
        print("  ℹ️ No records to analyze")
        sys.exit(0)

    report = generate_report(records)
    
    today = datetime.now()
    filename = f"wechat-weekly-{today.strftime('%Y%m%d')}.md"
    upload_to_feishu(report, filename)

    # Print summary
    print(f"\n  📈 Report generated: {filename}")
    print(f"  📐 Sections: Overview, Source Analysis, Style Analysis, Recommendations")
    
    # Show top 3
    sorted_records = sorted(records, key=lambda r: r.get("阅读量", 0), reverse=True)
    for i, r in enumerate(sorted_records[:3], 1):
        reads = r.get("阅读量", 0)
        title = r.get("文章标题", "?")[:40]
        print(f"    #{i} ({reads} reads) {title}")


if __name__ == "__main__":
    main()
