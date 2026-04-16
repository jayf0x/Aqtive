"""
Aqtive CLI entry point.

Usage:
  aqtive caff [--seconds N]      Start manual caffeination
  aqtive caff --stop             Stop caffeination
  aqtive clamshell --enable      Disable sleep on lid close
  aqtive clamshell --disable     Restore sleep on lid close
  aqtive status                  Print current Claude session status
  aqtive daemon [--interval N] [--network-guard] [--battery-threshold N]
"""
import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def _cmd_caff(args: argparse.Namespace) -> int:
    from aqtive.caffeinate import Caffeinator

    c = Caffeinator()
    if args.stop:
        c.stop()
        print("Caffeination stopped.")
    else:
        c.start(seconds=args.seconds)
        print(f"Caffeinating{' for ' + str(args.seconds) + 's' if args.seconds else ' indefinitely'}. Ctrl-C to stop.")
        try:
            import time
            while c.is_running:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            pass
    return 0


def _cmd_clamshell(args: argparse.Namespace) -> int:
    from aqtive.clamshell import ClamshellGuard

    g = ClamshellGuard()
    if args.enable:
        ok = g.enable()
        print("Clamshell mode enabled (sleep disabled)." if ok else "Failed — check sudoers config.")
        return 0 if ok else 1
    if args.disable:
        ok = g.restore()
        print("Clamshell mode disabled (sleep restored)." if ok else "Failed — check sudoers config.")
        return 0 if ok else 1
    print("Specify --enable or --disable", file=sys.stderr)
    return 1


def _cmd_status(_args: argparse.Namespace) -> int:
    from aqtive.battery import battery_percent, is_on_battery
    from aqtive.claude_monitor import get_session_status
    from aqtive.network import is_connected

    status, log_path = get_session_status()
    pct = battery_percent()
    on_bat = is_on_battery()
    connected = is_connected()

    print(f"Claude session : {status}")
    print(f"Log file       : {log_path or 'none'}")
    print(f"Battery        : {pct}% ({'on battery' if on_bat else 'charging/AC'})")
    print(f"Network (en0)  : {'connected' if connected else 'disconnected'}")
    return 0


def _cmd_daemon(args: argparse.Namespace) -> int:
    from aqtive.daemon import AqtiveDaemon

    d = AqtiveDaemon(
        poll_interval=args.interval,
        network_guard=args.network_guard,
        battery_threshold=args.battery_threshold,
    )
    d.run()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aqtive",
        description="macOS power state manager",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # caff
    p_caff = sub.add_parser("caff", help="Manual caffeination")
    p_caff.add_argument("--seconds", type=int, default=None, metavar="N", help="Duration in seconds")
    p_caff.add_argument("--stop", action="store_true", help="Stop caffeination")
    p_caff.set_defaults(func=_cmd_caff)

    # clamshell
    p_clam = sub.add_parser("clamshell", help="Lid-closed sleep toggle")
    grp = p_clam.add_mutually_exclusive_group(required=True)
    grp.add_argument("--enable", action="store_true", help="Disable sleep on lid close")
    grp.add_argument("--disable", action="store_true", help="Restore sleep on lid close")
    p_clam.set_defaults(func=_cmd_clamshell)

    # status
    p_status = sub.add_parser("status", help="Print current status")
    p_status.set_defaults(func=_cmd_status)

    # daemon
    p_daemon = sub.add_parser("daemon", help="Context-aware daemon")
    p_daemon.add_argument("--interval", type=int, default=10, metavar="N", help="Poll interval in seconds")
    p_daemon.add_argument("--network-guard", action="store_true", help="Stop on network loss")
    p_daemon.add_argument("--battery-threshold", type=int, default=15, metavar="N")
    p_daemon.set_defaults(func=_cmd_daemon)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
