import json
from pathlib import Path

from content_platform.business.daily_article.topic_planner import pick_primary_cluster
from content_platform.datasets.article_pool import build_article_pool


def run_daily_article_pipeline(
    date_str: str,
    workspace_dir: Path,
    materials: list[dict],
    topic_memory: dict | None = None,
) -> dict:
    memory = topic_memory or {"recent_outputs": []}
    pool = build_article_pool(materials, topic_memory=memory)
    candidates = pool["candidates"]
    if not candidates:
        return {"candidates": [], "selected": None}

    selected = pick_primary_cluster(candidates)
    dataset_dir = workspace_dir / "platform" / "datasets" / date_str
    dataset_dir.mkdir(parents=True, exist_ok=True)
    selection_file = dataset_dir / "article_selection.json"
    selection_file.write_text(
        json.dumps({"candidates": candidates, "selected": selected}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"candidates": candidates, "selected": selected, "selection_file": str(selection_file)}
