from fastapi import FastAPI, HTTPException
import asyncio, os, random
from typing import Dict, Set
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import start_http_server, Gauge, Counter
from otel_init import init_tracing

init_tracing("svc-d")
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)

start_http_server(9100)
g_inflight = Gauge("d_inflight", "requests in flight", ["device"])
c_mode = Counter("d_mode_total", "mode by decision", ["mode"])

SLOW_MS = int(os.getenv("SLOW_MS", "10000"))
DEFAULT_NORMAL_MS = int(os.getenv("DEFAULT_NORMAL_MS", "3000"))
SLOW_DEVICES: Set[str] = set([x.strip() for x in os.getenv("SLOW_DEVICES", "").split(",") if x.strip()])
HANG_DEVICES: Set[str] = set([x.strip() for x in os.getenv("HANG_DEVICES", "").split(",") if x.strip()])
PROB_SLOW = float(os.getenv("PROB_SLOW", "0.0"))
PROB_HANG = float(os.getenv("PROB_HANG", "0.0"))

locks: Dict[str, asyncio.Lock] = {}

@app.get("/health")
async def health():
    return {"ok": True, "slow_devices": sorted(list(SLOW_DEVICES)), "hang_devices": sorted(list(HANG_DEVICES))}

def decide_mode(device_id: str, query_mode: str | None):
    if query_mode in ("normal","slow","hang","error"):
        return query_mode
    if device_id in HANG_DEVICES:
        return "hang"
    if device_id in SLOW_DEVICES:
        return "slow"
    r = random.random()
    if r < PROB_HANG:
        return "hang"
    if r < PROB_HANG + PROB_SLOW:
        return "slow"
    return "normal"

@app.get("/do_work")
async def do_work(device_id: str, ms: int | None = None, mode: str | None = None):
    mode = decide_mode(device_id, mode)
    c_mode.labels(mode=mode).inc()

    lock = locks.setdefault(device_id, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=429, detail="device busy")

    async with lock:
        g_inflight.labels(device=device_id).set(1)
        try:
            if mode == "hang":
                await asyncio.Future()
            if mode == "error":
                raise HTTPException(status_code=500, detail="device error")
            sleep_ms = SLOW_MS if mode == "slow" else (ms if ms is not None else DEFAULT_NORMAL_MS)
            await asyncio.sleep(sleep_ms/1000)
            return {"device_id": device_id, "cost_ms": sleep_ms, "decided_mode": mode}
        finally:
            g_inflight.labels(device=device_id).set(0)