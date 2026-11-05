# Facilitator Guide

## Run of show: 60 minutes (`notebooks/workshop_60min.ipynb`)

Everyone works in **one notebook**. Each Colab notebook gets its own runtime, so using a single notebook avoids five reinstalls and five rounds of granting Secrets. The notebook keeps waits short. Traffic runs in background processes, and evals and experiments run concurrently (`nest_asyncio` + async tasks). Each step that takes a while has something to talk about or demo during it.

| Time | Segment | You do / say | Attendees' notebook is... |
|---|---|---|---|
| 0:00 | **Welcome + setup** (5) | Have everyone open the Colab link and run the setup cell **first**. The install takes 60–90 s. Meanwhile: why agents need observability (non-deterministic, multi-step, tool-using; APM can't tell you whether the *answer* was right). | installing |
| 0:05 | **1 · Observe** (10) | Explain the two-line instrumentation. After the first code cell: walk through the trace tree on the projector (tool span args, LLM span, `block_ssn` guardrail, metadata). Read `PROMPT_V1` aloud and ask what worries people. | sending 30 v1 requests in the background |
| 0:15 | **2 · Measure** (15) | Code vs. LLM judges; explanations matter. The judges take about 30 s. Show one failure's explanation. Then **go online**: the evaluators + continuous task cell. Emphasize that it's the same rubric, now running in Arize on every new trace. | judging concurrently |
| 0:30 | **3 · Improve** (13) | Traces → dataset. **Demo Prompt Playground from the front while the experiment cell runs** (about 1 min per experiment). Then go to the Compare view: look for regressions, not just the average. | running 2 experiments |
| 0:43 | **4 · Production** (10) | Attendees start v2 traffic, which the online task scores. **Demo Signal on the pre-seeded demo project** (attendee projects have only ~60 traces; Signal looks better with more). Show the pre-built dashboard; attendees add one widget and click Share. | sending 30 v2 requests in the background |
| 0:53 | **5 · Prove value** (6) | Run the ROI cell; point out that AI cost is cents and failure cost is dollars. Go through the 5-question worksheet as a discussion. | judging any unscored v2 traces |
| 0:59 | **Wrap** (1) | Point to the self-paced labs. **Have everyone run the cleanup cell.** | deleting online task |

### If you're running behind
- **At 0:30:** skip the `prod-failures` dataset and just describe it. Go straight to the golden dataset and experiments.
- **At 0:43:** skip attendee dashboards and show yours. Signal is demo-only anyway.
- **At 0:53:** show the ROI table from your own run on the projector, and spend the time on the worksheet discussion.
- **Concurrency/rate limits:** if attendees hit 429s, have them change `CONCURRENCY` to `3` in the setup cell and re-run it. Locally, the `WORKSHOP_CONCURRENCY` env var does the same.

### Self-paced / extended version (about 2.5 hours)
Labs 1–5 (`notebooks/01_…` through `05_…`) are the same material in depth, for take-home or a longer slot. For a 90–120 minute session, run the labs and demo Lab 2 §7 (online evals), Lab 3 Experiment C, and Lab 4 from the front.

## Before the event

- [ ] **Arize space** for attendees. Decide between per-attendee accounts and a shared workshop space with API keys. Each attendee's traces go to `civicassist-<initials>`, so a shared space works.
- [ ] **Pick the model provider and set it for everyone.** Decide on OpenAI, Anthropic, Azure OpenAI, or Bedrock, and hand out `LLM_PROVIDER` with the keys (see the README's provider table). Bedrock attendees need model access enabled in the chosen region, and Azure attendees need deployments named like the defaults (or `CIVIC_AGENT_MODEL` / `CIVIC_JUDGE_MODEL`).
- [ ] **A provider key with enough rate limit.** In the 60-minute notebook, each attendee runs up to `CONCURRENCY` (default 8, set in the setup cell) parallel judge or agent calls. With 50 attendees in sync, expect bursts of **several hundred requests per minute** on both the agent model and the judge model. On OpenAI use Tier 4+; on Anthropic, Azure, or Bedrock, check the per-model rate or token quota and request an increase if needed. Have a backup key. If your limit is lower, have attendees set `CONCURRENCY` to 3 or 4 in the setup cell.
- [ ] **Run `workshop_60min.ipynb` end to end in a fresh Colab runtime the day before, and time each part.** Also run the labs if you'll point people to them. Use the provider you'll run on the day, and confirm its default model IDs (`civic_agent/llm.py`) are still available. The Claude defaults (`claude-opus-5-5`) are slower per request than `gpt-4.1-mini`; if the timing is tight, set `CIVIC_AGENT_MODEL` to a faster model such as `claude-sonnet-5-5` or `claude-haiku-5-5`.
- [ ] **AI integration for online judges.** Lab 2 section 7 and Part 2 of the 60-minute notebook create (or reuse) an AI integration for the attendee's provider, named `civicassist-workshop-<provider>`. Bedrock integrations created this way use the Bedrock API key; if attendees use IAM credentials instead, create a Bedrock integration with an IAM role in Arize yourself. Integration names are unique per account, so in a shared account everyone reuses the first one created, with *that* person's key. Better: create it yourself with the workshop key beforehand, and give attendees its ID as `ARIZE_AI_INTEGRATION_ID` (Colab Secret or `.env`).
- [ ] **Online eval costs.** The 60-minute notebook creates one continuous task per attendee (two judge-model calls per new trace, ~60 calls during the session). The self-paced Lab 2 creates two tasks plus a backfill. Remind people to run the cleanup cell (last cell of the 60-minute notebook, or end of Lab 5). Afterward, check **Evals & Tasks** for leftover `civicassist-*` tasks and delete them.
- [ ] **Confirm that online tasks work end to end** in the workshop space. Specifically: (1) the `query_filter` syntax `name = '...' AND attributes.metadata.guardrail_triggered = 'none'` matches root spans; (2) the `attributes.metadata.tool_context` column mapping resolves; (3) the managed Contains Any Keyword evaluator accepts the `keywords` static param. If a backfill run says `COMPLETED` with 0 successes, one of these is the likely cause.
- [ ] **Seed a demo project** with more traffic than attendees will have, so Signal and dashboards look good on the projector:
  ```bash
  python scripts/generate_traffic.py --project civicassist-demo --n 200 --prompt-version v1 --concurrency 8
  python scripts/generate_traffic.py --project civicassist-demo --n 200 --prompt-version v2 --concurrency 8 --seed 11
  ```
  Then run Lab 2 (including the online tasks in section 7) and Lab 4 section 3 against it (set `WORKSHOP_PARTICIPANT=demo`). If you seeded this project before the `tool_context` metadata was added to the agent, re-seed it. Older traces don't have the field, so the online hallucination judge would see no tool results.
- [ ] **Pre-build the demo dashboard** from the Part 4 / Lab 4 widget table and confirm the Signal analysis shows meaningful issues on the demo project.
- [ ] **Verify the UI click paths** in Labs 2–4 (Playground, dataset Compare, Signal, Dashboards, online eval Tasks). Menu labels change between releases; update the notebook text if they've moved.
- [ ] Make the repo public (or share access) so Colab can clone it.

## What attendees should discover

These are the planted issues in `PROMPT_V1`. Let attendees find them rather than telling them up front.

| Planted flaw (v1) | Symptom in traces | Eval that catches it | Fixed in v2 by |
|---|---|---|---|
| "use your general knowledge" | Confident answers about student loans, Medicaid, homebuyer programs, unemployment | `hallucination` (LLM judge) | Rules 1 and 4: tool-grounded only; refer to hotline |
| "avoid asking follow-up questions" | Guesses household size, then answers eligibility | `tool_call_accuracy`; `missing_info` golden row | Rule 2: ask for missing info |
| Never requires `check_eligibility` | Model does income math itself, sometimes wrong (e.g., household of 8) | `eligibility_tool_used` (code); `tool_call_accuracy` | Rule 2 |
| No citation requirement | Answers without source links | `cites_source` (code) | Rule 6 |
| "confident" tone | Occasional "you'll definitely qualify" → output guardrail fires | Guardrail span + `guardrail_triggered` metadata | Rule 5 |

LLMs are non-deterministic, so not every flaw shows up in every run. That's a teaching point in itself: it's why you measure over a dataset instead of eyeballing one response.

## Talking points by lab

**Lab 1: Tracing**
- The integration is two lines and doesn't touch agent code. It's OpenTelemetry under the hood, so it fits existing OTel and Dynatrace pipelines.
- Traces go only where your OpenTelemetry exporter sends them. Nothing is sent to a framework vendor's cloud, which matters for data residency and ATO conversations.
- The same traces come out whichever provider runs the model (OpenAI, Anthropic, Azure OpenAI, or Bedrock). Agencies that have standardized on Azure or AWS keep the same workflow.
- Guardrails are plain Python, traced with a few lines of standard OpenTelemetry (`civic_agent/guardrails.py`). Any custom step can be traced the same way.
- Sessions and users: the `ask()` wrapper attaches `session.id`, `user.id`, and metadata. Show the Sessions view.

**Lab 2: Evals**
- Prototype offline, then promote to online. The same rubric goes from a notebook to a versioned evaluator in Arize, and a task runs it on every new trace. That's the step from "we evaluated it once" to "we catch issues in production."
- Online evaluators score one span at a time. That's why the agent writes its tool results onto the root span (`metadata.tool_context`). Instrumenting for evals is part of instrumenting.
- Use code evals for objective rules (cheap, run on 100% of traffic) and LLM judges for judgment calls. Sample LLM-judge evals in production.
- Explanations matter more than scores: they tell you *why*, which tells you what to fix.
- Judges need evaluating too. Mention building a small human-labeled set to measure judge agreement.

**Lab 3: Datasets & Experiments**
- Failures from production become regression tests. That's the flywheel.
- Playground is for intuition on one example. Experiments are for proof across many.
- Compare row by row, not only averages. Look for regressions.
- Experiment C sets up ROI: a smaller model with a better prompt can beat a bigger model with a bad prompt.

**Lab 4: Signal & Dashboards**
- Evals answer the questions you already knew to ask. Signal surfaces the ones you didn't.
- Prioritize by severity × frequency. In public sector work, a wrong eligibility answer carries equity and legal risk.
- Dashboards are for the people who *don't* open traces: program directors, security officers, budget owners. Ask the room who their audience is.

**Lab 5: ROI**
- AI cost per request is fractions of a cent; failure cost is dollars. Quality is the main ROI lever.
- Cost per successful outcome is the metric that holds up in a budget conversation.
- Agree on measurement before building. If a team can't fill in the worksheet, they aren't ready to staff the project.
- Non-dollar returns in public sector: after-hours access, language access, staff burnout, resident trust.

## Troubleshooting during the session

| Issue | Fix |
|---|---|
| Many attendees hit 429s (or Bedrock `ThrottlingException`) | Have everyone set `CONCURRENCY = 3` in the setup cell, or stagger by table. |
| Colab install is slow | It takes about 60–90 seconds the first time. Start Lab 1's setup cell during the welcome. |
| `export_spans` is empty right after sending traces | Ingestion lag. Wait a minute and re-run. |
| Eval columns missing in Lab 3/5 | Confirm Lab 2 `log_evals` printed ✅. Re-run it if needed. Labs fall back gracefully. |
| An attendee's v1 looks perfect | Non-determinism. Have them compare with a neighbor, or run more traffic. Use the demo project. |
