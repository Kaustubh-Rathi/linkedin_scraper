"""Pydantic models for LinkedIn Company data."""

from typing import List, Optional
from pydantic import Field, field_validator

from .base import BaseScraperModel


class CompanySummary(BaseScraperModel):
    """Summary information for affiliated/showcase companies."""
    linkedin_url: Optional[str] = None
    name: Optional[str] = None
    followers: Optional[str] = None


class Employee(BaseScraperModel):
    """Employee information."""
    name: str
    designation: Optional[str] = None
    linkedin_url: Optional[str] = None


class Company(BaseScraperModel):
    """
    LinkedIn Company model with validation.
    
    Represents a complete LinkedIn company page with all scraped data.
    """
    linkedin_url: str
    name: Optional[str] = None
    about_us: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    headquarters: Optional[str] = None
    founded: Optional[str] = None
    industry: Optional[str] = None
    company_type: Optional[str] = None
    company_size: Optional[str] = None
    specialties: Optional[str] = None
    # Reserved for future scrapers — CompanyScraper does not populate these yet.
    headcount: Optional[int] = None
    showcase_pages: List[CompanySummary] = Field(default_factory=list)
    affiliated_companies: List[CompanySummary] = Field(default_factory=list)
    employees: List[Employee] = Field(default_factory=list)
    
    @field_validator('linkedin_url')
    @classmethod
    def validate_linkedin_url(cls, v: str) -> str:
        """Validate that URL is a LinkedIn company URL."""
        if 'linkedin.com/company/' not in v:
            raise ValueError('Must be a valid LinkedIn company URL (contains /company/)')
        return v

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<Company {self.name}\n"
            f"  Industry: {self.industry}\n"
            f"  Size: {self.company_size}\n"
            f"  Headquarters: {self.headquarters}\n"
            f"  Employees: {len(self.employees) if self.employees else 0}>"
        )
