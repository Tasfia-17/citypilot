"""Arize Phoenix — OpenTelemetry instrumentation for all ADK agent spans."""

import os
import time
from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_tracer: trace.Tracer | None = None
_provider: TracerProvider | None = None


def setup_phoenix_tracing() -> bool:
    """Initialize Arize Phoenix tracing. Returns True if configured."""
    global _tracer, _provider
    phoenix_url = os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", "")
    if not phoenix_url:
        print("PHOENIX_COLLECTOR_ENDPOINT not set — tracing disabled.")
        return False

    try:
        from phoenix.otel import register
        _provider = register(
            project_name="citypilot",
            endpoint=phoenix_url,
        )
        _tracer = trace.get_tracer("citypilot")
        print(f"Arize Phoenix tracing enabled → {phoenix_url}")
        return True
    except ImportError:
        print("arize-phoenix not installed — tracing disabled.")
        return False
    except Exception as e:
        print(f"Phoenix tracing setup failed: {e}")
        return False


def get_tracer() -> trace.Tracer | None:
    return _tracer


@contextmanager
def trace_agent_run(
    agent_name: str,
    mission: str,
    parent_span: trace.Span | None = None,
) -> Generator[trace.Span | None, None, None]:
    """Context manager to trace a single agent execution."""
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(
        name=f"citypilot.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "mission": mission[:500],
            "citypilot.component": "agent",
        },
    ) as span:
        start_time = time.time()
        try:
            yield span
            span.set_attribute("agent.status", "success")
        except Exception as e:
            span.set_attribute("agent.status", "error")
            span.set_attribute("agent.error", str(e))
            raise
        finally:
            latency_ms = int((time.time() - start_time) * 1000)
            span.set_attribute("agent.latency_ms", latency_ms)


@contextmanager
def trace_mcp_call(
    tool_name: str,
    server: str,
    args: dict | None = None,
) -> Generator[trace.Span | None, None, None]:
    """Context manager to trace MCP tool calls."""
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(
        name=f"mcp.{server}.{tool_name}",
        attributes={
            "mcp.tool": tool_name,
            "mcp.server": server,
            "citypilot.component": "mcp_tool",
        },
    ) as span:
        if args:
            span.set_attribute("mcp.args", str(args)[:500])
        try:
            yield span
            span.set_attribute("mcp.status", "success")
        except Exception as e:
            span.set_attribute("mcp.status", "error")
            span.set_attribute("mcp.error", str(e))
            raise


def record_prediction_quality(
    agent_name: str,
    predicted: dict,
    actual: dict | None = None,
    confidence: float | None = None,
):
    """Record prediction quality metrics for Arize evaluation."""
    if _tracer is None:
        return

    with _tracer.start_as_current_span(
        name=f"citypilot.prediction_quality.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "prediction.confidence": confidence or 0.0,
            "prediction.has_actual": actual is not None,
            "citypilot.component": "evaluation",
        },
    ) as span:
        span.set_attribute("prediction.predicted_keys", str(list(predicted.keys())))


def get_agent_health_summary() -> dict:
    """Return agent health summary for the dashboard panel."""
    # In production this would query Phoenix MCP for recent trace data
    return {
        "tracing_enabled": _tracer is not None,
        "agents": {
            "signal_collector": {"status": "healthy", "avg_latency_ms": 0},
            "anomaly_detector": {"status": "healthy", "avg_latency_ms": 0},
            "impact_forecaster": {"status": "healthy", "avg_latency_ms": 0},
            "operations_planner": {"status": "healthy", "avg_latency_ms": 0},
            "executive_briefer": {"status": "healthy", "avg_latency_ms": 0},
        },
        "prediction_confidence": None,
        "phoenix_url": os.environ.get("PHOENIX_COLLECTOR_ENDPOINT", ""),
    }
