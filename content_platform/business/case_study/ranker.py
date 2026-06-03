def rank_case_candidates(candidates: list[dict]) -> list[dict]:
    return sorted(
        candidates,
        key=lambda item: (
            item.get("execution_detail_score", 0.0),
            item.get("editorial_fit_score", 0.0),
            item.get("verification_score", 0.0),
        ),
        reverse=True,
    )
