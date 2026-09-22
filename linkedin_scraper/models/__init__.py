"""Pydantic data models for LinkedIn scraper."""

from .base import BaseScraperModel
from .company import Company, CompanySummary, Employee
from .job import Job
from .person import Accomplishment, Contact, Education, Experience, Interest, Person
from .post import Post

__all__ = [
    "BaseScraperModel",
    "Person",
    "Experience",
    "Education",
    "Contact",
    "Accomplishment",
    "Interest",
    "Company",
    "CompanySummary",
    "Employee",
    "Job",
    "Post",
]
