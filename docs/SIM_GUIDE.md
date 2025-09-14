# Simulation & Observation
Start:
  docker compose up --build
Scale C:
  docker compose up -d --scale c=21

Test Device Services Directly:
  curl "http://localhost:8002/health"  # Fast device
  curl "http://localhost:8003/health"  # Slow device (3.3x multiplier)
  curl "http://localhost:8002/do_work?device_id=dev-1&ms=3000&mode=normal"  # ~3s (normal)
  curl "http://localhost:8003/do_work?device_id=dev-1&ms=3000&mode=normal"  # ~10s (slow)

Send E2E traffic (A→B→C→D):
  curl "http://localhost:8080/process?device_id=dev-fast-1&ms=3000&mode=normal"   # Routes to fast device (~3s)
  curl "http://localhost:8080/process?device_id=dev-slow-1&ms=3000&mode=normal"   # Routes to slow device (~10s)
  curl "http://localhost:8080/process?device_id=dev-hang-1&mode=hang"             # Hangs until C timeout (~3s)

Grafana:
  http://localhost:3000 → Dashboards → Golden Signals: B & C, C Availability

Tempo (Explore):
  { service.name="svc-b", span.duration > 5s }
  { name="/do_work", status!="" }  # C→D ~3s DEADLINE_EXCEEDED when hang

Automated Testing:
  ./test/quick-test.sh           # Basic functionality (2 min)
  ./test/run-all-tests.sh        # Full test suite (20+ min)
  python3 test/simple-load.py --testcase 10  # Retry storm test