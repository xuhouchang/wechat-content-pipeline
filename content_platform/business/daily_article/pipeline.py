from pathlib import Path

from content_platform.business.daily_article.topic_planner import pick_primary_cluster
from content_platform.datasets.article_pool import build_article_pool
from content_platform.storage.json_store import write_json


def run_daily_article_pipeline(
    date_str: str,
    workspace_dir: Path,
    materials: list[dict],
    topic_memory: dict | None = None,
) -> dict:
    memory = topic_memory or {"recent_outputs": []}
    pool = build_article_pool(materials, topic_memory=memory)
    candidates = pool["candidates"]
    dataset_dir = workspace_dir / "platform" / "datasets" / date_str
    dataset_dir.mkdir(parents=True, exist_ok=True)
    selection_file = dataset_dir / "article_selection.json"
    materials_file = dataset_dir / "article_materials.json"
    if not candidates:
        write_json(selection_file, {"candidates": [], "selected": None, "status": "failed"})
        write_json(materials_file, [])
        return {
            "candidates": [],
            "selected": None,
            "selection_file": str(selection_file),
            "materials_file": str(materials_file),
            "status": "failed",
        }

    selected = pick_primary_cluster(candidates)
    write_json(selection_file, {"candidates": candidates, "selected": selected, "status": "success"})
    write_json(materials_file, [selected])
    return {
        "candidates": candidates,
        "selected": selected,
        "selection_file": str(selection_file),
        "materials_file": str(materials_file),
        "status": "success",
    }
