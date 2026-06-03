from pathlib import Path


def test_requirements_include_collector_runtime_dependencies():
    requirements = Path("requirements.txt").read_text(encoding="utf-8").lower()

    assert "feedparser" in requirements
    assert "pyyaml" in requirements
    assert "requests" in requirements
