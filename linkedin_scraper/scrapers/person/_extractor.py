"""Shared base for composed person-section extractors."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..base import BaseScraper


class SectionExtractor:
    """Delegates page/navigation helpers to the owning :class:`BaseScraper`."""

    def __init__(self, host: "BaseScraper") -> None:
        self._host = host

    def __getattr__(self, name: str):
        return getattr(self._host, name)
