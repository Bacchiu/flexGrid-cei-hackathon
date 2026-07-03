"""Configurazione dell'Edge Controller, tutta via variabili d'ambiente."""
from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# Identità della sede (namespace edge → replicabile: una sede = una replica)
SITE_ID = os.getenv("SITE_ID", "azienda-demo")

# Broker MQTT (condiviso tra edge e cloud)
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = _i("MQTT_PORT", 1883)

# Topic: telemetria ↑ (edge→cloud), comandi ↓ (cloud→edge)
TOPIC_TELEMETRY = f"energy/{SITE_ID}/telemetry"
TOPIC_COMMAND = f"energy/{SITE_ID}/command"

# Cadenza di pubblicazione della telemetria (secondi)
PUBLISH_INTERVAL_S = _f("PUBLISH_INTERVAL_S", 2.0)

# --- Parametri asset della sede (default = Caso_Base_Demo.md) ---
PV_PEAK_KW = _f("PV_PEAK_KW", 200.0)        # fotovoltaico di picco
PV_FACTOR = _f("PV_FACTOR", 0.80)           # frazione del picco a T0 (pomeriggio sereno)

EV_CHARGERS = _i("EV_CHARGERS", 10)         # colonnine totali
EV_ACTIVE = _i("EV_ACTIVE", 8)              # colonnine in carica a T0
EV_KW_PER_CHARGER = _f("EV_KW_PER_CHARGER", 22.0)   # potenza nominale
EV_FLOOR_KW_PER_CHARGER = _f("EV_FLOOR_KW_PER_CHARGER", 7.0)  # smart-charging minimo

HVAC_BASE_KW = _f("HVAC_BASE_KW", 100.0)    # HVAC nominale
HVAC_MAX_REDUCTION_PCT = _f("HVAC_MAX_REDUCTION_PCT", 15.0)  # modulazione massima

CRITICAL_KW = _f("CRITICAL_KW", 200.0)      # carichi critici: MAI toccati

# Rumore per rendere i grafici "vivi" (frazione ±)
NOISE_PCT = _f("NOISE_PCT", 0.02)
