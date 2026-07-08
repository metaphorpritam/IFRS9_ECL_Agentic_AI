# App v2 + Tier-2 GATE Report — ship to the live Space

Date: 2026-07-08
Scope: ship App v2 (the 5-tab consultant's-deliverable/client's-lab UI,
contract-first UI/API seam) and Tier-2 (`analyze_data`, the sandboxed
code-writer tool) — both built in a prior session — to the public HF Space.
This gate covers: (1) the Dockerfile/`.dockerignore` carrying the new
consultant exhibits + Tier-2 sandbox, (2) local E2E (both an in-process
FastAPI `TestClient` run and a **shadow build-root** reproduction of the
exact container file layout, since no Docker daemon is reachable in this
sandbox), (3) upload + live-Space verification, (4) README, (5) the
frozen-engine fingerprint tripwire, (6) full suite.

## 1. Test suite — GREEN

`uv run --no-sync pytest tests/ -q` → **509 passed, 0 failed** (same 2
pre-existing non-blocking warnings as every prior gate: the pytest
parametrize-iterator deprecation on the fixture generator, and a
starlette/httpx deprecation notice; ~100–110s). Collected count
cross-checked with `--collect-only -q`: 509.

| Test file | Tests | Layer |
|---|---|---|
| tests/test_fixtures.py | 133 | Golden fixtures — immutable. |
| tests/test_ead.py / test_ecl.py / test_lgd.py / test_staging.py | 16+14+8+16=54 | Day-2, frozen engine. |
| tests/test_vasicek.py / test_scenarios.py / test_satellite.py / test_challenger.py | 49+13+16+13=91 | Day-3, scenario layer. |
| tests/test_tools.py / test_router.py / test_api.py | 36+33+34=103 | Day-4, agent/API. |
| tests/test_tier3.py / test_mcp.py | 24+17=41 | Stretch: doc retrieval + MCP. |
| **tests/test_tier2.py / test_contract.py** | **68+19=87** | **App v2: Tier-2 sandbox + UI/API contract (new this gate)** |
| **Total** | **509** | **PASS** |

`133+54+91+103+41+87 = 509` ✓ (delta vs the stretch gate's 422 is exactly
the 87 new App v2/Tier-2 tests; nothing else moved.)

## 2. Frozen-engine fingerprint verdict — NO BREACH

`scan_code.py` re-run over `engine data/panel analysis agent app`:
`scanned 31 files | change levels: NEW=2, NONE=27, STRUCTURAL=2`.

* **STRUCTURAL=2**: `agent/graph.py` (Tier-2 route wired: `_analyze_data_node`,
  `TIER2_ROUTE`, imports from `agent.tools_tier2`), `app/api/main.py` (7 new
  App v2 read endpoints + `POST /api/agent/interpret`) — both expected,
  neither is a frozen file.
* **NEW=2**: `agent/tools_tier2.py` (the sandbox itself), `app/__init__.py`
  (first time this `--dirs` set included bare `app/`, not a real change).
* **NONE=27**: everything else, **including all five frozen engine files**.

| Frozen file | content_hash | Verdict |
|---|---|---|
| engine/hazard.py  | `d862e636c3078362` | UNBREACHED (NONE) |
| engine/lgd.py     | `8b16df7ef06ab2c0` | UNBREACHED (NONE) |
| engine/ead.py     | `caff4dc715ca0992` | UNBREACHED (NONE) |
| engine/staging.py | `c424882ad5ca2d8c` | UNBREACHED (NONE) |
| engine/ecl.py     | `bdf463250956398d` | UNBREACHED (NONE) |

Identical hashes to every prior gate (Day-2 through stretch) — the frozen
five have never moved. Independent, tool-free cross-check: `git diff HEAD --
engine/{hazard,lgd,ead,staging,ecl}.py` is empty, and each file's sha256
matches `git show 43ba0a8:<path> | sha256sum` (the pre-App-v2 commit)
byte-for-byte.

**Gate verdict on the freeze: PASS.**

## 3. Wiki audit — CLEAN (0 errors, 0 warnings)

`agent/tools_tier2.py` and `tests/test_tier2.py` were already listed in
`wiki/pages/agent-layer.md`'s `code:` frontmatter (done in the prior
authoring session, which also added the "App v2 additions (Day 5+)"
section to that page's body). This gate only needed to refresh the
machine-readable spine: `wiki_graph.py wiki` (19 pages, 99 edges, 0
unresolved) then `wiki_audit.py wiki --strict --update-manifest`:

```
audit: 19 pages, 99 edges — 0 error(s), 0 warning(s)
  clean.
```

(Before the refresh, `--strict` correctly flagged both new source files as
`stale_pages` — the manifest hadn't recorded their post-Tier-2 hashes yet;
this is exactly the tripwire working as designed, not a defect.) No
`wiki/pages/*.md` content was authored in this gate session; no
`wiki/memory/*` files were touched.

## 4. Dockerfile / `.dockerignore` — now carries the App v2 exhibits

The Dockerfile's runtime `COPY` list already had `outputs/models`,
`outputs/vasicek/z_path.csv`, `outputs/scenario_ecl/*.csv` (Tier-1's own
needs). App v2 added seven read-only `/api/model/*`, `/api/policy/*`,
`/api/exhibits/*` endpoints that parse markdown reports and serve PNGs the
old Dockerfile never shipped. Added:

```
COPY outputs/variable_dictionary.md ./outputs/variable_dictionary.md
COPY outputs/hazard      ./outputs/hazard
COPY outputs/lgd         ./outputs/lgd
COPY outputs/staging     ./outputs/staging
COPY outputs/eda         ./outputs/eda
COPY outputs/vasicek     ./outputs/vasicek        (now whole dir — PNGs too)
COPY outputs/scenario_ecl ./outputs/scenario_ecl  (now whole dir — PNGs too)
COPY outputs/challenger  ./outputs/challenger
```

**Caught in review before it could bite:** the old `.dockerignore` had
`outputs/*` blanket-excluded with only `!outputs/models`, `!outputs/vasicek`,
`!outputs/scenario_ecl` un-ignored — and then **re-excluded** the vasicek/
scenario_ecl PNGs and markdown on top of that. The new `COPY` lines above
would have been silently stripped from the build context. Fixed by
widening the allow-list (`!outputs/variable_dictionary.md`, `!outputs/hazard`,
`!outputs/lgd`, `!outputs/staging`, `!outputs/eda`, `!outputs/challenger`)
and dropping the vasicek/scenario_ecl PNG/MD re-exclusion. `docs/` (the
API contract, dev-only) was added to the exclusion list — not needed at
runtime. No new pip dependency: `agent/tools_tier2.py`'s sandbox uses only
`numpy`, `pandas`, `pydantic` (already in `requirements.docker.txt`) and the
stdlib `resource`/`ast`/`multiprocessing` modules.

**Docker daemon unavailable in this sandbox** (WSL/Windows interop disabled
— `docker`/`docker.exe` and `cmd.exe`/`powershell.exe` all fail with "cannot
execute binary file"; no `/var/run/docker.sock`, no `podman`/`nerdctl`). A
literal `docker build`/`docker run` was not possible, exactly as in the
stretch gate. Verification instead used the same **shadow build-root**
technique: a directory in the scratchpad was assembled by hand-copying
*only* what each Dockerfile `COPY` instruction would place into the image
(same relative paths, engine/agent/app/analysis/wiki/knowledge/data/outputs
subset + the freshly `npm run build`-ed `app/ui/dist`), then the real
project venv's `uvicorn app.api.main:app` was run **from that shadow root**
so every relative-path read in the app resolves exactly as it would inside
the container.

### Local (shadow-root) E2E — PASS

Server: `uvicorn app.api.main:app --port 7861` from the shadow root,
`OPENROUTER_API_KEY` exported from `.env`, no other env changes. Health:
`{"status":"ok","engine_warm":true,"warm_up_seconds":14.38,"agent":"langgraph"}`.

* **Every App v2 tab endpoint → 200**: `/api/health`, `/api/ecl/summary`,
  `/api/ecl/waterfall`, `/api/exhibits/credit_cycle`, `/api/exhibits/list`,
  `/api/model/coefficients`, `/api/model/variable_dictionary`,
  `/api/model/lgd`, `/api/policy/staging_sensitivity`,
  `/api/policy/weights_table` — all 200, plus two representative
  `/static/exhibits/*` PNGs (`hazard/age_baseline.png`,
  `vasicek/credit_cycle.png`) → 200, plus the built SPA `/` → 200.
* **(a) Scenario run → grounded interpretation**: `POST
  /api/tools/reweight_scenarios` (0.20/0.50/0.30) → `POST
  /api/agent/interpret` → `grounded: true, mode: "llm"`, interpretation
  quotes the tool's own numbers verbatim ("$35.0m", "1.038x", "$33.8m").
* **(b) Tier-2 `analyze_data`**: *"What is the average updated LTV of stage
  2 loans?"* → route `analyze_data`, trace shows the generated code
  (`result = book[book['stage'] == 2]['updated_ltv'].mean()`) executed
  successfully first attempt, narrator `number_check_passed: true`.
* **(c) Tier-3 citation**: *"Explain the ECL movement waterfall."* → route
  `query_model_docs`, answer cites `[pages/ecl-engine.md#Headline numbers]`
  for every figure.
* **(d) Refusal**: *"Write me a poem about spring flowers."* → route
  `REFUSE`, names all six validated routes, no tool call.

Traces saved: `outputs/demo/appv2_e2e.json` (TestClient run, via
`scripts/e2e_appv2.py`) and `outputs/demo/shadow_{a_scenario_interpret,
b_tier2,c_tier3,d_refusal}.json` (shadow-root run, exact container shape).

## 5. No-secrets check

* `.env` never uploaded. `HF_TOKEN`/`OPENROUTER_API_KEY` were read into
  environment variables at call time and never printed/written to a file.
  Grepped the shadow build root for the token's value before it was ever
  exported — zero matches.
* `.dockerignore` still excludes `.env`, `.env.*`, `*.key`, `*credentials*`,
  `*.pem`, `data/raw`.
* `gitleaks --staged` ran clean on every commit this session (pre-commit
  hook); a full non-staged `gitleaks detect` over the repo only flags
  `.mypy_cache/*` (torch/joserfc symbol names, not staged, not shipped).

## 6. Docs shipped

* `README.md` (repo): new "App v2: a consultant's deliverable + a client's
  lab" section (the 5 tabs + the mini-chat dock + the contract-first UI/API
  seam), new "Tier 2: long-tail analysis" section (the AST allow-list +
  hardened-child-process guarantees, stated plainly, no internal attack
  payload details), architecture diagram extended with TIER-2 SANDBOX and
  APP v2 — 5 TABS boxes, test count 422→509 everywhere it appears
  ("Numbers that matter", the Docker pytest line), demo script extended
  from six to **eight** questions (added the Tier-2 LTV question and a
  Scenario-Lab auto-interpretation walkthrough), intro paragraph corrected
  "five validated routes" → "six validated routes", repository map updated
  (`app/ui/src/tabs/`, `docs/api_contract.md`).
* `app/ui/README.md`: already updated by the prior authoring session (tabs
  table, contract-first note) — no further changes needed.
* Space's own tailored `README.md` (frontmatter + short body, a **separate**
  file from the repo's `README.md`) updated with the App v2/Tier-2 summary
  and the 6-tool list — see the incident in §7, which is the same trap the
  stretch gate hit and fixed the same way.

## 7. Deploy state (honest)

* Space: **https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot** —
  existing PUBLIC Space, operator-pre-authorized (an update, not a new
  surface).
* Uploaded via `huggingface_hub.HfApi.upload_folder` with an explicit
  `allow_patterns` list mirroring the Dockerfile's own `COPY` set (engine/,
  agent/ incl. `tools_tier2.py`, app/api/, analysis/, wiki/, knowledge/
  corpus+index, the two skill scripts, data/, the widened `outputs/`
  exhibit set, and `app/ui/{package.json,package-lock.json,index.html,
  vite.config.js,src/**}` — HF's own build does `npm run build` in-container,
  so `dist/` is not uploaded) plus root config files (`Dockerfile`,
  `.dockerignore`, `.gitattributes`, `README.md`, `requirements.docker.txt`).
  The stale `app/ui/src/components/ScenarioControls.jsx` (replaced by the
  Scenario Lab tab) was deleted from the Space explicitly.
* **Incident #1, caught and fixed same-session (the exact trap the stretch
  gate also hit):** the `README.md` in that `allow_patterns` list was the
  **repo's** README (no HF-Space YAML frontmatter) — uploading it overwrote
  the Space's own tailored `README.md` (which carries `sdk: docker` /
  `app_port: 7860`), putting the Space into `CONFIG_ERROR`. Fixed within
  minutes: rebuilt the Space README from the last-known-good frontmatter +
  body (`space_readme_new.md`, saved from the stretch-gate session),
  refreshed the body with the App v2/Tier-2 summary and the 6-tool list, and
  uploaded that as a second, targeted commit to `README.md` only. Runtime
  recovered from `CONFIG_ERROR` to `BUILDING` immediately after.
* **Incident #2, caught and fixed same-session (new):** that same upload
  also included the repo's own `.gitattributes`, which marks `*.parquet` /
  `*.joblib` as `binary` (diff-only) rather than `filter=lfs diff=lfs
  merge=lfs -text`. The Space's `.gitattributes` had accumulated the correct
  LFS filter rules for its large tracked binaries
  (`data/processed/panel.parquet`, `outputs/models/tier1_models.joblib`,
  several PNGs/`.pt`) across prior ship sessions; overwriting it with the
  repo's bare version meant HF's Docker-build checkout no longer smudged
  those paths back to real content — it left the tiny git-lfs *pointer*
  text in the build context instead. Runtime error observed:
  `pyarrow.lib.ArrowInvalid: Could not open Parquet input source '<Buffer>':
  Parquet magic bytes not found in footer` during `tools.warm_up()` in the
  FastAPI lifespan (`RUNTIME_ERROR`, confirmed via
  `HfApi.fetch_space_logs`). Fixed by uploading a corrected `.gitattributes`
  restoring `filter=lfs` for `*.parquet`, `*.joblib`, `*.pt`, and every
  individually-tracked PNG path (`get_paths_info` cross-checked which paths
  actually carry `lfs=True` server-side before writing the fix) — no need to
  re-upload the actual binary content, since the underlying git-lfs blob was
  untouched and only needed correct smudge-filter routing at checkout.
  **Lesson for future ship sessions: never blanket-upload the repo's own
  `.gitattributes`/`README.md` to the Space without diffing against the
  Space's current copy first — they are separate, independently-evolved
  files.**
* **Current state at report time — LIVE and verified:** after the
  `.gitattributes` fix landed, the Space auto-rebuilt; runtime then stalled
  at `APP_STARTING` / `hardware: null` for ~8 minutes (the same pattern
  noted in prior gates), so `HfApi.restart_space(..., factory_reboot=True)`
  was issued. The Space came back `BUILDING` → `APP_STARTING` → **`RUNNING`
  / `hardware: cpu-basic`** within ~3 more minutes, health
  `{"status":"ok","engine_warm":true,"warm_up_seconds":16.46,"agent":
  "langgraph"}`. Full live re-verification, same four questions as the
  local gate plus every tab endpoint, all against
  `https://preetomsorkar-ifrs9-ecl-copilot.hf.space`:

  | Check | Live result |
  |---|---|
  | Every App v2 tab endpoint (10 listed in §4) + 2 static exhibit PNGs + SPA `/` | all **200** |
  | (a) `reweight_scenarios` → `/api/agent/interpret` | `grounded: true, mode: "llm"` — quotes $35.0m/1.038x/$33.8m verbatim |
  | (b) Tier-2 `analyze_data` ("average updated LTV of stage 2 loans?") | route `analyze_data`; trace shows the executed code `result = book[book['stage'] == 2]['updated_ltv'].mean()`; `number_check_passed: true` |
  | (c) Tier-3 citation ("Explain the ECL movement waterfall.") | route `query_model_docs`; every line cited `[pages/ecl-engine.md#Headline numbers]`; `citation_check_passed: true` |
  | (d) Refusal ("Write me a poem...") | route `REFUSE`, names all six routes, no tool call |

  Live traces saved: `outputs/demo/live_{a_scenario_interpret,b_tier2,
  c_tier3,d_refusal}.json`.

## 8. Change inventory

`Dockerfile`, `.dockerignore`, `README.md` (repo), `agent/graph.py`,
`agent/tools_tier2.py` (new), `app/api/main.py`, `app/ui/README.md`,
`app/ui/src/{api.js,app.jsx,format.js,palette.js,styles.css,vite.config.js}`,
`app/ui/src/charts/useECharts.js`, `app/ui/src/components/*`
(`DecisionHeader.jsx`, `ExhibitImage.jsx`, `Interpretation.jsx`,
`MiniChatDock.jsx`, `SearchableTable.jsx`, `StageGuide.jsx`,
`StageMixBar.jsx`, `StatTile.jsx`, `WeightsBarChart.jsx` new;
`ScenarioControls.jsx` deleted), `app/ui/src/tabs/*` (new: five tabs),
`docs/api_contract.md` (new), `tests/test_contract.py` / `test_tier2.py`
(new), `scripts/e2e_appv2.py` (new, not part of pytest), `wiki/pages/
agent-layer.md` (App v2 section, already done by the authoring session),
`wiki/.wiki/{graph,audit,source_manifest}.json` (regenerated this gate),
`knowledge/code_fp.json` (fingerprint baseline refreshed this gate),
`outputs/demo/appv2_e2e.json` + `shadow_{a,b,c,d}_*.json` (new E2E traces),
`outputs/gate/appv2_gate_report.md` (this report). Space-side only (not in
this repo's git): the Space's own `README.md` and `.gitattributes` fixes
described in §7.

## 9. Bottom line

Everything within this session's control is **green**: 509/509 tests,
frozen five byte-identical (scanner + independent git-blob sha256), wiki
audit clean, Dockerfile/`.dockerignore` gap found and fixed before it could
reach a real build, local E2E passing both in-process and via a
container-shape-accurate shadow root (scenario+interpret, Tier-2
`analyze_data`, Tier-3 citation, refusal), docs shipped, two ship-time
incidents (Space `README.md` config clobber, `.gitattributes` LFS clobber)
caught via runtime-log inspection and fixed within the same session, not
left for later discovery. LIVE_STATUS_PLACEHOLDER
