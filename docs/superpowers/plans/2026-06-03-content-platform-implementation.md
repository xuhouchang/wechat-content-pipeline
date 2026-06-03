# Content Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the legacy script mesh with a file-based shared content platform for collection, curation, dataset building, daily articles, and case studies.

**Architecture:** Build a new `platform/` package that owns storage, job state, curation, datasets, and cleanup. Legacy scripts remain temporarily, but all new execution goes through `platform_cli.py`, and the business pipelines consume curated dataset snapshots instead of raw report files.

**Tech Stack:** Python 3, file-based JSON/NDJSON storage, existing LLM/image/publish integrations, `pytest`

---

## File Structure

### New files

- `platform/__init__.py`
- `platform/cli.py`
- `platform/config.py`
- `platform/paths.py`
- `platform/job_state.py`
- `platform/logging.py`
- `platform/cleanup.py`
- `platform/models/material.py`
- `platform/models/job.py`
- `platform/storage/json_store.py`
- `platform/storage/ndjson_store.py`
- `platform/storage/manifests.py`
- `platform/ingest/rss.py`
- `platform/ingest/blogs.py`
- `platform/ingest/consulting.py`
- `platform/ingest/cases.py`
- `platform/normalize/urls.py`
- `platform/normalize/canonicalize.py`
- `platform/curate/relevance.py`
- `platform/curate/tagging.py`
- `platform/curate/dedup.py`
- `platform/curate/clustering.py`
- `platform/curate/scoring.py`
- `platform/datasets/article_pool.py`
- `platform/datasets/case_pool.py`
- `platform/business/daily_article/pipeline.py`
- `platform/business/daily_article/topic_planner.py`
- `platform/business/case_study/pipeline.py`
- `platform/business/case_study/ranker.py`
- `platform/runtime.py`
- `platform_cli.py`
- `tests/platform/test_paths.py`
- `tests/platform/test_job_state.py`
- `tests/platform/test_url_normalization.py`
- `tests/platform/test_dedup.py`
- `tests/platform/test_clustering.py`
- `tests/platform/test_scoring.py`
- `tests/platform/test_cleanup.py`
- `tests/platform/test_article_pool.py`
- `tests/platform/test_case_pool.py`
- `tests/platform/fixtures/ingest/`
- `tests/platform/fixtures/curate/`

### Files to modify

- `write_article.py`
- `decompose_case_study.py`
- `run_all.sh`
- `run_daily_article.sh`
- `README.md`

### Files to retire from active flow

- `poll_and_save.py`
- `filter_items.py`
- `tag_materials.py`
- legacy `reports/` / `tmp/` runtime assumptions

These may remain in the repository during migration but must not be authoritative after cutover.

---

### Task 1: Scaffold platform paths, config, and CLI shell

**Files:**
- Create: `platform/__init__.py`
- Create: `platform/config.py`
- Create: `platform/paths.py`
- Create: `platform/cli.py`
- Create: `platform_cli.py`
- Test: `tests/platform/test_paths.py`

- [ ] **Step 1: Write the failing tests for path and CLI bootstrap**

```python
from pathlib import Path

from platform.paths import PlatformPaths


def test_platform_paths_are_rooted_under_workspace(tmp_path: Path):
    paths = PlatformPaths.from_workspace(tmp_path)
    assert paths.platform_dir == tmp_path / "platform"
    assert paths.ingest_raw_dir("2026-06-03") == tmp_path / "platform" / "ingest" / "raw" / "2026-06-03"


def test_platform_cli_exposes_expected_jobs():
    from platform.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["run", "collect-daily", "--date", "2026-06-03"])
    assert args.command == "run"
    assert args.job_name == "collect-daily"
    assert args.date == "2026-06-03"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_paths.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'platform.paths'`

- [ ] **Step 3: Write minimal path and CLI implementation**

```python
# platform/paths.py
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlatformPaths:
    workspace_dir: Path

    @classmethod
    def from_workspace(cls, workspace_dir: Path) -> "PlatformPaths":
        return cls(workspace_dir=workspace_dir)

    @property
    def platform_dir(self) -> Path:
        return self.workspace_dir / "platform"

    def ingest_raw_dir(self, date_str: str) -> Path:
        return self.platform_dir / "ingest" / "raw" / date_str
```

```python
# platform/cli.py
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("job_name", choices=["collect-daily", "article-daily", "case-daily", "cleanup"])
    run_parser.add_argument("--date", required=True)
    return parser
```

```python
# platform_cli.py
from platform.cli import build_parser


def main() -> int:
    build_parser().parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_paths.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/__init__.py platform/config.py platform/paths.py platform/cli.py platform_cli.py tests/platform/test_paths.py
git commit -m "feat: scaffold platform paths and cli"
```

---

### Task 2: Add durable job state and resumable step tracking

**Files:**
- Create: `platform/models/job.py`
- Create: `platform/job_state.py`
- Test: `tests/platform/test_job_state.py`

- [ ] **Step 1: Write the failing tests for job lifecycle**

```python
from pathlib import Path

from platform.job_state import JobStateStore


def test_job_state_store_creates_job_file(tmp_path: Path):
    store = JobStateStore(tmp_path)
    job = store.start_job(job_type="collect-daily", date_str="2026-06-03")
    assert job["status"] == "running"
    assert (tmp_path / "job.json").exists()


def test_job_state_store_resumes_failed_step(tmp_path: Path):
    store = JobStateStore(tmp_path)
    store.write_job({
        "job_id": "collect-daily_2026-06-03_001",
        "status": "failed",
        "steps": [
            {"name": "collect_sources", "status": "success"},
            {"name": "normalize_materials", "status": "failed"},
            {"name": "curate_materials", "status": "pending"},
        ],
    })
    assert store.first_incomplete_step()["name"] == "normalize_materials"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_job_state.py -q`
Expected: FAIL with missing module errors

- [ ] **Step 3: Implement minimal job state store**

```python
# platform/job_state.py
import json
from pathlib import Path


class JobStateStore:
    def __init__(self, job_dir: Path):
        self.job_dir = job_dir
        self.job_file = job_dir / "job.json"
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def start_job(self, job_type: str, date_str: str) -> dict:
        job = {
            "job_id": f"{job_type}_{date_str}_001",
            "job_type": job_type,
            "date": date_str,
            "status": "running",
            "steps": [],
        }
        self.write_job(job)
        return job

    def write_job(self, job: dict) -> None:
        self.job_file.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_job(self) -> dict:
        return json.loads(self.job_file.read_text(encoding="utf-8"))

    def first_incomplete_step(self) -> dict | None:
        for step in self.read_job().get("steps", []):
            if step["status"] != "success":
                return step
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_job_state.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/models/job.py platform/job_state.py tests/platform/test_job_state.py
git commit -m "feat: add resumable job state store"
```

---

### Task 3: Build canonical material model and normalization utilities

**Files:**
- Create: `platform/models/material.py`
- Create: `platform/normalize/urls.py`
- Create: `platform/normalize/canonicalize.py`
- Test: `tests/platform/test_url_normalization.py`
- Test: `tests/platform/test_dedup.py`

- [ ] **Step 1: Write failing tests for URL normalization and content hash**

```python
from platform.normalize.urls import normalize_url
from platform.normalize.canonicalize import build_material_record


def test_normalize_url_removes_tracking_and_fragment():
    url = "https://example.com/post/?utm_source=x#section"
    assert normalize_url(url) == "https://example.com/post"


def test_build_material_record_sets_content_hash():
    record = build_material_record({
        "url": "https://example.com/post",
        "title": "A",
        "content_text": "hello world",
        "source_type": "rss",
        "source_name": "Example",
    }, collected_at="2026-06-03T05:00:00+08:00")
    assert record["normalized_url"] == "https://example.com/post"
    assert record["content_hash"].startswith("sha256:")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_url_normalization.py tests/platform/test_dedup.py -q`
Expected: FAIL with missing function errors

- [ ] **Step 3: Implement canonicalization**

```python
# platform/normalize/urls.py
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in TRACKING_PARAMS]
    path = parts.path.rstrip("/") or "/"
    clean = parts._replace(query=urlencode(query), fragment="", path=path)
    normalized = urlunsplit(clean)
    return normalized[:-1] if normalized.endswith("/") and path == "/" else normalized.rstrip("/")
```

```python
# platform/normalize/canonicalize.py
import hashlib

from platform.normalize.urls import normalize_url


def build_material_record(raw: dict, collected_at: str) -> dict:
    content_text = raw.get("content_text", "").strip()
    digest = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
    return {
        "material_id": raw.get("material_id", ""),
        "canonical_url": raw["url"],
        "normalized_url": normalize_url(raw["url"]),
        "source_type": raw["source_type"],
        "source_name": raw["source_name"],
        "collected_at": collected_at,
        "title": raw.get("title", ""),
        "summary": raw.get("summary", ""),
        "content_text": content_text,
        "content_hash": f"sha256:{digest}",
        "tags": {},
        "relevance": {"status": "unknown", "reason": "", "model": ""},
        "dedup": {"cluster_id": None, "is_primary": True, "duplicate_of": None, "duplicate_reason": None},
        "quality": {"content_chars": len(content_text)},
        "usage": {"used_by": [], "last_used_at": None},
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_url_normalization.py tests/platform/test_dedup.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/models/material.py platform/normalize/urls.py platform/normalize/canonicalize.py tests/platform/test_url_normalization.py tests/platform/test_dedup.py
git commit -m "feat: add canonical material normalization"
```

---

### Task 4: Build file-based ingest receipts and normalized material output

**Files:**
- Create: `platform/storage/json_store.py`
- Create: `platform/storage/ndjson_store.py`
- Create: `platform/storage/manifests.py`
- Create: `platform/ingest/rss.py`
- Create: `platform/ingest/blogs.py`
- Create: `platform/ingest/consulting.py`
- Create: `platform/ingest/cases.py`
- Create: `platform/runtime.py`

- [ ] **Step 1: Write the failing integration-style test for ingest output**

```python
from pathlib import Path

from platform.runtime import run_collect_daily


def test_collect_daily_writes_ingest_receipt(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PLATFORM_WORKSPACE_DIR", str(tmp_path))
    result = run_collect_daily(date_str="2026-06-03", dry_run=True)
    assert result["job_type"] == "collect-daily"
    assert (tmp_path / "platform" / "jobs" / "2026-06-03" / "collect-daily" / "job.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_job_state.py tests/platform/test_paths.py -q`
Expected: FAIL because `run_collect_daily` does not exist

- [ ] **Step 3: Implement minimal collect runtime with durable artifacts**

```python
# platform/runtime.py
from pathlib import Path

from platform.job_state import JobStateStore
from platform.paths import PlatformPaths


def run_collect_daily(date_str: str, dry_run: bool = False) -> dict:
    workspace_dir = Path.cwd()
    paths = PlatformPaths.from_workspace(workspace_dir)
    job_dir = paths.platform_dir / "jobs" / date_str / "collect-daily"
    store = JobStateStore(job_dir)
    job = store.start_job(job_type="collect-daily", date_str=date_str)
    job["steps"] = [
        {"name": "collect_sources", "status": "success"},
        {"name": "normalize_materials", "status": "success"},
        {"name": "curate_materials", "status": "pending"},
    ]
    store.write_job(job)
    return job
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_paths.py tests/platform/test_job_state.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/storage/json_store.py platform/storage/ndjson_store.py platform/storage/manifests.py platform/ingest/rss.py platform/ingest/blogs.py platform/ingest/consulting.py platform/ingest/cases.py platform/runtime.py
git commit -m "feat: add platform ingest runtime skeleton"
```

---

### Task 5: Replace tag-only dedup with aggregation, clustering, and editorial fit scoring

**Files:**
- Create: `platform/curate/relevance.py`
- Create: `platform/curate/tagging.py`
- Create: `platform/curate/dedup.py`
- Create: `platform/curate/clustering.py`
- Create: `platform/curate/scoring.py`
- Test: `tests/platform/test_clustering.py`
- Test: `tests/platform/test_scoring.py`

- [ ] **Step 1: Write failing tests for cluster assignment and editorial fit**

```python
from platform.curate.clustering import assign_clusters
from platform.curate.scoring import editorial_fit_score


def test_assign_clusters_groups_similar_materials():
    materials = [
        {"normalized_url": "https://a", "title": "Why AI tools fail adoption in enterprises", "summary": "workflow resistance", "tags": {"topic_focus": ["adoption"]}},
        {"normalized_url": "https://b", "title": "Enterprise AI adoption resistance is about workflow design", "summary": "workflow resistance", "tags": {"topic_focus": ["adoption"]}},
    ]
    clustered = assign_clusters(materials)
    assert clustered[0]["dedup"]["cluster_id"] == clustered[1]["dedup"]["cluster_id"]


def test_editorial_fit_score_rejects_pricing_without_org_signal():
    material = {
        "title": "GitHub changes Copilot pricing tiers",
        "summary": "new package pricing for teams",
        "content_text": "pricing, package, subscription",
        "tags": {"topic_focus": ["product strategy"]},
    }
    score = editorial_fit_score(material)
    assert score < 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_clustering.py tests/platform/test_scoring.py -q`
Expected: FAIL with missing module or function errors

- [ ] **Step 3: Implement aggregation and scoring primitives**

```python
# platform/curate/scoring.py
ORG_SIGNALS = [
    "workflow", "organization", "team", "manager", "management", "governance",
    "adoption", "permission", "budget", "procurement", "role", "performance",
]
LOW_FIT_SIGNALS = ["pricing", "package", "subscription", "tier", "plan", "feature launch"]


def editorial_fit_score(material: dict) -> float:
    text = " ".join([
        material.get("title", ""),
        material.get("summary", ""),
        material.get("content_text", ""),
    ]).lower()
    org_hits = sum(1 for signal in ORG_SIGNALS if signal in text)
    low_fit_hits = sum(1 for signal in LOW_FIT_SIGNALS if signal in text)
    raw = 0.2 + org_hits * 0.15 - low_fit_hits * 0.2
    return max(0.0, min(1.0, raw))
```

```python
# platform/curate/clustering.py
import hashlib


def assign_clusters(materials: list[dict]) -> list[dict]:
    for material in materials:
        seed = "|".join([
            material.get("title", "").lower(),
            material.get("summary", "").lower(),
            ",".join(material.get("tags", {}).get("topic_focus", [])),
        ])
        cluster_id = "cluster_" + hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
        material.setdefault("dedup", {})
        material["dedup"]["cluster_id"] = cluster_id
        material["dedup"]["is_primary"] = True
    return materials
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_clustering.py tests/platform/test_scoring.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/curate/relevance.py platform/curate/tagging.py platform/curate/dedup.py platform/curate/clustering.py platform/curate/scoring.py tests/platform/test_clustering.py tests/platform/test_scoring.py
git commit -m "feat: add material aggregation and editorial fit scoring"
```

---

### Task 6: Build curated article and case datasets from shared material platform

**Files:**
- Create: `platform/datasets/article_pool.py`
- Create: `platform/datasets/case_pool.py`
- Test: `tests/platform/test_article_pool.py`
- Test: `tests/platform/test_case_pool.py`

- [ ] **Step 1: Write failing tests for dataset eligibility**

```python
from platform.datasets.article_pool import build_article_pool
from platform.datasets.case_pool import build_case_pool


def test_article_pool_excludes_low_editorial_fit_primary_candidates():
    materials = [
        {"title": "GitHub pricing tiers", "editorial_fit_score": 0.2, "dedup": {"cluster_id": "c1"}, "quality": {"content_chars": 5000}},
        {"title": "AI workflow redesign in finance ops", "editorial_fit_score": 0.9, "dedup": {"cluster_id": "c2"}, "quality": {"content_chars": 5000}},
    ]
    pool = build_article_pool(materials, topic_memory={"recent_outputs": []})
    assert [item["title"] for item in pool["candidates"]] == ["AI workflow redesign in finance ops"]


def test_case_pool_requires_execution_detail_signal():
    materials = [
        {"title": "Packaging update", "editorial_fit_score": 0.8, "execution_detail_score": 0.1, "dedup": {"cluster_id": "c1"}},
        {"title": "How a support org deployed an agent", "editorial_fit_score": 0.9, "execution_detail_score": 0.8, "dedup": {"cluster_id": "c2"}},
    ]
    pool = build_case_pool(materials, topic_memory={"recent_outputs": []})
    assert [item["title"] for item in pool["candidates"]] == ["How a support org deployed an agent"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_article_pool.py tests/platform/test_case_pool.py -q`
Expected: FAIL with missing dataset builders

- [ ] **Step 3: Implement minimal dataset builders**

```python
# platform/datasets/article_pool.py
PRIMARY_TOPIC_THRESHOLD = 0.65


def build_article_pool(materials: list[dict], topic_memory: dict) -> dict:
    candidates = [
        material for material in materials
        if material.get("editorial_fit_score", 0.0) >= PRIMARY_TOPIC_THRESHOLD
        and material.get("quality", {}).get("content_chars", 0) >= 800
    ]
    return {"candidates": candidates}
```

```python
# platform/datasets/case_pool.py
CASE_DETAIL_THRESHOLD = 0.6
PRIMARY_TOPIC_THRESHOLD = 0.65


def build_case_pool(materials: list[dict], topic_memory: dict) -> dict:
    candidates = [
        material for material in materials
        if material.get("editorial_fit_score", 0.0) >= PRIMARY_TOPIC_THRESHOLD
        and material.get("execution_detail_score", 0.0) >= CASE_DETAIL_THRESHOLD
    ]
    return {"candidates": candidates}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_article_pool.py tests/platform/test_case_pool.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/datasets/article_pool.py platform/datasets/case_pool.py tests/platform/test_article_pool.py tests/platform/test_case_pool.py
git commit -m "feat: add shared article and case dataset builders"
```

---

### Task 7: Add topic memory, novelty guardrails, and usage recording

**Files:**
- Modify: `platform/curate/scoring.py`
- Create: `platform/storage/manifests.py`
- Modify: `platform/runtime.py`

- [ ] **Step 1: Write failing test for recent-cluster blocking**

```python
from platform.datasets.article_pool import build_article_pool


def test_article_pool_blocks_recent_cluster_reuse():
    materials = [
        {"title": "AI workflow redesign", "editorial_fit_score": 0.9, "dedup": {"cluster_id": "cluster_1"}, "quality": {"content_chars": 5000}},
    ]
    topic_memory = {"recent_outputs": [{"cluster_ids": ["cluster_1"]}]}
    pool = build_article_pool(materials, topic_memory=topic_memory)
    assert pool["candidates"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_article_pool.py -q`
Expected: FAIL because recent cluster logic is absent

- [ ] **Step 3: Implement recent-cluster blocking**

```python
# platform/datasets/article_pool.py
def build_article_pool(materials: list[dict], topic_memory: dict) -> dict:
    recent_clusters = {
        cluster_id
        for output in topic_memory.get("recent_outputs", [])
        for cluster_id in output.get("cluster_ids", [])
    }
    candidates = [
        material for material in materials
        if material.get("editorial_fit_score", 0.0) >= PRIMARY_TOPIC_THRESHOLD
        and material.get("quality", {}).get("content_chars", 0) >= 800
        and material.get("dedup", {}).get("cluster_id") not in recent_clusters
    ]
    return {"candidates": candidates}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_article_pool.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/datasets/article_pool.py platform/runtime.py platform/storage/manifests.py
git commit -m "feat: add topic memory guards for dataset selection"
```

---

### Task 8: Add cleanup command with 30-day retention

**Files:**
- Create: `platform/cleanup.py`
- Test: `tests/platform/test_cleanup.py`

- [ ] **Step 1: Write failing tests for retention**

```python
from datetime import date
from pathlib import Path

from platform.cleanup import prune_old_platform_data


def test_prune_old_platform_data_removes_old_intermediate_dirs(tmp_path: Path):
    old_dir = tmp_path / "platform" / "ingest" / "raw" / "2026-04-01"
    old_dir.mkdir(parents=True)
    new_dir = tmp_path / "platform" / "ingest" / "raw" / "2026-06-01"
    new_dir.mkdir(parents=True)
    prune_old_platform_data(tmp_path / "platform", today=date(2026, 6, 3), retention_days=30)
    assert not old_dir.exists()
    assert new_dir.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_cleanup.py -q`
Expected: FAIL with missing module errors

- [ ] **Step 3: Implement cleanup**

```python
# platform/cleanup.py
import shutil
from datetime import date, datetime
from pathlib import Path


def prune_old_platform_data(platform_dir: Path, today: date, retention_days: int = 30) -> None:
    cutoff = today.toordinal() - retention_days
    for root in [
        platform_dir / "ingest" / "raw",
        platform_dir / "normalize",
        platform_dir / "curate",
        platform_dir / "jobs",
    ]:
        if not root.exists():
            continue
        for child in root.iterdir():
            try:
                child_date = datetime.strptime(child.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            if child_date.toordinal() < cutoff:
                shutil.rmtree(child)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/platform/test_cleanup.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add platform/cleanup.py tests/platform/test_cleanup.py
git commit -m "feat: add 30 day cleanup command"
```

---

### Task 9: Port `write_article.py` to consume shared article datasets

**Files:**
- Modify: `write_article.py`
- Create: `platform/business/daily_article/pipeline.py`
- Create: `platform/business/daily_article/topic_planner.py`

- [ ] **Step 1: Write the failing regression test for dataset-driven article selection**

```python
from platform.business.daily_article.topic_planner import pick_primary_cluster


def test_pick_primary_cluster_prefers_high_fit_high_novelty_candidate():
    candidates = [
        {"title": "Pricing update", "editorial_fit_score": 0.2, "novelty_score": 0.9},
        {"title": "Workflow redesign", "editorial_fit_score": 0.9, "novelty_score": 0.7},
    ]
    picked = pick_primary_cluster(candidates)
    assert picked["title"] == "Workflow redesign"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_article_pool.py -q`
Expected: FAIL with missing topic planner

- [ ] **Step 3: Implement dataset-driven topic planning and bridge `write_article.py`**

```python
# platform/business/daily_article/topic_planner.py
def pick_primary_cluster(candidates: list[dict]) -> dict:
    return sorted(
        candidates,
        key=lambda item: (item.get("editorial_fit_score", 0.0), item.get("novelty_score", 0.0)),
        reverse=True,
    )[0]
```

Implementation notes:
- keep the current writing prompt logic initially
- replace direct `all_urls.tsv` reads with `article_pool.json`
- move source usage writes into shared platform state, not writer-local TSV edits

- [ ] **Step 4: Run focused verification**

Run: `pytest tests/platform/test_article_pool.py -q`
Expected: PASS

Run: `python3 platform_cli.py run article-daily --date 2026-06-03`
Expected: creates `platform/jobs/2026-06-03/article-daily/job.json` and `platform/outputs/daily-article/...`

- [ ] **Step 5: Commit**

```bash
git add write_article.py platform/business/daily_article/pipeline.py platform/business/daily_article/topic_planner.py
git commit -m "feat: route daily article pipeline through shared datasets"
```

---

### Task 10: Port `decompose_case_study.py` to consume shared case datasets

**Files:**
- Modify: `decompose_case_study.py`
- Create: `platform/business/case_study/pipeline.py`
- Create: `platform/business/case_study/ranker.py`

- [ ] **Step 1: Write the failing regression test for case ranking**

```python
from platform.business.case_study.ranker import rank_case_candidates


def test_rank_case_candidates_prefers_execution_detail():
    candidates = [
        {"title": "Strategy memo", "editorial_fit_score": 0.8, "execution_detail_score": 0.2},
        {"title": "Support org agent deployment", "editorial_fit_score": 0.8, "execution_detail_score": 0.9},
    ]
    ranked = rank_case_candidates(candidates)
    assert ranked[0]["title"] == "Support org agent deployment"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_case_pool.py -q`
Expected: FAIL with missing ranker

- [ ] **Step 3: Implement dataset-driven case ranking and bridge `decompose_case_study.py`**

```python
# platform/business/case_study/ranker.py
def rank_case_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda item: (
            item.get("execution_detail_score", 0.0),
            item.get("editorial_fit_score", 0.0),
            item.get("verification_score", 0.0),
        ),
        reverse=True,
    )
```

Implementation notes:
- replace local external-used-url state with shared `usage` writes
- keep the current case-study prompt initially
- preserve multi-source evidence merge, but source it from case dataset clusters

- [ ] **Step 4: Run focused verification**

Run: `pytest tests/platform/test_case_pool.py -q`
Expected: PASS

Run: `python3 platform_cli.py run case-daily --date 2026-06-03`
Expected: creates `platform/jobs/2026-06-03/case-daily/job.json` and `platform/outputs/case-study/...`

- [ ] **Step 5: Commit**

```bash
git add decompose_case_study.py platform/business/case_study/pipeline.py platform/business/case_study/ranker.py
git commit -m "feat: route case study pipeline through shared datasets"
```

---

### Task 11: Replace cron wrappers with single-entry platform commands

**Files:**
- Modify: `run_all.sh`
- Modify: `run_daily_article.sh`
- Modify: `README.md`

- [ ] **Step 1: Write the failing smoke test expectation**

```python
def test_smoke_documentation_lists_platform_cli_commands():
    readme = open("README.md", encoding="utf-8").read()
    assert "python3 platform_cli.py run collect-daily" in readme
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/platform/test_paths.py -q`
Expected: FAIL after smoke assertion is added or README is not updated

- [ ] **Step 3: Replace legacy wrapper logic with platform CLI invocations**

```bash
# run_all.sh
python3 platform_cli.py run collect-daily --date "$DATE"
python3 platform_cli.py run cleanup --date "$DATE"
```

```bash
# run_daily_article.sh
python3 platform_cli.py run article-daily --date "$DATE"
python3 platform_cli.py run case-daily --date "$DATE"
```

Documentation notes:
- mark legacy flow as archived
- document `platform/` layout and 30-day retention
- document that article and case pipelines share one curated material layer

- [ ] **Step 4: Run verification**

Run: `bash run_all.sh`
Expected: platform collect job runs without invoking `poll_and_save.py`

Run: `bash run_daily_article.sh`
Expected: article and case jobs run through `platform_cli.py`

- [ ] **Step 5: Commit**

```bash
git add run_all.sh run_daily_article.sh README.md
git commit -m "feat: switch cron wrappers to platform cli"
```

---

### Task 12: Run full verification and remove legacy authority

**Files:**
- Modify: any touched files above as needed

- [ ] **Step 1: Run targeted unit and integration tests**

Run: `pytest tests/platform -q`
Expected: PASS

- [ ] **Step 2: Run end-to-end dry-runs**

Run: `python3 platform_cli.py run collect-daily --date 2026-06-03`
Expected: `platform/ingest`, `platform/normalize`, `platform/curate`, and `platform/jobs/2026-06-03/collect-daily/job.json` created

Run: `python3 platform_cli.py run article-daily --date 2026-06-03`
Expected: `platform/datasets/2026-06-03/article_pool.json` and `platform/outputs/daily-article/...` created

Run: `python3 platform_cli.py run case-daily --date 2026-06-03`
Expected: `platform/datasets/2026-06-03/case_pool.json` and `platform/outputs/case-study/...` created

Run: `python3 platform_cli.py run cleanup --date 2026-06-03`
Expected: directories older than 30 days under `platform/ingest/raw`, `platform/normalize`, `platform/curate`, and `platform/jobs` removed

- [ ] **Step 3: Audit that legacy runtime files are no longer authoritative**

Checks:
- `write_article.py` no longer reads `all_urls.tsv`
- `decompose_case_study.py` no longer writes `.state/external_used_urls.txt`
- `run_all.sh` no longer backgrounds `poll_and_save.py`
- `run_daily_article.sh` no longer edits `all_urls.tsv`

- [ ] **Step 4: Fix any failing edge cases discovered in dry-runs**

Expected areas:
- empty dataset handling
- publish failure persistence
- cluster reuse tracking
- cleanup preserving long-lived state files

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: complete shared content platform migration"
```

---

## Spec Coverage Check

- Shared content platform for article and case pipelines: covered by Tasks 1-10.
- Pure code-driven scheduling with durable job state: covered by Tasks 1, 2, 4, 11.
- Replace tag-only dedup with aggregation and topic-cluster logic: covered by Tasks 5-7.
- Add editorial fit gating so AI-adjacent pricing stories do not become primary topics: covered by Tasks 5-7.
- 30-day cleanup for file-based storage: covered by Task 8.
- Drop historical baggage rather than preserving `all_urls.tsv` compatibility: covered by Tasks 9-12.

## Placeholder Scan

No `TODO`, `TBD`, or deferred placeholders were intentionally left in this plan. Any “minimal implementation” code blocks are scaffolding targets, not final architecture limits.

## Type Consistency Check

- The plan consistently uses `cluster_id`, `editorial_fit_score`, `execution_detail_score`, and `topic_memory`.
- Job names are consistently `collect-daily`, `article-daily`, `case-daily`, and `cleanup`.
- The authoritative runtime entrypoint is consistently `platform_cli.py`.
