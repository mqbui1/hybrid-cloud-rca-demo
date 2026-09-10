"""Shared OpenTelemetry setup for all travel-planner services."""
import logging
import os

from opentelemetry import _events, _logs, metrics, propagate, trace
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.sdk._events import EventLoggerProvider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def setup_otel(service_name: str) -> None:
    """
    Initialize OTel SDK for a travel-planner microservice.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT from the environment (set via the
    Splunk OTel Collector DaemonSet hostIP pattern in K8s manifests).
    """
    propagate.set_global_textmap(CompositePropagator([
        W3CBaggagePropagator(),
        TraceContextTextMapPropagator(),
    ]))

    resource = Resource.create(
        {
            SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", service_name),
            "deployment.environment": os.environ.get(
                "DEPLOYMENT_ENVIRONMENT", "hybrid-visibility-demo"
            ),
        }
    )

    tracer_provider = TracerProvider(resource=resource, sampler=ParentBased(ALWAYS_ON))
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(
        MeterProvider(resource=resource, metric_readers=[metric_reader])
    )

    # Logs — bridge Python logging → OTel SDK so trace_id/span_id inject automatically
    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    _logs.set_logger_provider(log_provider)
    _events.set_event_logger_provider(EventLoggerProvider())

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=log_provider)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.addHandler(stream_handler)
    root.setLevel(logging.INFO)

    # Instrumentations — LangChain spans + outbound HTTP context propagation
    LangchainInstrumentor().instrument()

    def _set_peer_service(span, request) -> None:
        # Sets peer.service so APM can attribute a failed connection (e.g.
        # connection refused) to the logical downstream service instead of
        # falling back to a synthetic host:port pseudo-service — there's no
        # server-side span to correlate against when the connection never
        # reaches the peer.
        from urllib.parse import urlparse
        hostname = urlparse(request.url).hostname
        if hostname:
            span.set_attribute("peer.service", hostname.split(".")[0])

    RequestsInstrumentor().instrument(request_hook=_set_peer_service)
