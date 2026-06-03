from content_platform.curate.clustering import assign_clusters


def test_assign_clusters_groups_similar_materials():
    materials = [
        {
            "normalized_url": "https://a",
            "title": "Why AI tools fail adoption in enterprises",
            "summary": "workflow resistance inside enterprise teams",
            "tags": {"topic_focus": ["adoption"]},
        },
        {
            "normalized_url": "https://b",
            "title": "Enterprise AI adoption resistance is about workflow design",
            "summary": "workflow resistance inside enterprise teams",
            "tags": {"topic_focus": ["adoption"]},
        },
    ]

    clustered = assign_clusters(materials)

    assert clustered[0]["dedup"]["cluster_id"] == clustered[1]["dedup"]["cluster_id"]
