# (Paste to Claude) System / Task

# Current State Overview
- A(REST) → B(REST) → C(CORBA; simulated as gRPC, single concurrency) → Devices (no proxy)
- C→Devices ~3s typical, up to 10s. If device hangs, only C’s own timeout ends the call.
- Goals: avoid retry storms; visualize E2E & per-hop latency; quantify C availability.


Problems to solve:
- Retry storm containment, E2E/per-hop observability, C availability.


# REQUIREMENTS
- B: connect timeout ~0.35s, request timeout ≤3s; no built-in connect retry (baseline); expose b_* metrics
- C: semaphore(1), device timeout ~3s, no retries; expose c_* metrics + availability gauges
- D: per-device mutex; modes: normal/hang/error



# Simulation & Observation
Start:
  docker compose up --build
Scale C:
  docker compose up -d --scale c=21

Send traffic:
  curl "http://localhost:8080/process?device_id=dev-1&ms=3000&mode=normal"
  curl "http://localhost:8080/process?device_id=dev-slow-1&ms=10000&mode=normal"
  curl "http://localhost:8080/process?device_id=dev-hang-1&mode=hang"

Grafana:
  http://localhost:3000 → Dashboards → Golden Signals: B & C, C Availability

Tempo (Explore):
  { service.name="svc-b", span.duration > 5s }
  { name="/do_work", status!="" }  # C→D ~3s DEADLINE_EXCEEDED when hang



# Claude Rules
- Don’t alter timeout/retry semantics without updating docs.
- Keep C single concurrency; B fails fast on busy.
- Tracing must be enabled; metrics must expose Golden Signals.
- /health must not hit downstream.


Deliverables:
- Runnable compose stack (B/C/D + Tempo + Prometheus + Grafana)
- Pre-provisioned Grafana datasources & dashboards
- Docs (OVERVIEW/REQUIREMENTS/SIM_GUIDE/CLAUDE_RULES)