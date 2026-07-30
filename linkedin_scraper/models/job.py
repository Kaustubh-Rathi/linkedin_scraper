"""Pydantic models for LinkedIn Job data."""

from typing import Optional
from pydantic import field_validator

from .base import BaseScraperModel


class Job(BaseScraperModel):
    """
    LinkedIn Job posting model with validation.
    
    Represents a job posting on LinkedIn with all scraped data.
    """
    linkedin_url: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    company_linkedin_url: Optional[str] = None
    location: Optional[str] = None
    posted_date: Optional[str] = None
    applicant_count: Optional[str] = None
    job_description: Optional[str] = None
    benefits: Optional[str] = None
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Validate that URL is a LinkedIn job URL."""
        if 'linkedin.com/jobs' not in v:
            raise ValueError('Must be a valid LinkedIn job URL (contains /jobs)')
        return v

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Job {self.job_title} at {self.company}\n"
            f"  Location: {self.location}\n"
            f"  Posted: {self.posted_date}\n"
            f"  Applicants: {self.applicant_count}>"
        )
