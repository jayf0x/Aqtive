"""
Network persistence check.

Detects whether the primary interface (en0) has an active IPv4 address,
indicating a live network connection.
"""
import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

_INTERFACE = "en0"
_INET_PATTERN = re.compile(r"inet\s+(\d+\.\d+\.\d+\.\d+)")


def _ifconfig_output(interface: str = _INTERFACE) -> str:
    try:
        result = subprocess.run(
            ["ifconfig", interface],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("ifconfig failed: %s", exc)
        return ""


def is_connected(interface: str = _INTERFACE, output: Optional[str] = None) -> bool:
    """Return True if interface has an active IPv4 address."""
    raw = output if output is not None else _ifconfig_output(interface)
    return bool(_INET_PATTERN.search(raw))
