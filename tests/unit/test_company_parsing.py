"""Tests for linkedin_scraper.scrapers.company_parsing."""
import pytest

from linkedin_scraper.scrapers.company.parser import (
    apply_dt_dd_label,
    classify_info_item,
    empty_overview,
)


@pytest.mark.unit
def test_empty_overview_has_all_expected_keys_as_none():
    overview = empty_overview()
    expected_keys = {
        "website",
        "phone",
        "headquarters",
        "founded",
        "industry",
        "company_type",
        "company_size",
        "specialties",
    }
    assert set(overview.keys()) == expected_keys
    assert all(value is None for value in overview.values())


@pytest.mark.unit
@pytest.mark.parametrize(
    "text,expected_field",
    [
        ("10,001+ employees", "company_size"),
        ("51-200 employees", "company_size"),
        ("5K+ followers", "company_size"),
    ],
)
def test_classify_info_item_company_size(text, expected_field):
    result = classify_info_item(text)
    assert result is not None
    field, value = result
    assert field == expected_field
    assert value == text.strip()


@pytest.mark.unit
def test_classify_info_item_headquarters_with_location_hint():
    result = classify_info_item("Redmond, Washington")
    assert result == ("headquarters", "Redmond, Washington")


@pytest.mark.unit
def test_classify_info_item_headquarters_requires_comma():
    # "Washington" alone has no comma, so it doesn't match the headquarters
    # pattern (falls through since it's not an industry hint either).
    assert classify_info_item("Washington") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    "text",
    ["Software Development", "Financial Services", "Higher Education"],
)
def test_classify_info_item_industry(text):
    result = classify_info_item(text)
    assert result is not None
    field, value = result
    assert field == "industry"
    assert value == text


@pytest.mark.unit
def test_classify_info_item_unrecognized_returns_none():
    assert classify_info_item("1,234 followers") is None


@pytest.mark.unit
def test_classify_info_item_strips_whitespace():
    result = classify_info_item("   10,000+ employees   ")
    assert result == ("company_size", "10,000+ employees")


@pytest.mark.unit
def test_apply_dt_dd_label_website():
    overview = empty_overview()
    apply_dt_dd_label("Website", "https://example.com", overview)
    assert overview["website"] == "https://example.com"


@pytest.mark.unit
def test_apply_dt_dd_label_phone():
    overview = empty_overview()
    apply_dt_dd_label("Phone number", "555-1234", overview)
    assert overview["phone"] == "555-1234"


@pytest.mark.unit
@pytest.mark.parametrize("label", ["Headquarters", "Location"])
def test_apply_dt_dd_label_headquarters(label):
    overview = empty_overview()
    apply_dt_dd_label(label, "Seattle, WA", overview)
    assert overview["headquarters"] == "Seattle, WA"


@pytest.mark.unit
def test_apply_dt_dd_label_founded():
    overview = empty_overview()
    apply_dt_dd_label("Founded", "1975", overview)
    assert overview["founded"] == "1975"


@pytest.mark.unit
@pytest.mark.parametrize("label", ["Industry", "Industries"])
def test_apply_dt_dd_label_industry(label):
    overview = empty_overview()
    apply_dt_dd_label(label, "Software", overview)
    assert overview["industry"] == "Software"


@pytest.mark.unit
@pytest.mark.parametrize("label", ["Company type", "Type"])
def test_apply_dt_dd_label_company_type(label):
    overview = empty_overview()
    apply_dt_dd_label(label, "Public Company", overview)
    assert overview["company_type"] == "Public Company"


@pytest.mark.unit
@pytest.mark.parametrize("label", ["Company size", "Size"])
def test_apply_dt_dd_label_company_size(label):
    overview = empty_overview()
    apply_dt_dd_label(label, "10,000+ employees", overview)
    assert overview["company_size"] == "10,000+ employees"


@pytest.mark.unit
def test_apply_dt_dd_label_specialties():
    overview = empty_overview()
    apply_dt_dd_label("Specialties", "Cloud, AI", overview)
    assert overview["specialties"] == "Cloud, AI"


@pytest.mark.unit
def test_apply_dt_dd_label_unknown_label_leaves_overview_unchanged():
    overview = empty_overview()
    apply_dt_dd_label("Something Unrelated", "value", overview)
    assert overview == empty_overview()
