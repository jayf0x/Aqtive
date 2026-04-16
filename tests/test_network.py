"""Tests for network connectivity detection."""
from aqtive.network import is_connected

CONNECTED = """\
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	ether aa:bb:cc:dd:ee:ff
	inet6 fe80::1%en0 prefixlen 64 scopeid 0x4
	inet 192.168.1.42 netmask 0xffffff00 broadcast 192.168.1.255
	nd6 options=201<PERFORMNUD,DAD>
	media: autoselect
	status: active
"""

DISCONNECTED = """\
en0: flags=8822<BROADCAST,SMART,SIMPLEX,MULTICAST> mtu 1500
	ether aa:bb:cc:dd:ee:ff
	nd6 options=201<PERFORMNUD,DAD>
	media: autoselect
	status: inactive
"""

EMPTY = ""


def test_connected():
    assert is_connected(output=CONNECTED) is True


def test_disconnected():
    assert is_connected(output=DISCONNECTED) is False


def test_empty_output():
    assert is_connected(output=EMPTY) is False
