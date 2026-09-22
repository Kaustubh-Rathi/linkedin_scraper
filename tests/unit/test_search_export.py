"""Unit tests for search export pipeline (CSV, JSON, JSONL)."""

from io import StringIO
import json
from pathlib import Path
import pytest

from linkedin_scraper.search import (
    CompanySearchResult,
    EmployeeSearchResult,
    ExportFormat,
    JobSearchResult,
    PersonSearchResult,
    PostSearchResult,
    SearchPage,
    export_results,
    export_to_csv,
    export_to_json,
    export_to_jsonl,
    infer_export_format,
)
from linkedin_scraper.search.export import _serialize_value_for_csv, _write_to_destination


@pytest.mark.unit
def test_export_format_parsing():
    assert ExportFormat.from_str("json") == ExportFormat.JSON
    assert ExportFormat.from_str("JSON") == ExportFormat.JSON
    assert ExportFormat.from_str(".json") == ExportFormat.JSON
    assert ExportFormat.from_str("csv") == ExportFormat.CSV
    assert ExportFormat.from_str("CSV") == ExportFormat.CSV
    assert ExportFormat.from_str(".csv") == ExportFormat.CSV
    assert ExportFormat.from_str("jsonl") == ExportFormat.JSONL
    assert ExportFormat.from_str("ndjson") == ExportFormat.JSONL
    assert ExportFormat.from_str(ExportFormat.CSV) == ExportFormat.CSV

    with pytest.raises(ValueError, match="Unsupported export format"):
        ExportFormat.from_str("xml")


@pytest.mark.unit
def test_infer_export_format():
    assert infer_export_format("out.csv") == ExportFormat.CSV
    assert infer_export_format(Path("data/results.json")) == ExportFormat.JSON
    assert infer_export_format("stream.jsonl") == ExportFormat.JSONL
    assert infer_export_format("stream.ndjson") == ExportFormat.JSONL
    assert infer_export_format("file.unknown", default=ExportFormat.CSV) == ExportFormat.CSV


@pytest.mark.unit
def test_serialize_value_for_csv():
    assert _serialize_value_for_csv(None) == ""
    assert _serialize_value_for_csv(True) == "True"
    assert _serialize_value_for_csv(False) == "False"
    assert _serialize_value_for_csv(42) == "42"
    assert _serialize_value_for_csv(3.14) == "3.14"
    assert _serialize_value_for_csv(["a", "b", "c"]) == "a; b; c"
    assert _serialize_value_for_csv([{"nested": 1}]) == '[{"nested": 1}]'
    assert _serialize_value_for_csv({"key": "val"}) == '{"key": "val"}'


@pytest.mark.unit
def test_export_to_json_person_results():
    people = [
        PersonSearchResult(
            name="Alice Smith",
            linkedin_url="https://www.linkedin.com/in/alicesmith/",
            headline="Principal Architect",
            location="San Francisco, CA",
            current_company="TechCorp",
        ),
        PersonSearchResult(
            name="Bob Jones",
            linkedin_url="https://www.linkedin.com/in/bobjones/",
            headline=None,
            location="London, UK",
        ),
    ]

    json_str = export_to_json(people, indent=2)
    parsed = json.loads(json_str)

    assert len(parsed) == 2
    assert parsed[0]["name"] == "Alice Smith"
    assert parsed[0]["headline"] == "Principal Architect"
    assert parsed[1]["name"] == "Bob Jones"
    assert parsed[1]["headline"] is None


@pytest.mark.unit
def test_export_search_page_directly():
    page = SearchPage[PersonSearchResult](
        items=[PersonSearchResult(name="Page Item", linkedin_url="https://linkedin.com/in/pageitem")]
    )
    json_out = export_to_json(page)
    parsed = json.loads(json_out)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "Page Item"


@pytest.mark.unit
def test_export_custom_object_with_dict():
    class CustomObj:
        def __init__(self):
            self.foo = "bar"
            self.count = 10

    obj = CustomObj()
    csv_out = export_to_csv([obj])
    assert "foo" in csv_out
    assert "bar" in csv_out


@pytest.mark.unit
def test_export_to_jsonl():
    companies = [
        CompanySearchResult(
            name="Acme Inc",
            linkedin_url="https://www.linkedin.com/company/acme/",
            industry="Software Development",
            followers_count=10000,
        ),
        CompanySearchResult(
            name="Beta LLC",
            linkedin_url="https://www.linkedin.com/company/beta/",
            industry="Biotechnology",
        ),
    ]

    jsonl_str = export_to_jsonl(companies)
    lines = [line for line in jsonl_str.strip().split("\n") if line]

    assert len(lines) == 2
    item1 = json.loads(lines[0])
    item2 = json.loads(lines[1])
    assert item1["name"] == "Acme Inc"
    assert item1["followers_count"] == 10000
    assert item2["name"] == "Beta LLC"
    assert item2["followers_count"] is None


@pytest.mark.unit
def test_export_to_csv_all_dto_types():
    jobs = [
        JobSearchResult(
            job_title="Senior Python Engineer",
            linkedin_url="https://www.linkedin.com/jobs/view/101/",
            company_name="Innovate Ltd",
            location="Remote",
            posted_date="2 days ago",
            easy_apply=True,
        ),
        JobSearchResult(
            job_title="DevOps Lead",
            linkedin_url="https://www.linkedin.com/jobs/view/102/",
            company_name="Cloud Corp",
            location="New York, NY",
            posted_date=None,
            easy_apply=False,
        ),
    ]

    csv_str = export_to_csv(jobs)
    lines = csv_str.strip().split("\n")

    assert len(lines) == 3  # Header + 2 data rows
    assert "job_title" in lines[0]
    assert "company_name" in lines[0]
    assert "easy_apply" in lines[0]
    assert "Senior Python Engineer" in lines[1]
    assert "True" in lines[1]
    assert "DevOps Lead" in lines[2]
    assert "False" in lines[2]


@pytest.mark.unit
def test_export_to_csv_employees_and_posts():
    employees = [
        EmployeeSearchResult(
            name="Carol Danvers",
            linkedin_url="https://www.linkedin.com/in/carol/",
            designation="VP Engineering",
            company_name="Acme",
        )
    ]
    csv_emp = export_to_csv(employees)
    assert "Carol Danvers" in csv_emp
    assert "VP Engineering" in csv_emp

    posts = [
        PostSearchResult(
            author_name="David Miller",
            linkedin_url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            text_snippet="Excited to announce our new product release!",
            reactions_count=42,
        )
    ]
    csv_post = export_to_csv(posts)
    assert "David Miller" in csv_post
    assert "Excited to announce" in csv_post
    assert "42" in csv_post


@pytest.mark.unit
def test_export_results_to_file(tmp_path):
    people = [
        PersonSearchResult(
            name="Eve Polastri",
            linkedin_url="https://www.linkedin.com/in/evepolastri/",
        )
    ]

    # Test CSV write to file
    csv_path = tmp_path / "subdir" / "people.csv"
    export_results(people, format="csv", destination=csv_path)
    assert csv_path.exists()
    content = csv_path.read_text(encoding="utf-8")
    assert "Eve Polastri" in content

    # Test JSON write to file
    json_path = tmp_path / "people.json"
    export_results(people, format="json", destination=json_path)
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data[0]["name"] == "Eve Polastri"

    # Test JSONL write to file
    jsonl_path = tmp_path / "people.jsonl"
    export_results(people, format="jsonl", destination=jsonl_path)
    assert jsonl_path.exists()
    assert "Eve Polastri" in jsonl_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_export_to_stream():
    stream = StringIO()
    people = [{"name": "Streamed User", "title": "Developer"}]
    export_results(people, format="csv", destination=stream)
    out = stream.getvalue()
    assert "Streamed User" in out
    assert "Developer" in out


@pytest.mark.unit
def test_export_empty_collections(tmp_path):
    assert export_to_json([]) == "[]"
    assert export_to_jsonl([]) == ""
    assert export_to_csv([]) == ""
    assert export_results(None, format="json") == "[]"

    # Destination empty write
    empty_csv = tmp_path / "empty.csv"
    export_to_csv([], destination=empty_csv)
    assert empty_csv.exists()
    assert empty_csv.read_text(encoding="utf-8") == ""


@pytest.mark.unit
def test_export_primitive_list():
    urls = ["https://linkedin.com/jobs/view/1", "https://linkedin.com/jobs/view/2"]
    csv_out = export_to_csv(urls)
    assert "value" in csv_out
    assert "https://linkedin.com/jobs/view/1" in csv_out

    json_out = export_to_json(urls)
    parsed = json.loads(json_out)
    assert parsed[0]["value"] == "https://linkedin.com/jobs/view/1"


@pytest.mark.unit
def test_write_to_destination_invalid():
    with pytest.raises(TypeError, match="Invalid destination type"):
        _write_to_destination("test", 12345)  # type: ignore[arg-type]
