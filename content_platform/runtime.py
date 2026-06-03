from datetime import datetime
from pathlib import Path

from content_platform.business.case_study.pipeline import run_case_study_pipeline
from content_platform.business.daily_article.pipeline import run_daily_article_pipeline
from content_platform.curate.clustering import assign_clusters
from content_platform.curate.scoring import editorial_fit_score
from content_platform.cleanup import prune_old_platform_data
from content_platform.datasets.article_pool import build_article_pool
from content_platform.datasets.case_pool import build_case_pool
from content_platform.job_state import JobStateStore
from content_platform.normalize.canonicalize import build_material_record
from content_platform.paths import PlatformPaths
from content_platform.storage.json_store import read_json
from content_platform.storage.json_store import write_json


def _curate_materials(raw_materials: list[dict], date_str: str) -> list[dict]:
    normalized = [
        build_material_record(material, collected_at=f"{date_str}T00:00:00+00:00")
        for material in raw_materials
    ]
    clustered = assign_clusters(normalized)
    curated = []
    for material, raw in zip(clustered, raw_materials):
        enriched = dict(material)
        enriched["editorial_fit_score"] = editorial_fit_score(
            {
                "title": enriched.get("title", ""),
                "summary": enriched.get("summary", ""),
                "content_text": enriched.get("content_text", ""),
                "tags": enriched.get("tags", {}),
            }
        )
        if "execution_detail_score" in raw:
            enriched["execution_detail_score"] = raw["execution_detail_score"]
        if "novelty_score" in raw:
            enriched["novelty_score"] = raw["novelty_score"]
        if "url" in raw:
            enriched["url"] = raw["url"]
        if "content" in raw:
            enriched["content"] = raw["content"]
        elif "content_text" in raw:
            enriched["content"] = raw["content_text"]
        curated.append(enriched)
    return curated


def run_collect_daily(
    date_str: str,
    workspace_dir: Path | None = None,
    materials: list[dict] | None = None,
) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "collect-daily")
    store = JobStateStore(job_dir)

    job = store.start_job(job_type="collect-daily", date_str=date_str)
    raw_materials = materials or []
    curated_materials = _curate_materials(raw_materials, date_str=date_str)
    article_pool = build_article_pool(curated_materials, topic_memory={"recent_outputs": []})
    case_pool = build_case_pool(curated_materials, topic_memory={"recent_outputs": []})

    write_json(paths.ingest_raw_dir(date_str) / "materials.json", raw_materials)
    write_json(paths.normalize_dir(date_str) / "materials.json", curated_materials)
    write_json(paths.curate_dir(date_str) / "materials.json", curated_materials)
    write_json(paths.datasets_dir(date_str) / "article_pool.json", article_pool)
    write_json(paths.datasets_dir(date_str) / "case_pool.json", case_pool)

    job["steps"] = [
        {"name": "collect_sources", "status": "success"},
        {"name": "normalize_materials", "status": "success"},
        {"name": "curate_materials", "status": "success"},
        {"name": "build_datasets", "status": "success"},
    ]
    job["status"] = "success"
    job["artifacts"] = {
        "ingest_file": str(paths.ingest_raw_dir(date_str) / "materials.json"),
        "normalize_file": str(paths.normalize_dir(date_str) / "materials.json"),
        "curate_file": str(paths.curate_dir(date_str) / "materials.json"),
        "article_pool_file": str(paths.datasets_dir(date_str) / "article_pool.json"),
        "case_pool_file": str(paths.datasets_dir(date_str) / "case_pool.json"),
    }
    store.write_job(job)
    return job


def run_cleanup(date_str: str, workspace_dir: Path | None = None) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "cleanup")
    store = JobStateStore(job_dir)

    job = store.start_job(job_type="cleanup", date_str=date_str)
    prune_old_platform_data(
        paths.platform_dir,
        today=datetime.strptime(date_str, "%Y-%m-%d").date(),
    )
    job["steps"] = [{"name": "cleanup_platform_data", "status": "success"}]
    job["status"] = "success"
    store.write_job(job)
    return job


def run_article_daily(
    date_str: str,
    workspace_dir: Path | None = None,
    materials: list[dict] | None = None,
) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "article-daily")
    store = JobStateStore(job_dir)

    job = store.start_job(job_type="article-daily", date_str=date_str)
    result = run_daily_article_pipeline(
        date_str=date_str,
        workspace_dir=resolved_workspace,
        materials=materials or [],
    )
    job["steps"] = [
        {"name": "build_article_pool", "status": "success"},
        {"name": "select_primary_cluster", "status": "success"},
    ]
    job["status"] = result.get("status", "failed")
    job["artifacts"] = {
        "selection_file": result.get("selection_file"),
        "materials_file": result.get("materials_file"),
    }
    store.write_job(job)
    return job


def run_case_daily(
    date_str: str,
    workspace_dir: Path | None = None,
    materials: list[dict] | None = None,
) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "case-daily")
    store = JobStateStore(job_dir)

    job = store.start_job(job_type="case-daily", date_str=date_str)
    result = run_case_study_pipeline(
        date_str=date_str,
        workspace_dir=resolved_workspace,
        materials=materials or [],
    )
    job["steps"] = [
        {"name": "build_case_pool", "status": "success"},
        {"name": "rank_case_candidates", "status": "success"},
    ]
    job["status"] = result.get("status", "failed")
    job["artifacts"] = {
        "selection_file": result.get("selection_file"),
        "materials_file": result.get("materials_file"),
    }
    store.write_job(job)
    return job


def load_materials_file(materials_file: str | None) -> list[dict] | None:
    if not materials_file:
        return None
    path = Path(materials_file)
    if not path.exists():
        return None
    return read_json(path)
