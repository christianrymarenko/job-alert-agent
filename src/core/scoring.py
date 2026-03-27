from __future__ import annotations

import re

from src.core.models import JobPosting, SearchSettings

STRONG_AI_SIGNAL_PATTERNS: list[tuple[str, str]] = [
    ("AI", r"\bai\b"),
    ("KI", r"\bki\b"),
    ("Artificial Intelligence", r"\bartificial intelligence\b"),
    ("Künstliche Intelligenz", r"\bkünstliche intelligenz\b"),
    ("Kuenstliche Intelligenz", r"\bkuenstliche intelligenz\b"),
    ("GenAI", r"\bgenai\b"),
    ("Generative AI", r"\bgenerative ai\b"),
    ("LLM", r"\bllm\b"),
    ("Large Language Model", r"\blarge language model\b"),
    ("AI transformation", r"\bai transformation\b"),
    ("AI implementation", r"\bai implementation\b"),
    ("KI Implementierung", r"\bki implementierung\b"),
    ("AI consulting", r"\bai consulting\b"),
    ("KI Beratung", r"\bki beratung\b"),
    ("AI strategy", r"\bai strategy\b"),
    ("KI Strategie", r"\bki strategie\b"),
    ("AI project", r"\bai project\b"),
    ("KI Projekt", r"\bki projekt\b"),
]

# Must indicate business-side AI ownership, not generic manager language.
BUSINESS_AI_ROLE_TERMS = {
    "ai consultant": 18,
    "ki consultant": 18,
    "ai berater": 18,
    "ki berater": 18,
    "ai manager": 16,
    "ki manager": 16,
    "ai transformation": 16,
    "ki transformation": 16,
    "ai implementation": 15,
    "ki implementierung": 15,
    "ai strategy": 14,
    "ki strategie": 14,
    "ai project": 14,
    "ki projekt": 14,
    "ai adoption": 13,
    "ai enablement": 13,
    "generative ai": 14,
    "genai": 14,
    "llm": 13,
    "project lead ai": 14,
    "projektleitung ki": 14,
    "programmmanagement ai": 13,
    "ai pmo": 13,
}

SUPPORTING_BUSINESS_TERMS = {
    "stakeholder management": 8,
    "stakeholder": 6,
    "consulting": 8,
    "beratung": 8,
    "projektleitung": 8,
    "project leadership": 8,
    "program management": 7,
    "programmmanagement": 7,
    "pmo": 7,
    "governance": 6,
    "rollout": 7,
    "adoption": 7,
    "enablement": 7,
    "implementation": 7,
    "implementierung": 7,
    "use case": 6,
    "saas": 6,
    "platform": 5,
    "plattform": 5,
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

# Hard reject list for clearly non-target generic roles.
HARD_EXCLUDE_PATTERNS: list[tuple[str, str]] = [
    ("paid social", r"\bpaid social\b"),
    ("PR", r"\bpr\b"),
    ("public relations", r"\bpublic relations\b"),
    ("influencer", r"\binfluencer\b"),
    ("programmatic advertising", r"\bprogrammatic advertising\b"),
    ("account manager", r"\baccount manager\b"),
    ("sales manager", r"\bsales manager\b"),
    ("media consultant", r"\bmedia consultant\b"),
    ("artist", r"\bartist\b"),
    ("social media", r"\bsocial media\b"),
]

# Strong downranking for technical engineering roles.
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


def _find_pattern_hits(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    hits: list[str] = []
    for label, pattern in patterns:
        if re.search(pattern, text):
            hits.append(label)
    return hits


def score_job(job: JobPosting, search: SearchSettings) -> tuple[int, str]:
    """Score role relevance for strict senior business-side AI profile."""
    title = _normalize(job.title)
    snippet = _normalize(job.description_snippet)
    company = _normalize(job.company)
    location = _normalize(job.location)
    blob = " ".join([title, snippet, company, location])

    score = 0
    reasons: list[str] = []

    # Hard exclusion first: generic non-AI target domains should never pass.
    hard_exclude_hits = _find_pattern_hits(blob, HARD_EXCLUDE_PATTERNS)
    if hard_exclude_hits:
        return 0, "Hard exclude: " + ", ".join(hard_exclude_hits)

    # Require at least one explicit strong AI/KI signal.
    strong_ai_hits = _find_pattern_hits(blob, STRONG_AI_SIGNAL_PATTERNS)
    if not strong_ai_hits:
        return 0, "Rejected: missing explicit AI/KI signal"
    reasons.append(f"AI signal: {', '.join(sorted(set(strong_ai_hits))[:4])}")

    role_score, role_hits = _count_weighted_terms(blob, BUSINESS_AI_ROLE_TERMS)
    score += role_score
    if role_hits:
        reasons.append(f"AI role fit: {', '.join(sorted(set(role_hits)))}")

    support_score, support_hits = _count_weighted_terms(blob, SUPPORTING_BUSINESS_TERMS)
    score += support_score
    if support_hits:
        reasons.append(f"Business fit: {', '.join(sorted(set(support_hits)))}")

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

    # Must show at least one business-side leadership/consulting cue.
    if not any(
        cue in blob
        for cue in (
            "consultant",
            "berater",
            "manager",
            "lead",
            "projekt",
            "project",
            "program",
            "programm",
            "transformation",
            "implementation",
            "adoption",
            "enablement",
            "strategy",
            "strategie",
            "pmo",
        )
    ):
        return 0, "Rejected: lacks business-side AI ownership cues"

    # Hard brake: technical engineering-heavy titles should stay low even with AI mentions.
    if any(term in title for term in ("engineer", "developer", "scientist", "mlops")) and not any(
        keep in title for keep in ("manager", "lead", "consultant", "berater", "projekt")
    ):
        score -= 20
        reasons.append("Engineering-heavy title downrank")

    # Generic titles with only weak coupling to AI business role should not pass too easily.
    if not role_hits and len(strong_ai_hits) <= 1:
        score -= 10
        reasons.append("Weak AI-role coupling penalty")

    score = max(0, min(100, score))
    reason = "; ".join(reasons) if reasons else "General AI/KI business relevance"
    return score, reason
