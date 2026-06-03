from pathlib import Path

from content_platform.paths import PlatformPaths


def test_platform_paths_are_rooted_under_workspace(tmp_path: Path):
    paths = PlatformPaths.from_workspace(tmp_path)

    assert paths.platform_dir == tmp_path / "platform"
    assert (
        paths.ingest_raw_dir("2026-06-03")
        == tmp_path / "platform" / "ingest" / "raw" / "2026-06-03"
    )


def test_platform_cli_exposes_expected_jobs():
    from content_platform.cli import build_parser

    parser = build_parser()
    args = parser.parse_args(["run", "collect-daily", "--date", "2026-06-03"])

    assert args.command == "run"
    assert args.job_name == "collect-daily"
    assert args.date == "2026-06-03"
