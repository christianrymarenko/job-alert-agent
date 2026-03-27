from __future__ import annotations

import re

from src.core.models import JobPosting, SearchSettings

# Strong signals in title for business-facing AI profile fit.
TITLE_BONUS_TERMS = {
    "ai": 14,
    "ki": 14,
    "genai": 14,
    "consultant": 12,
    "berater": 12,
    "manager": 10,
    "lead": 10,
    "projektleitung": 12,
    "projektmanager": 10,
    "program manager": 10,
    "programm manager": 10,
    "transformation": 11,
    "adoption": 9,
    "enablement": 9,
    "strategy": 9,
    "strategie": 9,
    "implementation": 10,
    "implementierung": 10,
    "delivery": 8,
    "product": 8,
    "produkt": 8,
    "owner": 6,
}

# Semantics from description/snippet emphasizing consulting + business leadership.
BODY_BONUS_TERMS = {
    "ai strategy": 9,
    "ki strategie": 9,
    "digital transformation": 10,
    "transformation": 8,
    "adoption": 8,
    "enablement": 8,
    "rollout": 8,
    "implementation": 8,
    "implementierung": 8,
    "use case": 7,
    "stakeholder management": 9,
    "stakeholder": 7,
    "consulting": 9,
    "beratung": 9,
    "project leadership": 8,
    "projektleitung": 8,
    "program management": 8,
    "programmmanagement": 8,
    "pmo": 6,
    "governance": 6,
    "change management": 8,
    "business development": 7,
    "saas": 8,
    "platform": 7,
    "plattform": 7,
    "product leadership": 7,
    "kunden": 6,
    "customer": 6,
}

# Language and geography preferences for this candidate.
GERMAN_LANGUAGE_TERMS = {
    "deutsch",
    "deutschkenntnisse",
    "german",
    "c1",
    "c2",
    "muttersprach",
}

MUNICH_BAVARIA_TERMS = {"munich", "muenchen", "münchen", "bayern", "bavaria"}

GERMANY_TERMS = {
    "germany",
    "deutschland",
    "berlin",
    "muenchen",
    "münchen",
    "munich",
    "bayern",
    "bavaria",
    "hamburg",
    "koeln",
    "köln",
    "cologne",
    "frankfurt",
    "stuttgart",
    "duesseldorf",
    "düsseldorf",
    "dusseldorf",
}

# Strong downranking for hands-on technical engineering roles.
NEGATIVE_TERMS = {
    "machine learning engineer": -35,
    "ml engineer": -34,
    "data scientist": -30,
    "research scientist": -30,
    "research engineer": -28,
    "phd": -18,
    "backend developer": -24,
    "full stack": -24,
    "deep learning engineer": -28,
    "deep learning": -18,
    "mlops": -24,
    "software engineer": -22,
    "python developer": -18,
    "hands-on coding": -16,
    "working student": -30,
    "werkstudent": -30,
    "intern": -35,
    "internship": -35,
    "junior": -14,
    "trainee": -14,
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
    """Score role relevance for senior business-facing AI transformation profile."""
    title = _normalize(job.title)
    snippet = _normalize(job.description_snippet)
    company = _normalize(job.company)
    location = _normalize(job.location)
    blob = " ".join([title, snippet, company, location])

    score = 0
    reasons: list[str] = []

    title_score, title_hits = _count_weighted_terms(title, TITLE_BONUS_TERMS)
    score += title_score
    if title_hits:
        reasons.append(f"Title: {', '.join(sorted(set(title_hits)))}")

    body_score, body_hits = _count_weighted_terms(blob, BODY_BONUS_TERMS)
    score += body_score
    if body_hits:
        reasons.append(f"Business AI fit: {', '.join(sorted(set(body_hits)))}")

    # Slightly reward semantic proximity to configured search intent.
    keyword_hits = 0
    for keyword in search.keywords:
        if _normalize(keyword) in blob:
            keyword_hits += 1
    if keyword_hits:
        score += min(24, keyword_hits * 6)
        reasons.append(f"Keyword hits: {keyword_hits}")

    # Seniority handling: prefer senior consultant/manager/lead forms.
    seniority_bonus = 0
    if any(term in blob for term in ("senior", "lead", "leiter", "head", "principal")):
        seniority_bonus += 12
    if any(term in blob for term in ("junior", "trainee", "entry level")):
        seniority_bonus -= 10
    score += seniority_bonus
    if seniority_bonus:
        reasons.append(f"Seniority: {seniority_bonus}")

    location_bonus = 0
    if any(term in blob for term in GERMANY_TERMS):
        location_bonus += 10
    if any(term in blob for term in MUNICH_BAVARIA_TERMS):
        location_bonus += 8
    preferred_hits = sum(1 for loc in search.preferred_locations if _normalize(loc) in blob)
    if preferred_hits:
        location_bonus += min(10, preferred_hits * 3)
    if search.allow_remote and any(term in blob for term in ("remote", "fully remote", "deutschlandweit")):
        location_bonus += 5
    if search.allow_hybrid and "hybrid" in blob:
        location_bonus += 5
    if any(
        term in location
        for term in ("usa", "united states", "switzerland", "zurich", "london", "uk")
    ):
        location_bonus -= 12
    score += location_bonus
    reasons.append(f"Location: {location_bonus}")

    language_bonus = 0
    if any(term in blob for term in GERMAN_LANGUAGE_TERMS):
        language_bonus += 6
    score += language_bonus
    if language_bonus:
        reasons.append("Language: German preferred")

    neg_score, neg_hits = _count_weighted_terms(blob, NEGATIVE_TERMS)
    score += neg_score
    if neg_hits:
        reasons.append(f"Penalties: {', '.join(sorted(set(neg_hits)))}")

    # Base score still allows sparse but likely-relevant postings to pass.
    score += 18

    # Hard brake: technical engineering-heavy titles should stay low even with AI mentions.
    if any(term in title for term in ("engineer", "developer", "scientist", "mlops")) and not any(
        keep in title for keep in ("manager", "lead", "consultant", "berater", "projekt")
    ):
        score -= 20
        reasons.append("Engineering-heavy title downrank")

    score = max(0, min(100, score))
    reason = "; ".join(reasons) if reasons else "General AI/KI business relevance"
    return score, reason
