"""Live smoke test of the LangGraph agent — NOT part of pytest.

Loads .env (OPENROUTER_API_KEY), warms the engine, then asks one real
question through agent.graph.run_agent and prints the trace + answer.
The offline suite (tests/test_router.py) proves the graph mechanics with
mocked LLMs; this script proves the OpenRouter plumbing end to end.

Run:  cd <project root> && uv run --no-sync python scripts/demo_agent.py
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

QUESTION = ("What happens to the allowance if unemployment rises "
            "2 percentage points?")


def main() -> int:
    from agent.graph import run_agent
    from agent.tools_tier1 import warm_up

    print(f"Q: {QUESTION}\n")

    t0 = time.perf_counter()
    warm_up()                       # pay the engine build up front
    print(f"[engine warm in {time.perf_counter() - t0:.1f}s]\n")

    t1 = time.perf_counter()
    final = run_agent(QUESTION)
    elapsed = time.perf_counter() - t1

    print("--- trace " + "-" * 50)
    for event in final["trace"]:
        print(json.dumps(event))
    print("-" * 60)
    print(f"\nroute:  {final['route']}")
    print(f"answer: {final['answer']}")
    print(f"\n[agent round trip {elapsed:.1f}s; full trace appended to "
          f"outputs/agent_log/agent_runs.jsonl]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
