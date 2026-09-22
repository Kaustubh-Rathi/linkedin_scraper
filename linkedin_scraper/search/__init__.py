"""LinkedIn search domain contracts, models, filters, queries, ports, workflows, and exporters."""

from .export import (
    ExportFormat,
    export_results,
    export_to_csv,
    export_to_json,
    export_to_jsonl,
    infer_export_format,
)
from .filters import (
    CompanySearchFilter,
    CompanySize,
    ConnectionDegree,
    DatePosted,
    EmployeeSearchFilter,
    EmploymentType,
    ExperienceLevel,
    JobSearchFilter,
    PersonSearchFilter,
    PostSearchFilter,
    SortBy,
    WorkplaceType,
)
from .ports import (
    CompanySearchPort,
    EmployeeSearchPort,
    JobSearchPort,
    PersonSearchPort,
    PostSearchPort,
)
from .queries import (
    CompanySearchQuery,
    EmployeeSearchQuery,
    JobSearchQuery,
    PersonSearchQuery,
    PostSearchQuery,
    SearchQuery,
)
from .results import (
    CompanySearchResult,
    EmployeeSearchResult,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchPage,
)
from .services import LinkedInSearchFacade
from .workflow import (
    SearchWorkflowResult,
    consume_search,
    execute_search_workflow,
    iterate_search_pages,
    iterate_search_results,
)

__all__ = [
    # Enums & Filters
    "ConnectionDegree",
    "DatePosted",
    "ExperienceLevel",
    "EmploymentType",
    "WorkplaceType",
    "CompanySize",
    "SortBy",
    "PersonSearchFilter",
    "CompanySearchFilter",
    "JobSearchFilter",
    "PostSearchFilter",
    "EmployeeSearchFilter",
    # Queries
    "SearchQuery",
    "PersonSearchQuery",
    "CompanySearchQuery",
    "JobSearchQuery",
    "PostSearchQuery",
    "EmployeeSearchQuery",
    # Results
    "PersonSearchResult",
    "CompanySearchResult",
    "JobSearchResult",
    "PostSearchResult",
    "EmployeeSearchResult",
    "SearchPage",
    # Ports
    "PersonSearchPort",
    "CompanySearchPort",
    "JobSearchPort",
    "PostSearchPort",
    "EmployeeSearchPort",
    # Service / Facade
    "LinkedInSearchFacade",
    # Exporters & Workflow
    "ExportFormat",
    "export_results",
    "export_to_csv",
    "export_to_json",
    "export_to_jsonl",
    "infer_export_format",
    "SearchWorkflowResult",
    "iterate_search_pages",
    "iterate_search_results",
    "consume_search",
    "execute_search_workflow",
]
