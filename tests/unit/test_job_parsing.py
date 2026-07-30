"""Tests for linkedin_scraper.scrapers.job_parsing."""
import pytest

from linkedin_scraper.scrapers.job.parser import (
    clean_job_url,
    looks_like_applicant_count,
    looks_like_location,
    looks_like_posted_date,
    parse_top_card_parts,
)


@pytest.mark.unit
def test_clean_job_url_strips_query_params():
    url = "https://www.linkedin.com/jobs/view/12345/?refId=abc&trk=xyz"
    assert clean_job_url(url) == "https://www.linkedin.com/jobs/view/12345/"


@pytest.mark.unit
def test_clean_job_url_adds_domain_for_relative_url():
    assert clean_job_url("/jobs/view/12345/") == "https://www.linkedin.com/jobs/view/12345/"


@pytest.mark.unit
def test_clean_job_url_leaves_absolute_url_without_query_untouched():
    url = "https://www.linkedin.com/jobs/view/12345/"
    assert clean_job_url(url) == url


@pytest.mark.unit
def test_clean_job_url_relative_with_query():
    assert clean_job_url("/jobs/view/999?refId=abc") == "https://www.linkedin.com/jobs/view/999"


@pytest.mark.unit
def test_parse_top_card_parts_full_text():
    text = "San Francisco, CA \u00b7 2 days ago \u00b7 50 applicants"
    location, posted_date, applicant_count = parse_top_card_parts(text)
    assert location == "San Francisco, CA"
    assert posted_date == "2 days ago"
    assert applicant_count == "50 applicants"


@pytest.mark.unit
def test_parse_top_card_parts_partial_text():
    text = "Remote \u00b7 1 week ago"
    location, posted_date, applicant_count = parse_top_card_parts(text)
    assert location == "Remote"
    assert posted_date == "1 week ago"
    assert applicant_count is None


@pytest.mark.unit
def test_parse_top_card_parts_empty_text_returns_all_none():
    assert parse_top_card_parts("") == (None, None, None)


@pytest.mark.unit
def test_parse_top_card_parts_none_text_returns_all_none():
    assert parse_top_card_parts(None) == (None, None, None)


@pytest.mark.unit
def test_parse_top_card_parts_takes_first_line_of_each_segment():
    text = (
        "New York, NY\nignored line \u00b7 "
        "United States\n3 hours ago \u00b7 "
        "42 applicants\nextra"
    )
    location, posted_date, applicant_count = parse_top_card_parts(text)
    assert location == "New York, NY"
    assert posted_date == "United States"
    assert applicant_count == "42 applicants"


@pytest.mark.unit
def test_looks_like_location_valid():
    assert looks_like_location("San Francisco, CA") is True


@pytest.mark.unit
def test_looks_like_location_remote_marker():
    assert looks_like_location("Remote") is True


@pytest.mark.unit
def test_looks_like_location_empty_text_is_false():
    assert looks_like_location("") is False


@pytest.mark.unit
def test_looks_like_location_equal_to_job_title_is_false():
    assert looks_like_location("Software Engineer, Remote", "Software Engineer, Remote") is False


@pytest.mark.unit
def test_looks_like_location_without_marker_is_false():
    assert looks_like_location("Not a location at all") is False


@pytest.mark.unit
def test_looks_like_location_too_short_is_false():
    assert looks_like_location(",") is False


@pytest.mark.unit
def test_looks_like_location_too_long_is_false():
    long_text = "United States, " + ("x" * 100)
    assert looks_like_location(long_text) is False


@pytest.mark.unit
def test_looks_like_location_dollar_amount_is_false():
    assert looks_like_location("$100,000 - $120,000") is False


@pytest.mark.unit
def test_looks_like_posted_date_valid():
    assert looks_like_posted_date("3 days ago") is True


@pytest.mark.unit
@pytest.mark.parametrize("marker", ["ago", "day", "week", "hour"])
def test_looks_like_posted_date_all_markers(marker):
    assert looks_like_posted_date(f"1 {marker}") is True


@pytest.mark.unit
def test_looks_like_posted_date_empty_is_false():
    assert looks_like_posted_date("") is False


@pytest.mark.unit
def test_looks_like_posted_date_without_marker_is_false():
    assert looks_like_posted_date("Full-time") is False


@pytest.mark.unit
def test_looks_like_posted_date_too_long_is_false():
    assert looks_like_posted_date("ago " + ("x" * 60)) is False


@pytest.mark.unit
def test_looks_like_applicant_count_valid():
    assert looks_like_applicant_count("50 applicants") is True


@pytest.mark.unit
@pytest.mark.parametrize("marker", ["applicant", "people clicked", "applied"])
def test_looks_like_applicant_count_all_markers(marker):
    assert looks_like_applicant_count(f"Over 10 {marker}") is True


@pytest.mark.unit
def test_looks_like_applicant_count_empty_is_false():
    assert looks_like_applicant_count("") is False


@pytest.mark.unit
def test_looks_like_applicant_count_without_marker_is_false():
    assert looks_like_applicant_count("Full-time") is False


@pytest.mark.unit
def test_looks_like_applicant_count_too_long_is_false():
    assert looks_like_applicant_count("applicant " + ("x" * 60)) is False
