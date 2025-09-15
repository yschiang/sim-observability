import os, asyncio, time, aiohttp, grpc
from grpc import aio
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry import trace, context
from opentelemetry.propagate import extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from prometheus_client import Gauge, Counter, Histogram, start_http_server
from otel_init import init_tracing

import sys
print("Starting service C...", flush=True)

init_tracing("svc-c")
# Don't auto-instrument gRPC server - we'll handle trace context manually
# GrpcInstrumentorServer().instrument()
AioHttpClientInstrumentor().instrument()

import sys
sys.path.append("/app/gen")
import device_proxy_pb2 as pb
import device_proxy_pb2_grpc as rpc

# Restore metrics functionality with unique port per container
import socket
import random

def get_available_port(start_port=9100):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + 100):  # Try 100 ports
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    # Fallback to random port
    return random.randint(9200, 9300)

# Try to start metrics server on an available port
metrics_started = False
try:
    metrics_port = get_available_port(9100)
    start_http_server(metrics_port)
    print(f"✓ Metrics server started on port {metrics_port}", flush=True)
    metrics_started = True
except Exception as e:
    print(f"⚠ Could not start metrics server: {e}", flush=True)
    print("Continuing with dummy metrics...", flush=True)

# Create real or dummy metrics based on server startup
if metrics_started:
    g_healthy = Gauge("c_healthy", "health of this C instance"); g_healthy.set(1)
    g_inflight = Gauge("c_inflight", "whether C is processing a request"); g_inflight.set(0)
    g_ejected = Gauge("c_ejected", "whether C is ejected"); g_ejected.set(0)
    
    # Revised metrics structure for dashboard visibility with deviceId labels
    TOTAL_RECEIVED = Counter("c_total_received", "Total requests received", ["device_id"])
    COMPLETED = Counter("c_completed", "Successfully completed requests", ["device_id"])
    FAILED = Counter("c_failed", "Failed requests", ["device_id"])
    ERRS = Counter("c_errors_total", "Total errors", ["code", "device_id"])
    LAT  = Histogram("c_process_ms", "C handling latency (ms)", ["device_id"],
                     buckets=[50,100,200,500,1000,2000,3000,5000,10000])
    CD   = Histogram("c_to_d_ms", "C→D downstream latency (ms)", ["device_id"],
                     buckets=[50,100,200,500,1000,2000,3000,5000,10000])
    
    # Keep legacy metrics for compatibility
    REQS = TOTAL_RECEIVED
    
    # Initialize metrics with zero values to ensure they appear in /metrics
    # With labeled metrics, we can't pre-initialize without specific labels
    # The metrics will appear once the first labeled increment occurs
    
    print("✓ Real metrics initialized", flush=True)
else:
    # Fallback dummy metrics
    class DummyMetric:
        def set(self, value): pass
        def inc(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self
    g_healthy = g_inflight = g_ejected = DummyMetric()
    TOTAL_RECEIVED = COMPLETED = FAILED = REQS = ERRS = LAT = CD = DummyMetric()
    print("✓ Dummy metrics initialized", flush=True)

# Configuration from baseline.env or tunable.env
D_FAST_URL = os.getenv("D_FAST_URL", "http://d-fast:8000")  
D_SLOW_URL = os.getenv("D_SLOW_URL", "http://d-slow:8000")
DEVICE_TIMEOUT_S = float(os.getenv("DEVICE_TIMEOUT_S", "60.0"))  # C→D timeout from config
ENABLE_C_TO_D_RETRIES = os.getenv("ENABLE_C_TO_D_RETRIES", "false").lower() == "true"
MAX_C_TO_D_RETRIES = int(os.getenv("MAX_C_TO_D_RETRIES", "0"))

PORT = os.getenv("PORT", "50051")

# Single-threaded behavior: Each C instance can only handle 1 request at a time
# This is the core constraint that causes the baseline problem
SEM = asyncio.Semaphore(1)

# Device routing based on device_id patterns
# Convert gRPC metadata to dictionary for OpenTelemetry extraction
def metadata_to_dict(metadata):
    return {item.key: item.value for item in metadata}

def get_device_url(device_id: str) -> str:
    if "slow" in device_id.lower():
        return D_SLOW_URL
    else:
        return D_FAST_URL

class S(rpc.DeviceProxyServicer):
    async def Process(self, req: pb.ProcessRequest, ctx: aio.ServicerContext):
        print(f"DEBUG: Process method called for device_id={req.device_id}", flush=True)
        
        # Extract trace context from gRPC metadata
        metadata = ctx.invocation_metadata()
        
        # Debug: Print received metadata
        print(f"DEBUG: Received gRPC metadata (count: {len(metadata)}):", flush=True)
        for item in metadata:
            key, value = item.key, item.value
            print(f"  {key}: {value}", flush=True)
            if 'trace' in key.lower():
                print(f"  *** TRACE HEADER: {key}: {value}", flush=True)
        
        # Convert metadata to dictionary and extract trace context
        metadata_dict = metadata_to_dict(metadata)
        print(f"DEBUG: Metadata dict: {metadata_dict}", flush=True)
        parent_context = extract(metadata_dict)
        
        # Debug: Check extracted context
        extracted_span = trace.get_current_span(parent_context)
        if extracted_span:
            extracted_context = extracted_span.get_span_context()
            print(f"DEBUG: Extracted trace_id={format(extracted_context.trace_id, '032x')}", flush=True)
        else:
            print(f"DEBUG: No span found in extracted context", flush=True)
        
        # Create a span manually with the extracted parent context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "deviceproxy.DeviceProxy/Process",
            context=parent_context,
            kind=trace.SpanKind.SERVER
        ) as span:
            # Debug: Print span info
            span_context = span.get_span_context()
            print(f"DEBUG: Created span with trace_id={format(span_context.trace_id, '032x')}, span_id={format(span_context.span_id, '016x')}", flush=True)
            print(f"C received request: device_id={req.device_id}, ms={req.ms}", flush=True)
            TOTAL_RECEIVED.labels(device_id=req.device_id).inc()  # Track total received
            
            # Simple semaphore handling without complex error cases
            await SEM.acquire()
            g_inflight.set(1)  # Mark as busy
            
            t0 = time.perf_counter()
            try:
                start = time.perf_counter()
                device_url = get_device_url(req.device_id)
                
                # Simplified HTTP request to device
                url = f"{device_url}/do_work?device_id={req.device_id}&ms={req.ms}&mode={req.mode}"
                timeout = aiohttp.ClientTimeout(total=DEVICE_TIMEOUT_S)
                
                print(f"C calling device: {url}", flush=True)
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=timeout) as response:
                        response.raise_for_status()
                        result = await response.json()
                
                print(f"C got device response: {result}", flush=True)
                
                # Track latency
                cd = (time.perf_counter() - start) * 1000
                CD.labels(device_id=req.device_id).observe(cd)
                
                # Track successful completion
                COMPLETED.labels(device_id=req.device_id).inc()
                
                # Return response without complex metadata handling for now
                return pb.ProcessReply(
                    device_id=result["device_id"], 
                    cost_ms=result["cost_ms"]
                )
                        
            except Exception as e:
                print(f"C error: {e}", flush=True)
                FAILED.labels(device_id=req.device_id).inc()  # Track failure
                ERRS.labels(code="UNAVAILABLE", device_id=req.device_id).inc()
                # Instead of ctx.abort, raise gRPC exception directly
                raise grpc.aio.AioRpcError(grpc.StatusCode.UNAVAILABLE, f"device error: {e}")
            finally:
                # Always release semaphore and mark as available
                LAT.labels(device_id=req.device_id).observe((time.perf_counter() - t0) * 1000)
                SEM.release()
                g_inflight.set(0)  # Mark as available
                print(f"C request completed", flush=True)

async def serve():
    print(f"Starting gRPC server on port {PORT}", flush=True)
    server = aio.server(options=[('grpc.keepalive_time_ms', 15000)])
    rpc.add_DeviceProxyServicer_to_server(S(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    print("✓ gRPC server configured", flush=True)
    
    await server.start()
    print("✓ gRPC server started and ready for requests", flush=True)
    
    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        print("Shutting down server...", flush=True)
        await server.stop(0)

if __name__ == "__main__":
    print("=== Service C Starting ===", flush=True)
    asyncio.run(serve())