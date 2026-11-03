"""Helper functions shared by the workshop notebooks.

These keep the notebooks focused on concepts. Read through them if you want
to see exactly how spans are exported and evals are logged back to Arize.
"""

from __future__ import annotations

import getpass
import json
import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd

# --------------------------------------------------------------------------
# Credentials
# --------------------------------------------------------------------------

REQUIRED_KEYS = ["ARIZE_SPACE_ID", "ARIZE_API_KEY", "OPENAI_API_KEY"]


def _from_colab_secrets(key: str) -> str | None:
    try:
        from google.colab import userdata  # type: ignore

        return userdata.get(key)
    except Exception:
        return None


def load_credentials(participant: str | None = None) -> str:
    """Load keys from (1) env / .env, (2) Colab secrets, or (3) a prompt.

    Returns the Arize project name for this participant, e.g. ``civicassist-jdoe``.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    for key in REQUIRED_KEYS:
        if not os.getenv(key):
            value = _from_colab_secrets(key) or getpass.getpass(f"{key}: ")
            os.environ[key] = value.strip()

    if not os.getenv("ARIZE_PROJECT_NAME"):
        participant = participant or os.getenv("WORKSHOP_PARTICIPANT") or input("Your initials or handle: ")
        handle = re.sub(r"[^a-z0-9-]", "", participant.lower().replace(" ", "-")) or "anon"
        os.environ["ARIZE_PROJECT_NAME"] = f"civicassist-{handle}"

    print(f"✅ Credentials loaded. Arize project: {os.environ['ARIZE_PROJECT_NAME']}")
    return os.environ["ARIZE_PROJECT_NAME"]


def arize_client():
    from arize import ArizeClient

    return ArizeClient(api_key=os.environ["ARIZE_API_KEY"])


# --------------------------------------------------------------------------
# Exporting traces
# --------------------------------------------------------------------------

KIND = "attributes.openinference.span.kind"
INPUT = "attributes.input.value"
OUTPUT = "attributes.output.value"
TRACE_ID = "context.trace_id"
SPAN_ID = "context.span_id"


def export_spans(hours: int = 24, where: str = "") -> pd.DataFrame:
    """Export spans for this participant's project from the last ``hours``."""
    client = arize_client()
    end = datetime.now(timezone.utc) + timedelta(minutes=5)
    start = end - timedelta(hours=hours)
    df = client.spans.export_to_df(
        space_id=os.environ["ARIZE_SPACE_ID"],
        project_name=os.environ["ARIZE_PROJECT_NAME"],
        start_time=start,
        end_time=end,
        where=where,
    )
    print(f"Exported {len(df):,} spans across {df[TRACE_ID].nunique() if len(df) else 0} traces.")
    return df


def _parse_metadata(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return {}


def root_spans(spans: pd.DataFrame) -> pd.DataFrame:
    """One row per request: the ``civicassist.handle_request`` span plus helpful columns.

    Adds:
      * ``tool_calls``    - list of tool names called in that trace
      * ``tool_context``  - concatenated tool outputs (what the agent was told)
      * ``prompt_version``, ``model``, ``guardrail_triggered`` - from span metadata
    """
    roots = spans[spans["name"] == "civicassist.handle_request"].copy()
    tools = spans[spans[KIND] == "TOOL"]

    tool_calls = tools.groupby(TRACE_ID)["name"].apply(list)
    tool_ctx = tools.groupby(TRACE_ID)[OUTPUT].apply(lambda s: "\n\n".join(str(x) for x in s if pd.notna(x)))
    roots["tool_calls"] = roots[TRACE_ID].map(tool_calls).apply(lambda v: v if isinstance(v, list) else [])
    roots["tool_context"] = roots[TRACE_ID].map(tool_ctx).fillna("(no tools were called)")

    meta_col = "attributes.metadata"
    meta = roots[meta_col].apply(_parse_metadata) if meta_col in roots else pd.Series([{}] * len(roots), index=roots.index)
    for key in ["prompt_version", "model", "guardrail_triggered"]:
        roots[key] = meta.apply(lambda m, k=key: m.get(k))

    roots = roots.rename(columns={INPUT: "input", OUTPUT: "output", **_canonical_eval_columns(roots.columns)})
    return roots.reset_index(drop=True)


_EVAL_COL = re.compile(r"^evals?[._](.+?)[._](label|score|explanation)$", re.IGNORECASE)


def _canonical_eval_columns(columns) -> dict:
    """Map exported eval columns to ``eval.<name>.<label|score|explanation>``,
    whatever separator or casing the export uses."""
    mapping = {}
    for col in columns:
        m = _EVAL_COL.match(str(col))
        if m:
            mapping[col] = f"eval.{m.group(1)}.{m.group(2).lower()}"
    return mapping


# --------------------------------------------------------------------------
# Logging evals back to Arize
# --------------------------------------------------------------------------

def to_arize_eval_columns(results: pd.DataFrame, eval_names: list[str]) -> pd.DataFrame:
    """Convert phoenix-evals output (``<name>_score`` dict columns) into the
    ``eval.<name>.label / .score / .explanation`` columns Arize expects."""
    out = pd.DataFrame({SPAN_ID: results[SPAN_ID]})
    for name in eval_names:
        scores = results[f"{name}_score"].apply(lambda s: s if isinstance(s, dict) else {})
        out[f"eval.{name}.label"] = scores.apply(lambda s: s.get("label") or ("pass" if s.get("score") == 1 else "fail" if s.get("score") == 0 else None))
        out[f"eval.{name}.score"] = scores.apply(lambda s: s.get("score"))
        out[f"eval.{name}.explanation"] = scores.apply(lambda s: s.get("explanation") or "")
    return out


def log_evals(eval_df: pd.DataFrame) -> None:
    """Send eval results to Arize, one evaluator at a time.

    Rows where an evaluator produced neither a label nor a score (for example,
    the judge call errored) are skipped, because Arize rejects them.
    """
    client = arize_client()
    names = sorted({c.split(".")[1] for c in eval_df.columns if c.startswith("eval.")})
    for name in names:
        cols = [c for c in eval_df.columns if c.startswith(f"eval.{name}.")]
        part = eval_df[[SPAN_ID, *cols]]
        part = part[part[f"eval.{name}.label"].notna() | part[f"eval.{name}.score"].notna()]
        if part.empty:
            continue
        client.spans.update_evaluations(
            space_id=os.environ["ARIZE_SPACE_ID"],
            project_name=os.environ["ARIZE_PROJECT_NAME"],
            dataframe=part.reset_index(drop=True),
        )
        print(f"✅ Logged {len(part)} '{name}' evals to Arize.")
    print("Refresh your project in Arize to see them.")


# --------------------------------------------------------------------------
# Cost math (used in the dashboards and ROI labs)
# --------------------------------------------------------------------------

# USD per 1M tokens. Check current pricing before you quote these numbers.
MODEL_PRICES = {
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}

PROMPT_TOKENS = "attributes.llm.token_count.prompt"
COMPLETION_TOKENS = "attributes.llm.token_count.completion"
MODEL_NAME = "attributes.llm.model_name"


def _price_for(model: str | None) -> dict:
    if not isinstance(model, str):
        return MODEL_PRICES["gpt-4.1-mini"]
    # match the longest known prefix, e.g. "gpt-4.1-mini-2025-04-14" -> "gpt-4.1-mini"
    for name in sorted(MODEL_PRICES, key=len, reverse=True):
        if model.startswith(name):
            return MODEL_PRICES[name]
    return MODEL_PRICES["gpt-4.1-mini"]


def cost_per_trace(spans: pd.DataFrame) -> pd.DataFrame:
    """Sum token usage and estimated cost per trace from LLM spans."""
    llm = spans[spans[KIND] == "LLM"].copy()
    for col in [PROMPT_TOKENS, COMPLETION_TOKENS]:
        llm[col] = pd.to_numeric(llm.get(col), errors="coerce").fillna(0)
    prices = llm.get(MODEL_NAME, pd.Series(index=llm.index, dtype=object)).apply(_price_for)
    llm["cost_usd"] = (
        llm[PROMPT_TOKENS] * prices.apply(lambda p: p["input"]) + llm[COMPLETION_TOKENS] * prices.apply(lambda p: p["output"])
    ) / 1_000_000
    per_trace = llm.groupby(TRACE_ID).agg(
        llm_calls=("name", "count"),
        prompt_tokens=(PROMPT_TOKENS, "sum"),
        completion_tokens=(COMPLETION_TOKENS, "sum"),
        cost_usd=("cost_usd", "sum"),
    )
    return per_trace.reset_index()
