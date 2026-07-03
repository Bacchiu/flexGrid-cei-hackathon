"""Contratti dati edge↔cloud (fonte: Caso_Base_Demo.md §9)."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Telemetry(BaseModel):
    """Telemetria pubblicata dall'edge verso il cloud."""

    site_id: str
    ts: str = Field(default_factory=_now_iso)
    pv_kw: float
    ev_kw: float
    hvac_kw: float
    critical_kw: float
    grid_kw: float  # prelievo dalla rete = consumo - produzione FV


class Command(BaseModel):
    """Comando di modulazione ricevuto dal cloud."""

    site_id: str
    event_id: str
    ev_setpoint_kw_per_charger: float = 22.0  # 22 = nominale, 7 = smart-charging
    hvac_reduction_pct: float = 0.0           # 0..15
    duration_s: int = 0                        # 0 = fino a nuovo comando; >0 = auto-rilascio
