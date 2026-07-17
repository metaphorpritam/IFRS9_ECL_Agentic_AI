"""Live smoke test of the REASONED route — NOT part of pytest.

Loads .env (OPENROUTER_API_KEY), warms the engine, then asks THREE real
questions through agent.graph.run_agent — one from each of the router's
three classes (spec: "3-way scope split") — and prints route + mode + the
first 200 characters of each answer:

  1. the MOTIVATING example (a live user report): a conceptually relevant
     modeling question with no fixed tool for it. Before this task it hit
     REFUSE; it must now come back route="REASONED", mode="reasoned".
  2. a REFUSAL-class question (no connection to this model or credit risk).
  3. a TOOL-class question (a fixed Tier-1 engine computation).

The offline suite (tests/test_reasoned.py) proves the REASONED node's
mechanics with a mocked LLM; this script proves the OpenRouter plumbing
(router classification + reasoning narration) end to end, live.

Run:  cd <project root> && uv run --no-sync python scripts/smoke_reasoned.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

QUESTIONS = [
    ("motivating (REASONED-class)",
     "Does the satellite need a UER x HPI interaction, or do the main "
     "effects and momentum already account for the joint stress "
     "response?"),
    ("refusal-class",
     "What's your view on Bitcoin as a hedge for our book?"),
    ("tool-class",
     "What happens to the allowance if unemployment rises 2 percentage "
     "points?"),
]


def main() -> int:
    from agent.graph import run_agent
    from agent.tools_tier1 import warm_up

    t0 = time.perf_counter()
    warm_up()                       # pay the engine build up front
    print(f"[engine warm in {time.perf_counter() - t0:.1f}s]\n")

    exit_code = 0
    for label, question in QUESTIONS:
        print(f"=== {label} " + "=" * (60 - len(label)))
        print(f"Q: {question}\n")

        t1 = time.perf_counter()
        try:
            final = run_agent(question)
        except Exception as exc:                       # pragma: no cover
            print(f"!! run_agent raised: {type(exc).__name__}: {exc}\n")
            exit_code = 1
            continue
        elapsed = time.perf_counter() - t1

        route = final["route"]
        mode = final.get("mode", "<no mode field>")
        answer = final["answer"]
        print(f"route: {route}")
        print(f"mode:  {mode}")
        print(f"answer (first 200 chars): {answer[:200]!r}")
        print(f"[{elapsed:.1f}s]\n")

        print("--- trace " + "-" * 50)
        for event in final["trace"]:
            print(json.dumps(event, default=str))
        print("-" * 61 + "\n")

    print("[full traces appended to outputs/agent_log/agent_runs.jsonl]")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
