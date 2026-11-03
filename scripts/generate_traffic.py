"""Simulate "production" traffic for CivicAssist and send the traces to Arize.

Usage (from the repo root):
    python scripts/generate_traffic.py --n 60 --prompt-version v1

Labs 4-6 (Signal, dashboards, ROI) work best with 50+ traces. Facilitators can
run this ahead of time against a shared project with --project.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from civic_agent import ask_async, flush, setup_tracing  # noqa: E402
from workshop_utils import load_credentials  # noqa: E402


async def main(n: int, prompt_version: str, model: str | None, concurrency: int, seed: int) -> None:
    questions = json.loads((ROOT / "data" / "traffic_questions.json").read_text())["questions"]
    rng = random.Random(seed)
    users = [f"resident-{i:03d}" for i in range(1, 16)]
    sem = asyncio.Semaphore(concurrency)
    done = 0

    async def one(i: int) -> None:
        nonlocal done
        user = rng.choice(users)
        q = questions[i % len(questions)] if i < len(questions) else rng.choice(questions)
        async with sem:
            try:
                r = await ask_async(q, prompt_version=prompt_version, model=model, user_id=user,
                                    session_id=f"{user}-s{rng.randint(1, 3)}", tags=["simulated-traffic"])
                flag = f" [guardrail: {r['guardrail_triggered']}]" if r["guardrail_triggered"] else ""
                status = f"tools={r['tools_called']}{flag}"
            except Exception as exc:  # keep going; the error is in the trace
                status = f"ERROR {type(exc).__name__}: {exc}"
        done += 1
        print(f"[{done:>3}/{n}] {q[:60]:<60} {status}")

    await asyncio.gather(*(one(i) for i in range(n)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=60, help="number of requests to send")
    parser.add_argument("--prompt-version", default="v1", choices=["v1", "v2"])
    parser.add_argument("--model", default=None, help="override the agent model")
    parser.add_argument("--project", default=None, help="Arize project name (default: civicassist-<handle>)")
    parser.add_argument("--participant", default=None, help="your initials/handle")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if args.project:
        os.environ["ARIZE_PROJECT_NAME"] = args.project
    load_credentials(args.participant)
    setup_tracing()
    asyncio.run(main(args.n, args.prompt_version, args.model, args.concurrency, args.seed))
    flush()
    print("\n✅ Done. Open your project in Arize to explore the traces.")
