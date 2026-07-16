"""Telemetry adapter — the seam where real hardware plugs in.

BSO is a software orchestration/decision-support layer. It INGESTS telemetry from a
stimulation platform (e.g. the partner platform / the device partner) and reasons about it; it never drives
the implant — real stimulation changes go through the certified clinical programmer.
This module defines that boundary explicitly: a read-only `TelemetrySource` contract
plus a simulated source, so a partner device becomes a drop-in by implementing one
small interface.

Illustrative research simulation — not a medical device.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class TelemetrySample:
    """One telemetry frame from a device (read-only)."""
    t: float
    channels: list[float]                       # per-contact delivered amplitude (mA)
    sensors: dict = field(default_factory=dict)  # optional: pressure, IMU, EMG...
    source: str = "simulated"


class TelemetrySource(Protocol):
    """A device a partner implements to feed BSO. READ-ONLY by design."""

    def info(self) -> dict: ...
    def read(self) -> TelemetrySample: ...


class SimulatedTelemetry:
    """Stand-in source so the pipeline runs end-to-end before real hardware exists."""

    def __init__(self, n_contacts: int = 16, seed: int = 0):
        self.n_contacts = n_contacts
        self.rng = np.random.default_rng(seed)
        self._t = 0.0
        self.writable = False                   # NEVER writable — we do not command

    def info(self) -> dict:
        return {"device": "SimulatedTelemetry", "n_contacts": self.n_contacts,
                "writable": self.writable, "units": {"amplitude": "mA"}}

    def read(self) -> TelemetrySample:
        self._t += 0.038                        # ~26 Hz device loop
        ch = (self.rng.random(self.n_contacts) * 2.0).round(2).tolist()
        return TelemetrySample(t=round(self._t, 3), channels=ch,
                               sensors={"bladder_pressure": round(float(self.rng.uniform(8, 30)), 1)},
                               source="simulated")


# Registry: a real vendor adapter (the partner platform / the device partner) registers here by name.
REGISTRY: dict[str, type] = {"simulated": SimulatedTelemetry}


def available() -> list[str]:
    return list(REGISTRY.keys())


def get_source(name: str = "simulated", **kw) -> TelemetrySource:
    if name not in REGISTRY:
        raise KeyError(f"unknown telemetry source '{name}'; available: {available()}")
    return REGISTRY[name](**kw)


def contract() -> dict:
    """The integration contract + the safety boundary, for a partner to read."""
    return {
        "interface": ["info() -> dict", "read() -> TelemetrySample{t, channels, sensors, source}"],
        "direction": "read-only (BSO ingests telemetry)",
        "safety_boundary": ("BSO never writes stimulation to the implant; real changes "
                            "go through the certified clinical programmer. Proposed changes "
                            "are surfaced to the clinician for approval (see clinical_approval)."),
        "available_sources": available(),
        "to_integrate_real_hardware": "implement TelemetrySource and register it in REGISTRY",
    }
