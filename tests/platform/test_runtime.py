from pathlib import Path

from content_platform.runtime import run_article_daily, run_case_daily, run_collect_daily


LONG_ARTICLE_TEXT = " ".join(
    [
        "enterprise workflow redesign manager incentives trust governance adoption resistance permissions"
        for _ in range(30)
    ]
)


def test_collect_daily_writes_job_file(tmp_path: Path):
    result = run_collect_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "url": "https://example.com/adoption",
                "title": "Why enterprise AI adoption stalls",
                "summary": "workflow redesign and manager incentives",
                "content_text": LONG_ARTICLE_TEXT,
                "source_type": "rss",
                "source_name": "Example Feed",
                "execution_detail_score": 0.8,
                "novelty_score": 0.7,
            },
            {
                "url": "https://example.com/pricing",
                "title": "GitHub changes Copilot pricing tiers",
                "summary": "new package pricing for teams",
                "content_text": "pricing package subscription tier changes for paid plans",
                "source_type": "blogs",
                "source_name": "Example Blog",
                "execution_detail_score": 0.1,
                "novelty_score": 0.9,
            },
        ],
    )

    assert result["job_type"] == "collect-daily"
    assert (
        tmp_path / "platform" / "jobs" / "2026-06-03" / "collect-daily" / "job.json"
    ).exists()
    assert (
        tmp_path / "platform" / "ingest" / "raw" / "2026-06-03" / "materials.json"
    ).exists()
    assert (
        tmp_path / "platform" / "normalize" / "2026-06-03" / "materials.json"
    ).exists()
    assert (
        tmp_path / "platform" / "curate" / "2026-06-03" / "materials.json"
    ).exists()
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "article_pool.json"
    ).exists()
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "case_pool.json"
    ).exists()


def test_article_daily_writes_selection_artifact(tmp_path: Path):
    result = run_article_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "title": "GitHub pricing tiers",
                "editorial_fit_score": 0.2,
                "novelty_score": 0.9,
                "dedup": {"cluster_id": "c1"},
                "quality": {"content_chars": 5000},
            },
            {
                "title": "Workflow redesign in support ops",
                "editorial_fit_score": 0.9,
                "novelty_score": 0.7,
                "dedup": {"cluster_id": "c2"},
                "quality": {"content_chars": 5000},
                "url": "https://example.com/article",
                "content": "substantive content",
            },
        ],
    )

    assert result["job_type"] == "article-daily"
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "article_selection.json"
    ).exists()
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "article_materials.json"
    ).exists()


def test_article_daily_fails_when_no_candidates(tmp_path: Path):
    result = run_article_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "title": "GitHub pricing tiers",
                "editorial_fit_score": 0.2,
                "novelty_score": 0.9,
                "dedup": {"cluster_id": "c1"},
                "quality": {"content_chars": 5000},
            },
        ],
    )

    assert result["status"] == "failed"


def test_case_daily_writes_selection_artifact(tmp_path: Path):
    result = run_case_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "title": "Packaging update",
                "editorial_fit_score": 0.8,
                "execution_detail_score": 0.2,
                "dedup": {"cluster_id": "c1"},
            },
            {
                "title": "Support org agent deployment",
                "editorial_fit_score": 0.8,
                "execution_detail_score": 0.9,
                "dedup": {"cluster_id": "c2"},
                "url": "https://example.com/case",
                "content": "substantive content",
            },
        ],
    )

    assert result["job_type"] == "case-daily"
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "case_selection.json"
    ).exists()
    assert (
        tmp_path / "platform" / "datasets" / "2026-06-03" / "case_materials.json"
    ).exists()


def test_case_daily_fails_when_no_candidates(tmp_path: Path):
    result = run_case_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "title": "Packaging update",
                "editorial_fit_score": 0.8,
                "execution_detail_score": 0.2,
                "dedup": {"cluster_id": "c1"},
            },
        ],
    )

    assert result["status"] == "failed"


def test_article_daily_uses_collect_dataset_when_materials_not_provided(tmp_path: Path):
    run_collect_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "url": "https://example.com/adoption",
                "title": "Why enterprise AI adoption stalls",
                "summary": "workflow redesign and manager incentives",
                "content_text": LONG_ARTICLE_TEXT,
                "source_type": "rss",
                "source_name": "Example Feed",
                "execution_detail_score": 0.8,
                "novelty_score": 0.7,
            }
        ],
    )

    result = run_article_daily(date_str="2026-06-03", workspace_dir=tmp_path)

    assert result["status"] == "success"


def test_case_daily_uses_collect_dataset_when_materials_not_provided(tmp_path: Path):
    run_collect_daily(
        date_str="2026-06-03",
        workspace_dir=tmp_path,
        materials=[
            {
                "url": "https://example.com/case",
                "title": "Support org agent deployment",
                "summary": "execution details for workflow redesign",
                "content_text": LONG_ARTICLE_TEXT,
                "source_type": "rss",
                "source_name": "Example Feed",
                "execution_detail_score": 0.9,
                "novelty_score": 0.7,
            }
        ],
    )

    result = run_case_daily(date_str="2026-06-03", workspace_dir=tmp_path)

    assert result["status"] == "success"
