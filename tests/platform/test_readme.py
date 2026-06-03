from pathlib import Path


def test_readme_mentions_platform_cli_runtime():
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "platform_cli.py run collect-daily" in readme
    assert "platform_cli.py run article-daily" in readme
    assert "platform/" in readme
