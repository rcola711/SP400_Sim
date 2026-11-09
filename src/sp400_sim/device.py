"""Simulated instrument: state machine, parameters, sensors and error queue."""

from __future__ import annotations

import enum
import math
import random
import time
from collections import deque
from typing import Any, Callable

from .profile import Profile


class DeviceState(enum.Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    ERROR = "ERROR"


class DeviceError(Exception):
    """Error raised by the device; `code` goes into the error queue."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Error codes (SCPI-style negative numbers).
E_NONE = 0
E_UNKNOWN_CMD = -100
E_BAD_PARAM = -101
E_OUT_OF_RANGE = -102
E_BAD_STATE = -200
E_FAULT = -300

ERROR_QUEUE_SIZE = 16


class Device:
    def __init__(
        self,
        profile: Profile,
        clock: Callable[[], float] = time.monotonic,
        seed: int | None = None,
    ):
        self.profile = profile
        self._clock = clock
        self._rng = random.Random(seed)
        self.errors: deque[tuple[int, str]] = deque(maxlen=ERROR_QUEUE_SIZE)
        self.reset()

    # --- lifecycle -------------------------------------------------------
    def reset(self) -> None:
        self.state = DeviceState.IDLE
        self.params: dict[str, Any] = {
            name: spec.default for name, spec in self.profile.parameters.items()
        }
        self._tracked: dict[str, float] = {
            name: s.base for name, s in self.profile.sensors.items() if s.track
        }
        self._last_update = self._clock()
        self.started_at: float | None = None
        self.sample_count = 0
        self.fault: str | None = None

    def start(self) -> None:
        if self.state is DeviceState.ERROR:
            raise DeviceError(E_BAD_STATE, f"device faulted: {self.fault}")
        if self.state is DeviceState.RUNNING:
            raise DeviceError(E_BAD_STATE, "already running")
        self.state = DeviceState.RUNNING
        self.started_at = self._clock()
        self.sample_count = 0

    def stop(self) -> None:
        if self.state is not DeviceState.RUNNING:
            raise DeviceError(E_BAD_STATE, "not running")
        self.state = DeviceState.IDLE
        self.started_at = None

    def inject_fault(self, reason: str) -> None:
        """Force the device into the ERROR state (for testing host software)."""
        self.state = DeviceState.ERROR
        self.fault = reason
        self.push_error(E_FAULT, reason)

    def clear_fault(self) -> None:
        if self.state is DeviceState.ERROR:
            self.state = DeviceState.IDLE
            self.fault = None

    # --- parameters ------------------------------------------------------
    def set_param(self, name: str, raw: str) -> None:
        spec = self.profile.parameters.get(name.upper())
        if spec is None:
            raise DeviceError(E_BAD_PARAM, f"unknown parameter {name}")
        try:
            self.params[spec.name] = spec.coerce(raw)
        except ValueError as exc:
            raise DeviceError(E_OUT_OF_RANGE, str(exc)) from exc

    def get_param(self, name: str) -> Any:
        key = name.upper()
        if key not in self.params:
            raise DeviceError(E_BAD_PARAM, f"unknown parameter {name}")
        return self.params[key]

    # --- sensors ---------------------------------------------------------
    def _advance(self) -> None:
        now = self._clock()
        dt = max(0.0, now - self._last_update)
        self._last_update = now
        for name, value in self._tracked.items():
            s = self.profile.sensors[name]
            target = float(self.params[s.track.upper()])
            alpha = 1.0 - math.exp(-dt / s.tau_s) if s.tau_s > 0 else 1.0
            self._tracked[name] = value + (target - value) * alpha

    def read_sensor(self, name: str) -> float:
        key = name.upper()
        s = self.profile.sensors.get(key)
        if s is None:
            raise DeviceError(E_BAD_PARAM, f"unknown sensor {name}")
        if self.state is DeviceState.ERROR:
            raise DeviceError(E_BAD_STATE, f"device faulted: {self.fault}")
        self._advance()
        value = self._tracked.get(key, s.base)
        if s.scale_by:
            value *= float(self.params[s.scale_by.upper()])
        if s.noise:
            value += self._rng.gauss(0.0, s.noise)
        self.sample_count += 1
        return value

    def measure_all(self) -> dict[str, float]:
        return {name: self.read_sensor(name) for name in self.profile.sensors}

    # --- errors ----------------------------------------------------------
    def push_error(self, code: int, message: str) -> None:
        self.errors.append((code, message))

    def pop_error(self) -> tuple[int, str]:
        return self.errors.popleft() if self.errors else (E_NONE, "No error")
