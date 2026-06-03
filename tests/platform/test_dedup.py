from content_platform.normalize.canonicalize import build_material_record


def test_build_material_record_tracks_content_length():
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

    assert record["quality"]["content_chars"] == len("hello world")
