import shutil
from datetime import date, datetime
from pathlib import Path


RETENTION_ROOTS = (
    ("ingest", "raw"),
    ("normalize",),
    ("curate",),
    ("jobs",),
)


def prune_old_platform_data(
    platform_dir: Path,
    today: date,
    retention_days: int = 30,
) -> None:
    cutoff = today.toordinal() - retention_days

    for root_parts in RETENTION_ROOTS:
        root = platform_dir.joinpath(*root_parts)
        if not root.exists():
            continue

        for child in root.iterdir():
            try:
                child_date = datetime.strptime(child.name, "%Y-%m-%d").date()
            except ValueError:
                continue

            if child_date.toordinal() < cutoff:
                shutil.rmtree(child)
