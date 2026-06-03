"""Job model helpers."""

from typing import Any


def make_job(job_id: str, job_type: str, date_str: str) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "job_type": job_type,
        "date": date_str,
        "status": "running",
        "steps": [],
    }
