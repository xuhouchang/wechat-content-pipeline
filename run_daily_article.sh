#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# run_daily_article.sh — Daily WeChat article pipeline
#
# Pure script-driven pipeline (no agent dependency):
#   Phase 0: tag_materials.py  → 增量打标（没打标的新素材）
#   Phase 1: write_article.py  → 写作 + 配图下载
#   Phase 2: embed_images.py   → IMAGE 占位符替换（兜底）
#   Phase 3: wechat_publish.py → 上传微信 + 转码 + 创建草稿
#   Phase 4: update all_urls.tsv → 素材标记为 used
#
# Environment:
#   WECHAT_APP_ID / WECHAT_APP_SECRET  — 从 .env 文件或环境变量读
#   REPORTS_DIR                         — 素材库根目录（默认 ~/workspace/reports）
#
# Logs to:  collector/logs/article_YYYY-MM-DD.log
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Config ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COLLECTOR_DIR="$SCRIPT_DIR"
REPORTS_DIR="${REPORTS_DIR:-$WORKSPACE_DIR/reports}"
ALL_URLS_FILE="$REPORTS_DIR/_index/all_urls.tsv"
LOG_DIR="$COLLECTOR_DIR/logs"

# Script paths
TAG_SCRIPT="$COLLECTOR_DIR/tag_materials.py"
WRITE_SCRIPT="$COLLECTOR_DIR/write_article.py"
EMBED_SCRIPT="$COLLECTOR_DIR/embed_images.py"
PUBLISH_SCRIPT="$COLLECTOR_DIR/wechat_publish.py"

# WeChat credentials — from .env next to publish script
WECHAT_ENV="$(dirname "$PUBLISH_SCRIPT")/.env"

# ── Date ──
DATE="$(date +%Y-%m-%d)"
LOG_FILE="$LOG_DIR/article_$DATE.log"

# ── Setup logging ──
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "📰 Daily Article Pipeline — $DATE"
echo "=========================================="
echo ""

# ── Phase 0: Incremental Tagging ──
echo "──────────────────────────────────────────"
echo "Phase 0: Incremental tagging (new materials)..."
echo "──────────────────────────────────────────"
START_TS=$(date +%s)

if [ -f "$TAG_SCRIPT" ]; then
    python3 "$TAG_SCRIPT" --max-batches 10 2>&1
    TAG_EXIT=$?
    echo "Phase 0 took $(( $(date +%s) - START_TS )) seconds"
    if [ $TAG_EXIT -ne 0 ]; then
        echo "⚠️  Phase 0 had issues (exit: $TAG_EXIT), continuing anyway"
    fi
else
    echo "⚠️  tag_materials.py not found, skipping"
fi
echo ""

# ── Phase 1: Write Article ──
echo "──────────────────────────────────────────"
echo "Phase 1: Writing article..."
echo "──────────────────────────────────────────"
START_TS=$(date +%s)

if [ ! -f "$WRITE_SCRIPT" ]; then
    echo "❌ write_article.py not found: $WRITE_SCRIPT"
    exit 1
fi

python3 "$WRITE_SCRIPT" --date "$DATE" --model openai-codex/gpt-5.5
WRITE_EXIT=$?

END_TS=$(date +%s)
echo "Phase 1 took $((END_TS - START_TS)) seconds"

if [ $WRITE_EXIT -ne 0 ]; then
    echo "❌ Phase 1 failed (exit: $WRITE_EXIT)"
    exit $WRITE_EXIT
fi

# Find the output directory (newest wechat-articles subdir)
OUTPUT_DIR=$(ls -td "$WORKSPACE_DIR/wechat-articles/"* 2>/dev/null | head -1)
if [ -z "$OUTPUT_DIR" ]; then
    echo "❌ No output directory found in wechat-articles/"
    exit 1
fi

ARTICLE_FILE="$OUTPUT_DIR/article.md"
IMAGES_DIR="$OUTPUT_DIR/images"

echo "   Output: $OUTPUT_DIR"
echo ""

# ── Phase 2: Embed Images (fallback) ──
echo "──────────────────────────────────────────"
echo "Phase 2: Embedding images (fallback)..."
echo "──────────────────────────────────────────"

if [ -f "$EMBED_SCRIPT" ] && [ -f "$ARTICLE_FILE" ] && [ -d "$IMAGES_DIR" ]; then
    python3 "$EMBED_SCRIPT" "$ARTICLE_FILE" "$IMAGES_DIR" 2>&1 || true
    echo "Phase 2 done"
else
    echo "⚠️  Skipped (script, article, or images dir missing)"
    [ ! -f "$EMBED_SCRIPT" ] && echo "   missing: $EMBED_SCRIPT"
    [ ! -f "$ARTICLE_FILE" ] && echo "   missing: $ARTICLE_FILE"
    [ ! -d "$IMAGES_DIR" ] && echo "   missing: $IMAGES_DIR"
fi
echo ""

# ── Phase 3: Publish to WeChat ──
echo "──────────────────────────────────────────"
echo "Phase 3: Publishing to WeChat..."
echo "──────────────────────────────────────────"

# Load WeChat credentials if .env exists
if [ -f "$WECHAT_ENV" ]; then
    set -a
    source "$WECHAT_ENV"
    set +a
fi

if [ -z "${WECHAT_APP_ID:-}" ] || [ -z "${WECHAT_APP_SECRET:-}" ]; then
    echo "⚠️  WECHAT_APP_ID / WECHAT_APP_SECRET not set — skipping publish"
    echo "   Set them in $WECHAT_ENV or as environment variables"
    PUBLISH_STATUS="skipped"
else
    if [ -f "$PUBLISH_SCRIPT" ] && [ -f "$ARTICLE_FILE" ]; then
        echo "Creating WeChat draft..."
        python3 "$PUBLISH_SCRIPT" \
            --article "$ARTICLE_FILE" \
            --images-dir "$IMAGES_DIR" \
            2>&1
        PUBLISH_EXIT=$?
        if [ $PUBLISH_EXIT -eq 0 ]; then
            echo "✅ WeChat draft created successfully"
            PUBLISH_STATUS="published"
        else
            echo "⚠️  WeChat publish had issues (exit: $PUBLISH_EXIT)"
            PUBLISH_STATUS="failed"
        fi
    else
        echo "⚠️  Skipped (publish script or article file missing)"
        PUBLISH_STATUS="skipped"
        [ ! -f "$PUBLISH_SCRIPT" ] && echo "   missing: $PUBLISH_SCRIPT"
        [ ! -f "$ARTICLE_FILE" ] && echo "   missing: $ARTICLE_FILE"
    fi
fi
echo ""

# ── Phase 4: Update all_urls.tsv ──
echo "──────────────────────────────────────────"
echo "Phase 4: Updating material index..."
echo "──────────────────────────────────────────"

if [ -f "$ALL_URLS_FILE" ]; then
    # Get URLs used in this article by scanning the article for URL references
    USED_URLS=$(grep -oP 'https?://[^)"'"'"'\s]+' "$ARTICLE_FILE" 2>/dev/null || true)
    if [ -n "$USED_URLS" ]; then
        COUNT=0
        while IFS= read -r url; do
            # Normalize URL (strip trailing slash)
            url_clean="${url%/}"
            # Update status in all_urls.tsv using a temp file
            if grep -qF "$url_clean" "$ALL_URLS_FILE"; then
                sed -i "s|$url_clean\tcollected|$url_clean\tused|g" "$ALL_URLS_FILE"
                COUNT=$((COUNT + 1))
            fi
        done <<< "$USED_URLS"
        echo "   Updated $COUNT URLs to 'used' status"
    else
        echo "   No URLs found in article to update"
    fi
else
    echo "⚠️  all_urls.tsv not found — skipping"
fi
echo ""

# ── Summary ──
echo "=========================================="
echo "📰 Daily Article Pipeline — $DATE — COMPLETE"
echo "   Output: $OUTPUT_DIR"
echo "   Publish: $PUBLISH_STATUS"
echo "   Log: $LOG_FILE"
echo "=========================================="
