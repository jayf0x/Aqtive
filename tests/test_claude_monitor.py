"""Tests for Claude session activity detection."""
import time
from pathlib import Path

import pytest

from aqtive.claude_monitor import (
    ACTIVITY_WINDOW_SECONDS,
    STOP_REASON_MARKER,
    _find_newest_jsonl,
    _last_line,
    get_session_status,
)


# ---------------------------------------------------------------------------
# _find_newest_jsonl
# ---------------------------------------------------------------------------

def test_find_newest_returns_most_recent(tmp_path):
    old = tmp_path / "old.jsonl"
    new = tmp_path / "new.jsonl"
    old.write_text('{"a":1}\n')
    new.write_text('{"b":2}\n')
    # touch new to be definitely newer
    new_time = old.stat().st_mtime + 10
    import os
    os.utime(new, (new_time, new_time))

    result = _find_newest_jsonl(tmp_path)
    assert result == new


def test_find_newest_ignores_non_jsonl(tmp_path):
    (tmp_path / "log.txt").write_text("nope\n")
    result = _find_newest_jsonl(tmp_path)
    assert result is None


def test_find_newest_empty_dir(tmp_path):
    result = _find_newest_jsonl(tmp_path)
    assert result is None


def test_find_newest_nested(tmp_path):
    sub = tmp_path / "proj" / "session"
    sub.mkdir(parents=True)
    f = sub / "chat.jsonl"
    f.write_text('{"x":1}\n')
    result = _find_newest_jsonl(tmp_path)
    assert result == f


# ---------------------------------------------------------------------------
# _last_line
# ---------------------------------------------------------------------------

def test_last_line_normal(tmp_path):
    f = tmp_path / "f.jsonl"
    f.write_text('line1\nline2\nline3\n')
    assert _last_line(f) == "line3"


def test_last_line_empty_file(tmp_path):
    f = tmp_path / "empty.jsonl"
    f.write_text("")
    assert _last_line(f) == ""


def test_last_line_single_line(tmp_path):
    f = tmp_path / "f.jsonl"
    f.write_text('{"only":true}')
    assert _last_line(f) == '{"only":true}'


def test_last_line_missing_file(tmp_path):
    result = _last_line(tmp_path / "ghost.jsonl")
    assert result == ""


# ---------------------------------------------------------------------------
# get_session_status
# ---------------------------------------------------------------------------

def _write_jsonl(path: Path, last_line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'{{"a":1}}\n{last_line}\n')


def test_status_active_recent_no_stop(tmp_path):
    f = tmp_path / "sess.jsonl"
    _write_jsonl(f, '{"type":"assistant_message"}')
    now = f.stat().st_mtime + 5  # 5 s after mtime → within window
    status, path = get_session_status(base=tmp_path, now=now)
    assert status == "Active"
    assert path == f


def test_status_idle_stop_reason(tmp_path):
    f = tmp_path / "sess.jsonl"
    _write_jsonl(f, '{"stop_reason":"end_turn","type":"message_delta"}')
    now = f.stat().st_mtime + 5
    status, _ = get_session_status(base=tmp_path, now=now)
    assert status == "Idle"


def test_status_idle_old_file(tmp_path):
    f = tmp_path / "sess.jsonl"
    _write_jsonl(f, '{"type":"assistant_message"}')
    now = f.stat().st_mtime + ACTIVITY_WINDOW_SECONDS + 1
    status, _ = get_session_status(base=tmp_path, now=now)
    assert status == "Idle"


def test_status_idle_no_files(tmp_path):
    status, path = get_session_status(base=tmp_path)
    assert status == "Idle"
    assert path is None


def test_status_picks_newest_file(tmp_path):
    import os

    old_f = tmp_path / "old.jsonl"
    new_f = tmp_path / "new.jsonl"
    _write_jsonl(old_f, '{"stop_reason":"end"}')
    _write_jsonl(new_f, '{"type":"live"}')

    new_mtime = old_f.stat().st_mtime + 20
    os.utime(new_f, (new_mtime, new_mtime))

    now = new_mtime + 5
    status, path = get_session_status(base=tmp_path, now=now)
    assert status == "Active"
    assert path == new_f
