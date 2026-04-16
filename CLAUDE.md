# Aqtive — project guide for Claude

## What this is
macOS CLI utility that prevents system sleep during long-running tasks (Claude Code sessions, builds, etc.). Wraps `caffeinate` and `pmset`. Python only, no GUI — SwiftBar integration is a future backlog item.

## Platform constraint
**macOS only.** `caffeinate`, `pmset`, `ifconfig`, `networksetup` are all macOS binaries. Tests that call these binaries real are in `tests/live/` (not yet created). Unit tests mock all subprocess calls.

## Project structure
```
aqtive/
  caffeinate.py      — caffeinate subprocess wrapper + atexit/SIGTERM cleanup
  clamshell.py       — pmset lid-close sleep toggle + atexit restore
  claude_monitor.py  — JSONL polling, Active/Idle detection
  battery.py         — battery threshold guard (pmset -g batt)
  network.py         — en0 connectivity check (ifconfig)
  daemon.py          — poll loop orchestrating all of the above
  cli.py             — argparse entry point
tests/
  test_battery.py
  test_caffeinate.py
  test_claude_monitor.py
  test_daemon.py
  test_network.py
```

`test.py` at the repo root is a throwaway scratch file — ignore it, do not import or test it.

## Running tests
```bash
python3 -m pytest tests/ -v          # all unit tests (39, all pass)
python3 -m pytest tests/ -q --tb=short  # quick check
```

No third-party runtime dependencies. Only `pytest` and `pytest-cov` are needed (see `requirements.txt`).

## Key architectural decisions
- **Injectable data everywhere.** `battery.py`, `network.py`, and `claude_monitor.py` functions all accept an optional `output: str` argument. Pass a string to test without hitting real binaries; omit to call the real binary. Same pattern must be followed in any new modules.
- **`get_session_status(base, now)` uses injected parameters** for both the directory and current timestamp, making time-dependent logic fully testable.
- **Signal handlers must be registered in the main thread.** `AqtiveDaemon.__init__` and `Caffeinator.__init__` both call `signal.signal()`. Always construct these objects in the main thread. Pass `.run()` to a background thread if needed — never construct inside the thread.
- **`atexit` + SIGTERM/SIGINT everywhere.** Every component that modifies system state registers a cleanup. This is non-negotiable for `pmset` (must restore sleep settings) and `caffeinate` (must terminate subprocess).

## What's already built (POC complete)
All modules above are implemented and tested. `aqtive caff`, `aqtive clamshell`, `aqtive status`, and `aqtive daemon` all work from the CLI.

## Current focus — Testing (see backlog.md)
The next coding session should work through the Testing section of `backlog.md` **in order** — the items have a hard dependency chain:

1. **Fix the BUG first** (`STOP_REASON_MARKER` unused in assertions) — small, self-contained.
2. **Refactor unit tests** to extract shared assertion helpers — prerequisite for live tests.
3. **Build `conftest.py`** with `--live` flag, session-scoped logger, marker registration.
4. **Build `tests/live/`** — four live test files, each described in detail in the backlog.

Do not start live tests before the refactor is done. The live tests import helpers from the unit test files.

## Sudo note
`clamshell.py` requires passwordless sudo for `pmset`. See README for one-time visudo setup. Unit tests do not exercise this path. Live tests for clamshell are not yet scoped.
