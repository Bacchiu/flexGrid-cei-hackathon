"""Writer InfluxDB (time-series che alimenta Grafana).

Best-effort: se InfluxDB è disabilitato o non raggiungibile, le scritture
vengono ignorate senza far cadere l'aggregatore (demo-resilient).
"""
from __future__ import annotations

import logging

from . import config
from .models import Telemetry

log = logging.getLogger("cloud.influx")

_write_api = None
_client = None


def init() -> None:
    global _client, _write_api
    if not config.INFLUX_ENABLED:
        log.info("InfluxDB disabilitato (INFLUX_ENABLED=false)")
        return
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        _client = InfluxDBClient(
            url=config.INFLUX_URL, token=config.INFLUX_TOKEN, org=config.INFLUX_ORG
        )
        _write_api = _client.write_api(write_options=SYNCHRONOUS)
        log.info("InfluxDB pronto: %s bucket=%s", config.INFLUX_URL, config.INFLUX_BUCKET)
    except Exception as exc:  # noqa: BLE001
        log.warning("InfluxDB non inizializzato (%s): le scritture saranno ignorate", exc)


def _write(record) -> None:
    if _write_api is None:
        return
    try:
        _write_api.write(bucket=config.INFLUX_BUCKET, org=config.INFLUX_ORG, record=record)
    except Exception as exc:  # noqa: BLE001
        log.debug("Scrittura InfluxDB fallita: %s", exc)


def write_telemetry(t: Telemetry) -> None:
    from influxdb_client import Point

    point = (
        Point("telemetry")
        .tag("site_id", t.site_id)
        .field("pv_kw", float(t.pv_kw))
        .field("ev_kw", float(t.ev_kw))
        .field("hvac_kw", float(t.hvac_kw))
        .field("critical_kw", float(t.critical_kw))
        .field("grid_kw", float(t.grid_kw))
    )
    _write(point)


def write_economics(snapshot: dict) -> None:
    from influxdb_client import Point

    point = (
        Point("economics")
        .tag("event_id", str(snapshot.get("event_id") or "none"))
        .field("delivered_kw", float(snapshot["delivered_kw"]))
        .field("energy_kwh", float(snapshot["energy_kwh"]))
        .field("value_eur", float(snapshot["value_eur"]))
        .field("company_eur", float(snapshot["company_eur"]))
        .field("platform_eur", float(snapshot["platform_eur"]))
    )
    _write(point)


def close() -> None:
    if _client is not None:
        try:
            _client.close()
        except Exception:  # noqa: BLE001
            pass
