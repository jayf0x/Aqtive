### SwiftBar Integration
- [ ] Plugin script that renders menu bar UI via SwiftBar
- [ ] Slider / increment buttons for caffeination timeout in menu bar
- [ ] Live status icons (awake / idle / battery warning)
- [ ] SwiftBar refresh triggers on state change

### Sudoers / Privilege Management
- [ ] One-time `visudo` setup script for passwordless `pmset`
- [ ] Runtime check that sudoers entry exists; warn user if missing
- [ ] Fallback to AppleScript sudo prompt when sudoers not configured

### Persistent State
- [ ] PID file written to `/tmp/aqtive.pid` for self-healing on hard restart
- [ ] launchd plist for auto-start on login
- [ ] State file (`~/.aqtive/state.json`) to survive crashes

### Context-Aware Triggers (extended)
- [ ] Active terminal session detection (check foreground process groups)
- [ ] File-system write monitor mode (FSEvents / watchdog)
- [ ] Configurable trigger list via `~/.aqtive/triggers.yaml`

### UX / CLI Polish
- [ ] `aqtive status` subcommand (rich table of active overrides)
- [ ] `aqtive logs` subcommand (tail the activity log)
- [ ] Color output / rich formatting
- [ ] Config file support (`~/.aqtive/config.toml`)

### Packaging
- [ ] `pyproject.toml` / pip-installable entry point
- [ ] Homebrew formula
- [ ] GitHub Actions CI (lint + test on macOS runner)

### Releases
- [ ] add setup for Github release
- [ ] add github actions that writes tests to a `./tests.log` (overwriting the previous), to show full transparency.

---

## Testing

### BUG: `STOP_REASON_MARKER` constant is imported but never used in assertions

**File:** `tests/test_claude_monitor.py`, line 9

**Problem:** `STOP_REASON_MARKER` is imported from `aqtive.claude_monitor` but no test body references it. `test_status_idle_stop_reason` hardcodes the raw string `'"stop_reason":"end_turn"'` in the test data instead of constructing it from the constant. This means if the constant's value ever changes in `claude_monitor.py`, this test will keep passing — giving false confidence.

**Also missing:** there is no boundary test that verifies a near-miss string (e.g. `stop_reason` without the leading quote, or `"stop_reason":` inside a key name) does *not* trigger Idle. This matters because the detection is a plain `in` substring check.

**Fix (two parts):**
1. In `test_status_idle_stop_reason`, build the last-line string using the constant:
   ```python
   last_line = f'{{{STOP_REASON_MARKER}"end_turn"}}'  # guarantees coupling
   ```
2. Add `test_status_active_near_miss_stop_reason`: write a last line that contains the word `stop_reason` but not the exact marker (e.g. `{"my_stop_reason":"x"}`) and assert status is `Active`.

---

### FEATURE: Refactor unit tests to support injectable data (prerequisite for live tests)

**Why this matters:** The current tests hardcode both input data and expected output inside each test function. To support live variants we need to separate *test logic* from *data source* without duplicating the assertion code.

**Approach — use pytest parametrize + a `--live` CLI flag:**

1. Add `conftest.py` at the repo root with:
   - A `--live` flag: `pytest --live` opts into live tests; without it they are skipped.
   - A `live_only` marker that skips unless `--live` is passed.
   - A `local_test_logger` fixture that appends structured lines to `local-tests.log` (overwritten at the start of each `--live` run). Format per line: `[ISO-8601 timestamp] [PASS|FAIL] <test_name> — <detail>`.

2. For each existing test function, extract the assertion logic into a plain helper:
   ```python
   # shared helper — not a test itself
   def assert_battery_percent(raw_output: str, expected: int) -> None:
       assert battery_percent(raw_output) == expected
   ```
   The existing `@pytest.mark.parametrize` unit tests call this helper with static fixture data. Live tests call the same helper with real data. No assertion code is duplicated.

3. Keep all existing unit tests passing and unchanged in behaviour. Only internal structure changes (extract helper, call helper from parametrize).

**What to parametrize per module:**
- `battery.py`: `is_on_battery(output)`, `battery_percent(output)`, `should_disable_overrides(threshold, output)` — each takes `output: str` as the first arg.
- `network.py`: `is_connected(output)` — takes `output: str`.
- `claude_monitor.py`: `get_session_status(base, now)` — takes `base: Path` (tmp_path or real dir) and `now: float`.
- `caffeinate.py` / `daemon.py`: already mock-based; live variants replace mocks with real subprocesses (see below).

---

### FEATURE: Live test suite — `tests/live/`

All live tests live in `tests/live/`. Run with `pytest tests/live/ --live -s`. They are skipped entirely in CI (no `--live` flag). All output is appended to `local-tests.log` (file is truncated at the start of each live run via the `local_test_logger` fixture in `conftest.py`).

Each live test:
- Prints a human-readable prompt to stdout when it needs user action.
- Polls with a configurable timeout (default 120 s, overridable via env var `AQTIVE_LIVE_TIMEOUT`).
- Calls the shared helper functions from the corresponding unit test file so assertion logic is never duplicated.
- Logs `PASS` / `FAIL` + detail to `local-tests.log` regardless of outcome.

---

#### Live test: Battery (`tests/live/test_battery_live.py`)

**Goal:** confirm that `battery_percent`, `is_on_battery`, and `should_disable_overrides` return correct values against actual `pmset -g batt` output on this machine.

**Steps:**
1. Call `pmset -g batt` and capture raw output once — store as `live_output`.
2. Call `battery_percent(live_output)` → store as `current_pct`. Assert it is an integer between 0–100.
3. Call `is_on_battery(live_output)` → assert it matches whether the machine is actually plugged in (prompt user to confirm: `"Is the charger currently connected? [y/n]"`).
4. Test `should_disable_overrides`:
   - If on battery and `current_pct > 5`: set `threshold = current_pct - 1` → assert returns `False` (we are above threshold). Set `threshold = current_pct` → assert returns `True` (at or below). No waiting required.
   - If on AC: assert `should_disable_overrides(threshold=100)` returns `False`.

Note: do NOT wait for the battery to drain — use the threshold-injection trick above. Actual drain waiting is impractical.

---

#### Live test: Claude Activity (`tests/live/test_claude_monitor_live.py`)

**Goal:** confirm that `get_session_status` correctly transitions from `Active` → `Idle` using a real Claude Code JSONL log.

**Steps:**
1. Record `test_start = time.time()`.
2. Find the newest `.jsonl` under `~/.claude/projects/` at test start. Store path + mtime as baseline.
3. Print: `">>> Open Claude Code and send any message (type anything). Press Enter when done."` Wait for Enter.
4. Poll `get_session_status()` in a loop (0.5 s delay, timeout 120 s) until status is `Active`. Assert it transitions; fail with timeout message if it doesn't.
5. Log `PASS — Active detected, log: <path>`.
6. Print: `">>> Wait for Claude to finish its response, then press Enter."` Wait for Enter.
7. Poll until status is `Idle`. Assert it transitions within timeout.
8. Read the final last-line of the log file and assert `STOP_REASON_MARKER in last_line`. This is the key assertion — it validates the exact constant, not a hardcoded string.
9. Log `PASS — Idle + stop_reason detected`.

---

#### Live test: Network (`tests/live/test_network_live.py`)

**Goal:** confirm `is_connected()` correctly reflects real en0 state when the interface goes down and comes back up.

**Context:** On macOS, Wi-Fi can be toggled without sudo via `networksetup -setairportpower en0 off/on`. Ethernet requires `ifconfig en0 down/up` which needs sudo. The test detects which is applicable.

**Steps:**
1. Call `is_connected()` → assert `True` (test requires network at start; skip with clear message if not).
2. Detect interface type: if `en0` is Wi-Fi (`networksetup -listallhardwareports` contains "Wi-Fi" mapped to en0) use `networksetup -setairportpower en0 off`. Otherwise print instructions to manually disconnect and press Enter.
3. For Wi-Fi path (automated):
   a. Run `networksetup -setairportpower en0 off`.
   b. Poll `is_connected()` in a loop (1 s delay, timeout 15 s) until it returns `False`. Assert within timeout.
   c. Log `PASS — disconnected correctly detected`.
   d. Run `networksetup -setairportpower en0 on`.
   e. Poll until `is_connected()` returns `True` again (timeout 30 s). Assert within timeout.
   f. Log `PASS — reconnection correctly detected`.
4. For manual path: prompt user to disconnect Wi-Fi, wait for Enter, assert `is_connected()` is `False`. Then prompt to reconnect, wait for Enter, assert `True`.

---

#### Live test: Daemon (`tests/live/test_daemon_live.py`)

**Goal:** confirm the daemon correctly engages/disengages `caffeinate` in response to real Claude session state, and cleans up on SIGTERM.

**Steps:**
1. Spawn `AqtiveDaemon(poll_interval=3)` as a real daemon in a background thread (not subprocess — we want to inspect its internal state). Use `threading.Thread(target=daemon.run, daemon=True)`.
2. Assert `daemon._caff.is_running` is `False` initially (no Claude activity yet).
3. Simulate an active Claude session by writing a fresh `.jsonl` file to a temp directory that the daemon is pointed at (pass `base=tmp_path` via monkeypatching `claude_monitor.CLAUDE_PROJECTS_DIR`). The last line must NOT contain `STOP_REASON_MARKER`.
4. Poll `daemon._caff.is_running` (1 s delay, timeout 15 s) until `True`. Assert it starts caffeinate.
5. Log `PASS — caffeinate engaged on Active`.
6. Append `STOP_REASON_MARKER + '"end_turn"'` as a new last line to the same file.
7. Poll until `daemon._caff.is_running` is `False`. Assert it stops caffeinate.
8. Log `PASS — caffeinate disengaged on Idle`.
9. **Cleanup test:** call `daemon._cleanup()` directly and assert `daemon._caff.is_running` is `False` and `daemon._running` is `False`. This validates the self-healing path.
10. Log overall `PASS — daemon lifecycle complete`.

Note: no real `caffeinate` binary needs to run for this test — but it will if the test machine is macOS. Add a check: if `shutil.which("caffeinate") is None`, skip the is_running assertions and log a warning.
