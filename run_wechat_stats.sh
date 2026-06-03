#!/bin/bash
# WeChat stats weekly pipeline
# Run: Sunday 8:00 AM
# 1. Fetch stats from WeChat API
# 2. Analyze and generate report
# 3. Upload report to Feishu Drive

set -e
cd "$(dirname "$0")"

echo "=== WeChat Stats Weekly Pipeline ==="
echo "Started: $(date)"

# Step 1: Fetch stats
echo ""
echo "--- Step 1: Fetch stats ---"
python3 fetch_wechat_stats.py || echo "  ⚠ fetch_wechat_stats.py failed (non-critical)"

# Step 2: Analyze and generate report
echo ""
echo "--- Step 2: Analyze data ---"
python3 analyze_wechat_data.py || echo "  ⚠ analyze_wechat_data.py failed (non-critical)"

# Step 3: Report file path
REPORT_FILE="../wechat-drafts/weekly-stats/wechat-weekly-$(date +%Y%m%d).md"
echo ""
echo "--- Report: $REPORT_FILE ---"

echo ""
echo "=== Done: $(date) ==="
