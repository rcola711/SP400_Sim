"""Command-line entry point: `sp400-sim`."""

from __future__ import annotations

import argparse
import logging
import sys

from .device import Device
from .profile import load_profile
from .protocol import CommandProcessor


def run_console(processor: CommandProcessor) -> None:
    print("SP400 simulator console. Type HELP for commands, Ctrl-D to exit.")
    for line in sys.stdin:
        reply = processor.handle(line)
        if reply is not None:
            print(reply, flush=True)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sp400-sim", description=__doc__)
    p.add_argument("--profile", help="path to a device profile JSON (default: bundled)")
    p.add_argument("--seed", type=int, help="RNG seed for reproducible sensor noise")
    p.add_argument("-v", "--verbose", action="store_true")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--tcp", type=int, metavar="PORT", help="serve over TCP on PORT")
    mode.add_argument("--pty", action="store_true", help="expose a virtual serial port")
    p.add_argument("--host", default="127.0.0.1", help="TCP bind address")
    p.add_argument("--link", help="with --pty: create a symlink to the pty at this path")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    device = Device(load_profile(args.profile), seed=args.seed)
    processor = CommandProcessor(device)

    if args.tcp is not None:
        from .transports.tcp import run_tcp

        run_tcp(processor, args.host, args.tcp)
    elif args.pty:
        from .transports.pty_serial import run_pty

        run_pty(processor, args.link)
    else:
        run_console(processor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
