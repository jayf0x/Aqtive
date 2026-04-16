"""
Toggle clamshell (lid-closed) sleep behaviour via `pmset`.

Requires passwordless sudo for:
  sudo pmset -a sleep 0
  sudo pmset -a sleep 1
See README for one-time visudo setup.
"""
import atexit
import logging
import subprocess

logger = logging.getLogger(__name__)

_PMSET_DISABLE = ["sudo", "pmset", "-a", "sleep", "0"]
_PMSET_ENABLE = ["sudo", "pmset", "-a", "sleep", "1"]


class ClamshellGuard:
    """Prevent sleep on lid close; restore on exit."""

    def __init__(self) -> None:
        self._active = False
        atexit.register(self.restore)

    def enable(self) -> bool:
        """Disable sleep-on-lid-close. Returns True on success."""
        result = subprocess.run(_PMSET_DISABLE, capture_output=True)
        if result.returncode == 0:
            self._active = True
            logger.info("Clamshell mode: sleep disabled")
            return True
        logger.error("pmset failed: %s", result.stderr.decode().strip())
        return False

    def restore(self) -> bool:
        """Re-enable sleep-on-lid-close. Returns True on success."""
        if not self._active:
            return True
        result = subprocess.run(_PMSET_ENABLE, capture_output=True)
        if result.returncode == 0:
            self._active = False
            logger.info("Clamshell mode: sleep restored")
            return True
        logger.error("pmset restore failed: %s", result.stderr.decode().strip())
        return False

    @property
    def is_active(self) -> bool:
        return self._active
