from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gh_src",
    "gh_jid",
    "ref",
    "referrer",
    "trk",
    "mc_cid",
    "mc_eid",
}


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query_items = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS
    ]
    query = urlencode(sorted(query_items))
    return urlunparse((scheme, netloc, path, "", query, ""))


def guess_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path or ""
    for pattern in (
        r"/job[s]?/([a-zA-Z0-9\-_]{4,})",
        r"/positions/([a-zA-Z0-9\-_]{4,})",
        r"/jobs/([0-9]{4,})",
    ):
        match = re.search(pattern, path)
        if match:
            return match.group(1).lower()
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key in ("gh_jid", "jobid", "job_id", "jk", "jid"):
        if query.get(key):
            return query[key].lower()
    return None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def title_company_fingerprint(title: str, company: str, location: str = "") -> str:
    payload = f"{normalize_text(title)}|{normalize_text(company)}|{normalize_text(location)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
