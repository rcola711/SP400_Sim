"""Line-based ASCII command protocol.

The command set below is a PLACEHOLDER (SCPI-style). Replace or extend it
with the real SP 400 commands by registering handlers on CommandProcessor.
"""

from __future__ import annotations

from typing import Callable

from .device import E_UNKNOWN_CMD, Device, DeviceError

Handler = Callable[[Device, list[str]], str | None]


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


class CommandProcessor:
    """Parses one command line and returns the response line (or None)."""

    def __init__(self, device: Device):
        self.device = device
        self.handlers: dict[str, Handler] = {}
        self._register_defaults()

    def register(self, name: str, handler: Handler) -> None:
        self.handlers[name.upper()] = handler

    def handle(self, line: str) -> str | None:
        line = line.strip()
        if not line:
            return None
        cmd, *args = line.split()
        handler = self.handlers.get(cmd.upper())
        try:
            if handler is None:
                raise DeviceError(E_UNKNOWN_CMD, f"unknown command {cmd}")
            return handler(self.device, args)
        except DeviceError as exc:
            self.device.push_error(exc.code, exc.message)
            return f"ERR {exc.code}"

    # --- default command set ---------------------------------------------
    def _register_defaults(self) -> None:
        def need(args: list[str], n: int) -> None:
            if len(args) != n:
                raise DeviceError(-101, f"expected {n} argument(s), got {len(args)}")

        def idn(d: Device, a: list[str]) -> str:
            i = d.profile.identity
            return ",".join(
                i.get(k, "") for k in ("manufacturer", "model", "serial", "firmware")
            )

        def rst(d: Device, a: list[str]) -> str:
            d.reset()
            return "OK"

        def start(d: Device, a: list[str]) -> str:
            d.start()
            return "OK"

        def stop(d: Device, a: list[str]) -> str:
            d.stop()
            return "OK"

        def stat(d: Device, a: list[str]) -> str:
            return d.state.value

        def set_(d: Device, a: list[str]) -> str:
            need(a, 2)
            d.set_param(a[0], a[1])
            return "OK"

        def get(d: Device, a: list[str]) -> str:
            need(a, 1)
            return _fmt(d.get_param(a[0]))

        def meas(d: Device, a: list[str]) -> str:
            if a:
                need(a, 1)
                return _fmt(d.read_sensor(a[0]))
            return ",".join(f"{k}={_fmt(v)}" for k, v in d.measure_all().items())

        def err(d: Device, a: list[str]) -> str:
            code, msg = d.pop_error()
            return f'{code},"{msg}"'

        def fault(d: Device, a: list[str]) -> str:
            d.inject_fault(" ".join(a) or "simulated fault")
            return "OK"

        def clr(d: Device, a: list[str]) -> str:
            d.clear_fault()
            d.errors.clear()
            return "OK"

        def help_(d: Device, a: list[str]) -> str:
            return " ".join(sorted(self.handlers))

        for name, fn in {
            "*IDN?": idn,
            "*RST": rst,
            "*CLS": clr,
            "START": start,
            "STOP": stop,
            "STAT?": stat,
            "SET": set_,
            "GET": get,
            "MEAS?": meas,
            "ERR?": err,
            "SIM:FAULT": fault,
            "HELP": help_,
        }.items():
            self.register(name, fn)
