"""Pydantic models for LinkedIn Person/Profile data."""

from typing import List, Optional

from pydantic import Field, field_validator

from .base import BaseScraperModel


class Interest(BaseScraperModel):
    name: str
    category: str
    linkedin_url: Optional[str] = None


class Contact(BaseScraperModel):
    type: str
    value: str
    label: Optional[str] = None


class Experience(BaseScraperModel):
    """Work experience model."""

    position_title: Optional[str] = None
    institution_name: Optional[str] = None
    linkedin_url: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class Education(BaseScraperModel):
    """Education model."""

    institution_name: Optional[str] = None
    degree: Optional[str] = None
    linkedin_url: Optional[str] = None
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    description: Optional[str] = None


class Accomplishment(BaseScraperModel):
    category: str
    title: str
    issuer: Optional[str] = None
    issued_date: Optional[str] = None
    credential_id: Optional[str] = None
    credential_url: Optional[str] = None
    description: Optional[str] = None


class Person(BaseScraperModel):
    """
    LinkedIn Person/Profile model with validation.

    Represents a complete LinkedIn profile with all scraped data.
    """

    linkedin_url: str
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    about: Optional[str] = None
    open_to_work: bool = False
    experiences: List[Experience] = Field(default_factory=list)
    educations: List[Education] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    volunteer_experiences: List[Experience] = Field(default_factory=list)
    interests: List[Interest] = Field(default_factory=list)
    accomplishments: List[Accomplishment] = Field(default_factory=list)
    contacts: List[Contact] = Field(default_factory=list)

    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Validate that URL is a LinkedIn profile URL."""
        if "linkedin.com/in/" not in v:
            raise ValueError("Must be a valid LinkedIn profile URL (contains /in/)")
        return v

    @property
    def company(self) -> Optional[str]:
        """
        Get the most recent company.

        Returns:
            Company name from most recent experience or None
        """
        if self.experiences:
            return self.experiences[0].institution_name
        return None

    @property
    def job_title(self) -> Optional[str]:
        """
        Get the most recent job title.

        Returns:
            Job title from most recent experience or None
        """
        if self.experiences:
            return self.experiences[0].position_title
        return None

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Person {self.name}\n"
            f"  Company: {self.company}\n"
            f"  Title: {self.job_title}\n"
            f"  Location: {self.location}\n"
            f"  Experiences: {len(self.experiences)}\n"
            f"  Education: {len(self.educations)}>"
        )
