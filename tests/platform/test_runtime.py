from pathlib import Path

from content_platform.runtime import run_article_daily, run_case_daily, run_collect_daily


def test_collect_daily_writes_job_file(tmp_path: Path):
    result = run_collect_daily(date_str="2026-06-03", workspace_dir=tmp_path)

    assert result["job_type"] == "collect-daily"
    assert (
        tmp_path / "platform" / "jobs" / "2026-06-03" / "collect-daily" / "job.json"
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
