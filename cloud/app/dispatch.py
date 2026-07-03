"""Motore di dispatch: dato il segnale Terna, calcola i comandi per sede.

Scala di priorità (Caso_Base_Demo.md §5):
  1. EV smart charging  (impatto zero → si usa per primo)
  2. HVAC               (modulazione limitata, solo se serve)
  3. Carichi critici    (MAI toccati)
  4. FV                 (sempre al massimo autoconsumo)

La richiesta viene ripartita tra le sedi in proporzione alla flessibilità
disponibile di ciascuna; dentro la sede si preleva prima da EV, poi da HVAC.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from .models import Command, Telemetry


@dataclass
class SiteFlex:
    site_id: str
    ev_kw: float
    hvac_kw: float
    n_active: int
    ev_flex_kw: float    # kW riducibili da EV (fino allo smart-charging minimo)
    hvac_flex_kw: float  # kW riducibili da HVAC (fino al massimo consentito)

    @property
    def total_flex_kw(self) -> float:
        return self.ev_flex_kw + self.hvac_flex_kw


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def site_flex(t: Telemetry) -> SiteFlex:
    n_active = max(0, round(t.ev_kw / config.EV_KW_PER_CHARGER))
    ev_floor = n_active * config.EV_FLOOR_KW_PER_CHARGER
    ev_flex = max(0.0, t.ev_kw - ev_floor)
    hvac_flex = max(0.0, t.hvac_kw * config.HVAC_MAX_REDUCTION_PCT / 100.0)
    return SiteFlex(t.site_id, t.ev_kw, t.hvac_kw, n_active, ev_flex, hvac_flex)


def plan_dispatch(
    telemetries: list[Telemetry], event_id: str, reduction_kw: float, duration_s: int
) -> tuple[list[Command], list[dict]]:
    """Ritorna (comandi da inviare, riepilogo allocazione per sede)."""
    flexes = [site_flex(t) for t in telemetries]
    total_flex = sum(f.total_flex_kw for f in flexes)

    commands: list[Command] = []
    summary: list[dict] = []

    for f in flexes:
        if total_flex <= 0:
            target = 0.0
        else:
            target = min(reduction_kw * (f.total_flex_kw / total_flex), f.total_flex_kw)

        ev_red = min(target, f.ev_flex_kw)
        hvac_red = min(target - ev_red, f.hvac_flex_kw)

        n_active = max(1, f.n_active)
        ev_setpoint = _clamp(
            config.EV_KW_PER_CHARGER - ev_red / n_active,
            config.EV_FLOOR_KW_PER_CHARGER,
            config.EV_KW_PER_CHARGER,
        )
        hvac_pct = _clamp(
            (hvac_red / f.hvac_kw * 100.0) if f.hvac_kw > 0 else 0.0,
            0.0,
            config.HVAC_MAX_REDUCTION_PCT,
        )

        commands.append(
            Command(
                site_id=f.site_id,
                event_id=event_id,
                ev_setpoint_kw_per_charger=round(ev_setpoint, 2),
                hvac_reduction_pct=round(hvac_pct, 2),
                duration_s=duration_s,
            )
        )
        summary.append(
            {
                "site_id": f.site_id,
                "target_kw": round(target, 1),
                "ev_reduction_kw": round(ev_red, 1),
                "hvac_reduction_kw": round(hvac_red, 1),
                "ev_setpoint_kw_per_charger": round(ev_setpoint, 2),
                "hvac_reduction_pct": round(hvac_pct, 2),
            }
        )

    return commands, summary


def release_commands(site_ids: list[str], event_id: str) -> list[Command]:
    """Comandi di rilascio: tutto torna al nominale."""
    return [
        Command(
            site_id=sid,
            event_id=event_id,
            ev_setpoint_kw_per_charger=config.EV_KW_PER_CHARGER,
            hvac_reduction_pct=0.0,
            duration_s=0,
        )
        for sid in site_ids
    ]
