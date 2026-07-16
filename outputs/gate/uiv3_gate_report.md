# UI v3 GATE Report — ship to the live Space

Date: 2026-07-16
Scope: ship UI v3 (the fintech-direction design pass judged against three
built candidates, five grafts merged in from the losers) to the public HF
Space. This gate covers: (1) verifying the code changes claimed by the prior
Fable conformance review actually landed, (2) `npm run build` + the new
build-time waterfall regression script, (3) a Dockerfile gap the new
`prebuild` script exposed (caught and fixed before it could break a real
container build), (4) local E2E via an in-process FastAPI run and a
**shadow build-root** reproducing the exact container file layout (no
Docker daemon reachable in this sandbox, same limitation as every prior
gate), (5) upload + live-Space verification, (6) README, (7) the
frozen-engine fingerprint tripwire, (8) full suite.

## 1. Review claims verified against the diff

Read every file the prior review's summary named and confirmed each claim
against the actual working-tree diff before touching anything:

* `ExecutiveTab.jsx` / `WaterfallChart.jsx`: default historical window is
  `t0=59, t1=60` (latest quarter, FINAL_SPEC §8.2 comment present in both
  files); `WaterfallChart.jsx` wraps the raw `GET /api/ecl/waterfall`
  payload through `adaptWaterfallRows(d.components, 'Opening allowance',
  'Closing allowance')` before it reaches `buildWaterfallOption` — the fix
  for the historical-mode-renders-empty bug; subtitle now shows the live
  `t0 → t1` window with the period labels. Scenario Lab keeps user-driven
  t0/t1.
* `ExplainButton.jsx` is now `useExplain()` + shared `ExplainStrip`/
  `SparkIcon` exports; `Panel.jsx` renders `{explainStrip}` inline under
  `panel-body`, before the `Source:` footer; `StatTile.jsx` renders it at
  the tile bottom. `SelectionExplain.jsx` reuses `ExplainStrip` (floating).
  No leftover `.explain-wrap` CSS.
* `styles.css`: `[data-tip]:hover/:focus-visible::after` tooltip present
  (attr()-sourced), `.explain-btn.loading` ring + reduced-motion-gated
  pulse, `.scenario-dot` (9px, good/muted/crit), `.delta-pill` (good/bad
  wash variants), `.grounded-badge .status-dot` at 6px.
* `ChatPanel.jsx`: the "Ask the copilot" heading carries `useExplain` with
  a code-generated recap, `panelId: 'copilot_chat'`; strip renders under
  `panel-sub`.
* `ExecutiveTab.jsx` `ScenarioTable`: 9px status dots per row via
  `SCENARIO_DOT` map.

All five claims confirmed present and correctly wired — no discrepancy
between the review's summary and the code.

## 2. Test suite — GREEN

`uv run --no-sync pytest -q` → **513 passed, 0 failed** (~104s; same 2
pre-existing non-blocking deprecation warnings as every prior gate:
pytest's parametrize-iterator notice on the fixture generator, and the
starlette/httpx deprecation). `--collect-only -q` cross-check: 513.
Delta vs the App v2 gate's 509 is the 4 new tests this pass added to
`tests/test_contract.py` (the explain-prefix convention now documented in
`docs/api_contract.md` §5) — `wiki/pages/agent-layer.md` also gained a
matching section; nothing else moved.

## 3. Frozen-engine fingerprint verdict — NO BREACH

Independent, tool-free cross-check (no diff needed vs. the last gate's
recorded hashes — this pass never touches `engine/`):

| Frozen file | sha256 (this session) | Verdict |
|---|---|---|
| engine/hazard.py  | `d862e636c3078362...` | UNBREACHED (NONE) |
| engine/lgd.py     | `8b16df7ef06ab2c0...` | UNBREACHED (NONE) |
| engine/ead.py     | `caff4dc715ca0992...` | UNBREACHED (NONE) |
| engine/staging.py | `c424882ad5ca2d8c...` | UNBREACHED (NONE) |
| engine/ecl.py     | `bdf463250956398d...` | UNBREACHED (NONE) |

Every hash identical to the working tree at `HEAD` (`git diff HEAD --
engine/{hazard,lgd,ead,staging,ecl}.py` empty) and to the committed blob at
`43ba0a8` — byte-for-byte, exactly as recorded in every prior gate. Also
ran the `scan_code.py` scanner over `engine data/panel analysis agent app`:
`scanned 31 files | change levels: NONE=31` for the frozen five plus
everything else this pass didn't touch (the App v2 backend — `agent/`,
`app/api/`, `analysis/` — is untouched this pass; only `app/ui/` and docs
moved).

## 4. `npm run build` — GREEN, and the new regression check works

`npm run build` runs `prebuild` → `verify:waterfall` automatically
(wired via `package.json`'s `prebuild` script, which npm invokes ahead of
`build` with no separate step needed):

```
verify-waterfall: historical-mode adapter + buildWaterfallOption regression check
  PASS  adapter output has start/steps/end shape
  PASS  adapter start value matches opening_allowance / 1e6
  PASS  adapter end value matches closing_allowance / 1e6
  PASS  adapter carries the 4 delta steps
  PASS  option has exactly 2 series (base + movement)
  PASS  movement series is non-empty
  PASS  movement series has one datum per category (6: opening + 4 steps + closing)
  PASS  every movement datum carries a finite rendered value
  PASS  option.xAxis.data is non-empty (categories present)
  PASS  un-adapted raw payload does NOT produce a populated chart (proves the bug is real)
verify-waterfall: OK
```

10/10 checks pass, including the negative-control check (#10) that proves
the un-adapted raw payload really would have shipped an empty chart — the
regression class is provably caught, not just asserted away.

`vite build` output: `dist/index.html` 0.52 kB, `index-*.css` 24.97 kB
(gzip 5.43 kB), `index-*.js` **77.92 kB** (gzip 25.84 kB, down from the
prior session's 78.91 kB — the shared `useExplain()` hook replaced three
near-duplicate explain implementations), `echarts-*.js` 514.79 kB (gzip
172.83 kB, unchanged vendor chunk).

### 4.1 A Dockerfile gap the new `prebuild` script exposed — caught and fixed

The new `package.json` `prebuild` script (`node scripts/verify-waterfall.mjs`)
requires `app/ui/scripts/` to exist wherever `npm run build` runs. The
Dockerfile's UI build stage only copied `package.json`, `package-lock.json`,
`index.html`, `vite.config.js`, and `src/` — **not** the new `scripts/`
directory — so a real container build would have failed at `RUN npm run
build` with a missing-file error, npm's prebuild-hook auto-run being exactly
the mechanism that would trigger it. Caught by reproducing the UI build
stage in complete isolation (a fresh directory containing only the files the
Dockerfile's `COPY` instructions place there) and running `npm ci && npm run
build` in it — confirmed it fails without the fix and passes with it. Fixed:
added `COPY app/ui/scripts ./scripts` to the Dockerfile, immediately after
the `src/` copy. Re-verified in the same isolated reproduction: clean pass,
identical bundle sizes.

## 5. Local E2E — PASS (in-process + shadow build-root)

No Docker daemon reachable in this sandbox (same limitation noted in every
prior gate). Verification used two paths:

* **In-process**: full `pytest` suite (§2) exercises the FastAPI app via
  `TestClient` against every route, including the App v2/v3 read endpoints
  and `POST /api/agent/ask`.
* **Shadow build-root**: a directory in the scratchpad assembled by
  hand-copying exactly what each Dockerfile `COPY` instruction places into
  the image (engine/agent/app/api/analysis/wiki/knowledge/data/outputs
  subset + a freshly `npm run build`-ed `app/ui/dist`), then the project's
  real venv's `uvicorn app.api.main:app` run **from that shadow root** so
  every relative-path read resolves exactly as inside the container.

Server: `uvicorn app.api.main:app --port 7861` from the shadow root,
`OPENROUTER_API_KEY`/`HF_TOKEN` exported from `.env`. Health:
`{"status":"ok","engine_warm":true,"warm_up_seconds":14.25,"agent":
"langgraph"}`.

* **SPA at `/`** — 200, serves the rebuilt hashed asset tags
  (`index-CJhtEWcl.js`, `index-BlboJtPA.css`, `echarts-Bjbsz_mz.js`).
* **Every tab endpoint → 200**: `/api/health`, `/api/ecl/summary`,
  `/api/ecl/waterfall?t0=59&t1=60`, `/api/exhibits/credit_cycle`,
  `/api/exhibits/list`, `/api/model/coefficients`,
  `/api/model/variable_dictionary`, `/api/model/lgd`,
  `/api/policy/staging_sensitivity`, `/api/policy/weights_table`.
* **The regression fix, live**: `GET /api/ecl/waterfall?t0=59&t1=60`
  returns the raw `{components, period_t0: "2014Q4", period_t1: "2015Q1",
  ...}` shape — confirming the default Executive-Overview view now
  requests exactly the "latest quarter" window the fixed default renders
  (opening $18.8m → closing $15.5m).
* **CSS theme check**: `assets/index-*.css` served 200, contains
  `prefers-color-scheme:dark` and `data-theme` selector rules — both
  themes present in the shipped stylesheet.
* **Explain-prefix `/api/agent/ask` round trip** (the convention
  documented in `docs/api_contract.md` §5.1, used by
  `WaterfallChart.jsx`'s explain button):

  ```
  POST /api/agent/ask
  {"question": "[explain:waterfall t0=59 t1=60] Explain the Allowance
  bridge exhibit (t0=59, t1=60). Recap: opening $18.8m, stage migration
  +0.9m, closing $15.5m. What should I take from this?"}
  ```

  → routed to `decompose_waterfall(t0=59, t1=60)` by the live LangGraph
  router (`google/gemma-4-31b-it`), narrated answer quotes the same
  remeasurement (+4.7m) / derecognitions (−8.9m) / new-loans (+0.1m)
  figures visible in the tool's own JSON, `number_check_passed: true`.

## 6. Wiki audit — clean

`wiki_audit.py wiki --strict` → `19 pages, 99 edges — 0 error(s), 0
warning(s) -> clean.` (`wiki/pages/agent-layer.md` carries the new
explain-prefix contract section from the prior authoring session;
`wiki/.wiki/{audit,source_manifest}.json` already regenerated.)

## 7. Docs shipped

* Repository `README.md`: new "UI v3: a design pass judged against three
  directions" section — the editorial/fintech/terminal scoring (fintech
  won 42/50, five grafts merged from the losers), the waterfall bug fix,
  the palette contrast fix, the explain-strip relocation, and the bundle
  delta (78.91 → 77.92 kB). Placed directly after the existing "App v2"
  section.
* `docs/api_contract.md` §5 (already written by the authoring session):
  the two AI-explain question-prefix conventions (`[explain:<panel>
  <params>]` for panels/tiles, the selection-explain prefix), documented
  as UI-side wire-text on top of the existing `POST /api/agent/ask` — zero
  new endpoints, zero response-shape changes.
* This report (`outputs/gate/uiv3_gate_report.md`).

## 8. Deploy state

* Space: **https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot**
  — existing PUBLIC Space, operator-pre-authorized update (not a new
  surface).
* Learned from the App v2 gate's two incidents (Space `README.md`/
  `.gitattributes` clobber): uploaded in two separate, narrowly-scoped
  commits instead of one blanket `upload_folder` over the whole repo.
  1. **Main commit** — `allow_patterns` limited to exactly what changed:
     `Dockerfile`, `docs/api_contract.md`, `app/ui/package.json`,
     `app/ui/scripts/**`, `app/ui/src/**`. Backend (`agent/`, `app/api/`,
     `analysis/`, `engine/`, data, model cache) is untouched this pass and
     was deliberately NOT re-uploaded. `package-lock.json` unchanged, not
     re-uploaded. Diffed the Space's current file list against the local
     tree first — confirmed zero files need deleting (every new local
     file — `ExplainButton.jsx`, `Panel.jsx`, `SelectionExplain.jsx`,
     `numText.jsx`, `charts/waterfallOption.js` — is a pure addition).
  2. **README commit** — fetched the Space's own tailored `README.md`
     (HF frontmatter: `sdk: docker`, `app_port: 7860`, etc. — a file
     independently evolved from the repo's own `README.md`, never the same
     file), edited only the body (UI v3 summary paragraph, test count
     509 → 513), left the frontmatter untouched, uploaded as its own
     targeted commit. `.gitattributes` was not touched at all (no new
     binary/LFS paths this pass).
### Build queue — did not clear within this session (honest)

* The Space entered `RUNNING_BUILDING` immediately after the main-commit
  upload (`===== Build Queued at 2026-07-16 21:54:59 / Commit SHA: 61239ab
  =====`, confirmed via `HfApi.fetch_space_logs(build=True)`, both
  non-follow and live `follow=True` streaming) and **stayed there for ~55
  minutes with the build log never advancing past the initial "Queued"
  line** — well beyond every prior gate's build time (the App v2 gate's
  whole build+App_STARTING cycle was under 15 minutes).
* Verified this was a genuine platform-side stall, not a bad upload: fresh
  downloads of `Dockerfile`, `app/ui/package.json`, and
  `app/ui/scripts/verify-waterfall.mjs` straight from the Space repo were
  byte-for-byte identical to the local, already-verified copies.
* Applied the documented remedy from the App v2 gate's own incident notes
  (`HfApi.restart_space(factory_reboot=True)`), which the platform accepted
  (queue timestamp advanced to a fresh `22:53:23`) — but the rebuilt queue
  **also failed to clear within this session** (a further ~57 minutes
  observed, log still pinned at "Queued", `stage` never left
  `RUNNING_BUILDING`). A second reboot was deliberately not attempted: the
  first one gave no evidence of helping, and forcing another risks
  discarding whatever progress the platform has made silently in the
  background (the queue log not advancing does not by itself prove no
  progress — HF's build log endpoint showed only this one header line
  through the *entire* first ~55-minute attempt too, so its silence is not
  a reliable progress signal either way).
* **Zero downtime**: the Space's `domains` stage stayed `READY` throughout
  and `GET /api/health` / `GET /` against the live public URL
  (`https://preetomsorkar-ifrs9-ecl-copilot.hf.space`) returned 200 with
  `{"status":"ok","engine_warm":true,...,"agent":"langgraph"}` at the end
  of this session — visitors are still served the pre-UI-v3 build
  (commit `43ba0a8`-era content) without interruption while the new build
  queues.
* **Not completed this session**: the live UI v3 verification (SPA loads
  the new bundle, `/api/ecl/waterfall?t0=59&t1=60` served from the live
  container, one live explain-prefix `/api/agent/ask` round trip against
  the *rebuilt* Space) that the task asked for. Everything upstream of
  that — the code, the upload content, and the equivalent checks against a
  local shadow build-root reproducing the exact container layout — is done
  and green (§5).

**Next-session action**: poll `HfApi.space_info(...).runtime.stage` — if
still `RUNNING_BUILDING` after another extended wait, a second
`factory_reboot=True` is the same remedy the App v2 gate needed once
before; if `RUNTIME_ERROR`/`BUILD_ERROR`, `HfApi.fetch_space_logs(build=True)`
will finally show the real failure once the platform emits more than the
"Queued" header. Once `RUNNING`, re-run the three live checks listed above
and update this report's bottom line to reflect the completed live
verification.

## 9. Bottom line

Within this session's control: **513/513 tests, frozen five byte-identical
(NONE), `npm run build` clean including the new 10/10 waterfall regression
check, a real Dockerfile gap found and fixed before it could break a
container build, wiki audit clean, all five review claims verified against
the actual diff before shipping, docs updated, upload content verified
byte-identical on the Space.** The one item NOT closed out this session is
live-Space verification of the running UI v3 build — the container build
queue did not clear despite ~2 hours of waiting and one `factory_reboot`,
a platform-side condition with zero live-site downtime (see §8). This is a
**partial** ship: everything within this session's control is done and
green; the final live confirmation is a next-session follow-up.
