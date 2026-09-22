"""Export pipeline for search results and domain models into CSV, JSON, and JSONL formats."""

from __future__ import annotations

import csv
import io
import json
from enum import Enum
from pathlib import Path
from typing import Any, Sequence, TextIO

from pydantic import BaseModel


class ExportFormat(str, Enum):
    """Supported export formats for search results."""

    JSON = "json"
    CSV = "csv"
    JSONL = "jsonl"

    @classmethod
    def from_str(cls, value: str | ExportFormat) -> ExportFormat:
        """Parse string or ExportFormat instance into validated ExportFormat enum."""
        if isinstance(value, ExportFormat):
            return value
        cleaned = str(value).strip().lower().lstrip(".")
        if cleaned == "ndjson":
            return cls.JSONL
        for member in cls:
            if member.value == cleaned:
                return member
        raise ValueError(
            f"Unsupported export format: {value!r}. Supported formats: {[m.value for m in cls]}"
        )


def infer_export_format(
    filepath: str | Path, default: ExportFormat = ExportFormat.JSON
) -> ExportFormat:
    """Infer the export format from a file path extension, falling back to default."""
    path = Path(filepath)
    ext = path.suffix.lower().lstrip(".")
    try:
        return ExportFormat.from_str(ext)
    except ValueError:
        return default


def _serialize_value_for_csv(value: Any) -> str:
    """Serialize a single Python value to a clean string suitable for CSV cells."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        # If list of primitive strings, join with semicolon for clean CSV readability
        if all(isinstance(x, (str, int, float, bool)) for x in value):
            return "; ".join(str(x) for x in value)
        return json.dumps(value, default=str, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, default=str, ensure_ascii=False)
    return str(value)


def _normalize_items_to_dicts(data: Any) -> list[dict[str, Any]]:
    """Convert search result items, SearchPage, Pydantic models, or dicts to a list of dictionaries."""
    if data is None:
        return []

    # Handle SearchPage instance
    if hasattr(data, "items") and isinstance(data.items, (list, tuple)):
        items_seq: Sequence[Any] = data.items
    elif isinstance(data, (list, tuple, set)):
        items_seq = list(data)
    else:
        items_seq = [data]

    results: list[dict[str, Any]] = []
    for item in items_seq:
        if isinstance(item, BaseModel):
            results.append(item.model_dump(mode="python"))
        elif isinstance(item, dict):
            results.append(dict(item))
        elif hasattr(item, "__dict__"):
            results.append(dict(item.__dict__))
        else:
            # Primitive value (e.g. str URL)
            results.append({"value": str(item)})
    return results


def export_to_json(
    items: Any,
    destination: str | Path | TextIO | None = None,
    indent: int = 2,
) -> str:
    """
    Export results as formatted JSON string, optionally writing to destination file/stream.
    """
    normalized = _normalize_items_to_dicts(items)
    content = json.dumps(normalized, indent=indent, default=str, ensure_ascii=False)

    if destination is not None:
        _write_to_destination(content, destination)
    return content


def export_to_jsonl(
    items: Any,
    destination: str | Path | TextIO | None = None,
) -> str:
    """
    Export results as JSON Lines (newline-delimited JSON), optionally writing to destination file/stream.
    """
    normalized = _normalize_items_to_dicts(items)
    lines = [
        json.dumps(item, default=str, ensure_ascii=False) for item in normalized
    ]
    content = "\n".join(lines)
    if content:
        content += "\n"

    if destination is not None:
        _write_to_destination(content, destination)
    return content


def export_to_csv(
    items: Any,
    destination: str | Path | TextIO | None = None,
) -> str:
    """
    Export results as CSV with headers, optionally writing to destination file/stream.
    """
    normalized = _normalize_items_to_dicts(items)
    if not normalized:
        content = ""
        if destination is not None:
            _write_to_destination(content, destination)
        return content

    # Collect all unique fieldnames in order of appearance across all dictionaries
    fieldnames: list[str] = []
    for item_dict in normalized:
        for key in item_dict.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    output_stream = io.StringIO()
    writer = csv.DictWriter(
        output_stream,
        fieldnames=fieldnames,
        extrasaction="ignore",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writeheader()

    for item_dict in normalized:
        row = {
            k: _serialize_value_for_csv(item_dict.get(k)) for k in fieldnames
        }
        writer.writerow(row)

    content = output_stream.getvalue()
    if destination is not None:
        _write_to_destination(content, destination)
    return content


def export_results(
    items: Any,
    format: str | ExportFormat = ExportFormat.JSON,
    destination: str | Path | TextIO | None = None,
    **kwargs: Any,
) -> str:
    """
    Unified export function dispatching to CSV, JSON, or JSONL exporters.

    :param items: SearchPage, list of Pydantic models, or list of dicts.
    :param format: ExportFormat enum or string ("json", "csv", "jsonl").
    :param destination: Optional file path (str/Path) or TextIO stream to write output to.
    :return: The serialized string content.
    """
    fmt = ExportFormat.from_str(format)
    if fmt == ExportFormat.CSV:
        return export_to_csv(items, destination=destination)
    elif fmt == ExportFormat.JSONL:
        return export_to_jsonl(items, destination=destination)
    elif fmt == ExportFormat.JSON:
        indent = kwargs.get("indent", 2)
        return export_to_json(items, destination=destination, indent=indent)
    else:
        raise ValueError(f"Unhandled export format: {fmt}")


def _write_to_destination(
    content: str, destination: str | Path | TextIO
) -> None:
    """Write string content to file path or TextIO stream with UTF-8 encoding."""
    if isinstance(destination, (str, Path)):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    elif hasattr(destination, "write"):
        destination.write(content)
    else:
        raise TypeError(f"Invalid destination type: {type(destination)}")


class SearchExporter:
    """Class wrapper for search export functions."""

    @staticmethod
    def export(
        items: Any,
        format: str | ExportFormat = ExportFormat.JSON,
        **kwargs: Any,
    ) -> str:
        return export_results(items, format=format, **kwargs)

    @staticmethod
    def export_to_file(
        items: Any,
        destination: str | Path | TextIO,
        format: str | ExportFormat = ExportFormat.JSON,
        **kwargs: Any,
    ) -> str:
        return export_results(items, format=format, destination=destination, **kwargs)
