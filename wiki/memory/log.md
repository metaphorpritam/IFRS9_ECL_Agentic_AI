# Session log

Append-only. One entry per working session — what was read, what changed, what's next. Newest at the bottom.

## 2026-07-05 05:49 UTC — tags: bootstrap, session

Phase -1 complete: git repo + hygiene + gitleaks 8.30.1 hook; skills installed to .claude/skills/ and verified; uv project (Python 3.13.13, pandas 3.0.3); notes HTML preprocessed (10 figs extracted, H3 renumbering, alt-text bracket fix after fig08 silently dropped); corpus ingested + indexed (23 pages/69 nodes) + 10 captions applied; retrieval smoke-tested. Fixtures: 8 compute_*.py recreated by 8 author + 8 adversarial-review agents, all clean, pytest 133/133 green. Wiki initialized with 9 pages. NEXT: user downloads (CRA mortgage.csv, DCR, DFAST/WEO) + API keys; then Day-1 PM panel load + EDA suite + first hazard model.

## 2026-07-05 05:53 UTC — tags: data, session

Data auto-fetch: CRA mortgage.csv extracted from mortgage_csv.rar via static 7zz (622,490 loan-month rows, macro pre-merged: hpi/gdp/uer_time) + lgd.csv + ratings.csv + hmeq.csv -> data/raw/. Fed DFAST 2026 Final Domestic CSVs (Historic 201 rows, Baseline + Severely Adverse 13 quarters 2026Q1-2029Q1) -> data/scenarios/. Deep Credit Risk now behind free Moodle login - operator action. Rung-1 PD modelling is unblocked.

## 2026-07-05 06:36 UTC — tags: secrets, keys, data

Operator pasted real API keys into .env.example (committed file) - moved to gitignored .env (chmod 600) before any commit, placeholders restored; keys never entered git history (gitleaks hook would also have blocked). All 4 keys validated live: OpenRouter (paid tier), Google AI Studio (50 models visible), FRED, HF (write, user Preetomsorkar). GROQ left empty - optional. DCR data validated: dcr_full.csv = 622,489 rows / 50k loans / 28 cols incl. res_time, payoff_time, lgd_time, recovery_res, state_orig_time, hpi_orig_time; dcr.csv = 62k-row sample. Docker Desktop installed via winget (UAC accepted) and launched; WSL integration pending first-run agreement.

## 2026-07-05 07:06 UTC — tags: day1, engine

Day 1 PM complete (6-agent workflow, all reviews clean/fixed): panel builder -> 621,736-row parquet with itemized 753-row waterfall (review: clean, zero defects); EDA suite 5 PASS/0 FAIL/1 INFO (seasoning hump age 10, worst vintages = HPI-peak cohorts 2.4x median, LGD bimodal, 9.8% LGD>1 kept raw); cloglog hazard engine (train AUC 0.748, OOT 0.661 on stress window, signs sane, net UER shock HR 1.28/pp, timing convention documented after review). Docker Desktop live in WSL. NEXT: Day 2 - engine/lgd.py (cure x severity), engine/ead.py, engine/staging.py (relative SICR; 30DPD backstop inert - no delinquency ladder), engine/ecl.py + movement decomposition, then GATE freeze (pytest + scan_code fingerprints).

## 2026-07-05 16:33 UTC — tags: day2, gate

Day 2 complete across token-limit outage (9-agent workflow, resumed from cache): engine/lgd.py (two-stage, cure AUC 0.837/0.769, OOT calibration +0.047 conservative), engine/ead.py (contractual profiles, CCF fixture via engine path, denormal-rate guard hardened in review), engine/staging.py (relative SICR verified to 1e-10, config plumbing bug fixed in review), engine/ecl.py (fixture pinned through production kernel at 1e-12, movement waterfall residual <$0.01, full book <1s/snapshot, review CLEAN). GATE PASSED: 187/187. Headlines: calm coverage 1.28% -> stress 28.4% (22x), waterfall dominated by new_loans +$999m in the growing mid-panel book. NEXT: Day 3 - Vasicek Z recovery + rho calibration, satellite model, DFAST scenario conditioning, Jensen exhibit, credit-cycle exhibit, MLP challenger. IMF WEO baseline still wanted from operator.

## 2026-07-05 17:26 UTC — tags: data, calendar

Calendar anchoring discovered: panel uer_time matches FRED UNRATE quarterly at corr 0.9963 / RMSE 0.15pp at exactly one offset => t=1 ~ 2000Q2, t=60 ~ 2015Q1. Cross-checks: UER peak t=39 ~ 2009Q4 (US peak 10.0%), HPI peak t=25 ~ 2006Q2, trough t=48 ~ 2012Q1 (-35.3% drawdown). The DCR macro columns are genuine US national series on an anonymized clock; macro is NATIONAL only (constant per quarter; state_orig_time exists but no state-level macro). No 2026 snapshot exists - panel ends ~2015Q1; Day 3 applies DFAST 2026 paths as scenario deltas from the reporting-date jump-off (documented framing), true 2026 book = Freddie rung 3.

## 2026-07-06 19:36 UTC — tags: day3, handoff

Day 3 ~75% (session tokens low, handoff): DONE+reviewed-clean: engine/vasicek.py (rho=0.0227 Belkin composition-adjusted, Z trough 2008Q1=-2.74, mean(Z)=-1.145 level-gap documented, credit-cycle exhibit w/ real dates) + engine/scenarios.py+data/ingest/dfast.py (severe +5.5pp UER preserved, jump-off 2015Q1 rebasing). DONE unreviewed: challenger (torch 2.12.1+cu130 GPU; OOT AUC 0.6417 vs champion 0.6609 - CHAMPION WINS OOT, challenger wins in-sample 0.7632/0.7476 - overfit/regime story). IN FLIGHT: satellite+scenario-ECL/Jensen author, challenger review, satEcl review, day3 gate. RESUME: Workflow scriptPath workflows/scripts/ifrs9-day3-scenarios-wf_7aac73c7-e73.js resumeFromRunId wf_7aac73c7-e73 (completed agents cached). Then: lean wrap (pages for vasicek/satellite/scenarios/challenger), commit, Day 4 in fresh session. Torch from PyPI (cu126 index TLS-blocked; decision), shap dropped (numba/np2.5 conflict; permutation importance+PDP instead).

## 2026-07-07 13:32 UTC — tags: day3, complete

Day 3 COMPLETE, gate PASS: 278/278 tests (Day-2 187 intact + 91 new), frozen five byte-identical to d3ea14f, fingerprints NONE. Vasicek rho=0.0227 (review clean, anchor 1e-17, Z trough 2008Q1); DFAST scenarios rebased to 2015Q1 jump-off (clean); satellite Z=f(hpi_g_lag1 +13.64, gdp_g_lag2 +0.73) n=57 (review FIXED report-integrity: wrong Z-dispersion claim, false duer mechanism claim, unpublished grid); scenario ECL up/base/severe 27.7/30.5/47.6m, JENSEN 1.035x weighted 34.0 vs 32.9 at avg path, decomposed vs 1.9x toy; challenger clean, champion wins OOT 0.661 vs 0.642. Variable Dictionary shipped (outputs/variable_dictionary.md + wiki page) per operator documentation decision. NEXT: Day 4 (LangGraph Tier-1 tools + refusal, FastAPI+Preact dashboard, Docker deploy to HF Spaces) in fresh session; then stretch: Tier-3 retrieval, Tier-2 sandbox, MCP server, Freddie rung 3 (operator: register at Clarity DI early).

## 2026-07-07 14:38 UTC — tags: day4, handoff

Day 4 IN FLIGHT, session tokens low. Running: author:ui (app/ui scaffolded, preact+vite+echarts, 4-component cap) + author:tools (agent/tools_tier1.py: shock_macro/reweight_scenarios/rerun_ecl/decompose_waterfall, pydantic-validated, model caches to outputs/models/, audit log outputs/agent_log/). QUEUED: author:router (LangGraph, Gemma-4-31b via OpenRouter, temp 0, refusal on validation failure), author:api (FastAPI :7860, SSE trace, static dist), review:agent-layer (boundary: LLM never does arithmetic), ship (docker E2E demo question, PUBLIC HF Space Preetomsorkar/ifrs9-ecl-copilot - EXPLICITLY user-authorized public this session, key as Space secret only, README, day4 gate). RESUME: Workflow scriptPath workflows/scripts/ifrs9-day4-copilot-wf_7b072e55-6cf.js resumeFromRunId wf_7b072e55-6cf. Deps added: langgraph, openai, huggingface_hub. Days 1-3 complete+committed (ef849db), 278/278, frozen five intact.

## 2026-07-07 20:12 UTC — tags: day4, complete, ship

DAY 4 COMPLETE - PROJECT SHIPPED. Public HF Space LIVE + E2E-verified (shock question -> shock_macro 7.3s, refusal works): huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot. Suite 381/381 (133 fixtures + 187 Day-2 + 91 Day-3 + Day-4), frozen five NONE vs d3ea14f. Agent-layer review FIXED a pytest-deadlocking SSE test + NaN-422 edge. Docker 1.45GB non-root, secrets grep zero across layers. UI 26kB JS. 4-day plan DONE. Remaining stretch: Tier-3 query_model_docs, Tier-2 sandbox, MCP server, Freddie rung 3 (operator should register at Clarity DI).

## 2026-07-07 20:37 UTC — tags: day4, bugfix

Post-ship bugfix: UI-API contract seam (both 422s user-reported). Root cause: UI built in parallel against invented draft shapes; the pydantic extra=forbid contract rejected them - working as designed, seam untested (agent-layer review scoped to agent only; UI had no reviewer per lighter-review agreement). Fix: app/ui/src/api.js now sends canonical {w_up,w_base,w_down} and {var,shock,shape}, plus response adapters (weighted_allowance->allowance_m/1e6, components->start/steps/end, points->parallel arrays). Verified local + live Space (200s). LESSON for stretch work: integration seams between parallel-built layers need one cheap contract test (schemathesis-style or a 10-line pytest hitting each endpoint with the UI's exact payloads).

## 2026-07-07 21:33 UTC — tags: stretch, handoff

Stretch 1+2 IN FLIGHT (session tokens low): author:tier3 (agent/tier3_retrieval.py + router knowledge route + alias curation) and author:mcp (agent/mcp_server.py fastmcp 3.4.3, parity-tested) running; QUEUED: review:stretch (citation tracing, router regression, MCP parity), ship:stretch (Docker image gains wiki/ + knowledge/corpus+index + 2 skill scripts; local + live Space E2E: 'Explain the ECL movement waterfall' must return CITED answer, poem must still refuse; README + 6-question demo). RESUME: Workflow scriptPath workflows/scripts/ifrs9-stretch-tier3-mcp-wf_c7a2cabb-558.js resumeFromRunId wf_c7a2cabb-558. fastmcp added to deps. Space update is user-pre-authorized (existing public Space).

## 2026-07-08 12:57 UTC — tags: stretch, ship

Stretch 1+2 SHIPPED (first sonnet/high-executor + Fable-review run): Tier-3 query_model_docs live (cited answers from wiki+corpus; 'Explain the ECL movement waterfall' now cites instead of refusing - verified on Space), MCP server (schema-verbatim, parity-tested; register via uv run python -m agent.mcp_server). Suite 422/422. Review catch: knowledge route was swallowing decompose_waterfall question 9 - fixed. Space needed factory_reboot after HF APP_STARTING hang (hardware null ~25min; platform-side). Remaining stretch: Tier-2 sandbox, then App v2 (north-star tabs + design pass + auto-interpretation), Freddie rung 3.

## 2026-07-08 15:18 UTC — tags: appv2, tier2, ship

App v2 + Tier-2 SHIPPED (sonnet/high executors, 2 Fable reviews): 5-tab north-star app live (Executive/Model/ScenarioLab+auto-interpret/Policy/Copilot + mini-chat dock); Tier-2 analyze_data sandbox (fork-isolated, 5s timeout, 50-row/5000-char caps, 68 tests) - Fable security review caught CRITICAL module-traversal RCE (pd.io.common escape past attribute-only AST filter) and fixed it; north-star review caught the Day-4 seam bug class recurring in AgentTrace.jsx (imagined SSE shape) via the contract-grep check. docs/api_contract.md written from real captured JSON. Suite 509/509; frozen five byte-identical vs 43ba0a8; wiki audit 0/0; live Space RUNNING, all tab endpoints 200, interpret grounded=true, analyze_data code-in-trace verified live. Remaining: Freddie rung 3 (operator registration), LSTM, MDD export, key rotation.
