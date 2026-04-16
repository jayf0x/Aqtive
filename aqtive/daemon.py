"""
Context-aware daemon: polls Claude session, battery, and network;
engages/disengages caffeination automatically.
"""
import atexit
import logging
import signal
import time

from aqtive.battery import should_disable_overrides
from aqtive.caffeinate import Caffeinator
from aqtive.claude_monitor import get_session_status
from aqtive.network import is_connected

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 10  # seconds


class AqtiveDaemon:
    """Poll loop that keeps the system awake while Claude is active."""

    def __init__(
        self,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        network_guard: bool = False,
        battery_threshold: int = 15,
    ) -> None:
        self.poll_interval = poll_interval
        self.network_guard = network_guard
        self.battery_threshold = battery_threshold
        self._running = False
        self._caff = Caffeinator()

        atexit.register(self._cleanup)
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("Aqtive daemon started (interval=%ds)", self.poll_interval)
        self._running = True
        while self._running:
            self._tick()
            time.sleep(self.poll_interval)

    def _tick(self) -> None:
        # Battery guard takes priority
        if should_disable_overrides(self.battery_threshold):
            if self._caff.is_running:
                logger.warning("Battery threshold hit — stopping caffeinate")
                self._caff.stop()
            return

        # Network guard
        if self.network_guard and not is_connected():
            if self._caff.is_running:
                logger.warning("Network lost — stopping caffeinate")
                self._caff.stop()
            return

        status, log_path = get_session_status()
        logger.debug("Claude status=%s log=%s", status, log_path)

        if status == "Active" and not self._caff.is_running:
            logger.info("Claude Active — starting caffeinate")
            self._caff.start()
        elif status == "Idle" and self._caff.is_running:
            logger.info("Claude Idle — stopping caffeinate")
            self._caff.stop()

    def _cleanup(self) -> None:
        self._running = False
        self._caff.stop()
        logger.info("Aqtive daemon cleaned up")

    def _handle_signal(self, signum: int, frame) -> None:  # noqa: ANN001
        logger.info("Signal %s — shutting down", signum)
        self._cleanup()
        raise SystemExit(0)
