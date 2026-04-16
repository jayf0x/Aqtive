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

> **Implementation order is strict — each item depends on the previous:**
> 1. Fix the BUG below (5 min, self-contained)
> 2. Refactor unit tests (shared helpers)
> 3. Add `conftest.py`
> 4. Build `tests/live/` (four files, any order once 1–3 are done)

### BUG: `STOP_REASON_MARKER` constant is imported but never used in assertions

**File:** `tests/test_claude_monitor.py`, line 9

**Problem:** `STOP_REASON_MARKER` is imported from `aqtive.claude_monitor` but no test body ever references it. `test_status_idle_stop_reason` hardcodes the raw string `'"stop_reason":"end_turn"'` in the fixture data instead of deriving it from the constant. If `STOP_REASON_MARKER`'s value changes in `claude_monitor.py`, this test keeps passing — false confidence.

**Fix — two parts, both required:**

1. In `test_status_idle_stop_reason`, construct the last-line using the constant so the test is coupled to its value:
   ```python
   last_line = STOP_REASON_MARKER + '"end_turn"'   # → "stop_reason":"end_turn"
   _write_jsonl(f, last_line)
   ```

2. Add a boundary test `test_status_active_near_miss_stop_reason`: write a last line that contains the substring `stop_reason` but NOT the exact marker (`"stop_reason":` with the leading quote). Example last line: `{"my_stop_reason":"x"}`. Assert status is `Active`. This matters because the detection is a plain `in` substring check — a too-loose marker would produce false Idle detections.

---

### FEATURE: Refactor unit tests to support injectable data (prerequisite for live tests)

**Why:** The current tests hardcode both input data and expected output inside each function body. To share assertion logic between unit tests and live tests without duplication, the logic must be extracted into helpers that accept data as arguments.

**What to build:**

#### 1. `conftest.py` at the repo root

```python
# conftest.py
import pytest

def pytest_addoption(parser):
    parser.addoption("--live", action="store_true", default=False,
                     help="Run live tests that require real hardware/network")

def pytest_configure(config):
    config.addinivalue_line("markers", "live: marks tests as live (skipped without --live)")

@pytest.fixture(scope="session")
def live_mode(request):
    return request.config.getoption("--live")

@pytest.fixture(autouse=True)
def skip_live_unless_flag(request, live_mode):
    if request.node.get_closest_marker("live") and not live_mode:
        pytest.skip("Pass --live to run this test")

@pytest.fixture(scope="session")
def local_test_logger(tmp_path_factory, live_mode):
    """Session-scoped fixture. Truncates local-tests.log once at start of live run."""
    log_path = "local-tests.log"
    if live_mode:
        open(log_path, "w").close()  # truncate
    import datetime, functools

    def log(status: str, test_name: str, detail: str = ""):
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        line = f"[{ts}] [{status}] {test_name} — {detail}\n"
        with open(log_path, "a") as f:
            f.write(line)

    return log
```

Note: the `skip_live_unless_flag` fixture is `autouse=True` — it applies to every test automatically, checking for the `live` marker. No test needs to explicitly call it.

#### 2. Extract shared assertion helpers per module

For each unit test file, pull the assertion logic out of the test functions into standalone helper functions (not test functions — no `test_` prefix). The existing test functions then call the helper with their static fixture data. Live tests call the same helper with real data.

**Example for battery:**
```python
# tests/test_battery.py  (refactored)
def assert_is_on_battery(output: str, expected: bool) -> None:
    assert is_on_battery(output) is expected

def assert_battery_percent(output: str, expected: int) -> None:
    assert battery_percent(output) == expected

def assert_should_disable(output: str, threshold: int, expected: bool) -> None:
    assert should_disable_overrides(threshold=threshold, output=output) is expected

# Existing test functions become thin wrappers:
def test_on_battery_true():
    assert_is_on_battery(BATTERY_50, True)
```

**Do the same for:**
- `test_network.py` → `assert_is_connected(output: str, expected: bool)`
- `test_claude_monitor.py` → keep `_write_jsonl` as-is (already a helper); extract `assert_session_status(base, now, expected_status)`.

**Constraint:** All 39 existing tests must continue to pass after the refactor. Run `pytest tests/ -q` before and after to confirm.

---

### FEATURE: Live test suite — `tests/live/`

**How to run:** `pytest tests/live/ --live -s`
The `-s` flag is required so interactive `input()` prompts reach the terminal.

**Skip in CI:** Live tests are skipped automatically whenever `--live` is not passed. No CI config change needed.

**Logging:** All live tests receive the `local_test_logger` fixture and call `log("PASS"/"FAIL", test_name, detail)`. The file `local-tests.log` is truncated once at session start (session-scoped fixture), then appended to by each test. Format per line:
```
[2026-04-16T14:32:01] [PASS] test_battery_live — battery_percent=74, threshold=73→False, threshold=74→True
```

**Timeout:** All polling loops use a configurable timeout: `int(os.environ.get("AQTIVE_LIVE_TIMEOUT", "120"))` seconds. Import `os` in each live test file.

---

#### Live test: Battery (`tests/live/test_battery_live.py`)

**Goal:** confirm `battery_percent`, `is_on_battery`, and `should_disable_overrides` return correct values against live `pmset -g batt` output.

**Precondition — must be on battery (not charging):**
Before running any assertions, call `pmset -g ps` (separate subprocess call, independent of the battery module) and check its output for the string `'Battery Power'`. If the string is absent (i.e., machine is on AC/charging), call `pytest.skip("Machine is charging — unplug to run battery live tests")`. Do NOT use the battery module itself for this check; `pmset -g ps` is the oracle.

**Steps:**
1. Run `pmset -g ps`, check for `'Battery Power'` — skip if absent (see above).
2. Run `pmset -g batt`, store output as `live_output`.
3. Call `battery_percent(live_output)` → store as `current_pct`. Call `assert_battery_percent(live_output, current_pct)` (verifies the value is self-consistent and parseable as int 0–100).
4. Call `assert_is_on_battery(live_output, True)` — we are on battery (confirmed by step 1).
5. Test `should_disable_overrides` without waiting for battery to drain — use threshold injection:
   - If `current_pct > 1`: call `assert_should_disable(live_output, threshold=current_pct - 1, expected=False)` (above threshold → no disable).
   - Call `assert_should_disable(live_output, threshold=current_pct, expected=True)` (at threshold → disable).
6. Log `PASS — battery_percent={current_pct}, threshold tests passed`.

---

#### Live test: Claude Activity (`tests/live/test_claude_monitor_live.py`)

**Goal:** confirm `get_session_status` transitions `Active` → `Idle` using a real Claude Code JSONL log and that `STOP_REASON_MARKER` is correctly detected.

**Precondition — session isolation:**
This test itself runs inside a Claude Code session that is also writing to `~/.claude/projects/`. Without isolation, `get_session_status()` might immediately return `Active` for the current session before the user does anything, or might detect the wrong session going Idle.

**Isolation approach:**
At step 1, snapshot the current state of `~/.claude/projects/` — record `{path: mtime}` for every `.jsonl` file found. In subsequent polling, only consider files whose mtime has advanced beyond the snapshot. Implement a helper `get_status_excluding_baseline(baseline: dict[Path, float]) -> tuple[str, Path | None]` that calls `_find_newest_jsonl`, skips any file whose mtime <= baseline mtime (or that wasn't in baseline at all but appears now), and applies the same Active/Idle logic. This ensures the test responds only to activity created AFTER the test started.

**Steps:**
1. Record `test_start = time.time()`.
2. Build baseline: walk `~/.claude/projects/`, store `{path: mtime}` for all `.jsonl` files.
3. Print to stdout: `">>> Go to another Claude Code session and send any message. Waiting for activity..."` (no Enter required — the test polls automatically).
4. Poll (0.5 s delay, timeout from `AQTIVE_LIVE_TIMEOUT`) using the isolation helper until a file NEWER than baseline is found AND status is `Active`. If timeout, `pytest.fail("No Active session detected within timeout")`.
5. Store the detected log path. Log `PASS — Active detected: {path}`.
6. Continue polling the SAME file (not the globally newest) until its last line contains `STOP_REASON_MARKER`. No user action required — Claude will finish its response naturally.
7. Assert `STOP_REASON_MARKER in _last_line(detected_path)`. This validates the constant directly, not a hardcoded string.
8. Assert `get_session_status()` now returns `"Idle"` (full function round-trip).
9. Log `PASS — Idle + stop_reason detected in {detected_path.name}`.

---

#### Live test: Network (`tests/live/test_network_live.py`)

**Goal:** confirm `is_connected()` correctly reflects real en0 state when the interface goes up and down.

**Precondition:** test requires an active network connection at start. If `is_connected()` returns `False` at entry, call `pytest.skip("No network at test start")`.

**Interface detection:**
Parse `networksetup -listallhardwareports` output to find the display name for en0. Example output line: `Hardware Port: Wi-Fi` followed by `Device: en0`. Store the display name (e.g., `"Wi-Fi"`) — use this for all `networksetup` commands, not the device name.

```python
def get_wifi_service_name() -> str | None:
    """Return the networksetup service name for en0, or None if not Wi-Fi."""
    out = subprocess.run(["networksetup", "-listallhardwareports"],
                         capture_output=True, text=True).stdout
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if "Device: en0" in line:
            # The Hardware Port line is 2 lines above
            for j in range(i - 1, max(i - 4, -1), -1):
                if lines[j].startswith("Hardware Port:"):
                    name = lines[j].split(":", 1)[1].strip()
                    return name if "Wi-Fi" in name or "AirPort" in name else None
    return None
```

**Steps:**
1. Assert `is_connected()` is `True` (skip if not).
2. Call `get_wifi_service_name()`. If `None` (en0 is not Wi-Fi), fall back to manual path (step 5).
3. **Automated Wi-Fi path:**
   a. Run `networksetup -setairportpower <service_name> off` (e.g., `"Wi-Fi"`).
   b. Poll `is_connected()` (1 s delay, timeout 15 s) until `False`. Assert within timeout; if not, re-enable Wi-Fi and `pytest.fail`.
   c. Call `assert_is_connected(output=None, expected=False)` — passes `output=None` so the function runs `ifconfig` live. (This is the live variant calling the shared helper.)
   d. Log `PASS — disconnected correctly detected`.
   e. Run `networksetup -setairportpower <service_name> on`.
   f. Poll `is_connected()` (1 s delay, timeout 30 s) until `True`. Assert within timeout.
   g. Log `PASS — reconnection correctly detected`.
4. Ensure Wi-Fi is re-enabled in a `finally` block regardless of test outcome (important — don't leave the machine offline).
5. **Manual fallback (non-Wi-Fi en0):**
   a. Print `">>> Manually disconnect your network. Press Enter when offline."`. Wait for Enter.
   b. Assert `is_connected()` is `False`.
   c. Print `">>> Reconnect your network. Press Enter when back online."`. Wait for Enter.
   d. Assert `is_connected()` is `True`.

---

#### Live test: Daemon (`tests/live/test_daemon_live.py`)

**Goal:** confirm the daemon correctly starts/stops caffeinate in response to file-based Claude session state changes, and cleans up on `_cleanup()`.

**Critical: daemon must be instantiated in the main thread.**
`AqtiveDaemon.__init__` calls `signal.signal()`, which raises `ValueError` if called from a non-main thread. Create the daemon object in the main test function (main thread), then pass `daemon.run` to a background thread. Never construct the daemon inside the thread.

```python
daemon = AqtiveDaemon(poll_interval=1, network_guard=False, battery_threshold=0)
# poll_interval=1 keeps tests fast; battery_threshold=0 disables battery guard
t = threading.Thread(target=daemon.run, daemon=True)
t.start()
```

**Session isolation:** Monkeypatch `aqtive.claude_monitor.CLAUDE_PROJECTS_DIR` to point at `tmp_path` so the daemon watches a controlled directory, not the real `~/.claude/projects/`. Since `get_session_status()` reads `CLAUDE_PROJECTS_DIR` at call time (not import time), monkeypatching the module variable is sufficient:

```python
import aqtive.claude_monitor as cm
monkeypatch.setattr(cm, "CLAUDE_PROJECTS_DIR", tmp_path)
```

**Steps:**
1. Create `daemon` and thread as shown above. Start the thread.
2. Wait 1.5 s for the first tick to complete, then assert `daemon._caff.is_running` is `False` (no JSONL in `tmp_path` yet → Idle).
3. Write a fresh `.jsonl` file to `tmp_path / "proj" / "chat.jsonl"` whose last line does NOT contain `STOP_REASON_MARKER`. Any content works, e.g. `'{"type":"assistant"}\n'`.
4. Poll `daemon._caff.is_running` (0.5 s delay, timeout 10 s) until `True`. Assert within timeout.
5. Log `PASS — caffeinate engaged on Active`.
6. Append a new last line containing the stop reason to the same file. Use a full valid JSON line:
   ```python
   with open(chat_path, "a") as f:
       f.write('{"stop_reason":"end_turn"}\n')
   ```
   Verify: `STOP_REASON_MARKER` (`"stop_reason":`) is a substring of `'"stop_reason":"end_turn"'` ✓
7. Poll `daemon._caff.is_running` (0.5 s delay, timeout 10 s) until `False`. Assert within timeout.
8. Log `PASS — caffeinate disengaged on Idle`.
9. **Cleanup / self-healing test:** Call `daemon._cleanup()` directly. Then join the thread (`t.join(timeout=5)`). Assert `daemon._running is False` and `daemon._caff.is_running is False`.
10. Log `PASS — daemon lifecycle complete`.

**Note on `caffeinate` binary:** `caffeinate` is macOS-only. If `shutil.which("caffeinate") is None` (e.g., running on Linux CI accidentally), skip the `is_running` assertions and log a warning. The daemon logic itself is still exercised.

**Note on `battery_threshold=0`:** Setting threshold to 0 ensures `should_disable_overrides` never fires during the test, even on battery, preventing the battery guard from interfering with daemon behaviour assertions.
