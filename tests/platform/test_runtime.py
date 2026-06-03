from pathlib import Path

from content_platform.runtime import run_collect_daily


def test_collect_daily_writes_job_file(tmp_path: Path):
    result = run_collect_daily(date_str="2026-06-03", workspace_dir=tmp_path)

    assert result["job_type"] == "collect-daily"
    assert (
        tmp_path / "platform" / "jobs" / "2026-06-03" / "collect-daily" / "job.json"
    ).exists()
