"""OpenTelemetry setup with a safe no-op fallback for local SQLite demos."""
from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
import logging
import os
from typing import Any

LOGGER = logging.getLogger(__name__)
_configured = False


def configure_observability() -> bool:
    """Export traces when an OTLP endpoint is configured; never block startup."""
    global _configured
    if _configured:
        return True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            # ``RESOURCE_ATTRIBUTES`` was removed from recent OpenTelemetry SDK
            # releases.  The OpenTelemetry semantic-convention key is stable, so
            # use the literal here to support both old and current SDK versions.
            resource=Resource.create({"service.name": "triple-u-api"})
        )
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _configured = True
        return True
    except Exception as exc:  # pragma: no cover - exporter must not break product API
        LOGGER.warning("OpenTelemetry disabled: %s", exc)
        return False


def learning_run_span(name: str, **attributes: Any) -> AbstractContextManager[Any]:
    """Return a real span if configured, otherwise a standard no-op context."""
    if not configure_observability():
        return nullcontext()
    try:
        from opentelemetry import trace

        span = trace.get_tracer("triple-u.learning-runs").start_as_current_span(name)
        for key, value in attributes.items():
            span.set_attribute(key, value)
        return span
    except Exception:  # pragma: no cover
        return nullcontext()
