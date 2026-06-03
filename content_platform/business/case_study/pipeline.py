from pathlib import Path

from content_platform.business.case_study.ranker import rank_case_candidates
from content_platform.datasets.case_pool import build_case_pool
from content_platform.storage.json_store import write_json


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
    materials_file = dataset_dir / "case_materials.json"
    status = "success" if selected else "failed"
    write_json(selection_file, {"candidates": ranked, "selected": selected, "status": status})
    write_json(materials_file, [selected] if selected else [])
    return {
        "candidates": ranked,
        "selected": selected,
        "selection_file": str(selection_file),
        "materials_file": str(materials_file),
        "status": status,
    }
