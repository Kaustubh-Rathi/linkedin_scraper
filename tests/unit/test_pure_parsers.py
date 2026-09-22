"""Unit tests for pure parsers in `linkedin_scraper.parsers` package."""

import pytest
from linkedin_scraper.parsers.company import parse_company_overview, parse_company_profile
from linkedin_scraper.parsers.job import parse_job_posting
from linkedin_scraper.parsers.person import (
    map_interest_tab_to_category,
    parse_about_section,
    parse_accomplishment_item,
    parse_contact_dialog_heading_and_links,
    parse_interest_item,
    parse_name_and_location,
    parse_open_to_work,
)
from linkedin_scraper.parsers.posts import parse_company_posts


# --- Person Parsers ---

@pytest.mark.unit
def test_parse_name_and_location_h1_primary():
    name, loc = parse_name_and_location(
        "Satya Nadella",
        ["About", "Experience"],
        "Satya Nadella\nCEO at Microsoft\nGreater Seattle Area\nContact info",
    )
    assert name == "Satya Nadella"
    assert loc == "Greater Seattle Area"


@pytest.mark.unit
def test_parse_name_and_location_h2_fallback():
    name, loc = parse_name_and_location(
        "",
        ["Notifications", "Bill Gates", "About"],
        "Bill Gates\nCo-chair, Bill & Melinda Gates Foundation\nSeattle, Washington\nContact info",
    )
    assert name == "Bill Gates"
    assert loc == "Seattle, Washington"


@pytest.mark.unit
def test_parse_name_and_location_missing():
    name, loc = parse_name_and_location(None, [], None)
    assert name is None
    assert loc is None



@pytest.mark.unit
def test_parse_open_to_work_cases():
    assert parse_open_to_work("John Doe #OPEN_TO_WORK profile picture") is True
    assert parse_open_to_work("John Doe profile picture") is False
    assert parse_open_to_work(None) is False


@pytest.mark.unit
def test_parse_about_section_valid():
    sections = [
        "Featured\nSome post",
        "About\nPassionate software builder and engineering leader.\n… more",
    ]
    about = parse_about_section(sections)
    assert about == "Passionate software builder and engineering leader."


@pytest.mark.unit
def test_parse_about_section_missing():
    assert parse_about_section(["Experience\nGoogle"]) is None


@pytest.mark.unit
def test_parse_accomplishment_item_certification():
    spans = [
        "AWS Certified Solutions Architect",
        "Issued by Amazon Web Services · Jan 2023",
        "Credential ID 12345",
    ]
    acc = parse_accomplishment_item(
        spans, "https://aws.amazon.com/verify/12345", "certification"
    )
    assert acc is not None
    assert acc.category == "certification"
    assert acc.title == "AWS Certified Solutions Architect"
    assert acc.issuer == "Amazon Web Services"
    assert acc.issued_date == "Jan 2023"
    assert acc.credential_id == "12345"
    assert acc.credential_url == "https://aws.amazon.com/verify/12345"


@pytest.mark.unit
def test_parse_accomplishment_item_invalid_title():
    acc = parse_accomplishment_item([], None, "honor")
    assert acc is None


@pytest.mark.unit
def test_map_interest_tab_to_category():
    assert map_interest_tab_to_category("Top Companies") == "company"
    assert map_interest_tab_to_category("Groups") == "group"
    assert map_interest_tab_to_category("Schools") == "school"
    assert map_interest_tab_to_category("Newsletters") == "newsletter"
    assert map_interest_tab_to_category("Top Voices") == "influencer"
    assert map_interest_tab_to_category("Other") == "other"


@pytest.mark.unit
def test_parse_interest_item_valid():
    interest = parse_interest_item(
        ["Microsoft", "10M followers"],
        "https://www.linkedin.com/company/microsoft/",
        "company",
    )
    assert interest is not None
    assert interest.name == "Microsoft"
    assert interest.category == "company"
    assert interest.linkedin_url == "https://www.linkedin.com/company/microsoft/"


@pytest.mark.unit
def test_parse_interest_item_invalid():
    assert parse_interest_item([], None, "company") is None


@pytest.mark.unit
def test_parse_contact_dialog_heading_and_links():
    links = [("https://github.com/testuser", "GitHub", "Personal")]
    contacts = parse_contact_dialog_heading_and_links("Websites", links, None)
    assert len(contacts) == 1
    assert contacts[0].type == "github"
    assert contacts[0].value == "https://github.com/testuser"


@pytest.mark.unit
def test_parse_contact_dialog_heading_plain_text():
    contacts = parse_contact_dialog_heading_and_links("Address", [], "Address\n123 Tech Lane")
    assert len(contacts) == 1
    assert contacts[0].type == "address"
    assert contacts[0].value == "123 Tech Lane"


# --- Company Parsers ---

@pytest.mark.unit
def test_parse_company_overview():
    info_items = ["10,001+ employees", "Redmond, Washington", "Software Development"]
    links = [("https://www.microsoft.com", "Visit website")]
    dt_dd = [("Founded", "1975")]

    overview = parse_company_overview(info_items, links, dt_dd)
    assert overview["company_size"] == "10,001+ employees"
    assert overview["headquarters"] == "Redmond, Washington"
    assert overview["industry"] == "Software Development"
    assert overview["website"] == "https://www.microsoft.com"


@pytest.mark.unit
def test_parse_company_overview_dt_dd_fallback():
    overview = parse_company_overview(
        [], [], [("Website", "https://example.com"), ("Company Size", "50-100 employees")]
    )
    assert overview["website"] == "https://example.com"
    assert overview["company_size"] == "50-100 employees"


@pytest.mark.unit
def test_parse_company_profile():
    company = parse_company_profile(
        linkedin_url="https://www.linkedin.com/company/microsoft/",
        name="Microsoft",
        about_us="Our mission is to empower every person...",
        info_item_texts=["10,000+ employees"],
        links=[],
    )
    assert company.name == "Microsoft"
    assert company.company_size == "10,000+ employees"


# --- Post Parsers ---

@pytest.mark.unit
def test_parse_company_posts():
    js_data = [
        {
            "urn": "urn:li:activity:7123456789",
            "text": "Excited to announce our newest product update!",
            "timeText": "2d • Edited",
            "reactions": "1,234 reactions",
            "comments": "56 comments",
            "reposts": "12 reposts",
            "images": ["https://media.licdn.com/image1.jpg"],
        }
    ]
    posts = parse_company_posts(js_data)
    assert len(posts) == 1
    assert posts[0].urn == "urn:li:activity:7123456789"
    assert "Excited to announce" in posts[0].text
    assert posts[0].posted_date == "2d"
    assert posts[0].reactions_count == 1234
    assert posts[0].comments_count == 56
    assert posts[0].reposts_count == 12


# --- Job Parsers ---

@pytest.mark.unit
def test_parse_job_posting_top_card():
    job = parse_job_posting(
        linkedin_url="https://www.linkedin.com/jobs/view/1000/",
        job_title="Senior Software Engineer",
        company="TechCorp",
        company_linkedin_url="/company/techcorp/",
        top_card_text="San Francisco, CA · 2 days ago · 45 applicants",
        job_description="We are hiring a Senior Software Engineer...",
    )
    assert job.job_title == "Senior Software Engineer"
    assert job.company == "TechCorp"
    assert job.company_linkedin_url == "https://www.linkedin.com/company/techcorp/"
    assert job.location == "San Francisco, CA"
    assert job.posted_date == "2 days ago"
    assert job.applicant_count == "45 applicants"


@pytest.mark.unit
def test_parse_job_posting_fallback():
    job = parse_job_posting(
        linkedin_url="https://www.linkedin.com/jobs/view/1001/",
        job_title="Product Manager",
        company="InnovateInc",
        company_linkedin_url=None,
        top_card_text=None,
        location_fallback="Remote",
        posted_date_fallback="1 week ago",
        applicant_count_fallback="100+ applicants",
    )
    assert job.location == "Remote"
    assert job.posted_date == "1 week ago"
    assert job.applicant_count == "100+ applicants"
