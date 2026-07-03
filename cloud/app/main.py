"""Aggregator / Dispatch Engine (namespace `cloud`).

- Sottoscrive la telemetria di tutte le sedi (MQTT), la archivia e la scrive su InfluxDB.
- Su segnale Terna calcola la ripartizione, invia i comandi e contabilizza i € (80/20).
- Espone API + una pagina di controllo (il "pulsante Terna" della demo).
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from . import config, influx
from .dispatch import plan_dispatch, release_commands
from .economics import EconomicsAccumulator
from .models import TernaEvent
from .models import Telemetry
from .store import StateStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s cloud %(levelname)s %(message)s")
log = logging.getLogger("cloud")

store = StateStore()
econ = EconomicsAccumulator()
_client: mqtt.Client | None = None
_release_task: asyncio.Task | None = None
_loop: asyncio.AbstractEventLoop | None = None
_active_event: dict | None = None


# --- MQTT -------------------------------------------------------------------
def _on_connect(client, userdata, flags, reason_code, properties=None):
    log.info("MQTT connesso (rc=%s), sottoscrivo %s", reason_code, config.TOPIC_TELEMETRY_WILDCARD)
    client.subscribe(config.TOPIC_TELEMETRY_WILDCARD)


def _on_message(client, userdata, msg):
    try:
        t = Telemetry(**json.loads(msg.payload.decode()))
    except Exception as exc:  # noqa: BLE001
        log.warning("Telemetria ignorata (%s)", exc)
        return
    store.update(t)
    influx.write_telemetry(t)
    # Contabilizza sull'evento attivo usando il prelievo totale corrente
    if econ.active:
        econ.update(store.total_grid_kw())
        influx.write_economics(econ.snapshot())


def _build_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cloud-aggregator")
    client.on_connect = _on_connect
    client.on_message = _on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    return client


def _publish_commands(commands) -> None:
    assert _client is not None
    for cmd in commands:
        _client.publish(config.command_topic(cmd.site_id), cmd.model_dump_json())


# --- Ciclo di vita evento ---------------------------------------------------
def _do_release() -> dict:
    global _active_event
    sites = store.site_ids()
    if _active_event:
        _publish_commands(release_commands(sites, _active_event["event_id"]))
    snap = econ.stop()
    if snap.get("event_id"):
        influx.write_economics(snap)
    result = {"released": True, "economics": snap, "event": _active_event}
    _active_event = None
    log.info("Evento rilasciato: %s", snap)
    return result


async def _auto_release_after(duration_s: int) -> None:
    try:
        await asyncio.sleep(duration_s)
        _do_release()
    except asyncio.CancelledError:  # rilascio manuale anticipato
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _client, _loop
    _loop = asyncio.get_running_loop()
    influx.init()
    _client = _build_client()
    _client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
    _client.loop_start()
    log.info("Cloud avviato: broker=%s:%s", config.MQTT_HOST, config.MQTT_PORT)
    try:
        yield
    finally:
        _client.loop_stop()
        _client.disconnect()
        influx.close()


app = FastAPI(title="Aggregator / Dispatch Engine", lifespan=lifespan)


# --- API --------------------------------------------------------------------
@app.get("/health")
def health() -> dict:
    return {"status": "ok", "n_sites": store.summary()["n_sites"]}


@app.get("/state")
def state() -> dict:
    return {
        "aggregate": store.summary(),
        "economics": econ.snapshot(),
        "active_event": _active_event,
    }


@app.get("/sites")
def sites() -> dict:
    return {"site_ids": store.site_ids(), "live": store.summary()["n_sites"]}


@app.post("/terna-event")
async def terna_event(event: TernaEvent) -> dict:
    global _active_event, _release_task
    if _active_event or econ.active:
        raise HTTPException(status_code=409, detail="Evento già attivo: rilascia prima di avviarne un altro")
    live = store.live_sites()
    if not live:
        raise HTTPException(status_code=409, detail="Nessuna sede attiva: avvia almeno un edge")

    event_id = "terna-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    price = event.price_eur_mwh if event.price_eur_mwh is not None else config.DEFAULT_PRICE_EUR_MWH
    baseline = store.total_grid_kw()

    commands, allocation = plan_dispatch(live, event_id, event.reduction_kw, event.duration_s)
    _publish_commands(commands)
    econ.start(event_id, price, baseline)

    _active_event = {
        "event_id": event_id,
        "reduction_kw": event.reduction_kw,
        "duration_s": event.duration_s,
        "price_eur_mwh": price,
        "baseline_grid_kw": round(baseline, 1),
        "allocation": allocation,
    }

    # Auto-rilascio programmato
    if _release_task and not _release_task.done():
        _release_task.cancel()
    _release_task = asyncio.create_task(_auto_release_after(event.duration_s))

    log.info("Evento Terna avviato: %s -%skW/%ss @ %s€/MWh su %d sedi",
             event_id, event.reduction_kw, event.duration_s, price, len(live))
    return _active_event


@app.post("/terna-event/release")
async def terna_release() -> dict:
    global _release_task
    if not _active_event:
        raise HTTPException(status_code=409, detail="Nessun evento attivo")
    if _release_task and not _release_task.done():
        _release_task.cancel()
    return _do_release()


# --- Pagina di controllo (il "pulsante Terna") ------------------------------
@app.get("/", response_class=HTMLResponse)
def control_panel() -> str:
    return CONTROL_HTML


CONTROL_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Terna Signal Control</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 1rem;color:#111}
 h1{font-size:1.3rem} button{font-size:1rem;padding:.6rem 1rem;margin:.3rem;border:0;border-radius:8px;cursor:pointer}
 .fire{background:#e11d48;color:#fff} .rel{background:#334155;color:#fff}
 pre{background:#0f172a;color:#e2e8f0;padding:1rem;border-radius:8px;overflow:auto;font-size:.85rem}
 .row{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
 .kpi{background:#f1f5f9;border-radius:8px;padding:.8rem 1rem;flex:1;min-width:140px}
 .kpi b{display:block;font-size:1.4rem}
</style></head><body>
<h1>Terna Signal Control Panel</h1>
<p>Smart Enterprise Energy Orchestrator</p>
<div class="row">
 <button class="fire" onclick="fire(130,900)">Trigger 130 kW for 15 min</button>
 <button class="fire" onclick="fire(260,900)">Trigger 260 kW for 15 min</button>
 <button class="rel" onclick="release()">Release</button>
</div>
<div class="row">
 <div class="kpi">Grid draw<b id="grid">0 kW</b></div>
 <div class="kpi">Flexibility<b id="deliv">0 kW</b></div>
 <div class="kpi">Company revenue (80%)<b id="company">0 EUR</b></div>
 <div class="kpi">Platform revenue (20%)<b id="plat">0 EUR</b></div>
</div>
<pre id="out">loading state</pre>
<script>
async function fire(kw,dur){
 await fetch('/terna-event',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({reduction_kw:kw,duration_s:dur})});
}
async function release(){ await fetch('/terna-event/release',{method:'POST'}); }
async function tick(){
 try{
  const s=await (await fetch('/state')).json();
  document.getElementById('grid').textContent=(s.aggregate.total_grid_kw??0)+' kW';
  document.getElementById('deliv').textContent=(s.economics.delivered_kw??0)+' kW';
  document.getElementById('company').textContent=(s.economics.company_eur??0).toFixed(2)+' EUR';
  document.getElementById('plat').textContent=(s.economics.platform_eur??0).toFixed(2)+' EUR';
  document.getElementById('out').textContent=JSON.stringify(s,null,2);
 }catch(e){ document.getElementById('out').textContent='error: '+e; }
}
setInterval(tick,1000); tick();
</script></body></html>"""
