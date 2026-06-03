ORG_SIGNALS = {
    "adoption",
    "budget",
    "enterprise",
    "governance",
    "incentive",
    "manager",
    "organization",
    "permission",
    "permissions",
    "procurement",
    "resistance",
    "role",
    "roles",
    "shadow ai",
    "team",
    "teams",
    "trust",
    "workflow",
}

LOW_FIT_SIGNALS = {
    "feature launch",
    "package",
    "paid plan",
    "plan",
    "pricing",
    "subscription",
    "tier",
    "tiers",
}


def editorial_fit_score(material: dict) -> float:
    text = " ".join(
        [
            material.get("title", ""),
            material.get("summary", ""),
            material.get("content_text", ""),
        ]
    ).lower()
    org_hits = sum(1 for signal in ORG_SIGNALS if signal in text)
    low_fit_hits = sum(1 for signal in LOW_FIT_SIGNALS if signal in text)
    raw_score = 0.2 + (org_hits * 0.12) - (low_fit_hits * 0.18)
    return max(0.0, min(1.0, raw_score))
