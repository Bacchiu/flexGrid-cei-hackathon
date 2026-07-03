"""Edge Controller + Asset Simulator (namespace `edge`).

- Pubblica la telemetria della sede su MQTT a intervalli regolari.
- Sottoscrive i comandi di modulazione dal cloud e li applica al simulatore.
- Espone endpoint FastAPI di health/stato per ispezione manuale.
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from fastapi import FastAPI

from . import config
from .models import Command
from .simulator import AssetSimulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s edge %(levelname)s %(message)s")
log = logging.getLogger("edge")

simulator = AssetSimulator()
_latest: dict = {}


def _on_connect(client, userdata, flags, reason_code, properties=None):
    log.info("MQTT connesso (rc=%s), sottoscrivo %s", reason_code, config.TOPIC_COMMAND)
    client.subscribe(config.TOPIC_COMMAND)


def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        cmd = Command(**payload)
    except Exception as exc:  # noqa: BLE001 - demo: log e ignora payload malformati
        log.warning("Comando ignorato (%s): %s", exc, msg.payload[:200])
        return
    simulator.apply_command(cmd)
    log.info(
        "Comando applicato event=%s ev_setpoint=%s hvac_-%s%% dur=%ss",
        cmd.event_id, cmd.ev_setpoint_kw_per_charger, cmd.hvac_reduction_pct, cmd.duration_s,
    )


def _build_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"edge-{config.SITE_ID}")
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    return client


async def _publish_loop(client: mqtt.Client) -> None:
    while True:
        sample = simulator.sample()
        global _latest
        _latest = sample.model_dump()
        client.publish(config.TOPIC_TELEMETRY, sample.model_dump_json())
        await asyncio.sleep(config.PUBLISH_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = _build_client()
    # connect_async + loop_start: la connessione viene ritentata anche se il
    # broker non è ancora pronto all'avvio.
    client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
    client.loop_start()
    task = asyncio.create_task(_publish_loop(client))
    log.info("Edge avviato: site=%s broker=%s:%s", config.SITE_ID, config.MQTT_HOST, config.MQTT_PORT)
    try:
        yield
    finally:
        task.cancel()
        client.loop_stop()
        client.disconnect()


app = FastAPI(title="Edge Controller", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "site_id": config.SITE_ID}


@app.get("/state")
def state() -> dict:
    return simulator.state()


@app.get("/telemetry")
def telemetry() -> dict:
    return _latest or {"detail": "nessun campione ancora"}
