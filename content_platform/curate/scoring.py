ORG_SIGNALS = {
    "across work",
    "adoption",
    "agent workflows",
    "agentic",
    "apps",
    "budget",
    "enterprise",
    "governance",
    "internal governance",
    "harnesses",
    "incentive",
    "manager",
    "models",
    "organization",
    "policy",
    "permission",
    "permissions",
    "procurement",
    "risk management",
    "resistance",
    "role",
    "roles",
    "safeguards",
    "shadow ai",
    "task",
    "team",
    "teams",
    "thresholds",
    "tools",
    "trust",
    "use ai",
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

EXECUTION_DETAIL_SIGNALS = {
    "capability thresholds",
    "evaluation",
    "framework",
    "implementation",
    "internal governance",
    "operating model",
    "process",
    "processes",
    "risk management",
    "rollout",
    "safeguards",
    "step",
    "steps",
    "thresholds",
    "workflow",
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


def execution_detail_score(material: dict) -> float:
    text = " ".join(
        [
            material.get("title", ""),
            material.get("summary", ""),
            material.get("content_text", ""),
        ]
    ).lower()
    detail_hits = sum(1 for signal in EXECUTION_DETAIL_SIGNALS if signal in text)
    raw_score = 0.12 + (detail_hits * 0.12)
    return max(0.0, min(1.0, raw_score))
