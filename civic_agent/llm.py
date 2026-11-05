"""Pick the model provider for the agent and the LLM judges.

Set ``LLM_PROVIDER`` to one of ``openai`` (default), ``anthropic``, ``azure``,
or ``bedrock``. Every chat model in the workshop comes from
:func:`get_chat_model`, so switching providers is a one-line change.

Each provider has three model "roles":

* ``agent``: runs CivicAssist (override with ``CIVIC_AGENT_MODEL``)
* ``judge``: the LLM-as-a-judge evaluators (override with ``CIVIC_JUDGE_MODEL``)
* ``small``: the cheaper model in the Lab 3 experiment (override with ``CIVIC_SMALL_MODEL``)

For Azure OpenAI, the model names are your **deployment names**.
"""

from __future__ import annotations

import os
from typing import Any

PROVIDERS = ("openai", "anthropic", "azure", "bedrock")

DEFAULT_MODELS: dict[str, dict[str, str]] = {
    "openai": {"agent": "gpt-4.1-mini", "judge": "gpt-4.1", "small": "gpt-4.1-nano"},
    # Azure: these are deployment names. Name your deployments after the models, or override.
    "azure": {"agent": "gpt-4.1-mini", "judge": "gpt-4.1", "small": "gpt-4.1-nano"},
    "anthropic": {"agent": "claude-opus-5-5", "judge": "claude-opus-5-5", "small": "claude-haiku-5-5"},
    # Bedrock model IDs. Some regions require an inference-profile ID instead
    # (for example with a "us." or "global." prefix); check the Bedrock console.
    "bedrock": {"agent": "anthropic.claude-opus-5-5", "judge": "anthropic.claude-opus-5-5",
                "small": "anthropic.claude-haiku-5-5"},
}

_ROLE_ENV = {"agent": "CIVIC_AGENT_MODEL", "judge": "CIVIC_JUDGE_MODEL", "small": "CIVIC_SMALL_MODEL"}

# Which credentials each provider needs. Bedrock accepts either a Bedrock API key
# (AWS_BEARER_TOKEN_BEDROCK) or standard AWS credentials (see load_credentials).
REQUIRED_ENV: dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "azure": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "bedrock": ["AWS_BEARER_TOKEN_BEDROCK", "AWS_REGION"],
}

AZURE_API_VERSION_DEFAULT = "2024-10-21"


def get_provider() -> str:
    provider = (os.getenv("LLM_PROVIDER") or "openai").strip().lower()
    aliases = {"azure_openai": "azure", "azure-openai": "azure", "aws": "bedrock", "claude": "anthropic"}
    provider = aliases.get(provider, provider)
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    return provider


def default_model(role: str = "agent", provider: str | None = None) -> str:
    provider = provider or get_provider()
    return os.getenv(_ROLE_ENV[role]) or DEFAULT_MODELS[provider][role]


def supports_temperature(provider: str | None = None, model: str | None = None) -> bool:
    """Current Claude models reject sampling parameters such as ``temperature``,
    so only send it to OpenAI-family models."""
    provider = provider or get_provider()
    return provider in ("openai", "azure") and not (model or "").startswith(("o1", "o3", "o4", "gpt-5"))


def get_chat_model(role: str = "agent", model: str | None = None, temperature: float | None = None, **kwargs: Any):
    """Return a LangChain chat model for the configured provider.

    ``temperature`` is applied only where the model accepts it.
    """
    provider = get_provider()
    model = model or default_model(role, provider)
    if temperature is not None and supports_temperature(provider, model):
        kwargs["temperature"] = temperature

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model, **kwargs)

    if provider == "azure":
        from langchain_openai import AzureChatOpenAI

        return AzureChatOpenAI(
            azure_deployment=model,
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version=os.getenv("OPENAI_API_VERSION", AZURE_API_VERSION_DEFAULT),
            **kwargs,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model, max_tokens=16_000, **kwargs)

    from langchain_aws import ChatBedrockConverse

    # Uses AWS_BEARER_TOKEN_BEDROCK (a Bedrock API key) if set, otherwise the
    # standard AWS credential chain (env vars, ~/.aws, instance role).
    return ChatBedrockConverse(
        model=model,
        region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
        max_tokens=16_000,
        **kwargs,
    )
