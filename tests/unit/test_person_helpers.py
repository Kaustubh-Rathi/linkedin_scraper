"""Person helper unit tests (moved from integration module)."""
import inspect
import pytest
from linkedin_scraper.scrapers.person.links import (
    classify_link,
    contact_type_from_heading,
    profile_detail_url,
    unwrap_href,
)
from linkedin_scraper.scrapers.person.parser import (
    parse_education_lines,
    parse_educations_text,
    parse_experience_lines,
    parse_experiences_text,
    section_lines,
)
from linkedin_scraper.scrapers.person import PersonScraper as PersonScraperCls
from linkedin_scraper.scrapers.person.profile import ProfileExtractor
from linkedin_scraper.scrapers.person.contacts import ContactsExtractor

@pytest.mark.unit
def test_unwrap_linkedin_safety_redirect():
    raw = (
        "https://www.linkedin.com/safety/go/?url="
        "https%3A%2F%2Fgithub.com%2FKaustubh-Rathi&urlhash=x"
    )
    assert unwrap_href(raw) == "https://github.com/Kaustubh-Rathi"


@pytest.mark.unit
def test_classify_github_link():
    contact = classify_link(
        "https://github.com/Kaustubh-Rathi", "GitHub"
    )
    assert contact.type == "github"
    assert "github.com" in contact.value


@pytest.mark.unit
def test_parse_educations_skips_grade_skills():
    text = """
Education
Indian Institute Of Information Technology Allahabad
Bachelor of Technology - BTech, Information Technology
Grade: 8.52/10
Skills: Keras, PyTorch, +11 skills
More profiles for you
"""
    edus = parse_educations_text(text)
    assert len(edus) == 1
    assert "Allahabad" in (edus[0].institution_name or "")
    assert "BTech" in (edus[0].degree or "")


@pytest.mark.unit
def test_parse_grouped_experience_retains_roles_and_description():
    lines = [
        "Amazon",
        "2 yrs 8 mos",
        "Software Development Engineer II",
        "Jan 2025 - Present · 1 yr 7 mos",
        "Bengaluru, Karnataka, India · Hybrid",
        "Built distributed services.",
        "Software Development Engineer",
        "May 2023 - Jan 2025 · 1 yr 9 mos",
        "Bengaluru, Karnataka, India",
        "Owned production APIs.",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/amazon/"
    )

    assert [experience.position_title for experience in experiences] == [
        "Software Development Engineer II",
        "Software Development Engineer",
    ]
    assert all(experience.institution_name == "Amazon" for experience in experiences)
    assert all(experience.linkedin_url for experience in experiences)
    assert experiences[0].description == "Built distributed services."


@pytest.mark.unit
def test_parse_single_role_experience_keeps_title_and_company():
    lines = [
        "CEO",
        "Acme Corp · Full-time",
        "Jan 2020 - Present · 6 yrs",
        "Remote",
        "Led product and engineering.",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/acme-corp/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "CEO"
    assert experiences[0].institution_name == "Acme Corp"
    assert experiences[0].linkedin_url == "https://www.linkedin.com/company/acme-corp/"
    assert experiences[0].location == "Remote"
    assert experiences[0].description == "Led product and engineering."


@pytest.mark.unit
def test_parse_single_role_company_first_layout():
    """Some cards emit company logo text before the job title."""
    lines = [
        "Microsoft",
        "Chairman and CEO",
        "Feb 2014 - Present · 12 yrs 6 mos",
        "Greater Seattle Area",
        "Member Board Of Trustees",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/microsoft/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"
    assert experiences[0].linkedin_url == "https://www.linkedin.com/company/microsoft/"


@pytest.mark.unit
def test_parse_single_role_company_first_with_employment_type():
    lines = [
        "Microsoft",
        "Chairman and CEO · Full-time",
        "Feb 2014 - Present · 12 yrs 6 mos",
        "Greater Seattle Area",
    ]

    experiences = parse_experience_lines(
        lines, "https://www.linkedin.com/company/microsoft/"
    )

    assert len(experiences) == 1
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"


@pytest.mark.unit
def test_parse_experiences_text_splits_flat_section():
    text = """
Experience
Chairman and CEO
Microsoft
Feb 2014 - Present · 12 yrs 6 mos
Greater Seattle Area
Member Board Of Trustees
University of Chicago
2018 - Present · 8 yrs 7 mos
Board Member
Starbucks
2017 - 2024 · 7 yrs
More profiles for you
"""
    experiences = parse_experiences_text(text)
    assert len(experiences) >= 3
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"
    assert experiences[1].position_title == "Member Board Of Trustees"
    assert experiences[1].institution_name == "University of Chicago"


@pytest.mark.unit
def test_parse_experience_without_company_url():
    lines = [
        "Independent Consultant",
        "Self-employed",
        "Mar 2019 - Present · 7 yrs",
    ]

    experiences = parse_experience_lines(lines)

    assert len(experiences) == 1
    assert experiences[0].position_title == "Independent Consultant"
    assert experiences[0].institution_name == "Self-employed"
    assert experiences[0].linkedin_url is None


@pytest.mark.unit
def test_parse_education_without_school_url():
    from linkedin_scraper.scrapers.person.parser import parse_education_lines

    education = parse_education_lines(
        [
            "Example University",
            "Bachelor of Science - BS, Computer Science",
            "2015 - 2019",
        ]
    )

    assert education is not None
    assert education.institution_name == "Example University"
    assert education.linkedin_url is None
    assert "Computer Science" in (education.degree or "")


@pytest.mark.unit
def test_missing_section_heading_does_not_parse_whole_page():
    assert section_lines("Name\nHeadline\nFooter", "Experience", {"Footer"}) == []


@pytest.mark.unit
def test_detail_url_handles_profile_without_trailing_slash():
    assert (
        profile_detail_url("https://www.linkedin.com/in/example", "details/experience/")
        == "https://www.linkedin.com/in/example/details/experience/"
    )


@pytest.mark.unit
def test_scrape_keeps_complete_sections_enabled_by_default():
    parameters = inspect.signature(PersonScraperCls.scrape).parameters
    assert parameters["include_interests"].default is True
    assert parameters["include_accomplishments"].default is True


@pytest.mark.unit
def test_plain_contact_fields_are_retained():
    assert contact_type_from_heading("Birthday") == "birthday"
    assert contact_type_from_heading("Address") == "address"
    assert (
        ContactsExtractor.plain_contact_value("Phone\n+1 555 0100", "Phone")
        == "+1 555 0100"
    )


@pytest.mark.unit
def test_location_from_header_not_suggested_profile():
    text = """
Reid Hoffman
He/Him
Co-Founder, LinkedIn.
United States
·
Contact info
2,781,927 followers
People who follow Reid also follow
Demis Hassabis
Nobel Laureate | Co-Founder & CEO, Google DeepMind
"""
    loc = ProfileExtractor.location_from_header_lines(text, "Reid Hoffman")
    assert loc == "United States"


@pytest.mark.unit
def test_location_from_header_without_headline():
    text = """
Ada Lovelace
London, England, United Kingdom
Contact info
500+ connections
"""
    loc = ProfileExtractor.location_from_header_lines(text, "Ada Lovelace")
    assert loc == "London, England, United Kingdom"
