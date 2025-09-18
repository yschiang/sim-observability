from fastapi import FastAPI, HTTPException, Response
import os, asyncio, time, uuid, json
import grpc
import psutil
import numpy as np
import threading
from typing import List
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

# CPU and Memory metrics
CPU_USAGE = Gauge("b_cpu_usage_percent", "Current CPU usage percentage")
MEM_USAGE = Gauge("b_memory_usage_percent", "Current memory usage percentage")
BATCH_PROCESSING = Gauge("b_batch_processing", "Whether batch processing is active (0/1)")
BATCH_SIZE = Histogram("b_batch_size", "Size of processed batches", 
                       buckets=[100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000])

# Keep legacy metrics for compatibility
REQS = TOTAL_RECEIVED

# Initialize metrics with zero values to ensure they appear in /metrics
TOTAL_RECEIVED.labels(endpoint="/process")._value.set(0)
COMPLETED.labels(endpoint="/process")._value.set(0) 
FAILED.labels(endpoint="/process")._value.set(0)

app = FastAPI()

# Background thread to monitor system metrics
def monitor_system_metrics():
    while True:
        try:
            # Get current process CPU and memory usage
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            mem_percent = process.memory_percent()
            
            # Update Prometheus metrics
            CPU_USAGE.set(cpu_percent)
            MEM_USAGE.set(mem_percent)
            
            time.sleep(1)  # Update every second
        except Exception as e:
            print(f"Error monitoring metrics: {e}")
            time.sleep(5)

# Start monitoring thread
monitoring_thread = threading.Thread(target=monitor_system_metrics, daemon=True)
monitoring_thread.start()

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

def cpu_intensive_batch_process(data_size: int, intensity: float = 1.0):
    """
    Simulate CPU-intensive batch data processing
    - data_size: Number of records to process
    - intensity: How CPU-intensive (1.0 = normal, 2.0 = double, etc.)
    """
    BATCH_PROCESSING.set(1)
    BATCH_SIZE.observe(data_size)
    
    try:
        print(f"Starting batch processing of {data_size} records with intensity {intensity}")
        
        # Simulate loading data into memory (creates large arrays)
        batch_data = []
        for i in range(min(data_size, 100000)):  # Cap at 100k to avoid memory issues
            # Create random data that simulates records
            record = np.random.random(int(100 * intensity))  # Adjust size based on intensity
            batch_data.append(record)
        
        # CPU-intensive processing phase
        results = []
        operations = int(1000 * intensity)  # Number of operations per record
        
        for record in batch_data:
            # Simulate complex calculations on each record
            for _ in range(operations):
                # Matrix operations are CPU-intensive
                result = np.sum(record ** 2)
                result = np.sqrt(result)
                result = np.log(result + 1)
            results.append(result)
        
        # Simulate data aggregation/reduction
        final_result = np.mean(results) if results else 0
        
        print(f"Batch processing completed. Final result: {final_result}")
        return {"records_processed": len(batch_data), "result": float(final_result)}
    
    finally:
        BATCH_PROCESSING.set(0)

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/__status")
async def status():
    return {"available_estimate": AVAILABLE._value.get()}

@app.post("/batch_process")
async def batch_process(size: int = 10000, intensity: float = 1.0):
    """
    Trigger batch processing that causes CPU spike
    - size: Number of records to process (default 10000)
    - intensity: CPU intensity multiplier (default 1.0, higher = more CPU)
    """
    ep = "/batch_process"
    TOTAL_RECEIVED.labels(endpoint=ep).inc()
    t0 = time.perf_counter()
    
    try:
        # Run CPU-intensive batch processing in a thread to not block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            cpu_intensive_batch_process, 
            size, 
            intensity
        )
        
        e2e = (time.perf_counter()-t0)*1000
        LAT.labels(endpoint=ep).observe(e2e)
        COMPLETED.labels(endpoint=ep).inc()
        
        return {
            "status": "success",
            "processing_time_ms": e2e,
            "records_processed": result["records_processed"],
            "result": result["result"]
        }
    except Exception as e:
        e2e = (time.perf_counter()-t0)*1000
        LAT.labels(endpoint=ep).observe(e2e)
        FAILED.labels(endpoint=ep).inc()
        ERRS.labels(code="500", endpoint=ep).inc()
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

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