"""Tests for linkedin_scraper.scrapers.company_parsing."""
import pytest

from linkedin_scraper.parsers.company import (
    apply_dt_dd_label,
    classify_info_item,
    empty_overview,
    parse_about_section,
    parse_company_name,
    parse_company_overview,
    parse_company_profile,
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


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_name,expected",
    [
        ("Acme Inc", "Acme Inc"),
        ("  Google  ", "Google"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_parse_company_name(raw_name, expected):
    assert parse_company_name(raw_name) == expected



@pytest.mark.unit
def test_parse_about_section_finds_first_nonempty_paragraph():
    sections = [
        ("Overview\nSome info", ["Not about us"]),
        ("About us\nDetailed description", ["   ", "We develop next-gen tools.", "Second paragraph"]),
    ]
    assert parse_about_section(sections) == "We develop next-gen tools."


@pytest.mark.unit
def test_parse_about_section_missing_returns_none():
    sections = [
        ("Overview\nSome info", ["Not about us"]),
        ("Jobs\nJob list", ["Software Engineer"]),
    ]
    assert parse_about_section(sections) is None


@pytest.mark.unit
def test_parse_company_overview_with_info_items_and_link():
    info_items = ["Software Development", "10,001+ employees", "Redmond, Washington"]
    links = [("https://microsoft.com", "Visit website")]
    overview = parse_company_overview(info_items, links)
    assert overview["industry"] == "Software Development"
    assert overview["company_size"] == "10,001+ employees"
    assert overview["headquarters"] == "Redmond, Washington"
    assert overview["website"] == "https://microsoft.com"
    assert overview["phone"] is None


@pytest.mark.unit
def test_parse_company_overview_dt_dd_fallback():
    info_items = []
    links = []
    dt_dd_pairs = [
        ("Website", "https://example.com"),
        ("Industry", "Technology"),
        ("Headquarters", "Austin, TX"),
        ("Founded", "2010"),
        ("Company size", "50-100 employees"),
        ("Type", "Privately Held"),
        ("Specialties", "AI, Cloud"),
        ("Phone", "555-0100"),
    ]
    overview = parse_company_overview(info_items, links, dt_dd_pairs)
    assert overview["website"] == "https://example.com"
    assert overview["industry"] == "Technology"
    assert overview["headquarters"] == "Austin, TX"
    assert overview["founded"] == "2010"
    assert overview["company_size"] == "50-100 employees"
    assert overview["company_type"] == "Privately Held"
    assert overview["specialties"] == "AI, Cloud"
    assert overview["phone"] == "555-0100"


@pytest.mark.unit
def test_parse_company_profile_constructs_model():
    from linkedin_scraper.models import Company
    info_items = ["Software Development", "500 employees", "New York, New York"]
    links = [("https://example.com", "Learn more")]
    company = parse_company_profile(
        linkedin_url="https://www.linkedin.com/company/example/",
        name="Example Inc",
        about_us="About Example",
        info_item_texts=info_items,
        links=links,
    )
    assert isinstance(company, Company)
    assert company.linkedin_url == "https://www.linkedin.com/company/example/"
    assert company.name == "Example Inc"
    assert company.about_us == "About Example"
    assert company.industry == "Software Development"
    assert company.company_size == "500 employees"
    assert company.headquarters == "New York, New York"
    assert company.website == "https://example.com"

