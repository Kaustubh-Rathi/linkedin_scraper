"""
Unit tests for LinkedInSearchUrlBuilder.
"""

from urllib.parse import parse_qs, unquote, urlparse
import pytest

from linkedin_scraper.adapters.search.url_builder import LinkedInSearchUrlBuilder
from linkedin_scraper.search.filters import (
    CompanySearchFilter,
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmployeeSearchFilter,
    EmploymentType,
    ExperienceLevel,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    SortBy,
    WorkplaceType,
)
from linkedin_scraper.search.queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)


@pytest.fixture
def url_builder():
    return LinkedInSearchUrlBuilder()


def test_person_url_minimal(url_builder):
    query = PersonSearchQuery(keywords="Software Engineer")
    url = url_builder.build_person_url(query)
    assert url.startswith("https://www.linkedin.com/search/results/people/?")
    assert "keywords=Software+Engineer" in url or "keywords=Software%20Engineer" in url


def test_person_url_all_filters(url_builder):
    filters = PersonSearchFilter(
        title="CTO",
        location=["103644278"],
        current_company=["1337"],
        past_company=["42"],
        industry=["4"],
        school=["18483"],
        connection_degrees=[ConnectionDegree.FIRST, ConnectionDegree.SECOND],
        profile_language=["en"],
        service_category=["cat1"],
    )
    query = PersonSearchQuery(keywords="Jane", filters=filters, continuation_token="2")
    url = url_builder.build_person_url(query)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert qs["keywords"] == ["Jane"]
    assert qs["title"] == ["CTO"]
    assert qs["page"] == ["2"]

    facet = unquote(qs["facet"][0])
    assert 'network=>["F","S"]' in facet
    assert 'geoUrn=>["103644278"]' in facet
    assert 'currentCompany=>["1337"]' in facet
    assert 'pastCompany=>["42"]' in facet
    assert 'industry=>["4"]' in facet
    assert 'schoolFilter=>["18483"]' in facet
    assert 'profileLanguage=>["en"]' in facet
    assert 'serviceCategory=>["cat1"]' in facet


def test_company_url_building(url_builder):
    filters = CompanySearchFilter(
        location=["103644278"],
        industry=["96"],
        company_size=[CompanySize.SIZE_11_50, CompanySize.SIZE_51_200],
    )
    query = CompanySearchQuery(keywords="Acme", filters=filters)
    url = url_builder.build_company_url(query)
    assert "search/results/companies/" in url
    assert "keywords=Acme" in url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    facet = unquote(qs["facet"][0])
    assert 'companySize=>["C","D"]' in facet


def test_job_url_building_preserves_existing_semantics(url_builder):
    filters = JobSearchFilter(
        location=["San Francisco, CA"],
        date_posted=DatePosted.PAST_24H,
        experience_levels=[ExperienceLevel.ENTRY_LEVEL, ExperienceLevel.MID_SENIOR],
        companies=["1337"],
        employment_types=[EmploymentType.FULL_TIME],
        workplace_types=[WorkplaceType.REMOTE],
        industries=["4"],
        easy_apply_only=True,
        under_ten_applicants=True,
    )
    query = JobSearchQuery(keywords="Python Developer", filters=filters, continuation_token="25")
    url = url_builder.build_job_url(query)

    parsed = urlparse(url)
    assert parsed.path == "/jobs/search/"
    qs = parse_qs(parsed.query)

    assert qs["keywords"] == ["Python Developer"]
    assert qs["location"] == ["San Francisco, CA"]
    assert qs["f_TPR"] == ["r86400"]
    assert qs["f_E"] == ["2,4"]
    assert qs["f_C"] == ["1337"]
    assert qs["f_JT"] == ["F"]
    assert qs["f_WT"] == ["2"]
    assert qs["f_I"] == ["4"]
    assert qs["f_AL"] == ["true"]
    assert qs["f_EA"] == ["true"]
    assert qs["start"] == ["25"]


def test_post_url_building(url_builder):
    filters = PostSearchFilter(
        date_posted=DatePosted.PAST_WEEK,
        author_company=["1337"],
        author_industry=["4"],
        sort_by=SortBy.DATE,
    )
    query = PostSearchQuery(keywords="AI innovation", filters=filters)
    url = url_builder.build_post_url(query)
    assert "search/results/content/" in url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs["datePosted"] == ["past-week"]
    assert qs["sortBy"] == ["date_posted"]
    facet = unquote(qs["facet"][0])
    assert 'authorCompany=>["1337"]' in facet


def test_employee_url_building(url_builder):
    filters = EmployeeSearchFilter(
        title="Engineering Manager",
        location=["103644278"],
        department=["Engineering"],
    )
    query = EmployeeSearchQuery(
        company_identifier="https://www.linkedin.com/company/google/",
        keywords="Infrastructure",
        filters=filters,
    )
    url = url_builder.build_employee_url(query)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    assert qs["currentCompany"] == ['["google"]']
    assert qs["keywords"] == ["Infrastructure"]
    assert qs["title"] == ["Engineering Manager"]
    facet = unquote(qs["facet"][0])
    assert 'geoUrn=>["103644278"]' in facet
    assert 'department=>["Engineering"]' in facet


def test_url_encoding_unicode_and_special_chars(url_builder):
    query = PersonSearchQuery(keywords="Müller & Cie (Tech)")
    url = url_builder.build_person_url(query)
    assert "M%C3%BCller" in url or "Müller" in url or "%26" in url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    assert qs["keywords"] == ["Müller & Cie (Tech)"]


def test_url_builder_empty_queries(url_builder):
    assert url_builder.build_person_url(PersonSearchQuery()) == "https://www.linkedin.com/search/results/people/"
    assert url_builder.build_company_url(CompanySearchQuery()) == "https://www.linkedin.com/search/results/companies/"
    assert url_builder.build_job_url(JobSearchQuery()) == "https://www.linkedin.com/jobs/search/"
    assert url_builder.build_post_url(PostSearchQuery()) == "https://www.linkedin.com/search/results/content/?sortBy=relevance"




def test_url_builder_non_digit_continuation(url_builder):
    q = PersonSearchQuery(keywords="dev", continuation_token="abc_token")
    url = url_builder.build_person_url(q)
    assert "start=abc_token" in url

