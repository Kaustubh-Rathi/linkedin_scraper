"""Tests for the pydantic models in linkedin_scraper.models."""
import json

import pytest
from pydantic import ValidationError

from linkedin_scraper.models import (
    Company,
    Contact,
    Education,
    Experience,
    Job,
    Person,
    Post,
)


# --- Person ------------------------------------------------------------------


@pytest.mark.unit
def test_person_url_validator_accepts_valid_profile_url():
    person = Person(linkedin_url="https://www.linkedin.com/in/example/")
    assert person.linkedin_url == "https://www.linkedin.com/in/example/"


@pytest.mark.unit
def test_person_url_validator_rejects_non_profile_url():
    with pytest.raises(ValidationError):
        Person(linkedin_url="https://www.linkedin.com/company/example/")


@pytest.mark.unit
def test_person_to_dict_contains_all_fields():
    person = Person(
        linkedin_url="https://linkedin.com/in/test",
        name="Test User",
        location="Test Location",
    )
    data = person.to_dict()
    assert data["name"] == "Test User"
    assert data["location"] == "Test Location"
    assert isinstance(data, dict)


@pytest.mark.unit
def test_person_to_json_returns_valid_json_string():
    person = Person(linkedin_url="https://linkedin.com/in/test", name="Test User")
    json_str = person.to_json()
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["name"] == "Test User"


@pytest.mark.unit
def test_person_company_property_uses_most_recent_experience():
    person = Person(
        linkedin_url="https://linkedin.com/in/test",
        experiences=[
            Experience(position_title="CEO", institution_name="Acme Corp"),
            Experience(position_title="Engineer", institution_name="Old Co"),
        ],
    )
    assert person.company == "Acme Corp"
    assert person.job_title == "CEO"


@pytest.mark.unit
def test_person_company_property_none_when_no_experiences():
    person = Person(linkedin_url="https://linkedin.com/in/test")
    assert person.company is None
    assert person.job_title is None


@pytest.mark.unit
def test_person_repr_contains_expected_fields():
    person = Person(
        linkedin_url="https://linkedin.com/in/test",
        name="Test User",
        location="Somewhere",
        experiences=[Experience(position_title="Engineer", institution_name="Acme")],
    )
    text = repr(person)
    assert "Test User" in text
    assert "Acme" in text
    assert "Engineer" in text
    assert "Somewhere" in text


# --- Company -------------------------------------------------------------


@pytest.mark.unit
def test_company_url_validator_accepts_valid_company_url():
    company = Company(linkedin_url="https://www.linkedin.com/company/example/")
    assert company.name is None


@pytest.mark.unit
def test_company_url_validator_rejects_invalid_url():
    with pytest.raises(ValidationError):
        Company(linkedin_url="https://www.linkedin.com/in/example/")


@pytest.mark.unit
def test_company_to_dict():
    company = Company(
        linkedin_url="https://linkedin.com/company/test",
        name="Test Company",
        website="https://test.com",
        industry="Technology",
    )
    data = company.to_dict()
    assert data["name"] == "Test Company"
    assert data["website"] == "https://test.com"


@pytest.mark.unit
def test_company_to_json():
    company = Company(linkedin_url="https://linkedin.com/company/test", name="Test Company")
    json_str = company.to_json()
    assert "Test Company" in json_str


@pytest.mark.unit
def test_company_repr_contains_expected_fields():
    company = Company(
        linkedin_url="https://linkedin.com/company/test",
        name="Test Co",
        industry="Software",
        company_size="10,000+",
        headquarters="Seattle, WA",
    )
    text = repr(company)
    assert "Test Co" in text
    assert "Software" in text
    assert "Seattle" in text


# --- Job -----------------------------------------------------------------


@pytest.mark.unit
def test_job_url_validator_accepts_valid_job_url():
    job = Job(linkedin_url="https://www.linkedin.com/jobs/view/12345/")
    assert job.job_title is None


@pytest.mark.unit
def test_job_url_validator_rejects_invalid_url():
    with pytest.raises(ValidationError):
        Job(linkedin_url="https://www.linkedin.com/in/example/")


@pytest.mark.unit
def test_job_to_dict():
    job = Job(
        linkedin_url="https://linkedin.com/jobs/view/123456",
        job_title="Software Engineer",
        company="Test Company",
    )
    data = job.to_dict()
    assert data["job_title"] == "Software Engineer"
    assert data["company"] == "Test Company"


@pytest.mark.unit
def test_job_to_json():
    job = Job(linkedin_url="https://linkedin.com/jobs/view/123456", job_title="Engineer")
    json_str = job.to_json()
    assert "Engineer" in json_str


@pytest.mark.unit
def test_job_repr_contains_expected_fields():
    job = Job(
        linkedin_url="https://linkedin.com/jobs/view/1",
        job_title="Engineer",
        company="Acme",
        location="Remote",
    )
    text = repr(job)
    assert "Engineer" in text
    assert "Acme" in text
    assert "Remote" in text


# --- Post ------------------------------------------------------------------


@pytest.mark.unit
def test_post_to_dict():
    post = Post(urn="urn:li:activity:123", text="Hello world", reactions_count=5)
    data = post.to_dict()
    assert data["urn"] == "urn:li:activity:123"
    assert data["reactions_count"] == 5


@pytest.mark.unit
def test_post_to_json():
    post = Post(text="Hello")
    json_str = post.to_json()
    assert "Hello" in json_str


@pytest.mark.unit
def test_post_repr_truncates_long_text():
    long_text = "x" * 200
    post = Post(text=long_text, posted_date="2d", reactions_count=3, comments_count=1)
    text = repr(post)
    assert "..." in text
    assert "x" * 80 in text
    assert "x" * 81 not in text


@pytest.mark.unit
def test_post_repr_does_not_truncate_short_text():
    post = Post(text="short text")
    text = repr(post)
    assert "short text" in text
    assert "..." not in text


@pytest.mark.unit
def test_post_repr_handles_none_text():
    post = Post()
    text = repr(post)
    assert "None" in text


# --- Contact / nested models ------------------------------------------------


@pytest.mark.unit
def test_contact_model_defaults():
    contact = Contact(type="website", value="https://example.com")
    assert contact.label is None


@pytest.mark.unit
def test_education_model_all_fields_optional_except_none_required():
    education = Education()
    assert education.institution_name is None
    assert education.degree is None
