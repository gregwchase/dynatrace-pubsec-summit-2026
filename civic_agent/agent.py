"""CivicAssist: a small agentic app built on the OpenAI Agents SDK.

The agent answers resident questions for the (fictional) State of Columbia
Department of Community Services. It has four tools, one input guardrail, and
one output guardrail, which is enough to produce interesting traces.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import uuid
from typing import Any

from agents import (
    Agent,
    InputGuardrailTripwireTriggered,
    ModelSettings,
    OutputGuardrailTripwireTriggered,
    RunConfig,
    Runner,
    ToolCallItem,
)
from openinference.instrumentation import using_attributes
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from .guardrails import GUARANTEE_FALLBACK, SSN_REFUSAL, block_ssn, no_approval_guarantees
from .prompts import PROMPTS
from .tools import ALL_TOOLS

DEFAULT_MODEL = os.getenv("CIVIC_AGENT_MODEL", "gpt-4.1-mini")

_tracer = otel_trace.get_tracer("civic_agent")


def build_agent(prompt_version: str = "v1", model: str | None = None, temperature: float = 0.3) -> Agent:
    """Create the CivicAssist agent with a given prompt version and model."""
    return Agent(
        name="CivicAssist",
        instructions=PROMPTS[prompt_version],
        model=model or DEFAULT_MODEL,
        model_settings=ModelSettings(temperature=temperature),
        tools=ALL_TOOLS,
        input_guardrails=[block_ssn],
        output_guardrails=[no_approval_guarantees],
    )


def _tool_names(result) -> list[str]:
    names = []
    for item in result.new_items:
        if isinstance(item, ToolCallItem):
            names.append(getattr(item.raw_item, "name", None) or "unknown")
    return names


async def ask_async(
    question: str,
    *,
    prompt_version: str = "v1",
    model: str | None = None,
    session_id: str | None = None,
    user_id: str = "workshop-user",
    tags: list[str] | None = None,
    trace_to_project: bool = True,
) -> dict[str, Any]:
    """Run one turn of the agent inside a top-level CHAIN span.

    The top-level span gives every trace a clean input/output pair (handy for
    evals) and carries session, user, and metadata attributes so you can
    filter traces in Arize.

    Set ``trace_to_project=False`` for experiment runs so they don't mix with
    "production" traffic (Arize records experiment runs separately).
    """
    agent = build_agent(prompt_version, model)
    if not trace_to_project:
        return await _run_untraced(agent, question)
    session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
    metadata = {"prompt_version": prompt_version, "model": str(agent.model), "app": "civicassist"}

    with using_attributes(session_id=session_id, user_id=user_id, metadata=metadata, tags=tags or []):
        with _tracer.start_as_current_span("civicassist.handle_request") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            span.set_attribute(SpanAttributes.INPUT_VALUE, question)
            span.set_attribute(SpanAttributes.SESSION_ID, session_id)
            span.set_attribute(SpanAttributes.USER_ID, user_id)
            span.set_attribute(SpanAttributes.METADATA, json.dumps(metadata))

            guardrail = None
            tools_called: list[str] = []
            try:
                result = await Runner.run(agent, question)
                answer = str(result.final_output)
                tools_called = _tool_names(result)
            except InputGuardrailTripwireTriggered:
                guardrail, answer = "block_ssn", SSN_REFUSAL
            except OutputGuardrailTripwireTriggered:
                guardrail, answer = "no_approval_guarantees", GUARANTEE_FALLBACK
            except Exception as exc:  # surface errors in the trace, then re-raise
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

            span.set_attribute(SpanAttributes.OUTPUT_VALUE, answer)
            # Record what happened in metadata too, so it's filterable in Arize.
            metadata.update({"tools_called": ",".join(tools_called), "guardrail_triggered": guardrail or "none"})
            span.set_attribute(SpanAttributes.METADATA, json.dumps(metadata))
            span.set_status(Status(StatusCode.OK))

            trace_id = format(span.get_span_context().trace_id, "032x")

    return {
        "question": question,
        "answer": answer,
        "tools_called": tools_called,
        "guardrail_triggered": guardrail,
        "session_id": session_id,
        "trace_id": trace_id,
    }


async def _run_untraced(agent: Agent, question: str) -> dict[str, Any]:
    guardrail, tools_called = None, []
    try:
        result = await Runner.run(agent, question, run_config=RunConfig(tracing_disabled=True))
        answer, tools_called = str(result.final_output), _tool_names(result)
    except InputGuardrailTripwireTriggered:
        guardrail, answer = "block_ssn", SSN_REFUSAL
    except OutputGuardrailTripwireTriggered:
        guardrail, answer = "no_approval_guarantees", GUARANTEE_FALLBACK
    return {"question": question, "answer": answer, "tools_called": tools_called, "guardrail_triggered": guardrail}


def ask(question: str, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper around :func:`ask_async`.

    Works in plain Python *and* inside Jupyter/Colab (which already has a
    running event loop) by running the coroutine on a worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ask_async(question, **kwargs))
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, ask_async(question, **kwargs)).result()
