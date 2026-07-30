"""Tests for linkedin_scraper.scrapers.posts_parsing."""
import pytest

from linkedin_scraper.models.post import Post
from linkedin_scraper.scrapers.company.posts_parser import (
    build_posts_url,
    extract_time_from_text,
    parse_count,
    post_from_js_data,
)


@pytest.mark.unit
def test_build_posts_url_appends_posts_segment():
    assert (
        build_posts_url("https://www.linkedin.com/company/microsoft")
        == "https://www.linkedin.com/company/microsoft/posts/"
    )


@pytest.mark.unit
def test_build_posts_url_strips_trailing_slash_before_appending():
    assert (
        build_posts_url("https://www.linkedin.com/company/microsoft/")
        == "https://www.linkedin.com/company/microsoft/posts/"
    )


@pytest.mark.unit
def test_build_posts_url_leaves_existing_posts_path_untouched():
    url = "https://www.linkedin.com/company/microsoft/posts"
    assert build_posts_url(url) == url


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("3d", "3d"),
        ("2 weeks ago", "2 weeks ago"),
        ("5h \u2022 Edited", "5h"),
        ("1 month ago \u2022 Visible to anyone", "1 month ago"),
    ],
)
def test_extract_time_from_text_regex_matches(text, expected):
    assert extract_time_from_text(text) == expected


@pytest.mark.unit
def test_extract_time_from_text_falls_back_to_bullet_split():
    assert extract_time_from_text("Just now \u2022 something else") == "Just now"


@pytest.mark.unit
def test_extract_time_from_text_empty_returns_none():
    assert extract_time_from_text("") is None


@pytest.mark.unit
def test_extract_time_from_text_none_returns_none():
    assert extract_time_from_text(None) is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected",
    [
        ("123", 123),
        ("1,234 reactions", 1234),
        ("42", 42),
    ],
)
def test_parse_count_valid(text, expected):
    assert parse_count(text) == expected


@pytest.mark.unit
def test_parse_count_no_digits_returns_none():
    assert parse_count("no numbers here") is None


@pytest.mark.unit
def test_parse_count_empty_returns_none():
    assert parse_count("") is None


@pytest.mark.unit
def test_parse_count_none_returns_none():
    assert parse_count(None) is None


@pytest.mark.unit
def test_post_from_js_data_builds_post_with_expected_fields():
    data = {
        "urn": "urn:li:activity:1234567890",
        "text": "Exciting news!",
        "timeText": "2d",
        "reactions": "150",
        "comments": "12",
        "reposts": "3",
        "images": ["https://example.com/img.jpg"],
    }

    post = post_from_js_data(data)

    assert isinstance(post, Post)
    assert post.urn == "urn:li:activity:1234567890"
    assert post.linkedin_url == (
        "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/"
    )
    assert post.text == "Exciting news!"
    assert post.posted_date == "2d"
    assert post.reactions_count == 150
    assert post.comments_count == 12
    assert post.reposts_count == 3
    assert post.image_urls == ["https://example.com/img.jpg"]


@pytest.mark.unit
def test_post_from_js_data_handles_missing_optional_fields():
    data = {"urn": "urn:li:activity:1", "text": None}

    post = post_from_js_data(data)

    assert post.posted_date is None
    assert post.reactions_count is None
    assert post.comments_count is None
    assert post.reposts_count is None
    assert post.image_urls == []
