from datetime import datetime

from src.core.emailer import build_subject


def test_build_subject() -> None:
    subject = build_subject(datetime(2026, 3, 27), 5)
    assert "5" in subject
    assert "AI/KI" in subject
