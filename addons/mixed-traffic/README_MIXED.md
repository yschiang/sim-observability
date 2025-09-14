# Mixed Traffic Add-on (Optional)

Copy everything in this folder to repo root to enable a realistic mix:
- 15% slow devices, 5% hang by default (configurable)
- Enhanced D app with SLOW_DEVICES / HANG_DEVICES / PROB_SLOW / PROB_HANG
- Tiny async load generator to send mixed traffic to B

Usage:
  cp -r addons/mixed-traffic/* .
  docker compose build d
  docker compose up -d
  docker compose up -d --scale c=21
  pip install -r load/requirements.txt
  python3 load/generator.py --rate 10 --duration 120 --normal 80 --slow 3 --hang 1