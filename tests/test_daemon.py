"""Tests for AqtiveDaemon tick logic."""
from unittest.mock import MagicMock, patch

import pytest

from aqtive.daemon import AqtiveDaemon


def _make_daemon(**kwargs):
    with patch("aqtive.daemon.atexit.register"), \
         patch("aqtive.daemon.signal.signal"), \
         patch("aqtive.caffeinate.atexit.register"), \
         patch("aqtive.caffeinate.signal.signal"):
        return AqtiveDaemon(**kwargs)


@patch("aqtive.daemon.should_disable_overrides", return_value=False)
@patch("aqtive.daemon.is_connected", return_value=True)
@patch("aqtive.daemon.get_session_status", return_value=("Active", None))
def test_tick_starts_caff_when_active(mock_status, mock_net, mock_batt):
    d = _make_daemon()
    d._caff = MagicMock()
    d._caff.is_running = False
    d._tick()
    d._caff.start.assert_called_once()


@patch("aqtive.daemon.should_disable_overrides", return_value=False)
@patch("aqtive.daemon.is_connected", return_value=True)
@patch("aqtive.daemon.get_session_status", return_value=("Idle", None))
def test_tick_stops_caff_when_idle(mock_status, mock_net, mock_batt):
    d = _make_daemon()
    d._caff = MagicMock()
    d._caff.is_running = True
    d._tick()
    d._caff.stop.assert_called_once()


@patch("aqtive.daemon.should_disable_overrides", return_value=True)
@patch("aqtive.daemon.get_session_status", return_value=("Active", None))
def test_tick_battery_guard_stops_caff(mock_status, mock_batt):
    d = _make_daemon()
    d._caff = MagicMock()
    d._caff.is_running = True
    d._tick()
    d._caff.stop.assert_called_once()
    mock_status.assert_not_called()  # battery guard short-circuits


@patch("aqtive.daemon.should_disable_overrides", return_value=False)
@patch("aqtive.daemon.is_connected", return_value=False)
@patch("aqtive.daemon.get_session_status", return_value=("Active", None))
def test_tick_network_guard_stops_caff(mock_status, mock_net, mock_batt):
    d = _make_daemon(network_guard=True)
    d._caff = MagicMock()
    d._caff.is_running = True
    d._tick()
    d._caff.stop.assert_called_once()
    mock_status.assert_not_called()


@patch("aqtive.daemon.should_disable_overrides", return_value=False)
@patch("aqtive.daemon.is_connected", return_value=False)
@patch("aqtive.daemon.get_session_status", return_value=("Active", None))
def test_tick_network_guard_disabled_by_default(mock_status, mock_net, mock_batt):
    d = _make_daemon(network_guard=False)
    d._caff = MagicMock()
    d._caff.is_running = False
    d._tick()
    # network guard off — session check still runs
    mock_status.assert_called_once()
