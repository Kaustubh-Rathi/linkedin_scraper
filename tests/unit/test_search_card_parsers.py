"""
Unit tests for pure search card parsers in linkedin_scraper.parsers.search.
"""

import pytest

from linkedin_scraper.parsers.search import (
    parse_company_search_card,
    parse_employee_search_card,
    parse_job_search_card,
    parse_person_search_card,
    parse_post_search_card,
)
from linkedin_scraper.search.results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
)


def test_parse_person_search_card_valid():
    raw = {
        "name": "  Alice Smith ",
        "linkedin_url": "https://www.linkedin.com/in/alicesmith",
        "headline": "Staff Engineer at TechCorp",
        "location": "San Francisco Bay Area",
        "current_company": "TechCorp",
    }
    res = parse_person_search_card(raw)
    assert isinstance(res, PersonSearchResult)
    assert res.name == "Alice Smith"
    assert res.linkedin_url == "https://www.linkedin.com/in/alicesmith"
    assert res.headline == "Staff Engineer at TechCorp"
    assert res.location == "San Francisco Bay Area"
    assert res.current_company == "TechCorp"


def test_parse_person_search_card_missing_required():
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_person_search_card({"linkedin_url": "https://www.linkedin.com/in/foo"})

    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_person_search_card({"name": "Bob"})


def test_parse_company_search_card_valid():
    raw = {
        "name": "Acme Inc",
        "url": "https://www.linkedin.com/company/acme",
        "industry": "Software Development",
        "location": "New York, NY",
        "followers_count": "10,500 followers",
    }
    res = parse_company_search_card(raw)
    assert isinstance(res, CompanySearchResult)
    assert res.name == "Acme Inc"
    assert res.linkedin_url == "https://www.linkedin.com/company/acme"
    assert res.industry == "Software Development"
    assert res.followers_count == 10500


def test_parse_job_search_card_valid():
    raw = {
        "job_title": "Senior Backend Engineer",
        "linkedin_url": "https://www.linkedin.com/jobs/view/12345678",
        "company_name": "Google",
        "location": "Mountain View, CA",
        "posted_date": "2 days ago",
        "easy_apply": True,
    }
    res = parse_job_search_card(raw)
    assert isinstance(res, JobSearchResult)
    assert res.job_title == "Senior Backend Engineer"
    assert res.linkedin_url == "https://www.linkedin.com/jobs/view/12345678"
    assert res.company_name == "Google"
    assert res.easy_apply is True


def test_parse_job_search_card_normalizes_relative_url():
    """Relative hrefs returned by JS extraction are absolutized."""
    raw = {
        "job_title": "Senior Backend Engineer",
        "linkedin_url": "/jobs/view/12345/",
        "company_name": "Acme",
        "location": "Remote",
        "easy_apply": False,
    }
    res = parse_job_search_card(raw)
    assert isinstance(res, JobSearchResult)
    assert res.linkedin_url == "https://www.linkedin.com/jobs/view/12345/"
    assert res.job_title == "Senior Backend Engineer"



def test_parse_post_search_card_valid():
    raw = {
        "linkedin_url": "https://www.linkedin.com/feed/update/urn:li:activity:123456/",
        "author_name": "Carol Danvers",
        "author_headline": "VP Product",
        "text_snippet": "Excited to announce our new release...",
        "posted_date": "1w",
        "reactions_count": "1.2k",
    }
    res = parse_post_search_card(raw)
    assert isinstance(res, PostSearchResult)
    assert res.author_name == "Carol Danvers"
    assert res.reactions_count == 1200
    assert res.text_snippet == "Excited to announce our new release..."


def test_parse_employee_search_card_valid():
    raw = {
        "name": "David Miller",
        "linkedin_url": "https://www.linkedin.com/in/dmiller",
        "designation": "Lead Architect",
        "company_name": "Acme",
    }
    res = parse_employee_search_card(raw)
    assert isinstance(res, EmployeeSearchResult)
    assert res.name == "David Miller"
    assert res.designation == "Lead Architect"
    assert res.company_name == "Acme"


def test_parser_helper_functions():
    from linkedin_scraper.parsers.search import _clean_str, _parse_int
    assert _clean_str(None) is None
    assert _clean_str("   ") is None
    assert _clean_str("hello") == "hello"

    assert _parse_int(None) is None
    assert _parse_int(42) == 42
    assert _parse_int("invalid") is None
    assert _parse_int("2.5M") == 2500000


def test_parse_employee_search_card_missing_required():
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_employee_search_card({"designation": "Manager"})


def test_parse_company_search_card_missing_required():
    with pytest.raises(ValueError, match="missing required field 'name'"):
        parse_company_search_card({"url": "https://linkedin.com/company/foo"})

    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_company_search_card({"name": "Acme"})


def test_parse_job_search_card_missing_required():
    with pytest.raises(ValueError, match="missing required field 'job_title'"):
        parse_job_search_card({"url": "https://linkedin.com/jobs/view/123"})

    with pytest.raises(ValueError, match="missing required field 'linkedin_url'"):
        parse_job_search_card({"job_title": "Engineer"})


