from content_platform.datasets.case_pool import build_case_pool


def test_case_pool_requires_execution_detail_signal():
    materials = [
        {
            "title": "Packaging update",
            "editorial_fit_score": 0.8,
            "execution_detail_score": 0.1,
            "dedup": {"cluster_id": "c1"},
        },
        {
            "title": "How a support org deployed an agent",
            "editorial_fit_score": 0.9,
            "execution_detail_score": 0.8,
            "dedup": {"cluster_id": "c2"},
        },
    ]

    pool = build_case_pool(materials, topic_memory={"recent_outputs": []})

    assert [item["title"] for item in pool["candidates"]] == [
        "How a support org deployed an agent"
    ]
