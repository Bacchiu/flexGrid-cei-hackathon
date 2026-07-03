"""Configurazione dell'Aggregator/Dispatch Engine, via variabili d'ambiente."""
from __future__ import annotations

import os


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# Broker MQTT (condiviso)
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = _i("MQTT_PORT", 1883)

# Sottoscrizione a TUTTE le sedi: energy/<site_id>/telemetry
TOPIC_TELEMETRY_WILDCARD = "energy/+/telemetry"


def command_topic(site_id: str) -> str:
    return f"energy/{site_id}/command"


# --- InfluxDB (time-series) ---
INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "dev-token")
INFLUX_ORG = os.getenv("INFLUX_ORG", "cei")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "energy")
INFLUX_ENABLED = os.getenv("INFLUX_ENABLED", "true").lower() == "true"

# --- Modello economico ---
SPLIT_COMPANY = _f("SPLIT_COMPANY", 0.80)   # quota azienda
SPLIT_PLATFORM = _f("SPLIT_PLATFORM", 0.20)  # quota piattaforma
DEFAULT_PRICE_EUR_MWH = _f("DEFAULT_PRICE_EUR_MWH", 400.0)

# --- Limiti asset per la logica di dispatch (coerenti con l'edge) ---
EV_KW_PER_CHARGER = _f("EV_KW_PER_CHARGER", 22.0)
EV_FLOOR_KW_PER_CHARGER = _f("EV_FLOOR_KW_PER_CHARGER", 7.0)
HVAC_MAX_REDUCTION_PCT = _f("HVAC_MAX_REDUCTION_PCT", 15.0)

# Considera "stale" una sede che non pubblica da questo tempo (s)
SITE_STALE_S = _f("SITE_STALE_S", 15.0)
