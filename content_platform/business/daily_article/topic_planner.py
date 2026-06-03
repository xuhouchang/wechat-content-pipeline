def pick_primary_cluster(candidates: list[dict]) -> dict:
    return sorted(
        candidates,
        key=lambda item: (
            item.get("editorial_fit_score", 0.0),
            item.get("novelty_score", 0.0),
        ),
        reverse=True,
    )[0]
