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

ARIZE_KEYS = ["ARIZE_SPACE_ID", "ARIZE_API_KEY"]
NOT_SECRET = {"AZURE_OPENAI_ENDPOINT", "AWS_REGION"}  # prompted with input(), not getpass()


def _from_colab_secrets(key: str) -> str | None:
    try:
        from google.colab import userdata  # type: ignore

        return userdata.get(key)
    except Exception:
        return None


def _ensure(key: str) -> None:
    if os.getenv(key):
        return
    value = _from_colab_secrets(key)
    if not value:
        value = input(f"{key}: ") if key in NOT_SECRET else getpass.getpass(f"{key}: ")
    os.environ[key] = value.strip()


def _has_aws_credentials() -> bool:
    if os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE"):
        return True
    try:
        import boto3

        return boto3.Session().get_credentials() is not None
    except Exception:
        return False


def load_credentials(participant: str | None = None, provider: str | None = None) -> str:
    """Load keys from (1) env / .env, (2) Colab secrets, or (3) a prompt.

    ``provider`` (or ``LLM_PROVIDER``) picks the model provider: ``openai``
    (default), ``anthropic``, ``azure``, or ``bedrock``. Only that provider's
    keys are requested.

    Returns the Arize project name for this participant, e.g. ``civicassist-jdoe``.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    if provider:
        os.environ["LLM_PROVIDER"] = provider
    elif not os.getenv("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"] = _from_colab_secrets("LLM_PROVIDER") or "openai"

    from civic_agent.llm import REQUIRED_ENV, default_model, get_provider

    provider = get_provider()
    os.environ["LLM_PROVIDER"] = provider
    needed = list(REQUIRED_ENV[provider])
    if provider == "bedrock" and not os.getenv("AWS_BEARER_TOKEN_BEDROCK") and not _from_colab_secrets("AWS_BEARER_TOKEN_BEDROCK") and _has_aws_credentials():
        needed.remove("AWS_BEARER_TOKEN_BEDROCK")  # standard AWS credentials work too
    if provider == "azure" and not os.getenv("OPENAI_API_VERSION"):
        if version := _from_colab_secrets("OPENAI_API_VERSION"):
            os.environ["OPENAI_API_VERSION"] = version
    # Optional model overrides can come from Colab Secrets too.
    for key in ["CIVIC_AGENT_MODEL", "CIVIC_JUDGE_MODEL", "CIVIC_SMALL_MODEL", "ARIZE_AI_INTEGRATION_ID"]:
        if not os.getenv(key) and (value := _from_colab_secrets(key)):
            os.environ[key] = value

    for key in ARIZE_KEYS + needed:
        _ensure(key)

    if not os.getenv("ARIZE_PROJECT_NAME"):
        participant = participant or os.getenv("WORKSHOP_PARTICIPANT") or input("Your initials or handle: ")
        handle = re.sub(r"[^a-z0-9-]", "", participant.lower().replace(" ", "-")) or "anon"
        os.environ["ARIZE_PROJECT_NAME"] = f"civicassist-{handle}"

    print(f"✅ Credentials loaded. Arize project: {os.environ['ARIZE_PROJECT_NAME']}")
    print(f"   Model provider: {provider} · agent: {default_model('agent')} · judge: {default_model('judge')}")
    return os.environ["ARIZE_PROJECT_NAME"]


def arize_client():
    from arize import ArizeClient

    return ArizeClient(api_key=os.environ["ARIZE_API_KEY"])


# --------------------------------------------------------------------------
# LLM judges (offline, in the notebook)
# --------------------------------------------------------------------------

class _JsonSchemaOutput:
    """Wraps a LangChain chat model so phoenix-evals asks for native JSON-schema
    output. (The default for some providers is a forced tool call, which
    current Claude models reject.) Everything else passes through."""

    def __init__(self, chat_model):
        self._chat_model = chat_model

    def __getattr__(self, name):
        return getattr(self._chat_model, name)

    def with_structured_output(self, schema, **kwargs):
        kwargs.setdefault("method", "json_schema")
        return self._chat_model.with_structured_output(schema, **kwargs)


def _rate_limit_errors() -> list:
    errors = []
    for module, name in [("openai", "RateLimitError"), ("anthropic", "RateLimitError")]:
        try:
            errors.append(getattr(__import__(module), name))
        except (ImportError, AttributeError):
            pass
    return errors


_JUDGE_PROVIDER = "civicassist"


def judge_model(model: str | None = None):
    """A phoenix-evals ``LLM`` backed by the configured provider's judge model.

    Same idea as ``LLM(provider="openai", model="gpt-4.1")``, but it works with
    any of the four workshop providers because it reuses ``civic_agent.llm``.
    """
    from phoenix.evals import LLM
    from phoenix.evals.llm.adapters.langchain.adapter import LangChainModelAdapter
    from phoenix.evals.llm.registries import PROVIDER_REGISTRY

    from civic_agent.llm import default_model, get_chat_model

    if not PROVIDER_REGISTRY.get_provider_registrations(_JUDGE_PROVIDER):
        PROVIDER_REGISTRY.register_provider(
            provider=_JUDGE_PROVIDER,
            adapter_class=LangChainModelAdapter,
            client_factory=lambda model, is_async=False, **kw: _JsonSchemaOutput(
                get_chat_model("judge", model=model, temperature=0.0, max_retries=6)),
            get_rate_limit_errors=_rate_limit_errors,
            dependencies=["langchain-core"],
        )
    return LLM(provider=_JUDGE_PROVIDER, model=model or default_model("judge"))


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


def wait_for_traces(min_traces: int, hours: int = 24, timeout: int = 180, poll: int = 15) -> pd.DataFrame:
    """Export spans, retrying until at least ``min_traces`` traces are queryable
    (ingestion takes a little while after spans are sent)."""
    import time

    deadline = time.time() + timeout
    while True:
        spans = export_spans(hours=hours)
        n = spans[TRACE_ID].nunique() if len(spans) else 0
        if n >= min_traces or time.time() > deadline:
            if n < min_traces:
                print(f"⚠️  Only {n} traces so far; continuing anyway. Re-run this cell later for more.")
            return spans
        print(f"   waiting for ingestion ({n}/{min_traces} traces)...")
        time.sleep(poll)


# --------------------------------------------------------------------------
# Background traffic (so the notebook keeps going while requests run)
# --------------------------------------------------------------------------

def start_traffic(prompt_version: str = "v1", n: int = 30, seed: int = 7, concurrency: int = 5):
    """Launch scripts/generate_traffic.py in the background. Returns the process."""
    import subprocess
    import sys

    log_path = f"traffic_{prompt_version}.log"
    log = open(log_path, "w")
    proc = subprocess.Popen(
        [sys.executable, "scripts/generate_traffic.py", "--n", str(n), "--prompt-version", prompt_version,
         "--project", os.environ["ARIZE_PROJECT_NAME"], "--seed", str(seed), "--concurrency", str(concurrency)],
        stdout=log, stderr=subprocess.STDOUT,
    )
    proc.n_requests, proc.log_path = n, log_path
    print(f"🚦 Sending {n} '{prompt_version}' requests in the background (log: {log_path})")
    return proc


def wait_for_traffic(proc, timeout: int = 300) -> None:
    proc.wait(timeout=timeout)
    with open(proc.log_path) as f:
        print("\n".join(f.read().strip().splitlines()[-3:]))
    if proc.returncode != 0:
        raise RuntimeError("Traffic generation failed; see the log file above.")


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
# Online evals: get-or-create helpers so notebook cells are safe to re-run
# --------------------------------------------------------------------------

def participant_handle() -> str:
    return os.environ["ARIZE_PROJECT_NAME"].removeprefix("civicassist-")


_ARIZE_PROVIDER = {"openai": "OPEN_AI", "azure": "AZURE_OPEN_AI", "anthropic": "ANTHROPIC", "bedrock": "AWS_BEDROCK"}


def get_or_create_ai_integration(client, name: str | None = None) -> str:
    """Return an AI integration ID the online LLM judges can use.

    Uses ``ARIZE_AI_INTEGRATION_ID`` if set (e.g. one your facilitator created).
    Otherwise reuses or creates an integration for your ``LLM_PROVIDER`` with
    the key you already loaded. Integration names are unique per account, so in
    a shared workshop account everyone reuses the first one created.
    """
    preset = os.getenv("ARIZE_AI_INTEGRATION_ID") or _from_colab_secrets("ARIZE_AI_INTEGRATION_ID")
    if preset:
        print("Using AI integration from ARIZE_AI_INTEGRATION_ID")
        return preset
    from arize.ai_integrations.types import AiIntegrationProvider

    from civic_agent.llm import default_model, get_provider

    provider = get_provider()
    name = name or f"civicassist-workshop-{provider}"
    existing = client.ai_integrations.list(name=name).ai_integrations
    match = next((i for i in existing if i.name == name), None)
    if match:
        print(f"Reusing AI integration '{name}'")
        return match.id

    kwargs = dict(name=name, provider=AiIntegrationProvider(_ARIZE_PROVIDER[provider]), function_calling_enabled=True,
                  model_names=[default_model("judge")])
    if provider == "openai":
        kwargs.update(api_key=os.environ["OPENAI_API_KEY"], enable_default_models=True)
    elif provider == "anthropic":
        kwargs.update(api_key=os.environ["ANTHROPIC_API_KEY"], enable_default_models=True)
    elif provider == "azure":
        kwargs.update(api_key=os.environ["AZURE_OPENAI_API_KEY"], base_url=os.environ["AZURE_OPENAI_ENDPOINT"])
    else:  # bedrock
        token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not token:
            raise RuntimeError(
                "Online judges on Bedrock need a Bedrock API key (AWS_BEARER_TOKEN_BEDROCK) or an AI integration "
                "set up with an IAM role. Ask your facilitator for ARIZE_AI_INTEGRATION_ID, or create one under "
                "Settings → AI Providers in Arize."
            )
        from arize.ai_integrations.types import AiIntegrationAuthType

        kwargs.update(api_key=token, auth_type=AiIntegrationAuthType.BEARER_TOKEN)
    try:
        created = client.ai_integrations.create(**kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"Couldn't create a {provider} AI integration in Arize ({exc}). Create one under Settings → AI Providers "
            "(or ask your facilitator) and set ARIZE_AI_INTEGRATION_ID."
        ) from exc
    print(f"Created AI integration '{name}'")
    return created.id


def online_judge_config(client):
    """The judge-model settings for Arize-hosted (online) evaluators, for your provider."""
    from arize.evaluators.types import EvaluatorLlmConfigRequest

    from civic_agent.llm import default_model, get_provider, supports_temperature

    provider, model = get_provider(), default_model("judge")
    provider_parameters: dict = {}
    if provider == "azure":
        provider_parameters["azure_params"] = {
            "azure_deployment_name": model,
            "azure_openai_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
            "azure_openai_version": os.getenv("OPENAI_API_VERSION", "2024-10-21"),
        }
    elif provider == "bedrock":
        provider_parameters["region"] = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"
        provider_parameters["bedrock_options"] = {"use_converse_endpoint": True}
    return EvaluatorLlmConfigRequest(
        ai_integration_id=get_or_create_ai_integration(client),
        model_name=model,
        # Current Claude models reject temperature; OpenAI judges run at 0 for repeatability.
        invocation_parameters={"temperature": 0} if supports_temperature(provider, model) else {},
        provider_parameters=provider_parameters,
    )


def find_evaluator(client, name: str):
    resp = client.evaluators.list(name=name, space=os.environ["ARIZE_SPACE_ID"])
    return next((e for e in resp.evaluators if e.name == name), None)


def find_task(client, name: str):
    resp = client.tasks.list(name=name, space=os.environ["ARIZE_SPACE_ID"])
    return next((t for t in resp.tasks if t.name == name), None)


def delete_online_evals(client, task_names: list[str], evaluator_names: list[str]) -> None:
    """Remove this participant's tasks (stops continuous scoring) and evaluators."""
    space = os.environ["ARIZE_SPACE_ID"]
    for name in task_names:
        if task := find_task(client, name):
            client.tasks.delete(task=task.id, space=space)
            print(f"Deleted task {name}")
    for name in evaluator_names:
        if ev := find_evaluator(client, name):
            client.evaluators.delete(evaluator=ev.id, space=space)
            print(f"Deleted evaluator {name}")


# --------------------------------------------------------------------------
# Cost math (used in the dashboards and ROI labs)
# --------------------------------------------------------------------------

# USD per 1M tokens. Check current pricing before you quote these numbers.
# Azure OpenAI and Bedrock bill through your cloud account and can differ
# from the list prices below; edit this table to match your contract.
MODEL_PRICES = {
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-opus-5-5": {"input": 4.00, "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "output": 10.00},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50},
}
FALLBACK_PRICE = MODEL_PRICES["gpt-4.1-mini"]

PROMPT_TOKENS = "attributes.llm.token_count.prompt"
COMPLETION_TOKENS = "attributes.llm.token_count.completion"
MODEL_NAME = "attributes.llm.model_name"


def _price_for(model: str | None) -> dict:
    if not isinstance(model, str):
        return FALLBACK_PRICE
    # Bedrock IDs look like "us.anthropic.claude-opus-5-5"; keep the model part.
    model = model.lower().rsplit("anthropic.", 1)[-1]
    # match the longest known prefix, e.g. "gpt-4.1-mini-2025-04-14" -> "gpt-4.1-mini"
    for name in sorted(MODEL_PRICES, key=len, reverse=True):
        if model.startswith(name):
            return MODEL_PRICES[name]
    return FALLBACK_PRICE


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
