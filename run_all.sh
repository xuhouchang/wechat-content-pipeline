#!/usr/bin/env bash
# ─────────────────────────────────────────────
# Research Report Collector — Pipeline Runner
# Called by system crontab
# ─────────────────────────────────────────────
set -euo pipefail

COLLECTOR_DIR="$(cd "$(dirname "$0")" && pwd)"
REPORTS_DIR="${REPORTS_DIR:-/home/ubuntu/.openclaw/workspace/reports}"
TMP_DIR="${TMP_DIR:-${COLLECTOR_DIR}/tmp}"
PYTHON="${PYTHON:-/usr/bin/python3}"
OPENCLAW="${OPENCLAW:-/usr/bin/openclaw}"

export REPORTS_DIR TMP_DIR PYTHON OPENCLAW

DATE=$(date +%Y-%m-%d)
DOW=$(date +%u)  # 1=Monday
LOG_DIR="${COLLECTOR_DIR}/logs"
mkdir -p "$LOG_DIR"

logfile="${LOG_DIR}/collect_${DATE}.log"
touch "$logfile"

log() {
    echo "[$(date '+%H:%M:%S')] $*" | tee -a "$logfile"
}

run_step() {
    local step_name="$1"
    shift
    log "▶  Starting: $step_name"
    if "$PYTHON" "$@" 2>&1 | tee -a "$logfile"; then
        log "✓  Completed: $step_name"
    else
        log "✗  FAILED: $step_name (exit code $?)"
    fi
}

log "══════════════════════════════════════════"
log "Research Report Collector — ${DATE} (DOW=${DOW})"
log "══════════════════════════════════════════"

# ── Phase 1: Raw Collection (all Python, no LLM) ──
log "--- Phase 1: Raw Collection ---"

# Part 1: RSS Feeds
run_step "collect_rss" "${COLLECTOR_DIR}/collect_rss.py"

# Part 2: AI Company Blogs
run_step "collect_blogs" "${COLLECTOR_DIR}/collect_blogs.py"

# Part 3+4: Consulting + Think Tanks (Mondays only)
if [ "$DOW" = "1" ]; then
    run_step "collect_consulting" "${COLLECTOR_DIR}/collect_consulting.py"
    run_step "collect_podcasts" "${COLLECTOR_DIR}/collect_podcasts.py"
fi

# ── Phase 2: Filter Items via LLM API ──
# Calls DeepSeek API (OpenAI-compatible) to determine pass/skip per item.
# Pure Python, no agent prompt scheduling.
log "--- Phase 2: Filter Items via LLM API ---"

FILTER_SOURCES="rss blogs"
if [ "$DOW" = "1" ]; then
    FILTER_SOURCES="rss blogs consulting thinktank"
fi

for src in $FILTER_SOURCES; do
    run_step "filter_${src}" "${COLLECTOR_DIR}/filter_items.py" "$src"
done

# ── Phase 3: Poll for Filter Results and Save ──
# filter_items.py writes filtered JSON, then poll_and_save.py saves to reports.
log "--- Phase 3: Poll for Filter Results and Save ---"

POLL_SOURCES="rss blogs"
if [ "$DOW" = "1" ]; then
    POLL_SOURCES="rss blogs consulting thinktank"
fi

log "Polling sources: ${POLL_SOURCES}"
for src in $POLL_SOURCES; do
    log "  Spawning poll_and_save for ${src}..."
    "$PYTHON" "${COLLECTOR_DIR}/poll_and_save.py" "$src" >> "$logfile" 2>&1 &
done

# Wait for all background poll processes to finish
log "Waiting for all save processes to complete..."
wait
log "All save processes finished."

# ── Phase 4 (Mondays only): Consulting Report Strategist (Agent) ──
# Runs an OpenClaw subagent to scan firm research pages and generate
# targeted search queries for reports that the raw Serper search missed
# (especially McKinsey/BCG/Deloitte which often return 403).
# The agent writes outputs/candidates_{DATE}.json, which poll_and_save
# consumes via --from-strategist.
if [ "$DOW" = "1" ]; then
    log "--- Phase 4: Consulting Report Strategist ---"
    
    STRATEGIST_DIR="${COLLECTOR_DIR}/../skills/consulting-report-strategist"
    OUTPUT_DIR="${STRATEGIST_DIR}/outputs"
    mkdir -p "$OUTPUT_DIR"
    
    CANDIDATES_FILE="${OUTPUT_DIR}/candidates_${DATE}.json"
    
    # Check if strategist already ran today (avoid re-run if pipeline restarts)
    if [ -f "$CANDIDATES_FILE" ]; then
        log "  Strategist output exists, skipping agent run: ${CANDIDATES_FILE}"
    else
        log "  Launching consulting-report-strategist agent..."
        # Spawn a short-lived OpenClaw subagent to do the strategist work
        $OPENCLAW cron create "consulting-report-strategist-${DATE}" \
            --schedule "now" \
            --prompt-file "${STRATEGIST_DIR}/prompts/strategist_task.txt" \
            --env "DATE=${DATE}" \
            --env "COLLECTOR_DIR=${COLLECTOR_DIR}" \
            --delete-after-run \
            >> "$logfile" 2>&1 || true
        
        # Wait a bit for the agent to write candidates
        log "  Waiting for strategist agent output..."
        AGENT_WAIT=0
        AGENT_MAX=600
        while [ $AGENT_WAIT -lt $AGENT_MAX ]; do
            if [ -f "$CANDIDATES_FILE" ]; then
                log "  ✓ Strategist candidates appeared after ${AGENT_WAIT}s"
                break
            fi
            sleep 30
            AGENT_WAIT=$((AGENT_WAIT + 30))
        done
        if [ ! -f "$CANDIDATES_FILE" ]; then
            log "  ⏱  Strategist agent timed out after ${AGENT_MAX}s, skipping"
        fi
    fi
    
    # Save strategist candidates if they exist
    if [ -f "$CANDIDATES_FILE" ]; then
        run_step "save_strategist" "${COLLECTOR_DIR}/poll_and_save.py" \
            "--from-strategist" "$CANDIDATES_FILE" \
            "--date" "$DATE"
    fi
fi

# ── Phase 5: Research Cards → Feishu ──
log "--- Phase 5: Research Cards → Feishu ---"
run_step "research_cards" "${COLLECTOR_DIR}/research_cards.py" "--max-cards" "5"

# ── Phase 6: Daily Stats ──
log "--- Phase 6: Daily Stats ---"
run_step "stats_daily" "${COLLECTOR_DIR}/stats_daily.py" "--save"

log "══════════════════════════════════════════"
log "Pipeline complete."
echo ""
echo "ℹ️  New unified CLI: python3 collector/collect.py --help"
