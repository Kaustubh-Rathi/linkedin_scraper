# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Person scraper uses composed section extractors instead of mixin MRO.
- Protocols/registry wording clarified as in-process plugin contracts (not microservices).
- Trimmed unused runtime dependencies (`requests`, `lxml`, `aiofiles`).
- `BaseScraper` reduced to helpers actually used by scrapers.
- Company posts scraper uses the JS extraction path only (removed dead DOM parsers).
- Packaging: `py.typed`, branch coverage, ruff/mypy, GitHub Actions unit CI.

### Fixed
- README/model documentation drift (Person/Company/Job field sketches).
- Registry encapsulation (`is_registered` / `has` instead of reading private factories).

## [3.1.2] - 2025-01-01

### Added
- Async Playwright scrapers for person, company, jobs, and company posts.
- CLI entry point (`linkedin-scraper`).
- Pydantic models, progress callbacks, rate-limit detection, and scraper registry.
