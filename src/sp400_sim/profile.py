"""Device profile: identity, parameters and simulated sensors, loaded from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass
class ParamSpec:
    name: str
    type: str  # "float" | "int" | "str"
    default: Any
    min: float | None = None
    max: float | None = None
    unit: str = ""

    def coerce(self, raw: str) -> Any:
        """Convert a raw string to the parameter's type and range-check it."""
        if self.type == "float":
            value: Any = float(raw)
        elif self.type == "int":
            value = int(raw)
        elif self.type == "str":
            value = raw
        else:
            raise ValueError(f"unknown parameter type {self.type!r}")
        if self.type in ("float", "int"):
            if self.min is not None and value < self.min:
                raise ValueError(f"{self.name} below min {self.min}")
            if self.max is not None and value > self.max:
                raise ValueError(f"{self.name} above max {self.max}")
        return value


@dataclass
class SensorSpec:
    name: str
    base: float
    noise: float = 0.0
    unit: str = ""
    scale_by: str | None = None  # multiply output by this parameter
    track: str | None = None  # first-order approach toward this parameter
    tau_s: float = 1.0  # time constant for `track`


@dataclass
class Profile:
    identity: dict[str, str]
    parameters: dict[str, ParamSpec] = field(default_factory=dict)
    sensors: dict[str, SensorSpec] = field(default_factory=dict)
    line_terminator: str = "\n"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        params = {
            name.upper(): ParamSpec(name=name.upper(), **spec)
            for name, spec in data.get("parameters", {}).items()
        }
        sensors = {
            name.upper(): SensorSpec(name=name.upper(), **spec)
            for name, spec in data.get("sensors", {}).items()
        }
        for s in sensors.values():
            for ref in (s.scale_by, s.track):
                if ref and ref.upper() not in params:
                    raise ValueError(f"sensor {s.name} references unknown parameter {ref}")
        return cls(
            identity=data.get("identity", {}),
            parameters=params,
            sensors=sensors,
            line_terminator=data.get("line_terminator", "\n"),
        )


def load_profile(path: str | Path | None = None) -> Profile:
    """Load a profile from `path`, or the bundled default profile."""
    if path is None:
        text = resources.files("sp400_sim").joinpath("profiles/default.json").read_text()
    else:
        text = Path(path).read_text()
    return Profile.from_dict(json.loads(text))
