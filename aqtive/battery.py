"""
Battery threshold guard.

Reads battery info from `pmset -g batt` and exposes:
  - is_on_battery() -> bool
  - battery_percent() -> Optional[int]
  - should_disable_overrides(threshold) -> bool
"""
import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

_BATT_PATTERN = re.compile(r"(\d+)%;?\s*(charging|discharging|charged|AC Power|finishing charge)", re.IGNORECASE)
_ON_BATTERY_PATTERN = re.compile(r"Now drawing from 'Battery Power'", re.IGNORECASE)


def _pmset_output() -> str:
    try:
        result = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("pmset batt failed: %s", exc)
        return ""


def is_on_battery(output: Optional[str] = None) -> bool:
    raw = output if output is not None else _pmset_output()
    return bool(_ON_BATTERY_PATTERN.search(raw))


def battery_percent(output: Optional[str] = None) -> Optional[int]:
    raw = output if output is not None else _pmset_output()
    m = _BATT_PATTERN.search(raw)
    if m:
        return int(m.group(1))
    return None


def should_disable_overrides(threshold: int = 15, output: Optional[str] = None) -> bool:
    """Return True when on battery AND level <= threshold."""
    raw = output if output is not None else _pmset_output()
    if not is_on_battery(raw):
        return False
    pct = battery_percent(raw)
    if pct is None:
        return False
    result = pct <= threshold
    if result:
        logger.warning("Battery at %d%% on battery — disabling overrides", pct)
    return result
