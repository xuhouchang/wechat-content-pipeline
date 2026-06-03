import json
from pathlib import Path

from content_platform.business.case_study.ranker import rank_case_candidates
from content_platform.datasets.case_pool import build_case_pool


def run_case_study_pipeline(
    date_str: str,
    workspace_dir: Path,
    materials: list[dict],
    topic_memory: dict | None = None,
) -> dict:
    memory = topic_memory or {"recent_outputs": []}
    pool = build_case_pool(materials, topic_memory=memory)
    candidates = pool["candidates"]
    ranked = rank_case_candidates(candidates) if candidates else []
    selected = ranked[0] if ranked else None
    dataset_dir = workspace_dir / "platform" / "datasets" / date_str
    dataset_dir.mkdir(parents=True, exist_ok=True)
    selection_file = dataset_dir / "case_selection.json"
    selection_file.write_text(
        json.dumps({"candidates": ranked, "selected": selected}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"candidates": ranked, "selected": selected, "selection_file": str(selection_file)}
