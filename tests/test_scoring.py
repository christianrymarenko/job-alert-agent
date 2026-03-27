from src.core.models import JobPosting, SearchSettings
from src.core.scoring import score_job


def _cfg() -> SearchSettings:
    return SearchSettings(
        country_focus="Germany",
        preferred_locations=["Munich", "Bavaria"],
        allow_remote=True,
        allow_hybrid=True,
        keywords=["AI Manager", "KI Consultant", "AI Transformation Manager"],
        discovery_queries=[],
    )


def test_high_score_for_relevant_business_ai_role() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="AI Transformation Manager (m/w/d)",
        company="Example GmbH",
        location="Munich / Hybrid",
        url="https://example.com/jobs/123",
        description_snippet=(
            "Lead AI adoption, stakeholder management, project leadership, "
            "consulting, implementation and rollout across business units."
        ),
    )

    score, reason = score_job(job, cfg)
    assert score >= 75
    assert "ai signal" in reason.lower()


def test_low_score_for_engineering_role() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Machine Learning Engineer",
        company="CodeCorp",
        location="Berlin",
        url="https://example.com/jobs/eng",
        description_snippet="Build MLOps platforms, train deep learning models in Python.",
    )

    score, reason = score_job(job, cfg)
    assert score < 50
    assert "rejected" in reason.lower() or "penalt" in reason.lower()


def test_generic_consulting_without_ai_signal_is_rejected() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Consultant Programmatic Advertising",
        company="MediaHouse",
        location="Munich",
        url="https://example.com/jobs/media-consulting",
        description_snippet="Drive media strategy and client campaigns with stakeholder management.",
    )
    score, reason = score_job(job, cfg)
    assert score == 0
    assert "hard exclude" in reason.lower()


def test_hard_exclusion_phrase_blocks_non_ai_role() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Account Manager",
        company="SalesOrg",
        location="Munich",
        url="https://example.com/jobs/account-manager",
        description_snippet="Account manager role for enterprise media clients.",
    )
    score, reason = score_job(job, cfg)
    assert score == 0
    assert "hard exclude" in reason.lower()


def test_ai_signal_in_description_allows_non_explicit_title() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Program Lead Digital Platforms",
        company="PlatformCo",
        location="Germany / Remote",
        url="https://example.com/jobs/program-lead",
        description_snippet=(
            "Lead Artificial Intelligence transformation, AI implementation, "
            "and AI strategy across business units."
        ),
    )
    score, reason = score_job(job, cfg)
    assert score >= 55
    assert "ai signal" in reason.lower()


def test_german_business_facing_consulting_role_scores_high() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Consultant KI-Transformation (m/w/d)",
        company="ConsultingPartner GmbH",
        location="Muenchen / Bayern / Hybrid",
        url="https://example.com/jobs/consulting-ki",
        description_snippet=(
            "Beratung zur KI-Implementierung, Stakeholder-Management, "
            "Programmsteuerung, AI Adoption und Enablement in SaaS-Umfeldern."
        ),
    )
    score, reason = score_job(job, cfg)
    assert score >= 70
    assert "ai role fit" in reason.lower()
    assert "location" in reason.lower()


def test_ambiguous_product_title_with_business_ai_context_is_accepted() -> None:
    cfg = _cfg()
    job = JobPosting(
        source="test",
        title="Senior Program Lead Digital Platforms",
        company="PlatformCo",
        location="Germany / Remote",
        url="https://example.com/jobs/program-lead",
        description_snippet=(
            "Drive AI rollout, AI strategy, customer-facing transformation roadmap, "
            "cross-functional stakeholder management and SaaS product leadership."
        ),
    )
    score, _ = score_job(job, cfg)
    assert score >= 55
