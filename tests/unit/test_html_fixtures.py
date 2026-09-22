"""Unit test that HTML fixtures are present for offline scraper coverage."""
from pathlib import Path

import pytest


@pytest.mark.unit
def test_html_fixtures_exist(html_fixtures_dir: Path):
    expected = {
        "company_overview.html",
        "job_details.html",
        "authwall.html",
        "search_people_results.html",
        "search_companies_results.html",
        "search_jobs_results.html",
        "search_posts_results.html",
        "search_employees_results.html",
        "feed_posts_update.html",
        "search_malformed_and_edge_cases.html",
    }
    present = {p.name for p in html_fixtures_dir.glob("*.html")}
    assert expected.issubset(present)
    for name in expected:
        assert (html_fixtures_dir / name).stat().st_size > 0

