"""
LinkedIn Search URL Builder.

Pure, deterministic URL construction component translating typed SearchQuery models
into LinkedIn search URLs with correct parameter encoding.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from linkedin_scraper.search.filters import (
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmploymentType,
    ExperienceLevel,
    SortBy,
    WorkplaceType,
)
from linkedin_scraper.search.queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
)

# Centralized Parameter Constants to prevent magic strings scattered across code
PARAM_KEYWORDS = "keywords"
PARAM_ORIGIN = "origin"
PARAM_START = "start"
PARAM_PAGE = "page"
PARAM_COMPANY_ID = "currentCompany"

# Base URL Constants
BASE_URL_SEARCH = "https://www.linkedin.com/search/results/"
BASE_URL_JOB_SEARCH = "https://www.linkedin.com/jobs/search/"
BASE_URL_COMPANY = "https://www.linkedin.com/company/"

# Filter Translation Mappings
DATE_POSTED_MAP_JOB: dict[DatePosted, str] = {
    DatePosted.PAST_24H: "r86400",
    DatePosted.PAST_WEEK: "r604800",
    DatePosted.PAST_MONTH: "r2592000",
}

DATE_POSTED_MAP_POST: dict[DatePosted, str] = {
    DatePosted.PAST_24H: "past-24-hours",
    DatePosted.PAST_WEEK: "past-week",
    DatePosted.PAST_MONTH: "past-24-hours",  # Fallback/best match for post date filtering
}

EXPERIENCE_LEVEL_MAP: dict[ExperienceLevel, str] = {
    ExperienceLevel.INTERNSHIP: "1",
    ExperienceLevel.ENTRY_LEVEL: "2",
    ExperienceLevel.ASSOCIATE: "3",
    ExperienceLevel.MID_SENIOR: "4",
    ExperienceLevel.DIRECTOR: "5",
    ExperienceLevel.EXECUTIVE: "6",
}

EMPLOYMENT_TYPE_MAP: dict[EmploymentType, str] = {
    EmploymentType.FULL_TIME: "F",
    EmploymentType.PART_TIME: "P",
    EmploymentType.CONTRACT: "C",
    EmploymentType.TEMPORARY: "T",
    EmploymentType.VOLUNTEER: "V",
    EmploymentType.INTERNSHIP: "I",
}

WORKPLACE_TYPE_MAP: dict[WorkplaceType, str] = {
    WorkplaceType.ON_SITE: "1",
    WorkplaceType.REMOTE: "2",
    WorkplaceType.HYBRID: "3",
}

COMPANY_SIZE_MAP: dict[CompanySize, str] = {
    CompanySize.SELF_EMPLOYED: "B",
    CompanySize.SIZE_11_50: "C",
    CompanySize.SIZE_51_200: "D",
    CompanySize.SIZE_201_500: "E",
    CompanySize.SIZE_501_1000: "F",
    CompanySize.SIZE_1001_5000: "G",
    CompanySize.SIZE_5001_10000: "H",
    CompanySize.SIZE_10000_PLUS: "I",
}

CONNECTION_DEGREE_MAP: dict[ConnectionDegree, str] = {
    ConnectionDegree.FIRST: "F",
    ConnectionDegree.SECOND: "S",
    ConnectionDegree.THIRD: "O",
}

SORT_BY_MAP: dict[SortBy, str] = {
    SortBy.RELEVANCE: "relevance",
    SortBy.DATE: "date_posted",
}

#: Job search uses its own sort codes (`sortBy=R` relevance, `sortBy=DD` date).
JOB_SORT_BY_MAP: dict[SortBy, str] = {
    SortBy.RELEVANCE: "R",
    SortBy.DATE: "DD",
}


def _format_facet_value(values: list[str] | list[Any]) -> str:
    """Format list of filter values into LinkedIn facet string: e.g. ["1", "2"] -> '["1","2"]'."""
    str_vals = [str(v) for v in values if v is not None]
    escaped = [f'"{v}"' for v in str_vals]
    return f"[{','.join(escaped)}]"


class LinkedInSearchUrlBuilder:
    """
    Pure builder component that constructs LinkedIn search URLs from typed SearchQuery objects.
    """

    def build_person_url(self, query: PersonSearchQuery) -> str:
        """Build search URL for People search."""
        base_url = f"{BASE_URL_SEARCH}people/"
        params: dict[str, str] = {}

        if query.keywords:
            params[PARAM_KEYWORDS] = query.keywords

        f = query.filters
        facets: list[str] = []

        if f.connection_degrees:
            mapped_degrees = [CONNECTION_DEGREE_MAP[d] for d in f.connection_degrees if d in CONNECTION_DEGREE_MAP]
            if mapped_degrees:
                facets.append(f"network=>{_format_facet_value(mapped_degrees)}")
        if f.location:
            facets.append(f"geoUrn=>{_format_facet_value(f.location)}")
        if f.current_company:
            facets.append(f"currentCompany=>{_format_facet_value(f.current_company)}")
        if f.past_company:
            facets.append(f"pastCompany=>{_format_facet_value(f.past_company)}")
        if f.industry:
            facets.append(f"industry=>{_format_facet_value(f.industry)}")
        if f.school:
            facets.append(f"schoolFilter=>{_format_facet_value(f.school)}")
        if f.profile_language:
            facets.append(f"profileLanguage=>{_format_facet_value(f.profile_language)}")
        if f.service_category:
            facets.append(f"serviceCategory=>{_format_facet_value(f.service_category)}")
        if f.title:
            params["title"] = f.title
        if f.first_name:
            params["firstName"] = f.first_name
        if f.last_name:
            params["lastName"] = f.last_name
        if f.company:
            params["company"] = f.company
        if f.school_name:
            params["school"] = f.school_name

        if facets:
            params["facet"] = quote(",".join(facets), safe="")

        if query.continuation_token:
            if query.continuation_token.isdigit():
                params[PARAM_PAGE] = query.continuation_token
            else:
                params["start"] = query.continuation_token

        if not params:
            return base_url
        return f"{base_url}?{urlencode(params)}"

    def build_company_url(self, query: CompanySearchQuery) -> str:
        """Build search URL for Company search."""
        base_url = f"{BASE_URL_SEARCH}companies/"
        params: dict[str, str] = {}

        if query.keywords:
            params[PARAM_KEYWORDS] = query.keywords

        f = query.filters
        facets: list[str] = []

        if f.location:
            facets.append(f"geoUrn=>{_format_facet_value(f.location)}")
        if f.industry:
            facets.append(f"industry=>{_format_facet_value(f.industry)}")
        if f.company_size:
            mapped_sizes = [COMPANY_SIZE_MAP[s] for s in f.company_size if s in COMPANY_SIZE_MAP]
            if mapped_sizes:
                facets.append(f"companySize=>{_format_facet_value(mapped_sizes)}")

        if facets:
            params["facet"] = quote(",".join(facets), safe="")

        if query.continuation_token:
            if query.continuation_token.isdigit():
                params[PARAM_PAGE] = query.continuation_token
            else:
                params["start"] = query.continuation_token

        if not params:
            return base_url
        return f"{base_url}?{urlencode(params)}"

    def build_job_url(self, query: JobSearchQuery) -> str:
        """Build search URL for Job search (preserving existing JobSearchScraper params)."""
        base_url = BASE_URL_JOB_SEARCH
        params: dict[str, str] = {}

        if query.keywords:
            params[PARAM_KEYWORDS] = query.keywords

        f = query.filters
        if f.location:
            params["location"] = ",".join(f.location)

        if f.date_posted and f.date_posted in DATE_POSTED_MAP_JOB:
            params["f_TPR"] = DATE_POSTED_MAP_JOB[f.date_posted]

        if f.experience_levels:
            mapped = [EXPERIENCE_LEVEL_MAP[e] for e in f.experience_levels if e in EXPERIENCE_LEVEL_MAP]
            if mapped:
                params["f_E"] = ",".join(mapped)

        if f.companies:
            params["f_C"] = ",".join(f.companies)

        if f.employment_types:
            mapped = [EMPLOYMENT_TYPE_MAP[t] for t in f.employment_types if t in EMPLOYMENT_TYPE_MAP]
            if mapped:
                params["f_JT"] = ",".join(mapped)

        if f.workplace_types:
            mapped = [WORKPLACE_TYPE_MAP[w] for w in f.workplace_types if w in WORKPLACE_TYPE_MAP]
            if mapped:
                params["f_WT"] = ",".join(mapped)

        if f.industries:
            params["f_I"] = ",".join(f.industries)

        if f.easy_apply_only:
            params["f_AL"] = "true"

        if f.under_ten_applicants:
            params["f_EA"] = "true"

        if f.sort_by is not None and f.sort_by in JOB_SORT_BY_MAP:
            params["sortBy"] = JOB_SORT_BY_MAP[f.sort_by]

        if f.distance is not None:
            params["distance"] = str(f.distance)

        if f.job_functions:
            params["f_F"] = ",".join(f.job_functions)

        if f.salary_buckets:
            params["f_SB2"] = ",".join(f.salary_buckets)

        if query.continuation_token:
            params[PARAM_START] = query.continuation_token

        if not params:
            return base_url
        return f"{base_url}?{urlencode(params)}"

    def build_post_url(self, query: PostSearchQuery) -> str:
        """Build search URL for Content / Post search."""
        base_url = f"{BASE_URL_SEARCH}content/"
        params: dict[str, str] = {}

        if query.keywords:
            params[PARAM_KEYWORDS] = query.keywords

        f = query.filters
        if f.date_posted and f.date_posted in DATE_POSTED_MAP_POST:
            params["datePosted"] = DATE_POSTED_MAP_POST[f.date_posted]

        if f.sort_by and f.sort_by in SORT_BY_MAP:
            params["sortBy"] = SORT_BY_MAP[f.sort_by]

        facets: list[str] = []
        if f.author_company:
            facets.append(f"authorCompany=>{_format_facet_value(f.author_company)}")
        if f.author_industry:
            facets.append(f"authorIndustry=>{_format_facet_value(f.author_industry)}")
        if f.content_types:
            facets.append(f"contentType=>{_format_facet_value(f.content_types)}")

        if facets:
            params["facet"] = quote(",".join(facets), safe="")

        if query.continuation_token:
            if query.continuation_token.isdigit():
                params[PARAM_PAGE] = query.continuation_token
            else:
                params["start"] = query.continuation_token

        if not params:
            return base_url
        return f"{base_url}?{urlencode(params)}"

    def build_employee_url(self, query: EmployeeSearchQuery) -> str:
        """Build search URL for Employee search (company-scoped people search).

        Formats standard LinkedIn people search URL with currentCompany filter.
        Accepts numeric company URN IDs, company slugs, or full company URLs.
        """
        base_url = f"{BASE_URL_SEARCH}people/"
        cid = query.company_identifier.strip()

        # Extract slug if a full URL was provided
        if "linkedin.com/company/" in cid:
            parts = cid.rstrip("/").split("/company/")
            if len(parts) > 1:
                cid = parts[1].split("/")[0].split("?")[0]
        elif cid.startswith("http://") or cid.startswith("https://"):
            cid = cid.rstrip("/").split("/")[-1].split("?")[0]

        params: dict[str, str] = {
            PARAM_COMPANY_ID: f'["{cid}"]',
        }
        if query.keywords:
            params[PARAM_KEYWORDS] = query.keywords

        f = query.filters
        if f.title:
            params["title"] = f.title

        facets: list[str] = []
        if f.location:
            facets.append(f"geoUrn=>{_format_facet_value(f.location)}")
        if f.department:
            facets.append(f"department=>{_format_facet_value(f.department)}")

        if facets:
            params["facet"] = quote(",".join(facets), safe="")

        if query.continuation_token:
            if query.continuation_token.isdigit():
                params[PARAM_PAGE] = query.continuation_token
            else:
                params["start"] = query.continuation_token

        return f"{base_url}?{urlencode(params)}"
