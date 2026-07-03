"""Simulatore degli asset energetici di una sede.

Modella FV (generazione), colonnine EV e HVAC (carichi flessibili) e carichi
critici (mai modulati). Applica i setpoint dei comandi e produce la telemetria.
"""
from __future__ import annotations

import random
import threading
import time

from . import config
from .models import Command, Telemetry


class AssetSimulator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Stato modulazione corrente (default = nominale, nessuna riduzione)
        self._ev_setpoint = config.EV_KW_PER_CHARGER
        self._hvac_reduction_pct = 0.0
        # Scadenza auto-rilascio (monotonic); 0 = nessuna
        self._expiry = 0.0
        self._active_event: str | None = None

    # --- Applicazione comandi -------------------------------------------------
    def apply_command(self, cmd: Command) -> None:
        with self._lock:
            self._ev_setpoint = max(
                config.EV_FLOOR_KW_PER_CHARGER,
                min(config.EV_KW_PER_CHARGER, cmd.ev_setpoint_kw_per_charger),
            )
            self._hvac_reduction_pct = max(
                0.0, min(config.HVAC_MAX_REDUCTION_PCT, cmd.hvac_reduction_pct)
            )
            self._active_event = cmd.event_id
            self._expiry = time.monotonic() + cmd.duration_s if cmd.duration_s > 0 else 0.0

    def _maybe_auto_release(self) -> None:
        """Rete di sicurezza: se il rilascio dal cloud si perde, torna al nominale."""
        if self._expiry and time.monotonic() >= self._expiry:
            self._ev_setpoint = config.EV_KW_PER_CHARGER
            self._hvac_reduction_pct = 0.0
            self._expiry = 0.0
            self._active_event = None

    # --- Campionamento telemetria --------------------------------------------
    @staticmethod
    def _noise(value: float) -> float:
        if config.NOISE_PCT <= 0:
            return value
        return value * (1.0 + random.uniform(-config.NOISE_PCT, config.NOISE_PCT))

    def sample(self) -> Telemetry:
        with self._lock:
            self._maybe_auto_release()

            pv = self._noise(config.PV_PEAK_KW * config.PV_FACTOR)
            ev = self._noise(config.EV_ACTIVE * self._ev_setpoint)
            hvac = self._noise(config.HVAC_BASE_KW * (1.0 - self._hvac_reduction_pct / 100.0))
            critical = config.CRITICAL_KW  # invariati per definizione

            consumption = ev + hvac + critical
            grid = consumption - pv

            return Telemetry(
                site_id=config.SITE_ID,
                pv_kw=round(pv, 1),
                ev_kw=round(ev, 1),
                hvac_kw=round(hvac, 1),
                critical_kw=round(critical, 1),
                grid_kw=round(grid, 1),
            )

    def state(self) -> dict:
        with self._lock:
            return {
                "site_id": config.SITE_ID,
                "ev_setpoint_kw_per_charger": self._ev_setpoint,
                "hvac_reduction_pct": self._hvac_reduction_pct,
                "active_event": self._active_event,
                "modulating": self._active_event is not None,
            }
