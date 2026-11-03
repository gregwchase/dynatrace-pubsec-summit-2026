"""One-call tracing setup for CivicAssist.

This is the entire integration: register an OpenTelemetry tracer provider
pointed at Arize, then turn on OpenInference auto-instrumentation for the
OpenAI Agents SDK. No changes to the agent code are required.
"""

from __future__ import annotations

import os

_TRACER_PROVIDER = None


def setup_tracing(project_name: str | None = None, *, verbose: bool = True):
    global _TRACER_PROVIDER
    if _TRACER_PROVIDER is not None:
        return _TRACER_PROVIDER

    from arize.otel import register
    from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor

    tracer_provider = register(
        space_id=os.environ["ARIZE_SPACE_ID"],
        api_key=os.environ["ARIZE_API_KEY"],
        project_name=project_name or os.environ["ARIZE_PROJECT_NAME"],
        verbose=verbose,
    )
    # Captures every agent step, LLM call, tool call, guardrail, and handoff.
    # (exclusive_processor defaults to True, so traces go to Arize only.)
    OpenAIAgentsInstrumentor().instrument(tracer_provider=tracer_provider)

    _TRACER_PROVIDER = tracer_provider
    return tracer_provider


def flush():
    """Make sure buffered spans are sent before you go look in the UI."""
    if _TRACER_PROVIDER is not None:
        _TRACER_PROVIDER.force_flush()
