"""Shared Pydantic helpers for scraper DTOs."""

from typing import Any, Dict

from pydantic import BaseModel


class BaseScraperModel(BaseModel):
    """Base model with convenience serialization helpers."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary via ``model_dump``."""
        return self.model_dump()

    def to_json(self, **kwargs: Any) -> str:
        """Convert to JSON string via ``model_dump_json``."""
        return self.model_dump_json(**kwargs)
