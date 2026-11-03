# Facilitator Guide

## Run of show (about 2 hours 15 minutes)

| Time | Segment | Notes |
|---|---|---|
| 0:00 | Welcome + why observability for agents (10 min) | Agents are non-deterministic, multi-step, and tool-using. Logs and APM alone don't tell you whether the *answer* was right. |
| 0:10 | **Lab 1: Tracing** (25 min) | Start traffic generation (section 5) before the UI tour, so it runs while you talk. |
| 0:35 | **Lab 2: Evals** (25 min) | The LLM judges take about 1 minute on 50 traces. |
| 1:00 | Break (5 min) | |
| 1:05 | **Lab 3: Datasets & Experiments** (30 min) | Each experiment takes 2–3 minutes. Demo Prompt Playground while experiments run. |
| 1:35 | **Lab 4: Signal & Dashboards** (20 min) | Start v2 traffic first, then demo Signal on a pre-seeded project while it runs. |
| 1:55 | **Lab 5: ROI** (15 min) | Mostly discussion. The notebook supplies the numbers. |
| 2:10 | Wrap-up + Q&A (5 min) | |

### If you only have 90 minutes
- Pre-generate traffic in each attendee's project, or use a shared project (see below). This skips Lab 1 section 5.
- Lab 3: skip Experiment C (nano model) and the dry run.
- Lab 4: demo Signal and dashboards from the front instead of having everyone build them.
- Lab 5: show the outputs and go straight to the worksheet discussion.

## Before the event

- [ ] **Arize space** for attendees. Decide between per-attendee accounts and a shared workshop space with API keys. Each attendee's traces go to `civicassist-<initials>`, so a shared space works.
- [ ] **OpenAI key with enough rate limit.** With 50 attendees running 45-request traffic batches and experiments at the same time, expect bursts of several hundred requests per minute on gpt-4.1-mini and 50+ on gpt-4.1 for judges. Tier 3+ is safer. Have a backup key.
- [ ] **Run every lab end to end** in a fresh Colab runtime the day before. Confirm that model names (`gpt-4.1-mini`, `gpt-4.1`, `gpt-4.1-nano`) are still available.
- [ ] **Seed a demo project** with more traffic than attendees will have, so Signal and dashboards look good on the projector:
  ```bash
  python scripts/generate_traffic.py --project civicassist-demo --n 200 --prompt-version v1 --concurrency 8
  python scripts/generate_traffic.py --project civicassist-demo --n 200 --prompt-version v2 --concurrency 8 --seed 11
  ```
  Then run Lab 2 and Lab 4 section 3 against it (set `WORKSHOP_PARTICIPANT=demo`).
- [ ] **Pre-build the demo dashboard** from the Lab 4 widget table and confirm the Signal analysis shows meaningful issues on the demo project.
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
- `exclusive_processor=True` (the default) means Agents SDK traces go only to your collector, not to OpenAI's trace dashboard. That matters for data residency and ATO conversations.
- Sessions and users: the `ask()` wrapper attaches `session.id`, `user.id`, and metadata. Show the Sessions view.

**Lab 2: Evals**
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
| Many attendees hit 429s | Have everyone drop to `--concurrency 2`, or stagger by table. |
| Colab install is slow | It takes about 60–90 seconds the first time. Start Lab 1's setup cell during the welcome. |
| `export_spans` is empty right after sending traces | Ingestion lag. Wait a minute and re-run. |
| Eval columns missing in Lab 3/5 | Confirm Lab 2 `log_evals` printed ✅. Re-run it if needed. Labs fall back gracefully. |
| An attendee's v1 looks perfect | Non-determinism. Have them compare with a neighbor, or run more traffic. Use the demo project. |
