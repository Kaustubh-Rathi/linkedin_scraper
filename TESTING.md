# LinkedIn Scraper - Testing Guide

## Test Summary

- **Unit tests** (`tests/unit/`): fast, mocked, no LinkedIn session
- **Integration tests** (`tests/integration/`): require `linkedin_session.json`

## Running Tests

### Unit only (CI default)

```bash
pip install -e ".[dev]"
pytest -m unit
```

### Integration (needs session)

```bash
linkedin-scraper login
pytest -m integration
```

### Coverage

```bash
pytest -m unit --cov=linkedin_scraper --cov-branch --cov-report=term-missing
```

Branch coverage is enabled in `pyproject.toml` (`[tool.coverage.run] branch = true`).

## Layout

```
tests/
├── conftest.py
├── unit/           # offline unit tests
└── integration/    # live LinkedIn / Playwright tests
```

## Notes

- Integration tests may use a headed browser and can hit rate limits.
- Refresh the session with `linkedin-scraper login` if auth fails.
