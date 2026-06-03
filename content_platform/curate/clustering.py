STOPWORDS = {
    "a",
    "about",
    "and",
    "are",
    "how",
    "in",
    "inside",
    "is",
    "it",
    "of",
    "the",
    "to",
    "why",
}

CANONICAL_TOKEN_MAP = {
    "design": "workflow",
    "enterprises": "enterprise",
    "teams": "team",
    "tools": "tool",
}

PRIORITY_CLUSTER_TOKENS = [
    "adoption",
    "workflow",
    "enterprise",
    "resistance",
    "governance",
    "permission",
    "budget",
    "manager",
    "team",
]


def _normalize_token(token: str) -> str:
    value = token.strip(" ,.!?:;()[]{}\"'").lower()
    value = CANONICAL_TOKEN_MAP.get(value, value)
    if value.endswith("s") and len(value) > 4 and value not in {"analysis"}:
        value = value[:-1]
    return value


def _tokenize(text: str) -> list[str]:
    tokens = []
    for raw_token in text.lower().split():
        token = _normalize_token(raw_token)
        if token and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def _cluster_seed(material: dict) -> str:
    tags = material.get("tags", {})
    topic_focus = tags.get("topic_focus", [])
    text = " ".join(
        [
            material.get("title", ""),
            material.get("summary", ""),
            " ".join(topic_focus),
        ]
    )
    tokens = _tokenize(text)
    seed = [token for token in PRIORITY_CLUSTER_TOKENS if token in tokens][:4]
    if not seed:
        seed = sorted(set(tokens))[:4] if tokens else ["misc"]
    return "cluster_" + "_".join(seed)


def assign_clusters(materials: list[dict]) -> list[dict]:
    clustered = []
    for material in materials:
        updated = dict(material)
        dedup = dict(updated.get("dedup", {}))
        dedup["cluster_id"] = _cluster_seed(updated)
        dedup["is_primary"] = dedup.get("is_primary", True)
        updated["dedup"] = dedup
        clustered.append(updated)
    return clustered
