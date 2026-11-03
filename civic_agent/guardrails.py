"""Guardrails for CivicAssist.

These are deliberately simple, code-based checks so they run instantly and
cost nothing. Each one shows up as a GUARDRAIL span in the trace, and when a
tripwire fires you'll see it in Arize.
"""

from __future__ import annotations

import re

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    input_guardrail,
    output_guardrail,
)

SSN_PATTERN = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")
GUARANTEE_PATTERN = re.compile(
    r"\b(you are guaranteed|guaranteed to (be approved|qualify|receive)|you will definitely (be approved|qualify|receive))\b",
    re.IGNORECASE,
)


@input_guardrail
async def block_ssn(ctx: RunContextWrapper, agent: Agent, user_input) -> GuardrailFunctionOutput:
    """Stop the run if the resident pastes a Social Security number."""
    text = user_input if isinstance(user_input, str) else str(user_input)
    found = bool(SSN_PATTERN.search(text))
    return GuardrailFunctionOutput(
        output_info={"pii_detected": found, "pii_type": "SSN" if found else None},
        tripwire_triggered=found,
    )


@output_guardrail
async def no_approval_guarantees(ctx: RunContextWrapper, agent: Agent, output) -> GuardrailFunctionOutput:
    """Caseworkers decide eligibility. The agent must never promise approval."""
    text = output if isinstance(output, str) else str(output)
    found = bool(GUARANTEE_PATTERN.search(text))
    return GuardrailFunctionOutput(
        output_info={"guarantee_language": found},
        tripwire_triggered=found,
    )


SSN_REFUSAL = (
    "For your security, please don't share your Social Security number here. "
    "I've stopped processing that message. You can ask your question again without it, "
    "or provide your SSN only through the secure DCS portal."
)

GUARANTEE_FALLBACK = (
    "I can share the program rules, but only a DCS caseworker can make a final eligibility decision. "
    "Please apply through the DCS portal or visit an office for a determination."
)
