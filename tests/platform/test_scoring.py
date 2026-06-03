from content_platform.curate.scoring import editorial_fit_score
from content_platform.curate.scoring import execution_detail_score


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


def test_editorial_fit_score_rewards_agentic_workflow_guidance():
    material = {
        "title": "A Guide to Which AI to Use in the Agentic Era",
        "summary": "It's not just chatbots anymore",
        "content_text": (
            "using AI has changed dramatically as agent workflows become practical. "
            "you can assign them to a task and they do them, using tools as appropriate. "
            "because of this change, you have to consider models, apps, and harnesses "
            "when deciding what AI to use across work."
        ),
        "tags": {"topic_focus": ["agentic ai"]},
    }

    score = editorial_fit_score(material)

    assert score >= 0.65


def test_editorial_fit_score_rewards_ai_governance_frameworks():
    material = {
        "title": "Responsible Scaling Policy",
        "summary": "updated risk governance framework for frontier AI systems",
        "content_text": (
            "this policy introduces capability thresholds, internal governance, "
            "risk management, safeguards, and model evaluation processes."
        ),
        "tags": {"topic_focus": ["governance"]},
    }

    score = editorial_fit_score(material)

    assert score >= 0.65


def test_execution_detail_score_rewards_operating_framework_detail():
    material = {
        "title": "Responsible Scaling Policy",
        "summary": "updated risk governance framework for frontier AI systems",
        "content_text": (
            "this update introduces capability thresholds, internal governance, "
            "risk management, safeguards, model evaluation processes, and "
            "practical implementation guidance."
        ),
    }

    score = execution_detail_score(material)

    assert score >= 0.6
