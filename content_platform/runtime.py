from datetime import datetime
from pathlib import Path
import subprocess
import sys

from content_platform.business.case_study.pipeline import run_case_study_pipeline
from content_platform.business.daily_article.pipeline import run_daily_article_pipeline
from content_platform.curate.clustering import assign_clusters
from content_platform.curate.scoring import editorial_fit_score
from content_platform.curate.scoring import execution_detail_score
from content_platform.cleanup import prune_old_platform_data
from content_platform.datasets.article_pool import build_article_pool
from content_platform.datasets.case_pool import build_case_pool
from content_platform.ingest.blogs import load_blog_materials
from content_platform.ingest.cases import load_case_materials
from content_platform.ingest.consulting import load_consulting_materials
from content_platform.ingest.rss import load_rss_materials
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
        else:
            enriched["execution_detail_score"] = execution_detail_score(
                {
                    "title": enriched.get("title", ""),
                    "summary": enriched.get("summary", ""),
                    "content_text": enriched.get("content_text", ""),
                }
            )
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
    raw_materials = materials
    if raw_materials is None:
        raw_materials = []
        raw_materials.extend(load_rss_materials(date_str))
        raw_materials.extend(load_blog_materials(date_str))
        raw_materials.extend(load_consulting_materials(date_str))
        raw_materials.extend(load_case_materials(date_str))
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


def _load_dataset_candidates(
    paths: PlatformPaths,
    date_str: str,
    dataset_name: str,
) -> list[dict]:
    dataset_file = paths.datasets_dir(date_str) / dataset_name
    if not dataset_file.exists():
        return []
    payload = read_json(dataset_file)
    return payload.get("candidates", [])


def _invoke_legacy_writer(script_path: Path, date_str: str, materials_file: str) -> subprocess.CompletedProcess:
    cmd = [
        sys.executable,
        str(script_path),
        "--date",
        date_str,
        "--materials",
        materials_file,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def _write_job_log(job_dir: Path, filename: str, content: str) -> str:
    path = job_dir / filename
    path.write_text(content, encoding="utf-8")
    return str(path)


def _extract_output_dir(stdout: str) -> str | None:
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if "Output:" not in line:
            continue
        return line.split("Output:", 1)[1].strip().rstrip("/")
    return None


def _capture_writer_artifacts(job_dir: Path, result: subprocess.CompletedProcess) -> dict:
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    artifacts = {
        "writer_returncode": result.returncode,
        "writer_stdout_log": _write_job_log(job_dir, "writer_stdout.log", stdout),
        "writer_stderr_log": _write_job_log(job_dir, "writer_stderr.log", stderr),
    }
    output_dir = _extract_output_dir(stdout)
    if output_dir:
        artifacts["writer_output_dir"] = output_dir
    return artifacts


def run_article_daily(
    date_str: str,
    workspace_dir: Path | None = None,
    materials: list[dict] | None = None,
) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "article-daily")
    store = JobStateStore(job_dir)
    input_materials = materials or _load_dataset_candidates(paths, date_str, "article_pool.json")

    job = store.start_job(job_type="article-daily", date_str=date_str)
    result = run_daily_article_pipeline(
        date_str=date_str,
        workspace_dir=resolved_workspace,
        materials=input_materials,
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
    if job["status"] == "success" and result.get("materials_file"):
        legacy_result = _invoke_legacy_writer(
            resolved_workspace / "write_article.py",
            date_str=date_str,
            materials_file=result["materials_file"],
        )
        job["artifacts"].update(_capture_writer_artifacts(job_dir, legacy_result))
        if legacy_result.returncode != 0:
            job["status"] = "failed"
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
    input_materials = materials or _load_dataset_candidates(paths, date_str, "case_pool.json")

    job = store.start_job(job_type="case-daily", date_str=date_str)
    result = run_case_study_pipeline(
        date_str=date_str,
        workspace_dir=resolved_workspace,
        materials=input_materials,
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
    if job["status"] == "success" and result.get("materials_file"):
        legacy_result = _invoke_legacy_writer(
            resolved_workspace / "decompose_case_study.py",
            date_str=date_str,
            materials_file=result["materials_file"],
        )
        job["artifacts"].update(_capture_writer_artifacts(job_dir, legacy_result))
        if legacy_result.returncode != 0:
            job["status"] = "failed"
    store.write_job(job)
    return job


def load_materials_file(materials_file: str | None) -> list[dict] | None:
    if not materials_file:
        return None
    path = Path(materials_file)
    if not path.exists():
        return None
    return read_json(path)
