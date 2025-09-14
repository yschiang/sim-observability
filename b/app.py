from fastapi import FastAPI, HTTPException, Response
import os, asyncio, time, uuid, json
import grpc
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.grpc import GrpcInstrumentorClient
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from prometheus_client import Gauge, Counter, Histogram, start_http_server
from otel_init import init_tracing

init_tracing("svc-b")
FastAPIInstrumentor().instrument()
GrpcInstrumentorClient().instrument()
AioHttpClientInstrumentor().instrument()

import sys
sys.path.append("/app/gen")
import device_proxy_pb2 as pb
import device_proxy_pb2_grpc as rpc

start_http_server(8081)

# Revised metrics structure for dashboard visibility
TOTAL_RECEIVED = Counter("b_total_received", "Total requests received", ["endpoint"])
COMPLETED = Counter("b_completed", "Successfully completed requests", ["endpoint"]) 
FAILED = Counter("b_failed", "Failed requests", ["endpoint"])
ERRS = Counter("b_errors_total", "Total error responses", ["code","endpoint"])
LAT  = Histogram("b_e2e_ms", "End-to-end latency (ms)",
                 buckets=[50,100,200,500,1000,2000,3000,5000,10000],
                 labelnames=["endpoint"])
AVAILABLE = Gauge("b_available_c_instances", "Available (idle & healthy) C instances")

# Keep legacy metrics for compatibility
REQS = TOTAL_RECEIVED

# Initialize metrics with zero values to ensure they appear in /metrics
TOTAL_RECEIVED.labels(endpoint="/process")._value.set(0)
COMPLETED.labels(endpoint="/process")._value.set(0) 
FAILED.labels(endpoint="/process")._value.set(0)

app = FastAPI()

C_TARGET = os.getenv("C_TARGET", "c:50051")

# Configuration from baseline.env or tunable.env
CONNECT_TIMEOUT_S = float(os.getenv("CONNECT_TIMEOUT_S", "1.0"))
REQUEST_TIMEOUT_S = float(os.getenv("REQUEST_TIMEOUT_S", "10.0"))  # B→C timeout
MAX_B_TO_C_RETRIES = int(os.getenv("MAX_B_TO_C_RETRIES", "2"))
ENABLE_B_TO_C_RETRIES = os.getenv("ENABLE_B_TO_C_RETRIES", "true").lower() == "true"
B_TO_C_RETRY_BACKOFF_MS = int(os.getenv("B_TO_C_RETRY_BACKOFF_MS", "100"))
MAP_RESOURCE_EXHAUSTED_TO_429 = os.getenv("MAP_RESOURCE_EXHAUSTED_TO_429", "false").lower() == "true"
MAP_UNAVAILABLE_TO_503 = os.getenv("MAP_UNAVAILABLE_TO_503", "false").lower() == "true"  
MAP_DEADLINE_EXCEEDED_TO_504 = os.getenv("MAP_DEADLINE_EXCEEDED_TO_504", "false").lower() == "true"

# Setup gRPC channel based on retry configuration
retry_enabled = 1 if ENABLE_B_TO_C_RETRIES else 0
CHANNEL = grpc.aio.insecure_channel(
    C_TARGET,
    options=[('grpc.lb_policy_name','round_robin'),
             ('grpc.keepalive_time_ms',15000),
             ('grpc.enable_retries', retry_enabled)]
)
STUB = rpc.DeviceProxyStub(CHANNEL)

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/__status")
async def status():
    return {"available_estimate": AVAILABLE._value.get()}

@app.get("/process")
async def process(device_id: str="dev-1", ms: int=3000, mode: str="normal"):
    ep = "/process"
    TOTAL_RECEIVED.labels(endpoint=ep).inc()  # Track total received
    rid = str(uuid.uuid4())
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(CHANNEL.channel_ready(), timeout=CONNECT_TIMEOUT_S)
        resp = await asyncio.wait_for(
            STUB.Process(pb.ProcessRequest(device_id=device_id, ms=int(ms), mode=mode)),
            timeout=REQUEST_TIMEOUT_S
        )
        e2e = (time.perf_counter()-t0)*1000
        LAT.labels(endpoint=ep).observe(e2e)
        COMPLETED.labels(endpoint=ep).inc()  # Track successful completion
        headers = {"X-Request-Id": rid, "Server-Timing": f"e2e;dur={e2e:.1f}"}
        return Response(content=json.dumps({"device_id": resp.device_id, "cost_ms": resp.cost_ms}),
                        media_type="application/json", headers=headers)
    except asyncio.TimeoutError:
        e2e = (time.perf_counter()-t0)*1000
        LAT.labels(endpoint=ep).observe(e2e)
        FAILED.labels(endpoint=ep).inc()  # Track failure
        ERRS.labels(code="504", endpoint=ep).inc()
        raise HTTPException(status_code=504, detail=f"upstream timeout {e2e:.1f}ms")
    except grpc.aio.AioRpcError as e:
        code = e.code().name
        FAILED.labels(endpoint=ep).inc()  # Track failure
        ERRS.labels(code=code, endpoint=ep).inc()
        
        # Error mapping based on configuration
        if code in ("RESOURCE_EXHAUSTED",):
            if MAP_RESOURCE_EXHAUSTED_TO_429:
                raise HTTPException(status_code=429, detail="C/D busy")
            else:
                # Baseline: no proper error mapping, treat as generic error
                raise HTTPException(status_code=502, detail="C/D busy")
        
        if code in ("UNAVAILABLE",):
            if MAP_UNAVAILABLE_TO_503:
                raise HTTPException(status_code=503, detail="C connect fail")
            else:
                # Baseline: no proper error mapping
                raise HTTPException(status_code=502, detail="C connect fail")
        
        if code in ("DEADLINE_EXCEEDED",):
            if MAP_DEADLINE_EXCEEDED_TO_504:
                raise HTTPException(status_code=504, detail="upstream timeout")
            else:
                # Baseline: no proper error mapping
                raise HTTPException(status_code=502, detail="upstream timeout")
                
        raise HTTPException(status_code=502, detail=f"grpc error: {code}")