"""Shared data contracts. Keep in sync with docs/contracts.md and frontend/src/types.ts.

Changing anything here needs agreement from all three contributors.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PlcStatus(BaseModel):
    plc01: Literal["normal", "suspicious", "compromised"] = "normal"
    plc02: Literal["normal", "suspicious", "compromised"] = "normal"
    plc03: Literal["normal", "suspicious", "compromised"] = "normal"


class Telemetry(BaseModel):
    """One observed plant snapshot (what sensors/controllers report), 1 Hz.

    pump1/pump2: True = running. valve1: True = open.
    """

    t: float
    tick: int
    tank1_level: float
    tank2_level: float
    pressure: float
    flow: float
    temperature: float
    pump1: bool
    pump2: bool
    valve1: bool
    plc_status: PlcStatus = Field(default_factory=PlcStatus)


class NetworkEvent(BaseModel):
    seq: int
    t: float
    src: str
    dst: str
    function_code: str
    register: str
    value: float | str | bool | None
    authorised: bool


class TwinState(BaseModel):
    t: float
    expected: dict[str, float]
    residual: dict[str, float]
    norm_residual: dict[str, float]


class Scores(BaseModel):
    """Detector scores in [0, 1]. Illustrative until real detectors replace the baseline."""

    t: float
    network: float = 0.0
    controller: float = 0.0
    process: float = 0.0
    twin: float = 0.0


class Evidence(BaseModel):
    type: str
    text: str
    tag: Literal["observed", "correlated", "inferred"]


class Incident(BaseModel):
    id: str
    t_start: float
    severity: Literal["low", "medium", "high"]
    confidence: float
    affected_devices: list[str]
    classification: Literal["attack", "fault", "unknown"]
    scores: dict[str, float]
    evidence: list[Evidence]
    status: Literal["open", "responding", "recovering", "recovered", "unresolved"]
