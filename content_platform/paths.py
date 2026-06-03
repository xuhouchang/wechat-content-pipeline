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

    def jobs_dir(self, date_str: str) -> Path:
        return self.platform_dir / "jobs" / date_str

    def job_dir(self, date_str: str, job_name: str) -> Path:
        return self.jobs_dir(date_str) / job_name
