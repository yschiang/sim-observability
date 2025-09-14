# Sim Observability – Full Bundle (Baseline + Mixed Traffic Add-on)

## Quickstart (baseline)
unzip sim-observability-full-bundle.zip -d sim-observability-full-bundle
cd sim-observability-full-bundle
docker compose up --build
docker compose up -d --scale c=21

Try:
  curl "http://localhost:8080/process?device_id=dev-1&ms=3000&mode=normal"
  curl "http://localhost:8080/process?device_id=dev-slow-1&ms=10000&mode=normal"
  curl "http://localhost:8080/process?device_id=dev-hang-1&mode=hang"

UIs:
  Grafana:     http://localhost:3000  (Dashboards → Golden Signals / C Availability)
  Prometheus:  http://localhost:9090
  Tempo Query: http://localhost:3200

## Mixed Traffic Add-on
Inside `addons/mixed-traffic/`, you’ll find:
- docker-compose.override.yml to enable a realistic mix (15% slow, 5% hang by default)
- d/app.py (enhanced device sim with SLOW_DEVICES/HANG_DEVICES/PROB_SLOW/PROB_HANG)
- load/generator.py (tiny async load tool)

To use the add-on:
  # from repo root
  cp -r addons/mixed-traffic/* .
  docker compose build d
  docker compose up -d
  docker compose up -d --scale c=21
  pip install -r load/requirements.txt
  python3 load/generator.py --rate 10 --duration 120 --normal 80 --slow 3 --hang 1