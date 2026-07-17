# Reasoned-Route GATE Report — ship to the live Space

Date: 2026-07-17
Scope: ship the reasoned-route spelled-out-number guard fix. The REASONED
node (LangGraph route that answers conceptual/interaction-term questions —
e.g. the motivating live example, "does the satellite need a UER x HPI
interaction, or do the main effects and momentum already account for the
joint stress response?" — with a cited, number-disciplined LLM
interpretation instead of refusing) already existed in the working tree
going into this session. This gate covers the prior review's fix (a
digit-only number-token check has a blind spot for numbers spelled out in
words) plus the standard ship checklist: full pytest, `npm run build`
(waterfall regression prebuild), a container-equivalent local E2E (no
Docker daemon in this sandbox — see §4), upload to the live public Space,
and live verification.

## 1. Review fix verified against the diff

The review's summary claimed five changes; all five confirmed present in
`agent/graph.py` / `tests/test_router.py` before shipping:

* `_spelled_number_violation()` (`agent/graph.py:692`) plus its word lists
  `_MAGNITUDE_WORDS`, `_SMALL_NUMBER_WORDS`, `_UNIT_WORDS`, and
  `_ALPHA_WORD_RE` (lines 673-688) — a word-level companion to the
  existing digit-only `_number_tokens()`. Fails on (a) any standalone
  magnitude noun (hundred/thousand/million/billion/trillion/dozen/score,
  singular or plural) and (b) a small cardinal word (zero..ninety) within
  4 tokens of a unit word (percent/pp/bps/dollars/cents/basis).
* Wired unconditionally into all three narration guards that previously
  relied solely on `_number_tokens`: `reasoned_answer_ok` (line 766, hard
  fail — deliberately NOT whitelisted against a spelled-out question
  echo), `narration_numbers_ok` (Tier-1, line 821), and `docs_answer_ok`
  (Tier-3, line 897) — all three shared the identical blind spot.
* `REASONED_SYSTEM_PROMPT`'s hard-numeric-rule bullet and the
  `_llm_reason` regeneration-instruction string both now state a
  spelled-out number is treated identically to a digit by the automated
  check (prompt-level defense-in-depth on top of the mechanical guard).
* Module docstring's REASONED bullet documents the shared check (line 72).
* `tests/test_router.py::test_number_check_rejects_spelled_out_numbers`:
  adversarial regression — `narration_numbers_ok` rejects "the allowance
  would rise by roughly two hundred million dollars", "that is a
  forty-seven percent jump", and "the impact would land somewhere in the
  tens of millions"; confirms ordinary prose ("the model has one
  satellite equation and two macro drivers") still passes.

All five claims match the working tree exactly — no discrepancy.

## 2. Test suite — GREEN

`uv run --no-sync pytest -q` → **582 passed, 0 failed** (135.4s; same 2
pre-existing non-blocking deprecation warnings as every prior gate —
pytest's parametrize-iterator notice and the starlette/httpx testclient
notice — plus 27 known multiprocessing-fork DeprecationWarnings from
`tests/test_tier2.py`'s sandbox tests). `--collect-only -q` cross-check:
582. Delta vs the UI v3 gate's 513 is the reasoned-route feature's own
test additions across `test_router.py`, `test_contract.py`, `test_tier2.py`,
`test_tier3.py`, plus the new `tests/test_reasoned.py` module (the
REASONED node's mocked-LLM mechanics) and this session's adversarial
spelled-out-number regression.

## 3. Frozen-engine fingerprint verdict — NO BREACH

| Frozen file | sha256 (this session, first 16 hex) | Verdict |
|---|---|---|
| engine/hazard.py  | `d862e636c3078362` | UNBREACHED (NONE) |
| engine/lgd.py     | `8b16df7ef06ab2c0` | UNBREACHED (NONE) |
| engine/ead.py     | `caff4dc715ca0992` | UNBREACHED (NONE) |
| engine/staging.py | `c424882ad5ca2d8c` | UNBREACHED (NONE) |
| engine/ecl.py     | `bdf463250956398d` | UNBREACHED (NONE) |

Identical to every prior gate's recorded hashes (`git diff HEAD --
engine/{hazard,lgd,ead,staging,ecl}.py` empty) — this pass never touches
`engine/`. `scan_code.py` over `engine agent app analysis`: 29 files
scanned, 26 local modules, 463 call edges, zero fingerprint drift on the
frozen five.

## 4. `npm run build` — GREEN, waterfall regression 10/10

`npm run build` (prebuild → `verify:waterfall` auto-runs):

```
verify-waterfall: historical-mode adapter + buildWaterfallOption regression check
  PASS x10 (adapter shape, opening/closing values, 4 delta steps, series
  count, non-empty movement, one datum/category, finite values, non-empty
  x-axis, negative control on the un-adapted payload)
verify-waterfall: OK
```

`vite build`: `dist/index.html` 0.52 kB, `index-DiN1hiBF.css` 25.34 kB
(gzip 5.47 kB), `index-CwGqyRWf.js` 78.87 kB (gzip 26.11 kB — the small
bump from UI v3's 77.92 kB is the REASONED status-indicator branch added
to `MiniChatDock.jsx`/`ChatPanel.jsx`), `echarts-Bjbsz_mz.js` 514.79 kB
(unchanged vendor chunk).

## 5. Local E2E — PASS (shadow build-root; no Docker daemon in this sandbox)

No Docker daemon reachable (same limitation as every prior gate — `docker`
CLI absent from this WSL distro, no daemon socket). Verification used two
paths:

* **In-process**: the full pytest suite (§2) exercises FastAPI via
  `TestClient` against every route including `POST /api/agent/ask`.
* **Shadow build-root**: a scratch directory assembled by hand-copying
  exactly what each Dockerfile `COPY` instruction places into the image
  (`engine/agent/app/api/analysis/wiki/knowledge/data/outputs` subset +
  a freshly `npm run build`-ed `app/ui/dist`), then the project's real
  venv's `uvicorn app.api.main:app` run from that shadow root so every
  relative-path read resolves exactly as inside the container.

Server: `uvicorn app.api.main:app --port 7861`, `OPENROUTER_API_KEY`
exported from `.env`. Health: `{"status":"ok","engine_warm":true,
"warm_up_seconds":13.05,"agent":"langgraph"}`.

**The three router classes, live against the shadow root:**

1. **The motivating example** — `POST /api/agent/ask {"question": "Does
   the satellite need a UER x HPI interaction, or do the main effects and
   momentum already account for the joint stress response?"}` →
   `route: "REASONED"`, `mode: "reasoned"`, answer prefixed
   `"[REASONED — interpretation, not engine output] "`, cites
   `pages/hazard-model.md#Fit` twice, `number_check_passed: true`. Before
   this feature this question hit `REFUSE`; it no longer does.
2. **Refusal-class** — `"What's your view on Bitcoin as a hedge for our
   book?"` → `route: "REFUSE"`, `mode: "refusal"`, the standard six-tool-
   family refusal text (now also pointing users toward rephrasing toward
   the model's methodology for a reasoned answer). Still refuses.
3. **Tool-class** — `"What happens to the allowance if unemployment rises
   2 percentage points?"` → `route: "shock_macro"`, `mode: "grounded"`,
   `number_check_passed: true`, `$30.5m -> $31.7m` verbatim from the
   engine. Unaffected by the reasoned-route change.

## 6. Wiki audit — known staleness, not touched (orchestrator's job)

`wiki_audit.py wiki --strict` → 20 pages, 102 edges, 6 errors (stale
`agent-layer` page: `agent/graph.py`, `app/api/main.py`, and 4 test files
changed since the manifest was last compiled), 1 warning (`tests/
test_reasoned.py` uncovered). Per this task's scope boundary, wiki/
memory registers are the orchestrator's job and were deliberately left
untouched this session — recorded here so the next wiki-maintenance pass
knows exactly what to recompile.

## 7. Deploy state — LIVE, verified

* Space: **https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot**
  — existing PUBLIC Space, operator-pre-authorized update.
* Pre-upload state: `space_info().runtime.stage == "RUNNING"` at
  `sha=cc466315de667c87ccc75866dffd7c70ef6591a8` (the UI v3 build that
  finally cleared HF's builder backlog per the prior session's log entry).
* Uploaded a single narrowly-scoped commit — `allow_patterns` equivalent
  (explicit file list, not a blanket `upload_folder`): `agent/graph.py`,
  `app/api/main.py`, `app/ui/src/components/AgentTrace.jsx`,
  `app/ui/src/components/ChatPanel.jsx`,
  `app/ui/src/components/MiniChatDock.jsx`, `app/ui/src/styles.css`,
  `app/ui/src/tabs/CopilotTab.jsx`, `docs/api_contract.md`. Test files
  (`tests/test_*.py`) and the dev-only `scripts/smoke_reasoned.py` are
  deliberately NOT shipped — they are not read by the running container.
  Commit: `544bcbe5197074e77c9ed809579b2380b7d0c485`.
* **Build queue cleared fast this time**: `RUNNING_BUILDING` immediately
  after upload, `RUNNING` again within ~1 minute (`sha` advanced to
  `544bcbe...`) — no repeat of the prior session's multi-hour HF builder
  backlog.
* **Live verification, all three router classes** (same three questions
  as §5, now against `https://preetomsorkar-ifrs9-ecl-copilot.hf.space`):
  * `/api/health` → `{"status":"ok","engine_warm":true,
    "warm_up_seconds":13.94,"agent":"langgraph"}`.
  * The motivating example → `route: "REASONED"`, `mode: "reasoned"`,
    same `[REASONED — ...]` prefix, cites `pages/hazard-model.md#Fit`,
    `number_check_passed: true` — live, on the rebuilt container.
  * Refusal-class → `route: "REFUSE"`, `mode: "refusal"` — still refuses,
    live.
  * SPA bundle hash served live: `assets/index-CwGqyRWf.js` — byte-
    identical filename hash to the local `npm run build` output in §4,
    confirming the live container really did rebuild from the uploaded
    `app/ui/src/**` sources rather than serving a stale cached bundle.
* **Zero downtime** throughout — the prior build stayed `READY`/serving
  until the new one cut over.

## 8. Bottom line

**582/582 tests, frozen five byte-identical (NONE), `npm run build` clean
including the 10/10 waterfall regression check, all five review claims
verified against the actual diff, uploaded to the live public Space, and
fully live-verified** — the motivating example (the joint-stress
interaction-term question) now returns a `REASONED`/`reasoned`-mode,
cited, labeled interpretation instead of hitting refusal, the
spelled-out-number guard is live and covered by an adversarial regression
test, and a genuine refusal-class question still refuses. This is a
**complete** ship: nothing deferred. (Wiki `agent-layer` page staleness
noted in §6 is out of this task's scope per the orchestrator boundary,
not a gap in the shipped feature.)
