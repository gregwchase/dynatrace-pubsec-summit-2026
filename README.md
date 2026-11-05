# Traces to Insights: A Hands-On Workshop with Arize AX

**Dynatrace Public Sector Summit 2026**

Start with an agentic application and leave with a reusable workflow: **observe → measure → improve → catch issues in production → prove ROI**. No prior experience needed. Everything runs in Google Colab or a local Python 3.10+ environment.

## The app: CivicAssist

CivicAssist is an AI agent for the **State of Columbia Department of Community Services** (a fictional agency). Residents ask it about benefit programs, eligibility, application status, and office locations. It's built with **LangGraph** and runs on **OpenAI, Anthropic, Azure OpenAI, or Amazon Bedrock**. It has:

- **4 tools:** `search_programs`, `check_eligibility`, `get_application_status`, `find_office`
- **2 guardrails:** block Social Security numbers (input) and block guaranteed-approval language (output)
- **A graph:** `input_guardrail → agent ⇄ tools → output_guardrail`
- **2 prompt versions:** `v1` (as shipped, with flaws you'll find using evals) and `v2` (the fix you'll prove with experiments)

All data is mock data. No real systems or personal information are involved.

## Live session (60 minutes): start here

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/workshop_60min.ipynb) **[`notebooks/workshop_60min.ipynb`](notebooks/workshop_60min.ipynb)**

One notebook covers all six topics in an hour. Traffic runs in the background, and evals and experiments run concurrently, so you spend the time exploring instead of waiting.

| Time | Part |
|---|---|
| 0:00 | Setup |
| 0:05 | **Observe:** trace the agent with OpenInference auto-instrumentation |
| 0:15 | **Measure:** code and LLM-as-a-judge evals, then promote them to online evaluators and a continuous task |
| 0:30 | **Improve:** traces → dataset, Prompt Playground, v1 vs. v2 experiments side by side |
| 0:43 | **Catch issues in production:** Signal and a shared dashboard |
| 0:53 | **Prove value:** cost per successful outcome; measure before you build |

## Self-paced labs (go deeper after the session)

The same material, expanded into five notebooks (about 2.5 hours total). They add backfill runs, online code evaluators, a cheaper-model experiment, more dashboard widgets, and time-to-value modeling.

| # | Lab | What you'll do | Time | Open |
|---|---|---|---|---|
| 1 | [Tracing](notebooks/01_tracing.ipynb) | Auto-instrument the agent with OpenInference; explore LLM, tool, guardrail, and agent spans; generate "production" traffic | 25 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/01_tracing.ipynb) |
| 2 | [Evals](notebooks/02_evals.ipynb) | Build code-based and LLM-as-a-judge evaluators (hallucination, tool-call accuracy, citations), log the results to your traces, then create them as **online evaluators and continuous tasks** in Arize with the SDK | 35 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/02_evals.ipynb) |
| 3 | [Datasets & Experiments](notebooks/03_datasets_experiments.ipynb) | Turn failing traces into a dataset, iterate in Prompt Playground, run v1 vs. v2 vs. a cheaper model, and compare side by side | 30 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/03_datasets_experiments.ipynb) |
| 4 | [Signal & Dashboards](notebooks/04_signal_and_dashboards.ipynb) | Get a ranked list of production issues from Signal, then build and share a dashboard for eval pass rate, cost per trace, latency, and guardrails | 20 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/04_signal_and_dashboards.ipynb) |
| 5 | [ROI](notebooks/05_roi.ipynb) | Calculate cost per successful outcome from your own traces, model time to value, and fill in the measure-before-you-build worksheet | 15 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/05_roi.ipynb) |

Run the labs in order. Each one builds on the traces, evals, and datasets from the one before. They're independent of the 60-minute notebook, but if you already ran it, the labs reuse the same project.

## What you need

- A laptop with a browser
- A Google account (for Colab) **or** Python 3.10+ locally
- An **Arize AX** account: your Space ID and an API key ([sign up free](https://app.arize.com/auth/join))
- A key for **one model provider** (your facilitator may provide one): OpenAI, Anthropic, Azure OpenAI, or Amazon Bedrock. See [Choose a model provider](#choose-a-model-provider).

## Setup

### Option A: Google Colab (recommended)
1. Click the **Open in Colab** badge for the 60-minute notebook (or Lab 1 for the self-paced version).
2. Add `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, and your provider's keys (below) as Colab **Secrets** (🔑 icon in the left sidebar), or paste them when prompted. If you're not using OpenAI, also add `LLM_PROVIDER` as a Secret, or set it in the first cell.
3. Run the first cell. It clones this repo and installs dependencies.

### Option B: Local
```bash
git clone https://github.com/gregwchase/dynatrace-pubsec-summit-2026.git
cd dynatrace-pubsec-summit-2026
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt jupyter
cp .env.example .env        # then fill in your keys
jupyter lab notebooks/
```

Each participant enters their initials on first run, so traces go to their own Arize project: `civicassist-<initials>`.

### Choose a model provider

Set `LLM_PROVIDER` (in `.env`, as a Colab Secret, or in the notebook's first cell). The agent, the offline LLM judges, and the online evaluators in Arize all use that provider. You only need its keys:

| `LLM_PROVIDER` | Keys | Agent / judge / cheaper model |
|---|---|---|
| `openai` (default) | `OPENAI_API_KEY` | `gpt-4.1-mini` / `gpt-4.1` / `gpt-4.1-nano` |
| `anthropic` | `ANTHROPIC_API_KEY` | `claude-opus-5-5` / `claude-opus-5-5` / `claude-haiku-5-5` |
| `azure` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, optional `OPENAI_API_VERSION` (default `2024-10-21`) | Deployment names; defaults are `gpt-4.1-mini` / `gpt-4.1` / `gpt-4.1-nano` |
| `bedrock` | `AWS_BEARER_TOKEN_BEDROCK` (a [Bedrock API key](https://docs.aws.amazon.com/bedrock/latest/userguide/api-keys.html)) and `AWS_REGION`, or your normal AWS credentials | `anthropic.claude-opus-5-5` / same / `anthropic.claude-haiku-5-5` |

Override any model with `CIVIC_AGENT_MODEL`, `CIVIC_JUDGE_MODEL`, or `CIVIC_SMALL_MODEL`. For Bedrock, some regions need an inference-profile ID (for example `us.anthropic.claude-opus-5-5`); copy it from the Bedrock console. Provider settings live in [`civic_agent/llm.py`](civic_agent/llm.py).

## Repository layout

```
civic_agent/            The agentic app
  agent.py              LangGraph graph + ask() entry point (adds session/user/metadata to traces)
  llm.py                Model provider selection: OpenAI, Anthropic, Azure OpenAI, Bedrock
  tools.py              The 4 LangChain tools
  guardrails.py         SSN input guardrail, no-guarantee output guardrail (GUARDRAIL spans)
  prompts.py            PROMPT_V1 (flawed) and PROMPT_V2 (fixed)
  knowledge_base.py     Mock programs, income limits, applications, offices
  tracing.py            setup_tracing(): arize.otel.register + LangChainInstrumentor
workshop_utils.py       Credentials, judge model, span export, eval logging, online-eval helpers, cost math
scripts/generate_traffic.py   Simulates production traffic
data/golden_dataset.csv       17 SME-written questions with expected answers and tools
data/traffic_questions.json   Resident questions used for simulated traffic
notebooks/              workshop_60min.ipynb (live session) + Labs 1–5 (self-paced)
docs/facilitator_guide.md     Run-of-show, talking points, and troubleshooting
```

## Use it with your own agent

The pattern carries over to your own code:

```python3
from arize.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor  # or OpenAI Agents, LlamaIndex, CrewAI, Bedrock, ...

tracer_provider = register(space_id="...", api_key="...", project_name="my-agent")
LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
```

Then reuse the evaluator patterns from Lab 2, the experiment loop from Lab 3, and the ROI worksheet from Lab 5.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No traces in Arize | Run `flush()`, wait 30–60s, refresh. Check that the project name matches `civicassist-<initials>`. |
| `export_spans` returns 0 rows | Traces can take a minute to become queryable. Also check that the time window (`hours=24`) covers your runs. |
| `429` / rate limit / `ThrottlingException` | Lower `--concurrency` in `generate_traffic.py` (e.g., `--concurrency 2`) and `concurrency=` in experiments. |
| Lab 3 says "no eval columns" | Finish Lab 2 section 5 (`log_evals`) first. The lab falls back to a sample of traces so you can keep going. |
| `model not found` / `DeploymentNotFound` | Set `CIVIC_AGENT_MODEL` (and `CIVIC_JUDGE_MODEL`) to a model your key can access: an Azure deployment name, or a Bedrock model or inference-profile ID. Or pass `model=` to `ask()`. |
| Bedrock `AccessDeniedException` | Enable model access for that model in the Bedrock console, in the same `AWS_REGION`. |
