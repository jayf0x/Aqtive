"""Tests for Caffeinator (mocked subprocess)."""
import signal
from unittest.mock import MagicMock, patch

import pytest

from aqtive.caffeinate import Caffeinator


@pytest.fixture()
def caff():
    with patch("aqtive.caffeinate.subprocess.Popen") as mock_popen, \
         patch("aqtive.caffeinate.atexit.register"), \
         patch("aqtive.caffeinate.signal.signal"):
        proc = MagicMock()
        proc.poll.return_value = None   # process running
        proc.pid = 12345
        mock_popen.return_value = proc
        c = Caffeinator()
        c._MockPopen = mock_popen
        c._mock_proc = proc
        yield c


def test_start_launches_process(caff):
    caff.start()
    assert caff._MockPopen.called
    assert caff.is_running


def test_start_with_timeout(caff):
    caff.start(seconds=300)
    cmd = caff._MockPopen.call_args[0][0]
    assert "-t" in cmd
    assert "300" in cmd


def test_start_idempotent(caff):
    caff.start()
    caff.start()
    assert caff._MockPopen.call_count == 1


def test_stop_terminates(caff):
    caff.start()
    caff.stop()
    caff._mock_proc.terminate.assert_called_once()


def test_stop_when_not_running_is_safe(caff):
    caff.stop()  # no proc started — should not raise


def test_is_running_false_after_stop(caff):
    caff.start()
    caff._mock_proc.poll.return_value = 0  # process exited
    assert not caff.is_running
