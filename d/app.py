from fastapi import FastAPI, HTTPException
import asyncio
import os
from typing import Dict
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import start_http_server, Gauge
from otel_init import init_tracing

# Device configuration
DEVICE_TYPE = os.getenv("DEVICE_TYPE", "normal")
SLOW_MULTIPLIER = float(os.getenv("SLOW_MULTIPLIER", "1.0"))
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "svc-d")

init_tracing(SERVICE_NAME)
app = FastAPI(title=f"Device Simulator ({DEVICE_TYPE})")
FastAPIInstrumentor.instrument_app(app)

start_http_server(9100)
g_inflight = Gauge("d_inflight", "requests in flight", ["device"])

locks: Dict[str, asyncio.Lock] = {}

@app.get("/health")
async def health():
    return {"ok": True, "device_type": DEVICE_TYPE, "slow_multiplier": SLOW_MULTIPLIER}

@app.get("/do_work")
async def do_work(device_id: str, ms: int = 3000, mode: str = "normal"):
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
            
            # Apply slow multiplier for slow devices
            actual_ms = int(ms * SLOW_MULTIPLIER)
            await asyncio.sleep(actual_ms/1000)
            return {"device_id": device_id, "cost_ms": actual_ms, "device_type": DEVICE_TYPE}
        finally:
            g_inflight.labels(device=device_id).set(0)