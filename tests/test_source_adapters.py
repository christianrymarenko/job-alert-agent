from src.core.models import SearchSettings, Settings, SourceSettings, SmtpSettings
from src.sources.search_discovery import SearchDiscoverySource


def _settings() -> Settings:
    return Settings(
        app={},
        search=SearchSettings(
            country_focus="Germany",
            preferred_locations=["Munich"],
            allow_remote=True,
            allow_hybrid=True,
            keywords=["AI Manager"],
            discovery_queries=["site:de AI Manager job"],
        ),
        sources=SourceSettings(
            enabled=["search_discovery", "company_pages"],
            adzuna={},
            greenhouse={},
            company_pages={},
            search_discovery={"allowed_domains": ["example.com"]},
        ),
        smtp=SmtpSettings(
            host="smtp.example.com",
            port=587,
            use_tls=True,
            username="u",
            password="p",
            email_from="from@example.com",
            email_to="to@example.com",
        ),
    )


def test_extract_result_url_from_duckduckgo_redirect() -> None:
    url = "/l/?uddg=https%3A%2F%2Fjobs.example.com%2Fai-manager"
    assert SearchDiscoverySource._extract_result_url(url) == "https://jobs.example.com/ai-manager"


def test_likely_job_link_detection() -> None:
    assert SearchDiscoverySource._is_likely_job_url("https://company.com/careers/ai-manager")
    assert not SearchDiscoverySource._is_likely_job_url("https://company.com/about")


def test_allowed_domain_filtering() -> None:
    source = SearchDiscoverySource(_settings())
    assert source._is_allowed_domain("https://jobs.example.com/ai-manager")
    assert not source._is_allowed_domain("https://other.org/jobs/ai-manager")

