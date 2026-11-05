"""CivicAssist: a small agentic app built with LangGraph.

The agent answers resident questions for the (fictional) State of Columbia
Department of Community Services. It has four tools, one input guardrail, and
one output guardrail, which is enough to produce interesting traces.

The graph:

    START → input_guardrail ──(SSN found)──────────────────────────→ END
                 │
                 ▼
               agent ⇄ tools        (the LLM loops until it stops calling tools)
                 │
                 ▼
          output_guardrail → END    (replaces approval guarantees with a safe answer)
"""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import Annotated, Any, Iterator, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from openinference.instrumentation import suppress_tracing, using_attributes
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode

from .guardrails import GUARANTEE_FALLBACK, SSN_REFUSAL, block_ssn, no_approval_guarantees
from .llm import default_model, get_chat_model, get_provider
from .prompts import PROMPTS
from .tools import ALL_TOOLS

MAX_STEPS = 12  # LangGraph recursion limit: enough for several tool calls, stops runaway loops
MAX_TOOL_CONTEXT_CHARS = 6_000

_tracer = otel_trace.get_tracer("civic_agent")


class AgentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    guardrail: str | None


def _text(message: AnyMessage) -> str:
    """Plain text of a message (Claude responses can be a list of content blocks)."""
    return str(message.text)


def build_agent(prompt_version: str = "v1", model: str | None = None, temperature: float = 0.3):
    """Build the CivicAssist graph for a prompt version and model."""
    llm = get_chat_model("agent", model=model, temperature=temperature).bind_tools(ALL_TOOLS)
    system = SystemMessage(PROMPTS[prompt_version])

    def input_guardrail(state: AgentState) -> dict:
        if block_ssn(_text(state["messages"][-1])):
            return {"guardrail": "block_ssn", "messages": [AIMessage(SSN_REFUSAL)]}
        return {"guardrail": None}

    def call_model(state: AgentState) -> dict:
        return {"messages": [llm.invoke([system, *state["messages"]])]}

    async def acall_model(state: AgentState) -> dict:
        return {"messages": [await llm.ainvoke([system, *state["messages"]])]}

    def output_guardrail(state: AgentState) -> dict:
        if no_approval_guarantees(_text(state["messages"][-1])):
            return {"guardrail": "no_approval_guarantees", "messages": [AIMessage(GUARANTEE_FALLBACK)]}
        return {}

    def after_input(state: AgentState) -> str:
        return END if state.get("guardrail") else "agent"

    def after_agent(state: AgentState) -> str:
        return "tools" if getattr(state["messages"][-1], "tool_calls", None) else "output_guardrail"

    graph = StateGraph(AgentState)
    graph.add_node("input_guardrail", input_guardrail)
    # Sync and async versions, so both ask() and ask_async() work without extra threads.
    graph.add_node("agent", RunnableLambda(call_model, afunc=acall_model, name="call_model"))
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_node("output_guardrail", output_guardrail)
    graph.add_edge(START, "input_guardrail")
    graph.add_conditional_edges("input_guardrail", after_input, ["agent", END])
    graph.add_conditional_edges("agent", after_agent, ["tools", "output_guardrail"])
    graph.add_edge("tools", "agent")
    graph.add_edge("output_guardrail", END)
    return graph.compile(name="CivicAssist")


def _summarize(state: AgentState) -> dict[str, Any]:
    messages = state["messages"]
    tools_called = [call["name"] for m in messages if isinstance(m, AIMessage) for call in (m.tool_calls or [])]
    outputs = [str(m.content) for m in messages if isinstance(m, ToolMessage)]
    return {
        "answer": _text(messages[-1]),
        "tools_called": tools_called,
        "guardrail_triggered": state.get("guardrail"),
        "tool_context": "\n\n".join(outputs)[:MAX_TOOL_CONTEXT_CHARS] or "(no tools were called)",
    }


@contextlib.contextmanager
def _request(question: str, *, prompt_version: str, model: str | None, session_id: str | None,
             user_id: str, tags: list[str] | None, trace_to_project: bool) -> Iterator[dict[str, Any]]:
    """Wrap one request in a top-level CHAIN span (or suppress tracing entirely).

    The caller runs the graph and stores the final state in ``record["state"]``.
    """
    model = model or default_model("agent")
    record: dict[str, Any] = {"question": question}
    if not trace_to_project:
        with suppress_tracing():
            yield record
        record.update(_summarize(record.pop("state")))
        record.pop("tool_context")
        return

    session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
    metadata = {"prompt_version": prompt_version, "model": model, "provider": get_provider(), "app": "civicassist"}
    with using_attributes(session_id=session_id, user_id=user_id, metadata=metadata, tags=tags or []):
        with _tracer.start_as_current_span("civicassist.handle_request") as span:
            span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, OpenInferenceSpanKindValues.CHAIN.value)
            span.set_attribute(SpanAttributes.INPUT_VALUE, question)
            span.set_attribute(SpanAttributes.SESSION_ID, session_id)
            span.set_attribute(SpanAttributes.USER_ID, user_id)
            span.set_attribute(SpanAttributes.METADATA, json.dumps(metadata))
            try:
                yield record
            except Exception as exc:  # surface errors in the trace, then re-raise
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            summary = _summarize(record.pop("state"))
            tool_context = summary.pop("tool_context")
            span.set_attribute(SpanAttributes.OUTPUT_VALUE, summary["answer"])
            # Record what happened in metadata too, so it's filterable in Arize.
            # tool_context also lets *online* evaluators (which read one span at a
            # time) see what the tools returned, without stitching child spans together.
            metadata.update({
                "tools_called": ",".join(summary["tools_called"]) or "none",
                "guardrail_triggered": summary["guardrail_triggered"] or "none",
                "returned_program_record": "true" if "source_url" in tool_context else "false",
                "tool_context": tool_context,
            })
            span.set_attribute(SpanAttributes.METADATA, json.dumps(metadata))
            span.set_status(Status(StatusCode.OK))
            record.update(summary, session_id=session_id, trace_id=format(span.get_span_context().trace_id, "032x"))


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
    graph = build_agent(prompt_version, model)
    with _request(question, prompt_version=prompt_version, model=model, session_id=session_id,
                  user_id=user_id, tags=tags, trace_to_project=trace_to_project) as record:
        record["state"] = await graph.ainvoke({"messages": [HumanMessage(question)]},
                                              {"recursion_limit": MAX_STEPS})
    return record


def ask(
    question: str,
    *,
    prompt_version: str = "v1",
    model: str | None = None,
    session_id: str | None = None,
    user_id: str = "workshop-user",
    tags: list[str] | None = None,
    trace_to_project: bool = True,
) -> dict[str, Any]:
    """Synchronous version of :func:`ask_async`. Works in scripts, Jupyter, and Colab."""
    graph = build_agent(prompt_version, model)
    with _request(question, prompt_version=prompt_version, model=model, session_id=session_id,
                  user_id=user_id, tags=tags, trace_to_project=trace_to_project) as record:
        record["state"] = graph.invoke({"messages": [HumanMessage(question)]}, {"recursion_limit": MAX_STEPS})
    return record
