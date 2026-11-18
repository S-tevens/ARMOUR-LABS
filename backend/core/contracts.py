"""Shared data contracts. Keep in sync with docs/contracts.md and frontend/src/types.ts.

Changing anything here needs agreement from all contributors.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

DeviceState = Literal["normal", "suspicious", "compromised"]


class IedStatus(BaseModel):
    """Security state of each intelligent electronic device (protection relay / controller)."""

    ied01: DeviceState = "normal"  # utility interface: CB-MAIN and the grid meter
    ied02: DeviceState = "normal"  # distributed energy resources: PV inverter, battery, CB-PV, CB-BESS
    ied03: DeviceState = "normal"  # load feeders: CB-CRIT (hospital) and CB-NC (campus)


class Telemetry(BaseModel):
    """One observed substation snapshot (what meters and relays report), 1 Hz.

    Powers are kW. grid_import_kw: positive = importing from the utility, negative = exporting.
    bess_kw: positive = discharging, negative = charging. Breakers: True = closed.
    """

    t: float
    tick: int
    frequency: float  # Hz
    bus_voltage: float  # per unit
    grid_import_kw: float
    pv_kw: float
    bess_kw: float
    bess_soc: float  # percent
    load_critical_kw: float  # hospital feeder
    load_noncritical_kw: float  # campus feeder
    irradiance: float  # W/m2, from the weather station
    cb_main: bool
    cb_pv: bool
    cb_bess: bool
    cb_crit: bool
    cb_nc: bool
    ied_status: IedStatus = Field(default_factory=IedStatus)


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
