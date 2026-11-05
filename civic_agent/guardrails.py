"""Guardrails for CivicAssist.

These are deliberately simple, code-based checks so they run instantly and
cost nothing. Each one runs as its own node in the LangGraph graph and records
a GUARDRAIL span, so when a guardrail fires you'll see it in Arize.
"""

from __future__ import annotations

import json
import re

from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace

SSN_PATTERN = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
GUARANTEE_PATTERN = re.compile(
    r"\b(you are guaranteed|guaranteed to (be approved|qualify|receive)|you will definitely (be approved|qualify|receive))\b",
    re.IGNORECASE,
)

_tracer = otel_trace.get_tracer("civic_agent.guardrails")


def _langgraph_context():
    """Nest the guardrail span under the LangGraph node span that is running it."""
    try:
        from openinference.instrumentation.langchain import get_current_span

        node_span = get_current_span()
    except Exception:
        node_span = None
    return otel_trace.set_span_in_context(node_span) if node_span else None


def _guardrail_span(name: str, text: str, check) -> bool:
    """Run ``check(text)`` inside a GUARDRAIL span and return whether it tripped."""
    if otel_context.get_value(otel_context._SUPPRESS_INSTRUMENTATION_KEY):  # untraced (experiment) runs
        return bool(check(text)["tripwire_triggered"])
    with _tracer.start_as_current_span(name, context=_langgraph_context()) as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.GUARDRAIL.value)
        span.set_attribute(SpanAttributes.INPUT_VALUE, text)
        result = check(text)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, json.dumps(result))
        span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
        return bool(result["tripwire_triggered"])


def block_ssn(user_input: str) -> bool:
    """Input guardrail: stop the run if the resident pastes a Social Security number."""

    def check(text: str) -> dict:
        found = bool(SSN_PATTERN.search(text))
        return {"tripwire_triggered": found, "pii_detected": found, "pii_type": "SSN" if found else None}

    return _guardrail_span("block_ssn", user_input, check)


def no_approval_guarantees(output: str) -> bool:
    """Output guardrail: caseworkers decide eligibility, so the agent must never promise approval."""

    def check(text: str) -> dict:
        found = bool(GUARANTEE_PATTERN.search(text))
        return {"tripwire_triggered": found, "guarantee_language": found}

    return _guardrail_span("no_approval_guarantees", output, check)


SSN_REFUSAL = (
    "For your security, please don't share your Social Security number here. "
    "I've stopped processing that message. You can ask your question again without it, "
    "or provide your SSN only through the secure DCS portal."
)

GUARANTEE_FALLBACK = (
    "I can share the program rules, but only a DCS caseworker can make a final eligibility decision. "
    "Please apply through the DCS portal or visit an office for a determination."
)
