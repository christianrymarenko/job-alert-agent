from src.core.canonicalize import canonicalize_url


def test_canonicalize_removes_utm_and_fragment() -> None:
    url = "https://example.com/jobs/123?utm_source=linkedin&page=1#top"
    canonical = canonicalize_url(url)
    assert canonical == "https://example.com/jobs/123?page=1"
