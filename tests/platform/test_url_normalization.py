from content_platform.normalize.canonicalize import build_material_record
from content_platform.normalize.urls import normalize_url


def test_normalize_url_removes_tracking_and_fragment():
    url = "https://example.com/post/?utm_source=x#section"

    assert normalize_url(url) == "https://example.com/post"


def test_build_material_record_sets_content_hash():
    record = build_material_record(
        {
            "url": "https://example.com/post",
            "title": "Example",
            "content_text": "hello world",
            "source_type": "rss",
            "source_name": "Example Source",
        },
        collected_at="2026-06-03T05:00:00+08:00",
    )

    assert record["normalized_url"] == "https://example.com/post"
    assert record["content_hash"].startswith("sha256:")
