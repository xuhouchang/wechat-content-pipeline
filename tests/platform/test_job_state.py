from pathlib import Path

from content_platform.job_state import JobStateStore


def test_job_state_store_creates_job_file(tmp_path: Path):
    store = JobStateStore(tmp_path)

    job = store.start_job(job_type="collect-daily", date_str="2026-06-03")

    assert job["status"] == "running"
    assert (tmp_path / "job.json").exists()


def test_job_state_store_resumes_failed_step(tmp_path: Path):
    store = JobStateStore(tmp_path)
    store.write_job(
        {
            "job_id": "collect-daily_2026-06-03_001",
            "status": "failed",
            "steps": [
                {"name": "collect_sources", "status": "success"},
                {"name": "normalize_materials", "status": "failed"},
                {"name": "curate_materials", "status": "pending"},
            ],
        }
    )

    assert store.first_incomplete_step()["name"] == "normalize_materials"
