from pathlib import Path


def get_workspace_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    return Path(__file__).resolve().parent.parent
