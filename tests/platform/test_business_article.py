from content_platform.business.daily_article.topic_planner import pick_primary_cluster


def test_pick_primary_cluster_prefers_high_fit_high_novelty_candidate():
    candidates = [
        {"title": "Pricing update", "editorial_fit_score": 0.2, "novelty_score": 0.9},
        {"title": "Workflow redesign", "editorial_fit_score": 0.9, "novelty_score": 0.7},
    ]

    picked = pick_primary_cluster(candidates)

    assert picked["title"] == "Workflow redesign"
