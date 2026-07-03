"""Contratti dati dell'Aggregator."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Telemetry(BaseModel):
    """Telemetria in arrivo da una sede edge."""

    site_id: str
    ts: str = Field(default_factory=_now_iso)
    pv_kw: float
    ev_kw: float
    hvac_kw: float
    critical_kw: float
    grid_kw: float


class Command(BaseModel):
    """Comando di modulazione verso una sede edge."""

    site_id: str
    event_id: str
    ev_setpoint_kw_per_charger: float = 22.0
    hvac_reduction_pct: float = 0.0
    duration_s: int = 0


class TernaEvent(BaseModel):
    """Richiesta di flessibilità (segnale Terna simulato)."""

    reduction_kw: float = Field(gt=0, description="Riduzione di prelievo richiesta, in kW")
    duration_s: int = Field(default=900, gt=0, description="Durata dell'evento in secondi")
    price_eur_mwh: Optional[float] = Field(default=None, description="Prezzo di attivazione €/MWh")
