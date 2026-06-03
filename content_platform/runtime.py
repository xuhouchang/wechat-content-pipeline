from datetime import datetime
from pathlib import Path

from content_platform.cleanup import prune_old_platform_data
from content_platform.job_state import JobStateStore
from content_platform.paths import PlatformPaths


def run_collect_daily(date_str: str, workspace_dir: Path | None = None) -> dict:
    resolved_workspace = Path(workspace_dir or Path.cwd())
    paths = PlatformPaths.from_workspace(resolved_workspace)
    job_dir = paths.job_dir(date_str, "collect-daily")
    store = JobStateStore(job_dir)

    job = store.start_job(job_type="collect-daily", date_str=date_str)
    job["steps"] = [
        {"name": "collect_sources", "status": "success"},
        {"name": "normalize_materials", "status": "success"},
        {"name": "curate_materials", "status": "pending"},
    ]
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
