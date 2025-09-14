# REQUIREMENTS
- B: connect timeout ~0.35s, request timeout ≤3s; no built-in connect retry (baseline); expose b_* metrics
- C: semaphore(1), device timeout ~3s, no retries; expose c_* metrics + availability gauges
- D: per-device mutex; modes: normal/hang/error