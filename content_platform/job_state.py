import json
from pathlib import Path
from typing import Any

from content_platform.models.job import make_job


class JobStateStore:
    def __init__(self, job_dir: Path):
        self.job_dir = Path(job_dir)
        self.job_file = self.job_dir / "job.json"
        self.job_dir.mkdir(parents=True, exist_ok=True)

    def start_job(self, job_type: str, date_str: str) -> dict[str, Any]:
        job = make_job(
            job_id=f"{job_type}_{date_str}_001",
            job_type=job_type,
            date_str=date_str,
        )
        self.write_job(job)
        return job

    def write_job(self, job: dict[str, Any]) -> None:
        self.job_file.write_text(
            json.dumps(job, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def read_job(self) -> dict[str, Any]:
        return json.loads(self.job_file.read_text(encoding="utf-8"))

    def first_incomplete_step(self) -> dict[str, Any] | None:
        for step in self.read_job().get("steps", []):
            if step.get("status") != "success":
                return step
        return None
