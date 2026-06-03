from datetime import date
from pathlib import Path

from content_platform.cleanup import prune_old_platform_data


def test_prune_old_platform_data_removes_old_intermediate_dirs(tmp_path: Path):
    old_dir = tmp_path / "platform" / "ingest" / "raw" / "2026-04-01"
    old_dir.mkdir(parents=True)
    new_dir = tmp_path / "platform" / "ingest" / "raw" / "2026-06-01"
    new_dir.mkdir(parents=True)

    prune_old_platform_data(
        tmp_path / "platform",
        today=date(2026, 6, 3),
        retention_days=30,
    )

    assert not old_dir.exists()
    assert new_dir.exists()
