from content_platform.curate.scoring import editorial_fit_score


def test_editorial_fit_score_rejects_pricing_without_org_signal():
    material = {
        "title": "GitHub changes Copilot pricing tiers",
        "summary": "new package pricing for teams",
        "content_text": "pricing package subscription tier changes for paid plans",
        "tags": {"topic_focus": ["product strategy"]},
    }

    score = editorial_fit_score(material)

    assert score < 0.5


def test_editorial_fit_score_rewards_org_change_signal():
    material = {
        "title": "Why enterprise AI adoption fails in support teams",
        "summary": "workflow redesign, manager incentives, trust and governance",
        "content_text": (
            "enterprise workflow redesign changed team roles, manager incentives, "
            "governance boundaries, adoption resistance and permissions"
        ),
        "tags": {"topic_focus": ["adoption"]},
    }

    score = editorial_fit_score(material)

    assert score >= 0.75
