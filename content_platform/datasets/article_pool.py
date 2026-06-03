PRIMARY_TOPIC_THRESHOLD = 0.65
MIN_CONTENT_CHARS = 800


def _recent_cluster_ids(topic_memory: dict) -> set[str]:
    return {
        cluster_id
        for output in topic_memory.get("recent_outputs", [])
        for cluster_id in output.get("cluster_ids", [])
    }


def build_article_pool(materials: list[dict], topic_memory: dict) -> dict:
    recent_clusters = _recent_cluster_ids(topic_memory)
    candidates = [
        material
        for material in materials
        if material.get("editorial_fit_score", 0.0) >= PRIMARY_TOPIC_THRESHOLD
        and material.get("quality", {}).get("content_chars", 0) >= MIN_CONTENT_CHARS
        and material.get("dedup", {}).get("cluster_id") not in recent_clusters
    ]
    return {"candidates": candidates}
