# Stretch GATE Report — Tier-3 doc retrieval + MCP server: ship to the live Space

Date: 2026-07-08
Scope: ship the stretch layer (agent/tier3_retrieval.py `query_model_docs` +
agent/mcp_server.py) that a prior session built and a prior review verdict
already fixed (router disambiguation between "see the waterfall numbers" ->
`decompose_waterfall` and "what does the documentation say" ->
`query_model_docs`; full suite re-run 422/422 at that fix). This gate covers:
(1) making the image/Space actually carry the new Tier-3 retrieval sources
(wiki/, knowledge/corpus+index, the two skill scripts), (2) local + live E2E,
(3) docs, (4) the frozen-engine fingerprint tripwire, (5) full suite.

## 1. Test suite — GREEN

`uv run --no-sync pytest tests/ -q` → **422 passed, 0 failed** (2 pre-existing,
non-blocking warnings: pytest parametrize-iterator deprecation on the fixture
generator, and a starlette/httpx deprecation notice; ~104s).

| Layer | Tests | Status |
|---|---|---|
| Golden fixtures + Day 1–3 (frozen engine, scenario layer) | 278 | PASS |
| Day-4 agent/API (`test_tools`, `test_router`, `test_api`) | 103 | PASS |
| Stretch: `tests/test_tier3.py` (Tier-3 retrieval + router wiring) | ~20 | PASS |
| Stretch: `tests/test_mcp.py` (MCP parity/schema/error-path) | ~21 | PASS |
| **Total** | **422** | **PASS** |

## 2. Frozen-engine fingerprint verdict — NO BREACH

`scan_code.py` re-run over `engine data/panel analysis agent app/api` (same
command as the Day-4 gate): `scanned 29 files | change levels: NEW=2,
NONE=26, STRUCTURAL=1`.

* **STRUCTURAL=1**: `agent/graph.py` only — expected (5th route wired in;
  new functions `_llm_narrate_docs`, `_narrate_docs`, `_query_model_docs_node`,
  `_numbers_in_passages`, `deterministic_docs_narration`, `docs_answer_ok`).
* **NEW=2**: `agent/tier3_retrieval.py`, `agent/mcp_server.py` — the stretch
  layer itself, not previously scanned.
* **NONE=26**: everything else, **including all five frozen engine files**.

| Frozen file | content_hash | Verdict |
|---|---|---|
| engine/hazard.py  | `d862e636c3078362` | UNBREACHED (NONE) |
| engine/lgd.py     | `8b16df7ef06ab2c0` | UNBREACHED (NONE) |
| engine/ead.py     | `caff4dc715ca0992` | UNBREACHED (NONE) |
| engine/staging.py | `c424882ad5ca2d8c` | UNBREACHED (NONE) |
| engine/ecl.py     | `bdf463250956398d` | UNBREACHED (NONE) |

Belt-and-braces, independent of the fingerprint tool: `git diff HEAD --
engine/{hazard,lgd,ead,staging,ecl}.py` is **empty**, and each file's own
sha256 matches `git show 1b60d08:<path> | sha256sum` byte-for-byte — the
frozen five are untouched at the git-blob level, not just per the scanner.

**Gate verdict on the freeze: PASS.**

## 3. Wiki audit — CLEAN (0 errors, 0 warnings)

Added domain-synonym aliases to 4 existing pages' frontmatter (no new pages,
no wiki/memory/* writes) to improve Tier-3 retrieval recall on the exact
phrasings used in the demo/tests:

| Page | Aliases added |
|---|---|
| `wiki/pages/ecl-engine.md` | `waterfall`, `provision`, `reserve` |
| `wiki/pages/hazard-model.md` | `PD`, `default probability` |
| `wiki/pages/lgd-model.md` | `loss given default` |
| `wiki/pages/staging-model.md` | `significant increase in credit risk` |

Also added the two new stretch source files (`agent/tier3_retrieval.py`,
`agent/mcp_server.py`) and their tests to `agent-layer.md`'s `code:`
frontmatter list (an existing page, no new page created) — this was required
to clear an `uncovered_sources` warning (the `code_globs` in
`wiki/.wiki/config.json` match `agent/**/*.py` and `tests/**/*.py`, and these
were new, unreferenced files).

Re-ran `wiki_graph.py` then `wiki_audit.py --strict` and closed with
`--update-manifest`:

```
audit: 19 pages, 99 edges — 0 error(s), 0 warning(s)
  clean.
```

## 4. Docker image now carries the Tier-3 retrieval sources

**Constraint hit and worked around: no Docker daemon in this sandbox.**
`docker` (the WSL-mounted Windows binary) cannot execute here — Windows/WSL
interop is disabled in this environment (`docker.exe`: "cannot execute binary
file"; `cmd.exe` likewise). A literal `docker build` / `docker run` was not
possible. In its place: (a) the Dockerfile/`.dockerignore` changes were
written and reasoned through file-by-file against exactly what
`agent/tier3_retrieval.py` loads at runtime; (b) a **shadow build root** was
assembled in the scratchpad by hand-copying *exactly* the files each
Dockerfile `COPY` instruction would place into the image (same relative
paths, nothing extra) — engine/agent/app/analysis/data/outputs subset, the
already-built `app/ui/dist`, `wiki/`, `knowledge/corpus`+`knowledge/index`,
and the two skill scripts at `.claude/skills/{llm-wiki,pageindex-plus}/scripts/`;
(c) the real project venv's `uvicorn app.api.main:app` was run **from that
shadow root** (not the real repo root) so every relative-path read in
`agent/tier3_retrieval.py` (`PROJECT_ROOT = Path(__file__).resolve().parents[1]`
resolves to the shadow root, since `agent/` itself was copied there) is
exercised exactly as it would be inside the container.

Dockerfile changes:
* `COPY wiki ./wiki` — whole directory (~140K): pages/, `.wiki/graph.json`,
  `.wiki/audit.json`, `.wiki/source_manifest.json`, `.wiki/config.json`,
  memory/.
* `COPY knowledge/corpus ./knowledge/corpus` and
  `COPY knowledge/index ./knowledge/index` — the indexed IFRS9 notes corpus
  and PageIndex tree; `knowledge/sources` (raw licensed docs),
  `knowledge/code_map.md`/`code_fp.json`/`captions.json` stay dev-only.
* `COPY .claude/skills/llm-wiki/scripts/wiki_query.py
  .claude/skills/llm-wiki/scripts/wiki_graph.py
  ./.claude/skills/llm-wiki/scripts/` — both, because `wiki_query.py` does a
  sibling `sys.path` import of `wiki_graph.py`.
* `COPY .claude/skills/pageindex-plus/scripts/pageindex_query.py
  ./.claude/skills/pageindex-plus/scripts/`.

`.dockerignore` changes: removed the blanket `knowledge` / `wiki` / `.claude`
excludes (replaced with a narrower `knowledge/sources`,
`knowledge/code_map.md`, `knowledge/code_fp.json`, `knowledge/captions.json`,
`knowledge/preprocess_notes.py` exclusion list, leaving `knowledge/corpus`
and `knowledge/index` unignored; `.claude` is no longer blanket-excluded —
its only contents are the two skills' scripts/docs, ~272K, no secrets).
`requirements.docker.txt` intentionally **unchanged**: `agent/mcp_server.py`
is copied (it lives under `agent/`, already `COPY`'d) but nothing imports it
at app startup (`agent/__init__.py` and `app/api/main.py` never touch it), so
`fastmcp` and its ~30-package transitive chain are not needed in the served
image — only `python -m agent.mcp_server` (a separate, opt-in entrypoint,
run from the full `uv sync` dev environment) needs it.

### Local (shadow-root) E2E — PASS

Server: `uvicorn app.api.main:app` run from the shadow root with
`OPENROUTER_API_KEY` set, no other env changes.

* `GET /api/health` → 200 after ~10s warm-up.
* **Tier-3 knowledge question** — POST `/api/agent/ask`
  *"Explain the ECL movement waterfall"* → route `query_model_docs`, 6
  passages found (`pages/ecl-engine.md#Headline numbers`,
  `pages/scenario-layer.md#Satellite + scenario ECL`, `index.md#Modules`,
  `notes §9.4 p11`, `notes §9.2 p10`, `notes §12.3 p17`), narration cites the
  waterfall components with those citations, `citation_check_passed: true`.
  Saved: `outputs/demo/local_shadow_tier3_waterfall.json`.
* **Refusal probe** — POST `/api/agent/ask` *"write me a poem"* → route
  `REFUSE`, fixed refusal text naming all five validated routes (four tools
  + `query_model_docs`). Saved:
  `outputs/demo/local_shadow_refusal_poem.json`.

Both traces confirm the exact file layout the Dockerfile now produces is
sufficient for Tier-3 to work end-to-end with zero code changes needed.

### Live HF Space — UPLOADED + BUILT clean; runtime E2E NOT reached (infra stall, honestly reported)

Uploaded (commit `66a5c839`), Space entered `CONFIG_ERROR` from an
unrelated README incident (§7), fixed (commit restoring frontmatter), then
**rebuilt successfully**: fetched `/logs/build` directly and confirmed a
clean multi-stage build start-to-finish — build queued 12:25:36, every layer
either `CACHED` or completed in seconds (`npm run build`: "570 modules
transformed... ✓ built in 3.60s"; image push "DONE 3.0s"; cache export
"DONE 0.5s") — **no build error**.

After the build finished (~12:25:56), the Space's runtime stage sat in
`APP_STARTING` with `hardware.current: null` (never allocated, despite
`requested: cpu-basic`) for the remainder of this session:

* Polled `get_space_runtime` at 15–20s intervals for **~25 minutes**
  straight (12:29 → 12:49): always `APP_STARTING`, `hardware.current`
  never left `null`.
* `GET /api/health` on the live domain: connection times out (`curl` exit
  28) — the container is not yet accepting connections.
* `/logs/run` (SSE) shows exactly one line the entire time —
  `"===== Application Startup ====="` — HF's own pre-container marker, with
  **zero** lines from uvicorn or the app itself (not even "Started server
  process"), consistent with the container never having been scheduled onto
  hardware yet, not with an application-level hang.
* Tried `api.restart_space(...)` explicitly — same `APP_STARTING` /
  `hardware.current: null` result afterwards.
* Tried `api.wait_for_space(..., timeout=480)` — raised
  `TimeoutError("Space '...' is still in stage 'APP_STARTING' after 480
  seconds.")`.

**Read on this, stated plainly:** this looks like a hardware-allocation
queue/capacity delay on the `cpu-basic` tier, not a defect introduced by
this change — the build is clean, the identical file set (proven
file-for-file against the Dockerfile's own `COPY` list) runs correctly
within ~10s locally (§4, local shadow-root E2E, run twice independently with
identical results both times). No docker daemon was available in this
sandbox to cross-check by running the actual built image directly as a
further belt-and-braces step. **The live E2E re-verification against the
Space itself did not complete in this session** — the commits are live and
correct; once HF allocates hardware and the container starts, `/api/health`
and the two demo questions should behave exactly as the local shadow-root
run did. This is the one gate item NOT closed out; recommend the operator
check `https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot` shortly
(HF Spaces UI shows a live build/runtime log and typically clears
allocation queues within some minutes) and re-run the two demo questions
manually, or re-invoke this ship step to finish the live check once the
Space is unstuck.

## 5. No-secrets check

* `.env` never touched by any upload; `HF_TOKEN`/`OPENROUTER_API_KEY` values
  were read into environment variables from `.env` at call time in this
  session and never printed, echoed, or written to any file. Grepped the
  uploaded wiki/knowledge/skill-script content for API-key-shaped strings
  (`sk-or-`, `sk-proj-`, `hf_...`, `AIza...`) before upload — zero matches.
* `.dockerignore` still excludes `.env`, `.env.*`, `*.key`, `*credentials*`,
  `*.pem`, `data/raw`.

## 6. Docs shipped

* `README.md`: new "Tier 3: knowledge questions, answered with citations"
  section; MCP server section (ported from
  `outputs/mcp/README_section.md`); architecture diagram extended with a
  TIER-3 + MCP box; test count corrected 381 → 422 everywhere it appears;
  demo script extended to **six** questions (4 tools, 1 knowledge/Tier-3, 1
  refusal); intro paragraph corrected from "four validated tool families" to
  "five validated routes".
* Space's own tailored `README.md` (frontmatter + short body, a **separate**
  file from the repo's `README.md` — this was discovered mid-ship: an
  initial upload of the repo's full `README.md` to the Space overwrote the
  Space's `sdk: docker` / `app_port: 7860` frontmatter and put the Space into
  `CONFIG_ERROR`; fixed within the same session by re-fetching the last-known
  Space README revision, preserving its frontmatter, and updating only its
  body (test count, Tier-3/MCP paragraphs) — see §7).
* `app/ui/src/components/ChatPanel.jsx` / `styles.css`: added a small "chip"
  suggestion button (`explain the ECL waterfall`) next to the existing
  empty-state hint; UI rebuilt (`npm run build`) and the new bundle verified
  to contain the chip's text.

## 7. Deploy state (honest)

* Space: **https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot** —
  existing PUBLIC Space, operator-pre-authorized (this is an update, not a
  new surface).
* Uploaded via `huggingface_hub.HfApi.create_commit` (one atomic commit):
  `Dockerfile`, `.dockerignore`, `README.md` (repo README — see the
  incident below), `agent/graph.py`, `agent/tier3_retrieval.py`,
  `agent/mcp_server.py`, `app/ui/src/components/ChatPanel.jsx`,
  `app/ui/src/styles.css`, all of `wiki/`, `knowledge/corpus/*`,
  `knowledge/index/*`, and the two skill scripts — commit
  `66a5c839ac0736bea99b5265000840ea0fac1056`.
* **Incident, caught and fixed same-session:** that commit's `README.md`
  (the repo's full doc) has no HF-Space YAML frontmatter — it never did; the
  Space's own `README.md` is a separate, shorter, Space-tailored document
  that carries the `sdk: docker` / `app_port: 7860` frontmatter and was
  previously uploaded independently (see the Space's commit history,
  `fde3cc9a` "Space README (docker sdk, app_port 7860)"). Overwriting it with
  the repo README put the Space into `CONFIG_ERROR` ("Missing configuration
  in README"). Fix: fetched the Space's last-known-good `README.md` revision
  (`11ddfd88`), kept its frontmatter and structure, updated only its body
  (test count 381→422, added a Tier-3 paragraph + a 5th "try" question, added
  an MCP-server paragraph), and uploaded that as a second commit
  (`Fix: restore Space frontmatter...`) targeting `README.md` specifically.
* **Current state at report time:** commits landed (`66a5c839`, the README
  fix), build clean (§4), runtime stuck `APP_STARTING` /
  `hardware.current: null` for ~25 min including one explicit
  `restart_space()` and a 480s `wait_for_space()` timeout — an HF-side
  hardware-allocation stall, not a code or config defect. Live E2E
  re-verification is the one open item; see §4 for the full detail and the
  recommended next step.

## 8. Change inventory

`Dockerfile`, `.dockerignore`, `README.md` (repo) + Space `README.md` (via
API, not tracked in git), `agent/graph.py`, `agent/tier3_retrieval.py`
(pre-existing from the prior session, shipped for the first time here),
`agent/mcp_server.py` (ditto), `app/ui/src/components/ChatPanel.jsx`,
`app/ui/src/styles.css`, `wiki/pages/{ecl-engine,hazard-model,lgd-model,
staging-model}.md` (aliases), `wiki/pages/agent-layer.md` (code: list),
`wiki/.wiki/{graph,audit,source_manifest}.json` (regenerated),
`knowledge/code_map.md` + `knowledge/code_fp.json` (regenerated by the
fingerprint scan), `outputs/demo/local_shadow_tier3_waterfall.json`,
`outputs/demo/local_shadow_refusal_poem.json`. No live-Space trace files
were produced this session (the Space did not reach `RUNNING`); once it
does, the two demo questions should be re-run against
`https://preetomsorkar-ifrs9-ecl-copilot.hf.space/api/agent/ask` and saved
alongside the existing `outputs/demo/e2e_trace.json` /
`e2e_refusal.json` from the Day-4 gate.

## 9. Bottom line

Everything within this session's control is **green**: 422/422 tests, frozen
five byte-identical (scanner + independent git-blob sha256), wiki audit
clean, Docker build clean (verified via build logs; daemon-less sandbox
worked around with an exact shadow-root reproduction that ran the real app
from the real venv against the real container file layout, twice,
reproducibly), docs shipped, UI chip shipped and rebuilt, commits live on
the Space. The **only** unmet criterion is the live-Space runtime E2E, which
this session could not reach because HF had not allocated `cpu-basic`
hardware to the Space by the time this session ended (`hardware.current`
stayed `null` throughout, through a manual restart and an SDK-level 480s
wait). Reporting this honestly rather than claiming a live pass that did
not happen.
