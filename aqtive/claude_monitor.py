"""
Monitor Claude Code sessions to detect active agentic tasks.

Logic:
- Recursively scans ~/.claude/projects/ for *.jsonl files.
- Picks the most recently modified file.
- Reads its last line.
- Session is "Active" if:
    * mtime < 60 s ago  AND
    * last line does NOT contain '"stop_reason":'
- Otherwise "Idle".
"""
import logging
import os
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
ACTIVITY_WINDOW_SECONDS = 60
STOP_REASON_MARKER = '"stop_reason":'


def _find_newest_jsonl(base: Path) -> Optional[Path]:
    """Return the most recently modified .jsonl under base, or None."""
    newest: Optional[Path] = None
    newest_mtime: float = 0.0

    try:
        for root, _dirs, files in os.walk(base):
            for fname in files:
                if not fname.endswith(".jsonl"):
                    continue
                fpath = Path(root) / fname
                try:
                    mtime = fpath.stat().st_mtime
                except OSError:
                    continue
                if mtime > newest_mtime:
                    newest_mtime = mtime
                    newest = fpath
    except OSError as exc:
        logger.warning("Cannot walk %s: %s", base, exc)

    return newest


def _last_line(path: Path) -> str:
    """Return the last non-empty line of a file efficiently."""
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)  # end of file
            size = fh.tell()
            if size == 0:
                return ""
            chunk = min(size, 4096)
            fh.seek(-chunk, 2)
            tail = fh.read().decode("utf-8", errors="replace")
            lines = [l for l in tail.splitlines() if l.strip()]
            return lines[-1] if lines else ""
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return ""


def get_session_status(
    base: Optional[Path] = None,
    now: Optional[float] = None,
) -> Tuple[str, Optional[Path]]:
    """
    Return (status, log_path) where status is 'Active' or 'Idle'.

    Parameters allow injection for testing.
    """
    base = base or CLAUDE_PROJECTS_DIR
    now = now or time.time()

    log_path = _find_newest_jsonl(base)
    if log_path is None:
        logger.debug("No JSONL found under %s", base)
        return "Idle", None

    try:
        mtime = log_path.stat().st_mtime
    except OSError:
        return "Idle", log_path

    age = now - mtime
    if age > ACTIVITY_WINDOW_SECONDS:
        logger.debug("Log is %.0fs old — Idle", age)
        return "Idle", log_path

    last = _last_line(log_path)
    if STOP_REASON_MARKER in last:
        logger.debug("stop_reason found — Idle")
        return "Idle", log_path

    logger.debug("Session Active (age=%.0fs)", age)
    return "Active", log_path
