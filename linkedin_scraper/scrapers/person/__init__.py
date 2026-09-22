"""Person/Profile scraper package for LinkedIn.

`scraper.py` composes per-section extractors (`profile`, `experience`,
`education`, `interests`, `accomplishments`, `contacts`) with shared helpers
in `parser.py` and `links.py`.
"""

from .scraper import PersonScraper

__all__ = ["PersonScraper"]
