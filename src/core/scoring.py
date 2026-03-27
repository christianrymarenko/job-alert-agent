from __future__ import annotations

import re

from src.core.models import JobPosting, SearchSettings

TITLE_BONUS_TERMS = {
    "ai": 14,
    "ki": 14,
    "genai": 14,
    "consultant": 10,
    "berater": 10,
    "manager": 9,
    "lead": 9,
    "projektleitung": 10,
    "projektmanager": 8,
    "transformation": 8,
    "adoption": 7,
    "enablement": 7,
    "strategy": 7,
    "produkt": 6,
    "product": 6,
    "implementation": 8,
    "delivery": 7,
}

BODY_BONUS_TERMS = {
    "stakeholder": 6,
    "consulting": 7,
    "beratung": 7,
    "digital transformation": 8,
    "rollout": 7,
    "use case": 6,
    "projektleitung": 7,
    "programm": 5,
    "governance": 5,
    "kunden": 5,
    "customer": 5,
}

NEGATIVE_TERMS = {
    "machine learning engineer": -25,
    "ml engineer": -24,
    "data scientist": -22,
    "research scientist": -24,
    "phd": -14,
    "backend developer": -18,
    "full stack": -18,
    "deep learning": -16,
    "mlops": -18,
    "working student": -28,
    "werkstudent": -28,
    "intern": -30,
    "internship": -30,
    "junior": -12,
}

GERMANY_TERMS = {
    "germany",
    "deutschland",
    "berlin",
    "muenchen",
    "munich",
    "bayern",
    "bavaria",
    "hamburg",
    "koeln",
    "cologne",
    "frankfurt",
    "stuttgart",
    "duesseldorf",
    "dusseldorf",
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _count_weighted_terms(text: str, weighted_terms: dict[str, int]) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    for term, weight in weighted_terms.items():
        if term in text:
            score += weight
            reasons.append(term)
    return score, reasons


def score_job(job: JobPosting, search: SearchSettings) -> tuple[int, str]:
    """Return score in [0, 100] and short reason string."""
    title = _normalize(job.title)
    snippet = _normalize(job.description_snippet)
    location = _normalize(job.location)
    blob = " ".join([title, snippet, _normalize(job.company), location])

    score = 0
    reasons: list[str] = []

    title_score, title_hits = _count_weighted_terms(title, TITLE_BONUS_TERMS)
    score += title_score
    if title_hits:
        reasons.append(f"Title: {', '.join(sorted(set(title_hits)))}")

    body_score, body_hits = _count_weighted_terms(blob, BODY_BONUS_TERMS)
    score += body_score
    if body_hits:
        reasons.append(f"Body: {', '.join(sorted(set(body_hits)))}")

    neg_score, neg_hits = _count_weighted_terms(blob, NEGATIVE_TERMS)
    score += neg_score
    if neg_hits:
        reasons.append(f"Penalties: {', '.join(sorted(set(neg_hits)))}")

    keyword_hits = 0
    for keyword in search.keywords:
        if _normalize(keyword) in blob:
            keyword_hits += 1
    if keyword_hits:
        score += min(24, keyword_hits * 6)
        reasons.append(f"Keyword hits: {keyword_hits}")

    seniority_bonus = 0
    if any(term in blob for term in ("senior", "lead", "leiter", "head", "principal")):
        seniority_bonus += 10
    if "junior" in blob or "trainee" in blob:
        seniority_bonus -= 8
    score += seniority_bonus
    if seniority_bonus:
        reasons.append(f"Seniority: {seniority_bonus}")

    location_bonus = 0
    if any(term in blob for term in GERMANY_TERMS):
        location_bonus += 10
    preferred_hits = sum(1 for loc in search.preferred_locations if _normalize(loc) in blob)
    if preferred_hits:
        location_bonus += min(8, preferred_hits * 3)
    if search.allow_remote and any(term in blob for term in ("remote", "fully remote")):
        location_bonus += 5
    if search.allow_hybrid and "hybrid" in blob:
        location_bonus += 4
    if any(
        term in location
        for term in ("usa", "united states", "switzerland", "zurich", "london", "uk")
    ):
        location_bonus -= 8
    score += location_bonus
    reasons.append(f"Location: {location_bonus}")

    # Base score so sparse but potentially relevant snippets can still pass thresholding.
    score += 25
    score = max(0, min(100, score))
    reason = "; ".join(reasons) if reasons else "General AI/KI business relevance"
    return score, reason
