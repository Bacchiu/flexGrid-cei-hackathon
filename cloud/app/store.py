"""Stato aggregato: ultima telemetria per sede (thread-safe)."""
from __future__ import annotations

import threading
import time

from . import config
from .models import Telemetry


class StateStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sites: dict[str, tuple[Telemetry, float]] = {}

    def update(self, t: Telemetry) -> None:
        with self._lock:
            self._sites[t.site_id] = (t, time.monotonic())

    def live_sites(self) -> list[Telemetry]:
        now = time.monotonic()
        with self._lock:
            return [
                t for (t, ts) in self._sites.values()
                if now - ts <= config.SITE_STALE_S
            ]

    def site_ids(self) -> list[str]:
        with self._lock:
            return sorted(self._sites.keys())

    def total_grid_kw(self) -> float:
        return sum(t.grid_kw for t in self.live_sites())

    def summary(self) -> dict:
        sites = self.live_sites()
        return {
            "sites": [t.model_dump() for t in sites],
            "n_sites": len(sites),
            "total_grid_kw": round(sum(t.grid_kw for t in sites), 1),
            "total_pv_kw": round(sum(t.pv_kw for t in sites), 1),
            "total_ev_kw": round(sum(t.ev_kw for t in sites), 1),
            "total_hvac_kw": round(sum(t.hvac_kw for t in sites), 1),
            "total_critical_kw": round(sum(t.critical_kw for t in sites), 1),
        }
