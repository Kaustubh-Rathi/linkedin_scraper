"""Targeted branch coverage tests for parsers (person, company, job)."""

import pytest

from linkedin_scraper.parsers.company import (
    apply_dt_dd_label,
    classify_info_item,
    parse_about_section as parse_company_about,
)
from linkedin_scraper.parsers.job import (
    clean_job_url,
    looks_like_applicant_count,
    looks_like_location,
    looks_like_posted_date,
    parse_job_posting,
    parse_top_card_parts,
)
from linkedin_scraper.parsers.person import (
    _single_role_title_and_company,
    parse_accomplishment_item,
    parse_contact_dialog_heading_and_links,
    parse_experience_lines,
)


@pytest.mark.unit
def test_infer_title_and_company_unusual_branches():
    # Empty before line
    title, company = _single_role_title_and_company(["", "Acme"], 0)
    assert title == ""

    # date_index = 1, before exists, before2 does not
    title, company = _single_role_title_and_company(["Acme Corp", "2020 - 2021"], 1)
    assert title == "Acme Corp"
    assert company == ""



@pytest.mark.unit
def test_parse_experience_grouped_roles_fallback_company():
    # Grouped roles where title_index - 1 is duration only
    lines = [
        "Acme Corp",
        "3 yrs 5 mos",
        "Senior Developer",
        "Jan 2021 - Present · 2 yrs",
        "Developer",
        "Jan 2019 - Jan 2021 · 2 yrs",
    ]
    exps = parse_experience_lines(lines)
    assert len(exps) == 2
    assert exps[0].institution_name == "Acme Corp"
    assert exps[1].institution_name == "Acme Corp"


@pytest.mark.unit
def test_parse_accomplishment_date_branches():
    # Accomplishment with month in text and dot separator
    spans = ["Certified Security Analyst", "Security Org", "Nov 2022 · License 12345"]
    acc = parse_accomplishment_item(spans, None, "licenses_and_certifications")
    assert acc is not None
    assert acc.title == "Certified Security Analyst"

    # Accomplishment with plain month in text
    spans2 = ["Certified Architect", "Cloud Org", "Dec 2021"]
    acc2 = parse_accomplishment_item(spans2, None, "licenses_and_certifications")
    assert acc2 is not None

    # Oversized span ignored
    long_span = "A" * 600
    acc3 = parse_accomplishment_item([long_span], None, "licenses")
    assert acc3 is None


@pytest.mark.unit
def test_parse_contact_dialog_mailto_tel_and_unknown():
    # Unknown heading returns empty list
    assert parse_contact_dialog_heading_and_links("Unknown Custom Field", [], None) == []

    # Mailto link
    contacts = parse_contact_dialog_heading_and_links(
        "Email", [("mailto:alice@example.com", "alice@example.com", "Personal")], None
    )
    assert len(contacts) == 1
    assert contacts[0].value == "alice@example.com"
    assert contacts[0].type == "email"

    # Tel link
    contacts_tel = parse_contact_dialog_heading_and_links(
        "Phone", [("tel:+1234567890", "+1234567890", "Mobile")], None
    )
    assert len(contacts_tel) == 1
    assert contacts_tel[0].value == "+1234567890"
    assert contacts_tel[0].type == "phone"

    # Plain text container fallback
    contacts_plain = parse_contact_dialog_heading_and_links(
        "Address", [], "Address\n123 Market St\nSan Francisco, CA"
    )
    assert len(contacts_plain) == 1
    assert "123 Market St" in contacts_plain[0].value


@pytest.mark.unit
def test_parse_company_about_and_overview_branches():
    # About section with tuple data
    section_data = [("About us\nWe build innovative software.", ["We build innovative software for developers worldwide."])]
    about = parse_company_about(section_data)
    assert about is not None
    assert "innovative software" in about

    # Classify info items
    assert classify_info_item("10,000+ employees")[0] == "company_size"
    assert classify_info_item("Redmond, Washington")[0] == "headquarters"
    assert classify_info_item("Software Development")[0] == "industry"
    assert classify_info_item("Unrelated string") is None

    # DT/DD labels
    overview = {}
    apply_dt_dd_label("Company size", "500 employees", overview)
    apply_dt_dd_label("Specialties", "AI, Cloud", overview)
    assert overview["company_size"] == "500 employees"
    assert overview["specialties"] == "AI, Cloud"


@pytest.mark.unit
def test_parse_job_branches():
    # Clean job URL
    assert clean_job_url("jobs/view/123?ref=search#details") == "https://www.linkedin.com/jobs/view/123"
    assert clean_job_url("") == ""

    # Parse top card
    loc, date, app = parse_top_card_parts("New York, NY · 1 day ago · 25 applicants")
    assert loc == "New York, NY"
    assert date == "1 day ago"
    assert app == "25 applicants"

    # Heuristics
    assert looks_like_location("San Francisco, CA") is True
    assert looks_like_posted_date("Posted 3 days ago") is True
    assert looks_like_applicant_count("Over 100 applicants") is True

    # Parse job posting model
    job = parse_job_posting(
        linkedin_url="https://www.linkedin.com/jobs/view/123",
        job_title="Software Engineer",
        company="Microsoft",
        company_linkedin_url="/company/microsoft/",
        top_card_text="Redmond, WA · 2 days ago · 50 applicants",
    )
    assert job.company_linkedin_url == "https://www.linkedin.com/company/microsoft/"
    assert job.location == "Redmond, WA"

