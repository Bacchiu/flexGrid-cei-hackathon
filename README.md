# Smart Enterprise Energy Orchestrator

**Track 2 [COP-PILOT] — OpenSlice & Distributed Energy Services** · Cloud-Edge-IoT Open-Source Hackathon (Cagliari).

A B2B **Virtual Power Plant (VPP)** aggregator that modulates a company's flexible loads
(**PV + EV chargers + HVAC**) in response to a **Terna** grid signal — without ever touching
critical loads — and splits the revenue **80/20**. **OpenSlice** orchestrates the services along
the *computing continuum* (edge ↔ cloud). Everything is designed to **run on a single laptop**.

> Background docs: [ARCHITETTURA.md](ARCHITETTURA.md) · [Caso_Base_Demo.md](Caso_Base_Demo.md) · [Stack_Tecnologico.md](Stack_Tecnologico.md) · [Traccia2_OpenSlice_Kubernetes.md](Traccia2_OpenSlice_Kubernetes.md) · [PITCH.md](PITCH.md)

---

## What it does

A modern company is both a consumer and a producer of energy (a *prosumer*). The Edge Controller
groups its assets into three logical classes:

| Asset class | Examples | Behaviour under a grid event |
|---|---|---|
| **Local generation** | Rooftop photovoltaics (PV) | Always maximized — free, zero-carbon self-consumption. |
| **Flexible loads** | EV chargers, HVAC | Modulated on demand: EV **smart charging** first (e.g. 22 → 7 kW per charger), then HVAC (~10–15%). |
| **Critical loads** | Servers, security, production lines | **Never touched** — business continuity is guaranteed. |

When Terna detects stress on the national grid it emits an activation signal. The **Aggregator**
computes how much flexibility each site can offer, sends modulation **commands** down to the
edge, and the site drops its grid draw in seconds. The **economic value** of the delivered
flexibility is settled **80% to the company / 20% to the platform** (SaaS/orchestration fee).

**The role of OpenSlice:** it treats the distributed edge↔cloud infrastructure as a catalog of
digital services. Activating flexibility for a new site = **one service order on the catalog**,
which instantiates another edge node. *"Adding a site is a click on the catalog."*

---

## Architecture

```
                      ┌──────────── namespace: cloud ─────────────┐
  Terna button ─────► │  AGGREGATOR / DISPATCH  (FastAPI :8000)    │
  (HTTP)              │   • generates the Terna signal            │
                      │   • dispatch EV → HVAC (never critical)    │
                      │   • computes the € 80/20 split             │
                      │   • writes telemetry to InfluxDB          │
                      │        InfluxDB ◄── Grafana (:3000)        │
                      └───────────────▲──────────┬─────────────────┘
                            telemetry │  commands │   (MQTT)
                      ┌───────────────┴──────────▼─────────────────┐
                      │  namespace: edge — EDGE CONTROLLER (FastAPI)│
                      │   ☀ PV  🔌 EV  ❄ HVAC  🏭 critical (simulated)│
                      │   (replicas = more company sites)           │
                      └────────────────────────────────────────────┘
                 Mosquitto (MQTT) — broker shared across namespaces
```

### Data contracts (MQTT)

**Telemetry** `energy/<site_id>/telemetry` (edge → cloud):
```json
{ "site_id": "azienda-demo", "ts": "…Z", "pv_kw": 160, "ev_kw": 176, "hvac_kw": 100, "critical_kw": 200, "grid_kw": 316 }
```
**Command** `energy/<site_id>/command` (cloud → edge):
```json
{ "site_id": "azienda-demo", "event_id": "terna-…", "ev_setpoint_kw_per_charger": 7, "hvac_reduction_pct": 10, "duration_s": 900 }
```

---

## Setup

### Prerequisites
- **Docker** (with Compose) — the only requirement for the demo path.
- *For Kubernetes:* **kind** *or* **minikube** + `kubectl`.
- *For OpenSlice:* an OpenSlice install + **ArgoCD** on the target cluster (see below).

### Quick start — docker-compose (demo path)

```bash
docker compose up --build
```

This brings up the full stack on your laptop: Mosquitto + InfluxDB + Grafana + the two services.

| Service | URL | Credentials |
|---|---|---|
| **Control panel** (Terna button) | http://localhost:8001 | — |
| **Grafana** dashboard | http://localhost:3000 | `admin` / `admin` |
| InfluxDB | http://localhost:8086 | org `cei`, bucket `energy`, token `dev-token` |

> Multi-site (scalability demo): `docker compose --profile multi up --build` adds a second site (`sede-2`).

### The demo scene
1. **At rest:** grid draw ~**316 kW**, revenue at €0.
2. On the panel click **"Event: −130 kW / 15 min"** — or:
   ```bash
   curl -X POST localhost:8001/terna-event \
     -H 'content-type: application/json' \
     -d '{"reduction_kw":130,"duration_s":900}'
   ```
3. Within seconds: **EV 176 → 56 kW**, **HVAC 100 → 90 kW**, **critical unchanged**.
4. The grid-draw curve drops **316 → 186 kW**; the **€ counter rises** (company 80% / platform 20%).
5. When the event expires (or you click **"Release"**) everything returns to the baseline.

---

## Kubernetes (track requirement — 2 namespaces: edge / cloud)

```bash
# 1) Local cluster
kind create cluster --name cei            # or: minikube start

# 2) Build the local images
docker build -t edge-controller:dev ./edge
docker build -t aggregator:dev       ./cloud

# 3) Load the images into the cluster
kind load docker-image edge-controller:dev aggregator:dev --name cei
#   minikube:  minikube image load edge-controller:dev && minikube image load aggregator:dev

# 4) Full deploy (namespaces + broker + influx + grafana + services)
kubectl apply -k deploy

# 5) Status
kubectl get pods -A

# 6) Access
kubectl port-forward -n cloud svc/aggregator 8000:8000   # Terna panel → localhost:8000
kubectl port-forward -n cloud svc/grafana    3000:3000   # Grafana     → localhost:3000
#   (or via NodePort: aggregator :30800, grafana :30300)
```

**Add a site** (the OpenSlice story — "one click on the catalog" = one new service order):
```bash
kubectl apply -f deploy/k8s/51-edge-sede2.yaml
```

---

## Deploy via Helm + OpenSlice

The stack is packaged as a self-contained **Helm chart** in
[deploy/helm/energy-orchestrator/](deploy/helm/energy-orchestrator/) — this is the artifact OpenSlice deploys.

**Direct Helm** (fallback, or to test the chart without OpenSlice):
```bash
helm install eo deploy/helm/energy-orchestrator            # whole stack (edge + cloud)
helm upgrade eo deploy/helm/energy-orchestrator \
  --set-json 'sites=[{"name":"azienda-demo"},{"name":"sede-2","env":{"EV_ACTIVE":"6"}}]'   # +1 site
```

**Via OpenSlice** — mechanism (ETSI OSL, *Helm Chart Deployment as a Service*): OpenSlice does
**not** call `helm` directly. It creates an **ArgoCD Application**
([deploy/openslice/argocd-application.yaml](deploy/openslice/argocd-application.yaml), the `_CR_SPEC`);
ArgoCD syncs the chart from the Git repo, and OpenSlice monitors `status.health.status`.

Service Design onboarding, in short:
1. **RFSS** (Resource-Facing Service Spec) bound to the ArgoCD `Application` resource type:
   `_CR_SPEC` = the `argocd-application.yaml` (with your `repoURL`), `_CR_CHECK_FIELD` = `status.health.status`,
   states mapped `Healthy → ACTIVE`, `Progressing → RESERVED`, `Degraded/Missing → TERMINATED`.
2. **CFSS** (Customer-Facing Service Spec) wrapping the RFSS.
3. **Publish** the CFSS in a Category/Catalog so it becomes orderable.
4. **Service Order** → OpenSlice creates the Application → ArgoCD deploys the chart → the service
   appears in the Resource Inventory.

Verify the pattern without the OpenSlice UI (plain ArgoCD → Helm flow):
```bash
kubectl apply -f deploy/openslice/argocd-application.yaml    # requires ArgoCD on the cluster
kubectl -n argocd get applications energy-orchestrator -w    # wait for Healthy
```
> For the Definition of Done it is enough to show **≥1 service deployed through OpenSlice**; the rest
> can be pre-deployed with `kubectl apply -k deploy` as a fallback to de-risk the demo.
> Docs: <https://osl.etsi.org/documentation/latest/service_design/examples/jenkins_helm_install_aas/jenkins_helm_install_aas/>

---

## Project structure

```
edge/                    Edge Controller + Asset Simulator (FastAPI + MQTT)
  app/{config,models,simulator,main}.py
cloud/                   Aggregator / Dispatch Engine (FastAPI + MQTT + InfluxDB)
  app/{config,models,dispatch,economics,influx,store,main}.py
deploy/
  mosquitto/mosquitto.conf
  grafana/provisioning/… + grafana/dashboards/energy.json    (single source: compose & k8s)
  k8s/*.yaml               manifests (namespaces, broker, influx, grafana, services)
  helm/energy-orchestrator/  Helm chart (the OpenSlice-deployed artifact)
  openslice/argocd-application.yaml   the _CR_SPEC used by OpenSlice
  kustomization.yaml        kubectl apply -k deploy
docker-compose.yml       demo stack on a single laptop
```

---

## Configuration (environment variables)

All services are configured via env vars — no hard-coded secrets.

**Edge Controller**

| Variable | Default | Meaning |
|---|---|---|
| `SITE_ID` | `azienda-demo` | site identity (one site = one replica) |
| `MQTT_HOST` / `MQTT_PORT` | `localhost` / `1883` | shared broker |
| `PUBLISH_INTERVAL_S` | `2.0` | telemetry publish cadence (s) |
| `PV_PEAK_KW` / `PV_FACTOR` | `200` / `0.80` | PV peak and fraction at T0 |
| `EV_CHARGERS` / `EV_ACTIVE` | `10` / `8` | total / currently-charging chargers |
| `EV_KW_PER_CHARGER` / `EV_FLOOR_KW_PER_CHARGER` | `22` / `7` | nominal / smart-charging floor |
| `HVAC_BASE_KW` / `HVAC_MAX_REDUCTION_PCT` | `100` / `15` | nominal HVAC / max modulation |
| `CRITICAL_KW` | `200` | critical loads — never touched |

**Aggregator / Dispatch**

| Variable | Default | Meaning |
|---|---|---|
| `MQTT_HOST` / `MQTT_PORT` | `localhost` / `1883` | shared broker |
| `INFLUX_URL` / `INFLUX_TOKEN` / `INFLUX_ORG` / `INFLUX_BUCKET` | `…:8086` / `dev-token` / `cei` / `energy` | InfluxDB |
| `INFLUX_ENABLED` | `true` | toggle time-series writes |
| `SPLIT_COMPANY` / `SPLIT_PLATFORM` | `0.80` / `0.20` | revenue split |
| `DEFAULT_PRICE_EUR_MWH` | `400` | zonal price used for settlement |

---

## Aggregator API

| Method | Path | Description |
|---|---|---|
| GET | `/` | control panel (Terna button) |
| POST | `/terna-event` | start an event `{reduction_kw, duration_s, price_eur_mwh?}` |
| POST | `/terna-event/release` | manual release |
| GET | `/state` | aggregated state + economics + active event |
| GET | `/sites` | live sites |
| GET | `/health` | health check |