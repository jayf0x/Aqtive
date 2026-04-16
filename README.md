# Aqtive

macOS power state manager — CLI POC.

Prevents sleep during long-running tasks (Claude Code sessions, builds, etc.) with automatic cleanup on exit or crash.

## Structure

```
aqtive/
  __init__.py
  caffeinate.py      # caffeinate subprocess wrapper
  clamshell.py       # pmset lid-close sleep toggle
  claude_monitor.py  # Claude Code session activity detector
  battery.py         # battery threshold guard
  network.py         # en0 connectivity check
  daemon.py          # context-aware polling loop
  cli.py             # argparse entry point
tests/
  test_caffeinate.py
  test_claude_monitor.py
  test_battery.py
  test_network.py
  test_daemon.py
```

## Requirements

- macOS (uses `caffeinate`, `pmset`, `ifconfig`)
- Python 3.11+
- No third-party runtime deps — only `pytest` for tests

## Setup

```bash
pip install pytest pytest-cov
```

### One-time sudoers config (for clamshell / pmset)

```bash
sudo visudo -f /etc/sudoers.d/aqtive
```

Add (replace `youruser`):

```
youruser ALL=(ALL) NOPASSWD: /usr/bin/pmset -a sleep 0
youruser ALL=(ALL) NOPASSWD: /usr/bin/pmset -a sleep 1
```

## Usage

```bash
# Manual caffeination for 30 minutes
python -m aqtive.cli caff --seconds 1800

# Stop caffeination
python -m aqtive.cli caff --stop

# Prevent sleep on lid close (requires sudoers config)
python -m aqtive.cli clamshell --enable
python -m aqtive.cli clamshell --disable

# Print current status
python -m aqtive.cli status

# Context-aware daemon (polls every 10s)
python -m aqtive.cli daemon

# Daemon with network guard and custom poll interval
python -m aqtive.cli daemon --interval 5 --network-guard --battery-threshold 20
```

## Tests

```bash
pytest tests/ -v --cov=aqtive --cov-report=term-missing
```

## How it works

### Claude session detection

Scans `~/.claude/projects/**/*.jsonl` for the most recently modified file.
- **Active** — file modified < 60 s ago AND last line lacks `"stop_reason":`
- **Idle** — file is stale OR last line contains `"stop_reason":`

### Cleanup / self-healing

Every component registers `atexit` handlers and catches `SIGTERM`/`SIGINT`.
`caffeinate` is always terminated before process exit, and `pmset` sleep is restored
if clamshell mode was enabled.

### Battery guard

If the Mac is on battery and charge drops to ≤ 15 %, all sleep-prevention overrides
are disabled automatically.

### Network guard (optional)

Pass `--network-guard` to the daemon to stop caffeination when `en0` loses its
IPv4 address (useful to avoid draining battery while travelling).

## Backlog

See [backlog.md](backlog.md) for planned features (SwiftBar integration, launchd,
persistent state, sudoers setup script, etc.).
