from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_PARAMS
    ]
    normalized_path = parts.path.rstrip("/") or "/"
    normalized = parts._replace(
        path=normalized_path,
        query=urlencode(filtered_query),
        fragment="",
    )
    value = urlunsplit(normalized)
    return value[:-1] if value.endswith("/") and normalized_path == "/" else value.rstrip("/")
