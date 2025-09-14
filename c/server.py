import os, asyncio, time, aiohttp, grpc
from grpc import aio
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from prometheus_client import Gauge, Counter, Histogram, start_http_server
from otel_init import init_tracing

init_tracing("svc-c")
GrpcInstrumentorServer().instrument()
AioHttpClientInstrumentor().instrument()

import sys
sys.path.append("/app/gen")
import device_proxy_pb2 as pb
import device_proxy_pb2_grpc as rpc

METRICS_PORT = int(os.getenv("METRICS_PORT", "9100"))
start_http_server(METRICS_PORT)
g_healthy = Gauge("c_healthy", "health of this C instance"); g_healthy.set(1)
g_inflight = Gauge("c_inflight", "whether C is processing a request"); g_inflight.set(0)
g_ejected = Gauge("c_ejected", "whether C is ejected"); g_ejected.set(0)

REQS = Counter("c_requests_total", "Total requests")
ERRS = Counter("c_errors_total", "Total errors", ["code"])
LAT  = Histogram("c_process_ms", "C handling latency (ms)",
                 buckets=[50,100,200,500,1000,2000,3000,5000,10000])
CD   = Histogram("c_to_d_ms", "C→D downstream latency (ms)",
                 buckets=[50,100,200,500,1000,2000,3000,5000,10000])

SEM = asyncio.Semaphore(1)
# Support multiple device services
D_FAST_URL = os.getenv("D_FAST_URL", "http://d-fast:8000")  
D_SLOW_URL = os.getenv("D_SLOW_URL", "http://d-slow:8000")
DEVICE_TIMEOUT_S = float(os.getenv("DEVICE_TIMEOUT_S", "3.0"))
PORT = os.getenv("PORT", "50051")

# Device routing based on device_id patterns
def get_device_url(device_id: str) -> str:
    if "slow" in device_id.lower():
        return D_SLOW_URL
    else:
        return D_FAST_URL

class S(rpc.DeviceProxyServicer):
    async def Process(self, req: pb.ProcessRequest, ctx: aio.ServicerContext):
        REQS.inc()
        if not SEM.locked():
            await SEM.acquire(); g_inflight.set(1)
        else:
            ERRS.labels(code="RESOURCE_EXHAUSTED").inc()
            await ctx.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "C busy")
        t0 = time.perf_counter()
        try:
            start = time.perf_counter()
            device_url = get_device_url(req.device_id)
            async with aiohttp.ClientSession() as sess:
                url = f"{device_url}/do_work?device_id={req.device_id}&ms={req.ms}&mode={req.mode}"
                async with sess.get(url, timeout=DEVICE_TIMEOUT_S) as r:
                    if r.status == 429:
                        ERRS.labels(code="DEVICE_BUSY").inc()
                        await ctx.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "device busy")
                    r.raise_for_status()
                    j = await r.json()
                    cd = (time.perf_counter()-start)*1000
                    CD.observe(cd)
                    await ctx.set_trailing_metadata((('x-cd-ms', f'{cd:.1f}'),))
                    return pb.ProcessReply(device_id=j["device_id"], cost_ms=j["cost_ms"])
        except asyncio.TimeoutError:
            ERRS.labels(code="DEADLINE_EXCEEDED").inc()
            await ctx.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "device timeout")
        except Exception as e:
            ERRS.labels(code="UNAVAILABLE").inc()
            await ctx.abort(grpc.StatusCode.UNAVAILABLE, f"device error: {e}")
        finally:
            LAT.observe((time.perf_counter()-t0)*1000)
            if SEM.locked():
                SEM.release(); g_inflight.set(0)

async def serve():
    server = aio.server(options=[('grpc.keepalive_time_ms', 15000)])
    rpc.add_DeviceProxyServicer_to_server(S(), server)
    server.add_insecure_port(f"[::]:{PORT}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(serve())