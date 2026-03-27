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
    assert score >= 70
    assert "title" in reason.lower()


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
    assert "penalties" in reason.lower()
