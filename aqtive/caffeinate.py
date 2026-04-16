"""
Wrapper around macOS `caffeinate` for manual sleep prevention.
"""
import atexit
import logging
import signal
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class Caffeinator:
    """Spawns and manages a `caffeinate` subprocess."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        atexit.register(self.stop)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------
    def start(self, seconds: Optional[int] = None) -> None:
        """Start caffeination. seconds=None means indefinite."""
        if self._proc and self._proc.poll() is None:
            logger.info("caffeinate already running (pid=%s)", self._proc.pid)
            return

        cmd = ["caffeinate", "-d", "-i", "-m", "-s"]
        if seconds is not None:
            cmd += ["-t", str(seconds)]

        self._proc = subprocess.Popen(cmd)
        logger.info("caffeinate started (pid=%s, timeout=%s)", self._proc.pid, seconds)

    def stop(self) -> None:
        """Terminate caffeination if running."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            logger.info("caffeinate stopped (pid=%s)", self._proc.pid)
        self._proc = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    def _handle_signal(self, signum: int, frame) -> None:  # noqa: ANN001
        logger.info("Signal %s received — stopping caffeinate", signum)
        self.stop()
        raise SystemExit(0)
