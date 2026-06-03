from content_platform.business.case_study.ranker import rank_case_candidates


def test_rank_case_candidates_prefers_execution_detail():
    candidates = [
        {"title": "Strategy memo", "editorial_fit_score": 0.8, "execution_detail_score": 0.2},
        {"title": "Support org agent deployment", "editorial_fit_score": 0.8, "execution_detail_score": 0.9},
    ]

    ranked = rank_case_candidates(candidates)

    assert ranked[0]["title"] == "Support org agent deployment"
