"""App v2 + Tier-2 local E2E smoke test (NOT part of pytest).

Exercises the five checks from the ship task against the real FastAPI app
(in-process via TestClient — same code path uvicorn would run) and the live
LLM router (OPENROUTER_API_KEY from .env). Saves every trace to
outputs/demo/appv2_e2e.json for the gate report.

Run:  cd <project root> && uv run --no-sync python scripts/e2e_appv2.py
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

from fastapi.testclient import TestClient  # noqa: E402

results: dict[str, object] = {}
ok = True


def record(name: str, passed: bool, detail: object) -> None:
    global ok
    ok = ok and passed
    results[name] = {"passed": passed, "detail": detail}
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")


def main() -> int:
    from app.api.main import app

    with TestClient(app) as client:
        # (e) every tab's data endpoints return 200 per contract
        endpoints = [
            "/api/health",
            "/api/ecl/summary",
            "/api/ecl/waterfall?t0=20&t1=40",
            "/api/exhibits/credit_cycle",
            "/api/exhibits/list",
            "/api/model/coefficients",
            "/api/model/variable_dictionary",
            "/api/model/lgd",
            "/api/policy/staging_sensitivity",
            "/api/policy/weights_table",
        ]
        endpoint_status = {}
        for ep in endpoints:
            r = client.get(ep)
            endpoint_status[ep] = r.status_code
        record("e_tab_endpoints_200", all(v == 200 for v in endpoint_status.values()),
               endpoint_status)

        # (a) scenario run -> /api/agent/interpret returns grounded interpretation
        scenario_resp = client.post("/api/tools/reweight_scenarios", json={
            "w_up": 0.2, "w_base": 0.5, "w_down": 0.3,
        })
        scenario_json = scenario_resp.json() if scenario_resp.status_code == 200 else None
        interpret_detail: dict = {"scenario_status": scenario_resp.status_code}
        if scenario_json is not None:
            interp_resp = client.post("/api/agent/interpret", json={
                "tool": "reweight_scenarios", "result": scenario_json,
            })
            interpret_detail["interpret_status"] = interp_resp.status_code
            interpret_detail["interpret_body"] = interp_resp.json()
            record("a_scenario_interpret", interp_resp.status_code == 200 and
                   bool(interp_resp.json().get("interpretation")), interpret_detail)
        else:
            interpret_detail["scenario_body"] = scenario_resp.text
            record("a_scenario_interpret", False, interpret_detail)

        # (b) Tier-2: analyze_data with code in trace
        t0 = time.perf_counter()
        tier2_resp = client.post("/api/agent/ask", json={
            "question": "What is the average updated LTV of stage 2 loans?",
        })
        tier2_elapsed = time.perf_counter() - t0
        tier2_json = tier2_resp.json() if tier2_resp.status_code == 200 else None
        trace = tier2_json.get("trace", []) if tier2_json else []
        has_code = any(
            "code" in ev
            or (isinstance(ev.get("args"), dict) and "code" in ev.get("args", {}))
            or (isinstance(ev.get("attempts"), list) and
                any("code" in a for a in ev["attempts"]))
            for ev in trace
        )
        record("b_tier2_analyze_data", tier2_resp.status_code == 200 and
               tier2_json.get("route") == "analyze_data" and has_code,
               {"status": tier2_resp.status_code,
                "elapsed_s": round(tier2_elapsed, 1),
                "route": tier2_json.get("route") if tier2_json else None,
                "answer": tier2_json.get("answer") if tier2_json else None,
                "trace": trace})

        # (c) Tier-3 citation question still works
        tier3_resp = client.post("/api/agent/ask", json={
            "question": "Explain the ECL movement waterfall.",
        })
        tier3_json = tier3_resp.json() if tier3_resp.status_code == 200 else None
        record("c_tier3_citation", tier3_resp.status_code == 200 and
               tier3_json.get("route") == "query_model_docs",
               {"status": tier3_resp.status_code,
                "route": tier3_json.get("route") if tier3_json else None,
                "answer": tier3_json.get("answer") if tier3_json else None})

        # (d) poem still refuses
        poem_resp = client.post("/api/agent/ask", json={
            "question": "Write me a poem about spring flowers.",
        })
        poem_json = poem_resp.json() if poem_resp.status_code == 200 else None
        record("d_poem_refusal", poem_resp.status_code == 200 and
               poem_json.get("route") == "REFUSE",
               {"status": poem_resp.status_code,
                "route": poem_json.get("route") if poem_json else None,
                "answer": poem_json.get("answer") if poem_json else None})

    out_dir = ROOT / "outputs" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "appv2_e2e.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {out_path}")
    print(f"\nOVERALL: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
