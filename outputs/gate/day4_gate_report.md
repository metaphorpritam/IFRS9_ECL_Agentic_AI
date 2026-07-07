# Day-4 GATE Report — Ship: Docker, E2E, HF Spaces, README

Date: 2026-07-07
Scope: final ship gate. Verifies (1) the full test suite, (2) the frozen-engine
fingerprint tripwire vs the Day-2/Day-3 baselines, (3) the containerised E2E demo
(local Docker + live HF Space), (4) the no-secrets-in-image check, and (5) the
change inventory for the Day-4 ship layer.

## 1. Test suite — GREEN

`uv run --no-sync pytest tests/ -q` → **381 passed, 0 failed** (2 warnings:
the known pytest parametrize-iterator deprecation on the fixture generator +
one capture warning; non-blocking; 93.0s). Collected count cross-checked with
`--collect-only -q`: 381.

| Test file | Tests | Status | Layer |
|---|---|---|---|
| tests/test_fixtures.py | 133 | PASS | Golden fixtures — immutable. |
| tests/test_ead.py | 16 | PASS | Day-2, frozen engine. |
| tests/test_ecl.py | 14 | PASS | Day-2, frozen engine. |
| tests/test_lgd.py | 8 | PASS | Day-2, frozen engine. |
| tests/test_staging.py | 16 | PASS | Day-2, frozen engine. |
| **Day-2 subtotal** | **187** | **PASS** | Matches Day-2/Day-3 gate counts exactly. |
| tests/test_vasicek.py | 49 | PASS | Day-3. |
| tests/test_scenarios.py | 13 | PASS | Day-3. |
| tests/test_satellite.py | 16 | PASS | Day-3. |
| tests/test_challenger.py | 13 | PASS | Day-3. |
| **Day-3 subtotal** | **91** | **PASS** | Matches Day-3 gate count exactly (278 cumulative). |
| tests/test_tools.py | 36 | PASS | Day-4: Tier-1 tools. |
| tests/test_router.py | 33 | PASS | Day-4: LangGraph router (mocked LLM, offline). |
| tests/test_api.py | 34 | PASS | Day-4: FastAPI service. |
| **Day-4 subtotal** | **103** | **PASS** | |
| **Total** | **381** | **PASS** | |

## 2. Frozen-engine fingerprint verdict — NO BREACH

Re-ran the tripwire (Day-3 command + the Day-4 dirs `agent` and `app/api` added
to the store):

```
uv run --no-sync python .claude/skills/pageindex-plus/scripts/scan_code.py \
  --root /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI \
  --dirs engine data/panel analysis agent app/api \
  --out knowledge/code_map.md --fingerprints knowledge/code_fp.json
```

Result: `scanned 27 files | change levels: NEW=5, NONE=22`. Frozen five vs the
Day-3 baseline store (backed up to the session scratchpad before the scan) —
**both** `struct_hash` **and** `content_hash` identical:

| Frozen file | Classification | struct_hash | content_hash | Verdict |
|---|---|---|---|---|
| engine/hazard.py | **NONE** | `1786dacea90bf08e` | `d862e636c3078362` | UNBREACHED |
| engine/lgd.py | **NONE** | `d5a98c1dc6fc76d0` | `8b16df7ef06ab2c0` | UNBREACHED |
| engine/ead.py | **NONE** | `b120dc99602dd3f7` | `caff4dc715ca0992` | UNBREACHED |
| engine/staging.py | **NONE** | `9354043a443a12d0` | `c424882ad5ca2d8c` | UNBREACHED |
| engine/ecl.py | **NONE** | `7c7feef9c97494fe` | `bdf463250956398d` | UNBREACHED |

All 22 pre-existing files classify NONE (zero content-hash changes among files
present in the Day-3 store). The 5 NEW entries are exactly the Day-4 layer:
`agent/__init__.py`, `agent/graph.py`, `agent/tools_tier1.py`,
`app/api/__init__.py`, `app/api/main.py`. Day-3 modules
`engine/{vasicek,scenarios,satellite}.py`: NONE — not extended on Day 4.

Belt-and-braces: `git diff d3ea14f..HEAD -- engine/{hazard,lgd,ead,staging,ecl}.py`
and the working-tree diff on the same paths are both **empty** — the frozen five
are byte-identical to the Day-2 gate commit.

**Gate verdict on the freeze: PASS.**

## 3. Container E2E — PASS (local Docker AND live HF Space)

Image: `ifrs9-ecl-copilot:day4` (multi-stage: node:22-alpine builds the SPA →
python:3.13-slim runtime from `requirements.docker.txt`, exported from uv.lock
with `--prune torch`; 73 locked packages; image 1.45 GB; runs as uid 1000).

* **Health:** container ready in ~10s; `/api/health` →
  `{"status":"ok","engine_warm":true,"warm_up_seconds":12.81,"agent":"langgraph"}`
  (joblib warm start; the OPENROUTER key injected at run time only).
* **Demo E2E** (`outputs/demo/e2e_trace.json`): POST `/api/agent/ask`
  *"What happens to Stage 2 ECL if unemployment rises 2%?"* → route
  `shock_macro`, trace `router → shock_macro → narrator`, 12.2s; answer quotes
  the engine's numbers: base allowance $30.5m → $31.7m (+1.2m, +4.1%).
* **Refusal E2E** (`outputs/demo/e2e_refusal.json`): *"Should I buy Tesla stock
  this quarter?"* → route `REFUSE`, trace `router → refusal`, 3.2s, fixed
  refusal text naming the four validated tool families. No tool ran.
* **SPA + SSE:** `GET /` serves the built UI (200); `GET /api/agent/stream`
  replays the latest trace as SSE `data:` lines.
* **Live Space re-run:** the same shock question against
  `https://preetomsorkar-ifrs9-ecl-copilot.hf.space/api/agent/ask` → 200,
  route `shock_macro`, 7.3s.

## 4. No-secrets-in-image check — PASS

* `docker save ifrs9-ecl-copilot:day4 | grep -a -c "sk-or-"` → **0 matches**
  across every layer.
* `/app/.env` does not exist in the image; `.dockerignore` excludes `.env*`,
  keys, credentials, `data/raw`.
* The image runs as non-root `appuser` (uid 1000, HF Spaces convention); only
  `outputs/` is writable by it (audit trail + cache refresh).
* On HF, the key lives as a **Space secret** (`OPENROUTER_API_KEY`), injected
  as an env var at runtime; the frontend never sees it and no endpoint echoes
  environment state.

## 5. Deploy state (honest)

* Space: **https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot** —
  PUBLIC (operator-authorized this session), Docker SDK, `app_port: 7860`,
  hardware `cpu-basic`.
* Build reached **RUNNING**; live `/api/health` 200 with
  `engine_warm: true, warm_up_seconds: 24.87, agent: langgraph`, and a live
  agent round trip succeeded (§3). A final README-count fix triggered one more
  rebuild after these checks; layer-cached, re-verified RUNNING at gate close.

## 6. Change inventory (Day-4 ship layer)

New/changed since `b750a2b` (Day-4 WIP): `Dockerfile`, `.dockerignore`,
`requirements.docker.txt` (uv-lock export, torch pruned — used only by the
non-shipped challenger study), `agent/graph.py`, `app/__init__.py`, `app/api/`,
`tests/test_router.py`, `tests/test_api.py`, `scripts/demo_agent.py`,
`outputs/demo/`, `README.md`, this report, and the knowledge-store refresh
(`knowledge/code_fp.json`, `code_map.md`) performed by this gate's own scan.
None touch a frozen file (§2).

## 7. Gate verdict

**PASS.**

* Suite green: 381/381 (133 golden fixtures; Day-2 187 and Day-3 91 subtotals
  unchanged; +103 Day-4).
* Frozen five all NONE and byte-identical to the Day-2 gate commit.
* Local container answers the demo E2E and the refusal E2E; image contains no
  secrets; live HF Space serves the same answers publicly.
