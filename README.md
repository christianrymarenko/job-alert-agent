# German AI/KI Job Search Agent (Production-Ready MVP)

Automated Python job agent for the German market:

- searches AI/KI-relevant roles once per day
- scores each role against a senior business-facing AI profile
- deduplicates against previously sent jobs (persistent SQLite)
- sends one daily email at **10:00 Europe/Berlin** with only new matches

This MVP is built to be modular and robust, with clear extension points for additional sources.

## Features

- **Daily run** with APScheduler (or manual run via CLI)
- **Source modularity**: enable/disable sources in YAML config
- **Relevance scoring**:
  - title and semantic role match
  - seniority fit
  - Germany/hybrid/remote fit
  - business-facing AI consulting/project/transformation relevance
  - penalties for engineering-heavy roles
- **Deduplication**:
  - canonical URL
  - source + external job ID
  - company + title fingerprint
- **SQLite persistence** for jobs, run logs, and error events
- **SMTP email delivery** using environment variables for secrets
- **Structured logging** and graceful partial-failure handling
- **Basic test suite** for canonicalization, scoring, dedupe, email formatting

## Project Structure

```text
.
├── config.example.yaml
├── .env.example
├── requirements.txt
├── run_once.py
├── main.py
├── src
│   ├── core
│   │   ├── canonicalize.py
│   │   ├── config.py
│   │   ├── dedupe.py
│   │   ├── emailer.py
│   │   ├── logging_setup.py
│   │   ├── models.py
│   │   ├── pipeline.py
│   │   ├── scoring.py
│   │   ├── sources.py
│   │   └── storage.py
│   └── sources
│       ├── adzuna.py
│       ├── base.py
│       ├── company_pages.py
│       └── greenhouse.py
└── tests
    ├── test_canonicalize.py
    ├── test_dedupe.py
    ├── test_emailer.py
    └── test_scoring.py
```

## Implemented Sources (MVP)

1. **Adzuna API source**
   - reliable API-style access pattern
   - configurable pages/results
   - uses keyword query loop with Germany focus
2. **Greenhouse boards source**
   - direct board API endpoint (`boards-api.greenhouse.io`)
   - configurable board tokens list
3. **Company pages source (seed URLs)**
   - conservative HTML extraction from configured career pages
   - **robots.txt aware** and domain allowlist controls
   - optional crawl depth (default conservative) and per-domain request caps
   - filters likely job/career links and keeps source metadata
4. **Search discovery source (market-wide, search-engine based)**
   - broad query generation across major market platforms:
     - LinkedIn Jobs
     - Indeed Germany
     - StepStone
     - XING Jobs
     - JobScout24
     - Google Jobs style discovery
   - combines role/context/location query variants and lightly randomizes combinations per run
   - extracts candidate job URLs from search results and applies strict job-detail URL filtering
   - fetches job detail pages for enrichment (title/company/location/description snippet) where possible
   - deduplicates URLs across query/platform buckets
   - supports host allowlists and robots-aware behavior
5. **Google-jobs-focused discovery adapter**
   - separate search-discovery profile focused on Google Jobs-like query patterns
   - disabled/enabled via config as an independent source module

### Why not scrape everything directly?

Some large job boards are heavily dynamic and/or restricted. This MVP favors:

- official/public API endpoints where available
- direct company career pages with robots awareness
- search-engine-assisted discovery to locate company-hosted postings
- legally safer, modular discovery methods

Additional adapters can be added under `src/sources/` and enabled via config.

### Source-level compliance controls

The company-page and discovery adapters include conservative controls:

- robots.txt checks before crawling configured domains
- request throttling between calls
- small crawl depth / limited URLs per run
- optional host/path allowlists to restrict discovery
- graceful handling of blocked pages and partial failures

### Diversity controls

To reduce company bias and over-representation:

- configurable `max_jobs_per_company` cap applied at pipeline stage
- configurable `min_unique_companies` target with soft fallback behavior
- run summary logs include:
  - jobs by source
  - unique company count
  - dropped-by-diversity count
  - dropped-by-score count

## Setup

### 1) Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment

```bash
cp .env.example .env
```

Set SMTP credentials and recipient in `.env`.

### 4) Configure runtime options

```bash
cp config.example.yaml config.yaml
```

Adjust:

- `app.send_time` (default `10:00`)
- `app.timezone` (default `Europe/Berlin`)
- `app.min_relevance_score`
- `sources.enabled`
- source-specific settings (`adzuna`, `greenhouse`, `company_pages`, `search_discovery`, `google_jobs_discovery`)
- keyword/search preferences

## Running

### Manual one-off run (testing)

```bash
python run_once.py --config config.yaml --env-file .env
```

Optional flags:

- `--dry-run` (skip SMTP completely; still writes console + report artifacts)
- `--html-report` (generate browser-ready HTML + JSON reports under `reports/`)
- `--test-email` (force immediate email attempt using current run results)
- `--test-recipient you@example.com` (override recipient for test email)

### Daily scheduler process

```bash
python main.py
```

This runs continuously and executes daily at configured time in Europe/Berlin.

### Dry-run workflow (no SMTP required)

Use this when SMTP is disabled/broken or when you only want to validate results locally:

```bash
python run_once.py --config config.yaml --env-file .env --dry-run --html-report
```

Behavior:

- executes normal source + scoring + dedupe logic
- **never sends email** in dry-run mode
- writes local artifacts:
  - `daily_jobs.txt`
  - `data/latest_jobs.json`
- if `--html-report` is enabled, also writes:
  - `reports/latest_jobs.html`
  - `reports/latest_jobs.json`
  - optional archives under `reports/archive/`
- prints a readable summary and job list to console
- run succeeds even if SMTP is not configured

### Broad market discovery tuning

For wider German-market coverage, configure:

- `search.role_keywords`
- `search.context_keywords`
- `search.location_keywords`
- `search.search_query_variants`
- `search.discovery_queries` (optional explicit additions)
- `search.max_jobs_per_company`
- `search.min_unique_companies`

You can also toggle platform-style discovery sources independently via:

- `sources.search_discovery.enabled`
- `sources.google_jobs_discovery.enabled`

### HTML report mode (browser review)

Generate a clean report you can open locally in a browser:

```bash
python run_once.py --config config.yaml --env-file .env --dry-run --html-report
```

Report outputs:

- `reports/latest_jobs.html`
- `reports/latest_jobs.json`
- archive copies:
  - `reports/archive/jobs_YYYY-MM-DD_HH-MM.html`
  - `reports/archive/jobs_YYYY-MM-DD_HH-MM.json`

Open report:

```bash
xdg-open reports/latest_jobs.html
```

or just double-click `reports/latest_jobs.html` in your file browser.

### Test email mode (immediate send attempt)

If you want to test SMTP delivery immediately:

```bash
python run_once.py --config config.yaml --env-file .env --test-email --test-recipient you@example.com
```

Behavior:

- executes normal source + scoring + dedupe pipeline
- attempts immediate SMTP send (subject is prefixed with `[TEST]`)
- if SMTP fails, run still succeeds and fallback artifacts are still written
- does **not** mark jobs as sent in test mode, so repeated formatting tests remain possible

## Cron-Friendly Alternative

If you prefer system cron instead of APScheduler:

```cron
0 10 * * * cd /path/to/project && /path/to/python run_once.py --config config.yaml --env-file .env
```

Ensure system timezone and environment variable loading are configured correctly.

## Email Format

Daily email includes:

- subject with date + number of new jobs
- short intro
- numbered list of jobs
  - title, company, location, source
  - optional match reason
  - direct link

Example subject:

- `Neue passende AI/KI Jobs - 5 neue Treffer - 2026-03-27`

## Deduplication Details

A job is considered already sent if any of these match prior sent records:

1. `canonical_url` match
2. same `source` + same external `job_id`
3. normalized `(company, title)` fingerprint match

This protects against tracking parameters, URL changes, and minor source URL churn.

## Scoring Logic (High-Level)

Weighted heuristic model:

- positive:
  - AI/KI/GenAI title terms
  - consultant/manager/lead/project/transformation/adoption terms
  - business-facing responsibilities
  - senior-level cues
  - Germany + remote/hybrid fit
- negative:
  - engineering-heavy terms (backend, full stack, MLOps, deep learning)
  - research-heavy cues (scientist, PhD, research)
  - junior/internship/working student cues
  - non-Germany location cues

Only jobs at or above `min_relevance_score` are considered for email.

## Testing

Run:

```bash
pytest
```

Included tests cover:

- URL canonicalization
- dedupe key behavior
- scoring behavior (positive/negative)
- email body formatting
- source adapter extraction/parsing behavior

## Compliance, Reliability, and Tradeoffs

- Respect robots.txt and source Terms of Service before enabling aggressive crawling.
- Prefer official APIs and career pages over brittle scraping.
- Keep request rate conservative and configurable.
- Use source isolation: if one source fails, pipeline continues and logs error.
- For high-volume/production deployment:
  - run behind process supervisor (systemd, Docker, etc.)
  - centralize logs
  - monitor email delivery failures
  - regularly review source adapter validity

## Extending Sources

Add a new adapter in `src/sources/` implementing `SourceAdapter.fetch_jobs()`, then wire it in:

- `src/core/sources.py` registry
- `config.yaml` enabled list/settings

This design lets you switch sources on/off independently.
