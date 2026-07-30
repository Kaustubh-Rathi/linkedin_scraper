"""Tests for linkedin_scraper.scrapers.person.links."""
import pytest

from linkedin_scraper.models import Contact
from linkedin_scraper.scrapers.person.links import (
    classify_link,
    contact_type_from_heading,
    merge_contacts,
    profile_detail_url,
    unwrap_href,
)


@pytest.mark.unit
def test_profile_detail_url_with_trailing_slash():
    result = profile_detail_url(
        "https://www.linkedin.com/in/example/", "details/experience/"
    )
    assert result == "https://www.linkedin.com/in/example/details/experience/"


@pytest.mark.unit
def test_profile_detail_url_without_trailing_slash():
    result = profile_detail_url(
        "https://www.linkedin.com/in/example", "details/experience/"
    )
    assert result == "https://www.linkedin.com/in/example/details/experience/"


@pytest.mark.unit
def test_profile_detail_url_strips_query_and_fragment():
    result = profile_detail_url(
        "https://www.linkedin.com/in/example/?trk=nav", "overlay/contact-info/"
    )
    assert result == "https://www.linkedin.com/in/example/overlay/contact-info/"


@pytest.mark.unit
def test_unwrap_href_safety_go_redirect():
    raw = (
        "https://www.linkedin.com/safety/go/?url="
        "https%3A%2F%2Fgithub.com%2Fexample&urlhash=x"
    )
    assert unwrap_href(raw) == "https://github.com/example"


@pytest.mark.unit
def test_unwrap_href_redir_redirect():
    raw = (
        "https://www.linkedin.com/redir/redirect?url="
        "https%3A%2F%2Fexample.com%2Fpage&urlhash=y"
    )
    assert unwrap_href(raw) == "https://example.com/page"


@pytest.mark.unit
def test_unwrap_href_leaves_plain_url_untouched():
    plain = "https://github.com/example"
    assert unwrap_href(plain) == plain


@pytest.mark.unit
def test_unwrap_href_returns_original_when_no_url_param():
    raw = "https://www.linkedin.com/safety/go/?urlhash=x"
    assert unwrap_href(raw) == raw


@pytest.mark.unit
@pytest.mark.parametrize(
    "href,expected_type",
    [
        ("https://github.com/example", "github"),
        ("https://www.github.com/example", "github"),
        ("https://twitter.com/example", "twitter"),
        ("https://x.com/example", "twitter"),
        ("https://gitlab.com/example", "gitlab"),
        ("https://youtube.com/example", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://medium.com/@example", "medium"),
        ("https://stackoverflow.com/users/1", "stackoverflow"),
    ],
)
def test_classify_link_known_hosts(href, expected_type):
    contact = classify_link(href, "Label")
    assert contact.type == expected_type
    assert contact.value == href
    assert contact.label == "Label"


@pytest.mark.unit
def test_classify_link_unknown_host_defaults_to_website():
    contact = classify_link("https://my-personal-blog.example", "My Blog")
    assert contact.type == "website"
    assert contact.value == "https://my-personal-blog.example"
    assert contact.label == "My Blog"


@pytest.mark.unit
def test_classify_link_without_label_returns_none_label():
    contact = classify_link("https://github.com/example")
    assert contact.label is None


@pytest.mark.unit
def test_classify_link_empty_label_normalizes_to_none():
    contact = classify_link("https://github.com/example", "")
    assert contact.label is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "heading,expected",
    [
        ("Profile", "linkedin"),
        ("Your Profile", "linkedin"),
        ("Website", "website"),
        ("Email", "email"),
        ("Phone", "phone"),
        ("Twitter", "twitter"),
        ("X.com", "twitter"),
        ("Birthday", "birthday"),
        ("Address", "address"),
    ],
)
def test_contact_type_from_heading_known_headings(heading, expected):
    assert contact_type_from_heading(heading) == expected


@pytest.mark.unit
def test_contact_type_from_heading_unknown_returns_none():
    assert contact_type_from_heading("Instant Messenger") is None


@pytest.mark.unit
def test_contact_type_from_heading_is_case_insensitive():
    assert contact_type_from_heading("EMAIL") == "email"
    assert contact_type_from_heading("phone") == "phone"


@pytest.mark.unit
def test_merge_contacts_deduplicates_by_type_and_value():
    primary = [Contact(type="website", value="https://example.com")]
    extra = [Contact(type="website", value="https://example.com")]

    merged = merge_contacts(primary, extra)

    assert len(merged) == 1


@pytest.mark.unit
def test_merge_contacts_prefers_richer_label():
    primary = [Contact(type="website", value="https://example.com", label=None)]
    extra = [Contact(type="website", value="https://example.com", label="Personal")]

    merged = merge_contacts(primary, extra)

    assert len(merged) == 1
    assert merged[0].label == "Personal"


@pytest.mark.unit
def test_merge_contacts_keeps_existing_label_when_extra_has_none():
    primary = [Contact(type="website", value="https://example.com", label="Personal")]
    extra = [Contact(type="website", value="https://example.com", label=None)]

    merged = merge_contacts(primary, extra)

    assert len(merged) == 1
    assert merged[0].label == "Personal"


@pytest.mark.unit
def test_merge_contacts_keeps_distinct_entries():
    primary = [Contact(type="website", value="https://a.example")]
    extra = [Contact(type="website", value="https://b.example")]

    merged = merge_contacts(primary, extra)

    assert len(merged) == 2
