"""Tests for linkedin_scraper.scrapers.person.parser (fixture-testable
LinkedIn person-section parsers)."""
import pytest

from linkedin_scraper.scrapers.person.parser import (
    clean_lines,
    is_education_metadata,
    is_valid_institution,
    looks_like_date_line,
    looks_like_degree,
    parse_education_lines,
    parse_education_times,
    parse_educations_text,
    parse_experience_lines,
    parse_experiences_text,
    parse_work_times,
    section_lines,
)


@pytest.mark.unit
def test_clean_lines_strips_and_drops_blank_lines():
    text = "  Line One  \n\n  Line Two\n   \nLine Three  "
    assert clean_lines(text) == ["Line One", "Line Two", "Line Three"]


@pytest.mark.unit
def test_clean_lines_drops_adjacent_duplicates():
    text = "Same\nSame\nDifferent\nSame"
    assert clean_lines(text) == ["Same", "Different", "Same"]


@pytest.mark.unit
def test_clean_lines_empty_text_returns_empty_list():
    assert clean_lines("") == []


@pytest.mark.unit
def test_section_lines_missing_header_returns_empty_list():
    text = "Name\nHeadline\nFooter"
    assert section_lines(text, "Experience", {"Footer"}) == []


@pytest.mark.unit
def test_section_lines_returns_lines_until_stop_header():
    text = "Experience\nRole One\nRole Two\nEducation\nSchool"
    result = section_lines(text, "Experience", {"Education"})
    assert result == ["Role One", "Role Two"]


@pytest.mark.unit
def test_section_lines_stops_at_linkedin_corporation_footer():
    text = "Experience\nRole One\nLinkedIn Corporation © 2024"
    result = section_lines(text, "Experience", set())
    assert result == ["Role One"]


@pytest.mark.unit
def test_section_lines_filters_out_ui_chrome_lines():
    text = "Experience\nRole One\nShow all experiences\nRole Two"
    result = section_lines(text, "Experience", set())
    assert result == ["Role One", "Role Two"]


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jan 2020 - Present · 6 yrs", ("Jan 2020", "Present", "6 yrs")),
        ("2000 - Present · 26 yrs 1 mo", ("2000", "Present", "26 yrs 1 mo")),
        ("Jan 2020 - Dec 2022 · 2 yrs", ("Jan 2020", "Dec 2022", "2 yrs")),
        ("2015 - Present", ("2015", "Present", None)),
        ("2015 \u2013 2019", ("2015", "2019", None)),
        ("2015 \u2014 2019", ("2015", "2019", None)),
        ("", (None, None, None)),
    ],
)
def test_parse_work_times_variants(raw, expected):
    assert parse_work_times(raw) == expected


@pytest.mark.unit
def test_parse_work_times_none_input_returns_all_none():
    assert parse_work_times(None) == (None, None, None)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1973 - 1977", ("1973", "1977")),
        ("2015", ("2015", "2015")),
        ("", (None, None)),
        ("no years here", (None, None)),
    ],
)
def test_parse_education_times_variants(raw, expected):
    assert parse_education_times(raw) == expected


@pytest.mark.unit
def test_looks_like_date_line_digit_only_year():
    # A bare 4-digit year (isdigit()) is treated as a date line.
    assert looks_like_date_line("2020") is True


@pytest.mark.unit
def test_looks_like_date_line_range():
    assert looks_like_date_line("2015 - 2019") is True


@pytest.mark.unit
def test_looks_like_date_line_with_separator():
    assert looks_like_date_line("Jan 2020 - Present") is True


@pytest.mark.unit
def test_looks_like_date_line_without_year_is_false():
    assert looks_like_date_line("Remote") is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "line",
    [
        "Bachelor of Science - BS, Computer Science",
        "Master of Business Administration",
        "PhD in Physics",
        "MBA",
        "B.Tech in Mechanical Engineering",
        "Diploma in Design",
    ],
)
def test_looks_like_degree_true_cases(line):
    assert looks_like_degree(line) is True


@pytest.mark.unit
def test_looks_like_degree_false_case():
    assert looks_like_degree("Studied Computer Science") is False


@pytest.mark.unit
@pytest.mark.parametrize(
    "line",
    ["Grade: 8.52/10", "Skills: Python, Java", "Activities: Chess Club", "Activities and societies: Debate"],
)
def test_is_education_metadata_true_cases(line):
    assert is_education_metadata(line) is True


@pytest.mark.unit
def test_is_education_metadata_false_case():
    assert is_education_metadata("Example University") is False


@pytest.mark.unit
def test_is_valid_institution_true_for_plain_name():
    assert is_valid_institution("Example University") is True


@pytest.mark.unit
def test_is_valid_institution_false_for_metadata():
    assert is_valid_institution("Grade: 9.0/10") is False


@pytest.mark.unit
def test_is_valid_institution_false_for_date_line():
    assert is_valid_institution("2015 - 2019") is False


@pytest.mark.unit
def test_is_valid_institution_false_for_short_degree_line():
    assert is_valid_institution("MBA") is False


@pytest.mark.unit
def test_is_valid_institution_false_for_empty_string():
    assert is_valid_institution("") is False


# --- parse_experience_lines -------------------------------------------------


@pytest.mark.unit
def test_parse_experience_lines_grouped_retains_roles_and_description():
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

    assert [exp.position_title for exp in experiences] == [
        "Software Development Engineer II",
        "Software Development Engineer",
    ]
    assert all(exp.institution_name == "Amazon" for exp in experiences)
    assert experiences[0].description == "Built distributed services."


@pytest.mark.unit
def test_parse_experience_lines_single_role():
    lines = [
        "CEO",
        "Acme Corp · Full-time",
        "Jan 2020 - Present · 6 yrs",
        "Remote",
        "Led product and engineering.",
    ]

    experiences = parse_experience_lines(lines)

    assert len(experiences) == 1
    assert experiences[0].position_title == "CEO"
    assert experiences[0].institution_name == "Acme Corp"
    assert experiences[0].location == "Remote"
    assert experiences[0].description == "Led product and engineering."


@pytest.mark.unit
def test_parse_experience_lines_company_first_layout():
    lines = [
        "Microsoft",
        "Chairman and CEO",
        "Feb 2014 - Present · 12 yrs 6 mos",
        "Greater Seattle Area",
    ]

    experiences = parse_experience_lines(lines)

    assert len(experiences) == 1
    assert experiences[0].position_title == "Chairman and CEO"
    assert experiences[0].institution_name == "Microsoft"


@pytest.mark.unit
def test_parse_experience_lines_no_date_returns_empty():
    assert parse_experience_lines(["Just some text", "No dates here"]) == []


@pytest.mark.unit
def test_parse_experience_lines_filters_ui_chrome():
    lines = [
        "Show all experiences",
        "CEO",
        "Acme Corp",
        "Jan 2020 - Present · 6 yrs",
    ]
    experiences = parse_experience_lines(lines)
    assert len(experiences) == 1


# --- parse_education_lines ---------------------------------------------------


@pytest.mark.unit
def test_parse_education_lines_full_card():
    lines = [
        "Example University",
        "Bachelor of Science - BS, Computer Science",
        "2015 - 2019",
    ]

    education = parse_education_lines(lines)

    assert education is not None
    assert education.institution_name == "Example University"
    assert "Computer Science" in education.degree
    assert education.from_date == "2015"
    assert education.to_date == "2019"


@pytest.mark.unit
def test_parse_education_lines_invalid_institution_returns_none():
    assert parse_education_lines(["Grade: 9.0/10"]) is None


@pytest.mark.unit
def test_parse_education_lines_empty_returns_none():
    assert parse_education_lines([]) is None


@pytest.mark.unit
def test_parse_education_lines_retains_metadata_as_description():
    lines = [
        "Example University",
        "Bachelor of Technology - BTech, Information Technology",
        "Grade: 8.52/10",
        "Skills: Keras, PyTorch, +11 skills",
    ]

    education = parse_education_lines(lines)

    assert education is not None
    assert "Grade: 8.52/10" in education.description
    assert "Skills: Keras" in education.description


# --- text fallback parsers ----------------------------------------------------


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


@pytest.mark.unit
def test_parse_experiences_text_no_experience_header_returns_empty():
    assert parse_experiences_text("Name\nHeadline") == []


@pytest.mark.unit
def test_parse_educations_text_skips_grade_and_skills_metadata():
    text = """
Education
Indian Institute Of Information Technology Allahabad
Bachelor of Technology - BTech, Information Technology
Grade: 8.52/10
Skills: Keras, PyTorch, +11 skills
More profiles for you
"""
    educations = parse_educations_text(text)
    assert len(educations) == 1
    assert "Allahabad" in (educations[0].institution_name or "")
    assert "BTech" in (educations[0].degree or "")


@pytest.mark.unit
def test_parse_educations_text_multiple_entries():
    text = """
Education
Example University
Bachelor of Science - BS, Computer Science
2015 - 2019
Another College
Diploma in Arts
2010 - 2013
People also viewed
"""
    educations = parse_educations_text(text)
    assert len(educations) == 2
    assert educations[0].institution_name == "Example University"
    assert educations[1].institution_name == "Another College"


@pytest.mark.unit
def test_parse_educations_text_no_header_returns_empty():
    assert parse_educations_text("Name\nHeadline") == []
