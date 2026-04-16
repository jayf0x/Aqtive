"""Tests for battery threshold guard."""
import pytest

from aqtive.battery import battery_percent, is_on_battery, should_disable_overrides

# Realistic pmset -g batt output samples
AC_FULL = """\
Now drawing from 'AC Power'
 -InternalBattery-0 (id=...)	100%; charged; 0:00 remaining present: true
"""

BATTERY_50 = """\
Now drawing from 'Battery Power'
 -InternalBattery-0 (id=...)	50%; discharging; 3:22 remaining present: true
"""

BATTERY_10 = """\
Now drawing from 'Battery Power'
 -InternalBattery-0 (id=...)	10%; discharging; 0:30 remaining present: true
"""

BATTERY_15 = """\
Now drawing from 'Battery Power'
 -InternalBattery-0 (id=...)	15%; discharging; 0:50 remaining present: true
"""

CHARGING_80 = """\
Now drawing from 'AC Power'
 -InternalBattery-0 (id=...)	80%; charging; 1:10 remaining present: true
"""


# ---------------------------------------------------------------------------
# is_on_battery
# ---------------------------------------------------------------------------

def test_on_battery_true():
    assert is_on_battery(BATTERY_50) is True


def test_on_battery_false_ac():
    assert is_on_battery(AC_FULL) is False


def test_on_battery_false_charging():
    assert is_on_battery(CHARGING_80) is False


# ---------------------------------------------------------------------------
# battery_percent
# ---------------------------------------------------------------------------

def test_battery_percent_ac():
    assert battery_percent(AC_FULL) == 100


def test_battery_percent_discharging():
    assert battery_percent(BATTERY_50) == 50


def test_battery_percent_low():
    assert battery_percent(BATTERY_10) == 10


def test_battery_percent_empty_string():
    assert battery_percent("") is None


# ---------------------------------------------------------------------------
# should_disable_overrides
# ---------------------------------------------------------------------------

def test_disable_true_below_threshold():
    assert should_disable_overrides(threshold=15, output=BATTERY_10) is True


def test_disable_true_at_threshold():
    assert should_disable_overrides(threshold=15, output=BATTERY_15) is True


def test_disable_false_above_threshold():
    assert should_disable_overrides(threshold=15, output=BATTERY_50) is False


def test_disable_false_on_ac():
    assert should_disable_overrides(threshold=15, output=AC_FULL) is False


def test_disable_false_charging():
    assert should_disable_overrides(threshold=15, output=CHARGING_80) is False
