"""Argparse entrypoint for the linkedin-scraper CLI."""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Optional

from . import commands


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linkedin-scraper",
        description="Scrape LinkedIn profiles, companies, jobs, and posts.",
    )
    parser.add_argument(
        "--session",
        default="linkedin_session.json",
        help="Path to session storage file (default: linkedin_session.json)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    login = sub.add_parser("login", help="Create a session via manual browser login")
    login.add_argument(
        "--timeout-minutes",
        type=int,
        default=5,
        help="Minutes to wait for manual login (default: 5)",
    )

    person = sub.add_parser("person", help="Scrape a person profile")
    person.add_argument("url", help="LinkedIn profile URL")
    person.add_argument("--headed", action="store_true", help="Show the browser")
    person.add_argument("--output", "-o", help="Write JSON to this file")

    company = sub.add_parser("company", help="Scrape a company page")
    company.add_argument("url", help="LinkedIn company URL")
    company.add_argument("--headed", action="store_true", help="Show the browser")
    company.add_argument("--output", "-o", help="Write JSON to this file")

    jobs = sub.add_parser("jobs", help="Search jobs (optionally scrape details)")
    jobs.add_argument("--keywords", help="Job search keywords")
    jobs.add_argument("--location", help="Job location")
    jobs.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    jobs.add_argument(
        "--details",
        action="store_true",
        help="Scrape full job postings instead of returning URLs only",
    )
    jobs.add_argument("--headed", action="store_true", help="Show the browser")
    jobs.add_argument("--output", "-o", help="Write JSON to this file")

    posts = sub.add_parser("posts", help="Scrape company posts")
    posts.add_argument("url", help="LinkedIn company URL")
    posts.add_argument("--limit", type=int, default=10, help="Max posts (default: 10)")
    posts.add_argument("--headed", action="store_true", help="Show the browser")
    posts.add_argument("--output", "-o", help="Write JSON to this file")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    session = args.session

    try:
        if args.command == "login":
            return asyncio.run(
                commands.cmd_login(
                    session=session,
                    timeout_ms=args.timeout_minutes * 60 * 1000,
                )
            )
        if args.command == "person":
            return asyncio.run(
                commands.cmd_person(
                    url=args.url,
                    session=session,
                    headed=args.headed,
                    output=args.output,
                )
            )
        if args.command == "company":
            return asyncio.run(
                commands.cmd_company(
                    url=args.url,
                    session=session,
                    headed=args.headed,
                    output=args.output,
                )
            )
        if args.command == "jobs":
            return asyncio.run(
                commands.cmd_jobs(
                    keywords=args.keywords,
                    location=args.location,
                    limit=args.limit,
                    session=session,
                    headed=args.headed,
                    output=args.output,
                    scrape_details=args.details,
                )
            )
        if args.command == "posts":
            return asyncio.run(
                commands.cmd_posts(
                    url=args.url,
                    limit=args.limit,
                    session=session,
                    headed=args.headed,
                    output=args.output,
                )
            )
    except FileNotFoundError as exc:
        print("Session file not found: {}".format(exc), file=sys.stderr)
        print("Run: linkedin-scraper login", file=sys.stderr)
        return 1
    except Exception as exc:
        print("Error: {}".format(exc), file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    sys.exit(main())
