# Traces to Insights: A Hands-On Workshop with Arize AX

**Dynatrace Public Sector Summit 2026**

Start with an agentic application and leave with a reusable workflow: **observe → measure → improve → catch issues in production → prove ROI**. No prior experience needed. Everything runs in Google Colab or a local Python 3.10+ environment.

## The app: CivicAssist

CivicAssist is an AI agent for the **State of Columbia Department of Community Services** (a fictional agency). Residents ask it about benefit programs, eligibility, application status, and office locations. It's built on the **OpenAI Agents SDK** and has:

- **4 tools:** `search_programs`, `check_eligibility`, `get_application_status`, `find_office`
- **2 guardrails:** block Social Security numbers (input) and block guaranteed-approval language (output)
- **2 prompt versions:** `v1` (as shipped, with flaws you'll find using evals) and `v2` (the fix you'll prove with experiments)

All data is mock data. No real systems or personal information are involved.

## Labs

| # | Lab | What you'll do | Time | Open |
|---|---|---|---|---|
| 1 | [Tracing](notebooks/01_tracing.ipynb) | Auto-instrument the agent with OpenInference; explore LLM, tool, guardrail, and agent spans; generate "production" traffic | 25 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/01_tracing.ipynb) |
| 2 | [Evals](notebooks/02_evals.ipynb) | Build code-based and LLM-as-a-judge evaluators (hallucination, tool-call accuracy, citations) and log the results to your traces | 25 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/02_evals.ipynb) |
| 3 | [Datasets & Experiments](notebooks/03_datasets_experiments.ipynb) | Turn failing traces into a dataset, iterate in Prompt Playground, run v1 vs. v2 vs. a cheaper model, and compare side by side | 30 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/03_datasets_experiments.ipynb) |
| 4 | [Signal & Dashboards](notebooks/04_signal_and_dashboards.ipynb) | Get a ranked list of production issues from Signal, then build and share a dashboard for eval pass rate, cost per trace, latency, and guardrails | 20 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/04_signal_and_dashboards.ipynb) |
| 5 | [ROI](notebooks/05_roi.ipynb) | Calculate cost per successful outcome from your own traces, model time to value, and fill in the measure-before-you-build worksheet | 15 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gregwchase/dynatrace-pubsec-summit-2026/blob/main/notebooks/05_roi.ipynb) |

Run the labs in order. Each one builds on the traces, evals, and datasets from the one before.

## What you need

- A laptop with a browser
- A Google account (for Colab) **or** Python 3.10+ locally
- An **Arize AX** account: your Space ID and an API key ([sign up free](https://app.arize.com/auth/join))
- An **OpenAI API key** (your facilitator may provide one)

## Setup

### Option A: Google Colab (recommended)
1. Click the **Open in Colab** badge for Lab 1.
2. Add `ARIZE_SPACE_ID`, `ARIZE_API_KEY`, and `OPENAI_API_KEY` as Colab **Secrets** (🔑 icon in the left sidebar), or paste them when prompted.
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

## Repository layout

```
civic_agent/            The agentic app
  agent.py              Agent definition + ask() entry point (adds session/user/metadata to traces)
  tools.py              The 4 function tools
  guardrails.py         SSN input guardrail, no-guarantee output guardrail
  prompts.py            PROMPT_V1 (flawed) and PROMPT_V2 (fixed)
  knowledge_base.py     Mock programs, income limits, applications, offices
  tracing.py            setup_tracing(): arize.otel.register + OpenAIAgentsInstrumentor
workshop_utils.py       Credentials, span export, eval logging, cost math
scripts/generate_traffic.py   Simulates production traffic
data/golden_dataset.csv       17 SME-written questions with expected answers and tools
data/traffic_questions.json   Resident questions used for simulated traffic
notebooks/              Labs 1–5
docs/facilitator_guide.md     Run-of-show, talking points, and troubleshooting
```

## Use it with your own agent

The pattern carries over to your own code:

```python3
from arize.otel import register
from openinference.instrumentation.openai_agents import OpenAIAgentsInstrumentor  # or LangChain, LlamaIndex, CrewAI, Bedrock, ...

tracer_provider = register(space_id="...", api_key="...", project_name="my-agent")
OpenAIAgentsInstrumentor().instrument(tracer_provider=tracer_provider)
```

Then reuse the evaluator patterns from Lab 2, the experiment loop from Lab 3, and the ROI worksheet from Lab 5.

## Troubleshooting

| Symptom | Fix |
|---|---|
| No traces in Arize | Run `flush()`, wait 30–60s, refresh. Check that the project name matches `civicassist-<initials>`. |
| `export_spans` returns 0 rows | Traces can take a minute to become queryable. Also check that the time window (`hours=24`) covers your runs. |
| OpenAI `429 Rate limit` | Lower `--concurrency` in `generate_traffic.py` (e.g., `--concurrency 2`) and `concurrency=` in experiments. |
| Lab 3 says "no eval columns" | Finish Lab 2 section 5 (`log_evals`) first. The lab falls back to a sample of traces so you can keep going. |
| `model not found` | Set `CIVIC_AGENT_MODEL` to a model your key can access, or pass `model=` to `ask()`. |
