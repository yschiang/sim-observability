import os
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

def init_tracing(default_service: str):
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    svc = os.getenv("OTEL_SERVICE_NAME", default_service)
    tp = TracerProvider(resource=Resource.create({"service.name": svc}))
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")))
    trace.set_tracer_provider(tp)