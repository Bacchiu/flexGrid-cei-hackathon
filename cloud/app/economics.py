"""Contabilità economica dell'evento di flessibilità (ripartizione 80/20).

Integra nel tempo la potenza di flessibilità realmente erogata
(delivered = prelievo_base - prelievo_corrente) e ne calcola il controvalore.
"""
from __future__ import annotations

import threading
import time

from . import config


class EconomicsAccumulator:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset()

    def _reset(self) -> None:
        self.active = False
        self.event_id: str | None = None
        self.price_eur_mwh = config.DEFAULT_PRICE_EUR_MWH
        self.baseline_grid_kw = 0.0        # somma del prelievo base pre-evento
        self.delivered_kw = 0.0            # flessibilità istantanea erogata
        self.energy_kwh = 0.0              # integrale nel tempo
        self._last_t = 0.0

    # --- Ciclo di vita evento -------------------------------------------------
    def start(self, event_id: str, price_eur_mwh: float, baseline_grid_kw: float) -> None:
        with self._lock:
            self._reset()
            self.active = True
            self.event_id = event_id
            self.price_eur_mwh = price_eur_mwh
            self.baseline_grid_kw = baseline_grid_kw
            self._last_t = time.monotonic()

    def stop(self) -> dict:
        with self._lock:
            snap = self._snapshot_locked()
            self.active = False
            return snap

    # --- Aggiornamento (chiamato all'arrivo di nuova telemetria) --------------
    def update(self, current_total_grid_kw: float) -> None:
        with self._lock:
            if not self.active:
                return
            now = time.monotonic()
            dt_h = (now - self._last_t) / 3600.0
            self._last_t = now
            self.delivered_kw = max(0.0, self.baseline_grid_kw - current_total_grid_kw)
            self.energy_kwh += self.delivered_kw * dt_h

    # --- Snapshot -------------------------------------------------------------
    def _snapshot_locked(self) -> dict:
        energy_mwh = self.energy_kwh / 1000.0
        value = energy_mwh * self.price_eur_mwh
        return {
            "active": self.active,
            "event_id": self.event_id,
            "price_eur_mwh": round(self.price_eur_mwh, 2),
            "baseline_grid_kw": round(self.baseline_grid_kw, 1),
            "delivered_kw": round(self.delivered_kw, 1),
            "energy_kwh": round(self.energy_kwh, 4),
            "value_eur": round(value, 4),
            "company_eur": round(value * config.SPLIT_COMPANY, 4),
            "platform_eur": round(value * config.SPLIT_PLATFORM, 4),
        }

    def snapshot(self) -> dict:
        with self._lock:
            return self._snapshot_locked()
