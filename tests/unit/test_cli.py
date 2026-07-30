"""Unit tests for CLI argument parsing (no LinkedIn / browser)."""
import pytest

from linkedin_scraper.cli.main import build_parser, main


@pytest.mark.unit
def test_build_parser_person_defaults():
    args = build_parser().parse_args(
        ["person", "https://www.linkedin.com/in/example/"]
    )
    assert args.command == "person"
    assert args.url == "https://www.linkedin.com/in/example/"
    assert args.session == "linkedin_session.json"
    assert args.headed is False
    assert args.output is None


@pytest.mark.unit
def test_build_parser_person_flags():
    args = build_parser().parse_args(
        [
            "--session",
            "custom.json",
            "person",
            "https://www.linkedin.com/in/example/",
            "--headed",
            "-o",
            "out.json",
        ]
    )
    assert args.session == "custom.json"
    assert args.headed is True
    assert args.output == "out.json"


@pytest.mark.unit
def test_build_parser_company():
    args = build_parser().parse_args(
        ["company", "https://www.linkedin.com/company/acme/"]
    )
    assert args.command == "company"
    assert "company/acme" in args.url


@pytest.mark.unit
def test_build_parser_jobs():
    args = build_parser().parse_args(
        [
            "jobs",
            "--keywords",
            "engineer",
            "--location",
            "Remote",
            "--limit",
            "3",
            "--details",
        ]
    )
    assert args.command == "jobs"
    assert args.keywords == "engineer"
    assert args.location == "Remote"
    assert args.limit == 3
    assert args.details is True


@pytest.mark.unit
def test_build_parser_posts():
    args = build_parser().parse_args(
        ["posts", "https://www.linkedin.com/company/acme/", "--limit", "5"]
    )
    assert args.command == "posts"
    assert args.limit == 5


@pytest.mark.unit
def test_build_parser_login():
    args = build_parser().parse_args(["login", "--timeout-minutes", "10"])
    assert args.command == "login"
    assert args.timeout_minutes == 10


@pytest.mark.unit
def test_main_requires_subcommand(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2
