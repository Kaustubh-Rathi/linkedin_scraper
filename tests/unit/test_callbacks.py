"""Tests for linkedin_scraper.callbacks."""
import json
from unittest.mock import AsyncMock

import pytest

from linkedin_scraper.callbacks import (
    ConsoleCallback,
    JSONLogCallback,
    MultiCallback,
    ProgressCallback,
    SilentCallback,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_silent_callback_all_methods_are_no_ops(capsys):
    callback = SilentCallback()

    await callback.on_start("person", "https://example.com")
    await callback.on_progress("halfway", 50)
    await callback.on_complete("person", {"ok": True})
    await callback.on_error(ValueError("boom"))

    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_progress_callback_base_methods_are_no_ops():
    callback = ProgressCallback()
    # Should not raise, even though the base class does nothing.
    await callback.on_start("job", "url")
    await callback.on_progress("msg", 10)
    await callback.on_complete("job", None)
    await callback.on_error(RuntimeError("x"))


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_callback_prints_start_message(capsys):
    callback = ConsoleCallback()
    await callback.on_start("person", "https://linkedin.com/in/example")

    captured = capsys.readouterr()
    assert "person" in captured.out
    assert "https://linkedin.com/in/example" in captured.out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_callback_verbose_prints_every_progress(capsys):
    callback = ConsoleCallback(verbose=True)
    await callback.on_progress("step one", 5)

    captured = capsys.readouterr()
    assert "step one" in captured.out
    assert "5%" in captured.out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_callback_non_verbose_only_prints_multiples_of_twenty(capsys):
    callback = ConsoleCallback(verbose=False)

    await callback.on_progress("not a multiple", 7)
    captured = capsys.readouterr()
    assert captured.out == ""

    await callback.on_progress("is a multiple", 20)
    captured = capsys.readouterr()
    assert "is a multiple" in captured.out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_callback_prints_completion(capsys):
    callback = ConsoleCallback()
    await callback.on_complete("company", object())

    captured = capsys.readouterr()
    assert "company" in captured.out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_console_callback_prints_error(capsys):
    callback = ConsoleCallback()
    await callback.on_error(ValueError("something broke"))

    captured = capsys.readouterr()
    assert "something broke" in captured.out


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_log_callback_writes_start_event(tmp_path):
    log_file = tmp_path / "log.jsonl"
    callback = JSONLogCallback(str(log_file))

    await callback.on_start("person", "https://example.com")

    assert log_file.exists()
    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event_type"] == "start"
    assert entry["scraper_type"] == "person"
    assert entry["url"] == "https://example.com"
    assert "timestamp" in entry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_log_callback_writes_all_event_types(tmp_path):
    log_file = tmp_path / "log.jsonl"
    callback = JSONLogCallback(str(log_file))

    await callback.on_start("job", "url")
    await callback.on_progress("halfway", 50)
    await callback.on_complete("job", {"done": True})
    await callback.on_error(ValueError("oops"))

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 4
    event_types = [json.loads(line)["event_type"] for line in lines]
    assert event_types == ["start", "progress", "complete", "error"]

    error_entry = json.loads(lines[3])
    assert error_entry["error"] == "oops"
    assert error_entry["error_type"] == "ValueError"

    assert callback.logs[1]["message"] == "halfway"
    assert callback.logs[1]["percent"] == 50


@pytest.mark.unit
@pytest.mark.asyncio
async def test_json_log_callback_appends_across_multiple_instances(tmp_path):
    log_file = tmp_path / "log.jsonl"
    await JSONLogCallback(str(log_file)).on_start("a", "url-a")
    await JSONLogCallback(str(log_file)).on_start("b", "url-b")

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_callback_fans_out_to_all_children():
    child1 = AsyncMock(spec=ProgressCallback)
    child2 = AsyncMock(spec=ProgressCallback)
    multi = MultiCallback(child1, child2)

    await multi.on_start("person", "url")
    await multi.on_progress("msg", 42)
    await multi.on_complete("person", {"ok": True})
    error = RuntimeError("bad")
    await multi.on_error(error)

    child1.on_start.assert_awaited_once_with("person", "url")
    child2.on_start.assert_awaited_once_with("person", "url")
    child1.on_progress.assert_awaited_once_with("msg", 42)
    child2.on_progress.assert_awaited_once_with("msg", 42)
    child1.on_complete.assert_awaited_once_with("person", {"ok": True})
    child2.on_complete.assert_awaited_once_with("person", {"ok": True})
    child1.on_error.assert_awaited_once_with(error)
    child2.on_error.assert_awaited_once_with(error)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_callback_with_no_children_does_not_raise():
    multi = MultiCallback()
    await multi.on_start("person", "url")
    await multi.on_progress("msg", 1)
    await multi.on_complete("person", None)
    await multi.on_error(ValueError("x"))
