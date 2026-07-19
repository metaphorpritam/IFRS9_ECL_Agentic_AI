# MDD + Freddie ("Real Data") Tab — Ship Gate

Baseline `HEAD` = `8fbce5f` ("Rung 3 Phase B: SFLLD hazard/LGD/backtest/LSTM — gate
659/659"). This session ships the already-built Freddie ("Real Data") tab + the
compiled Model Development Document to the live HF Space and refreshes both READMEs
(the project's and the Space card's). Gate run 2026-07-19.

## 1. Test suite — GREEN, 664/664

```
uv run --no-sync pytest -q
...
664 passed, 29 warnings in 291.65s (0:04:51)
```

- Baseline (pre-this-session, Phase B gate): 659/659.
- New tests this session: 5, in `tests/test_contract.py` (the Real Data tab's
  UI/API contract — `/api/freddie/summary`, `/hazard`, `/backtest`, `/exhibits`).
- 659 + 5 = **664** — matches the full-suite run exactly. Zero failures, zero
  errors, zero skips. 29 warnings are all pre-existing/environmental
  (`httpx`/Starlette deprecation, a `parametrize` iterator deprecation, a
  `multiprocessing.fork()` warning from `tests/test_tier2.py`) — none touch
  this session's code.

## 2. UI build — GREEN

```
cd app/ui && npm run build
```

- `prebuild` → `npm run verify:waterfall`: all 10 checks PASS (historical-mode
  waterfall adapter regression guard, unchanged from Phase-B-era UI v3).
- `vite build`: 589 modules transformed, built in 5.45s.
  - `dist/assets/index-DP9C4-QY.js` (93.35 kB, gzip 30.04 kB) — includes the new
    `FreddieTab.jsx` + the `freddie` entry in `TABS`.
  - `dist/assets/echarts-Bjbsz_mz.js` (514.79 kB, gzip 172.83 kB) — unchanged
    vendor chunk.
  - `dist/assets/index-DiOdsYmQ.css` (26.08 kB, gzip 5.59 kB).

## 3. Dockerfile fix

`outputs/freddie/**` and `outputs/mdd/**` were **not** copied into the runtime
image — the `/api/freddie/*` endpoints and the `/static/mdd` mount would 404 (or
silently skip-mount, per `app/api/main.py`'s guarded `MDD_DIR.exists()` check) on
a fresh container build despite working locally. Fixed by adding, following the
existing `outputs/*` copy pattern:

```dockerfile
# Rung 3 (SFLLD real-data study) + the compiled Model Development Document:
# the /api/freddie/* endpoints parse outputs/freddie/**'s reports/CSVs/JSON
# and StaticFiles mounts serve outputs/freddie/** (Freddie tab exhibits) and
# outputs/mdd/** (the MDD.html + assets) — same read-only pattern as above.
COPY outputs/freddie ./outputs/freddie
COPY outputs/mdd ./outputs/mdd
```

Both directories are small (`outputs/freddie` 2.1M, `outputs/mdd` 1.1M — no
model checkpoints, only reports/CSVs/JSON/PNGs) and contain nothing excluded by
`.dockerignore` (which excludes secrets, node_modules/dist, raw data, and dev
tooling — not `outputs/`). Verified `.dockerignore` does not block either path
before adding the `COPY` lines.

## 4. README refresh

### Project `README.md` (repo root)

- New **"The honest backtest"** section near the top (right after the intro
  paragraph, before Architecture): the 2007-12 GFC-miss story (9.42x
  underprediction, hindsight ceiling 1.90x, and the mirror 2019-12 saturation
  failure at 0.06x), framed as the analytical case for IFRS 9 ¶5.5.17.
- New **"Real data at scale: the Freddie Mac SFLLD study"** section: panel scale
  (837,500 loans / 39,522,565 loan-months / 17 vintages), a DCR-vs-SFLLD hazard
  AUC comparison table (0.748/0.661 vs 0.8536/0.6847), the COVID verdict
  (EXCLUDE, review overturn), and the LSTM path-dependence decomposition
  (0.9925 OOT overall; 0.957 vs 0.570 on prior-delinquency-spell loans, near
  parity 0.529 vs 0.539 on clean history).
- Architecture diagram: added a 6th "REAL DATA — SFLLD (Rung 3)" box; App v2 box
  relabeled "6 TABS" with Real Data in the tab row.
- App v2 tab table: added the **Real Data** row; "Five tabs" → "Six tabs" in
  prose.
- Key exhibits table: 7 new rows (SFLLD EDA, the ALFRED backtest panel, hazard
  coefficients/calibration, LGD severity/cure, LSTM lift-split, and the MDD
  itself — linking `outputs/mdd/MDD.md` and the live `/static/mdd/MDD.html`).
- Test-discipline bullet and quickstart command: **509 → 664** tests, with the
  category breakdown extended (77 Rung 3 Phase B + 5 this session's contract
  tests) and the gate-history chain spelled out (509 → 582 → 659 → 664).
- Repository map: `freddie/` row added; wiki page count corrected 19 → 20
  (verified by listing `wiki/pages/` directly, 20 files); `outputs/` row notes
  `mdd/`; tab count 5 → 6.
- Left existing sections (Tier 2/3 explanations, quickstart, MCP server, App v2
  narrative, UI v3 design-pass narrative, demo script, numbers-that-matter
  bullets not touched above) unchanged, per instruction not to delete anything.

### Space card `README.md` (HF frontmatter + short pitch, hand-maintained
separately from the project README — no source file for it exists in the repo;
confirmed by diffing the live Space's README against the project's before
editing)

- `short_description` updated (kept ≤60 chars — the HF YAML validator enforces
  this at upload time; a first draft failed validation at 76 chars and was
  shortened).
- Retitled "IFRS 9 ECL Copilot — Real Data edition"; body updated to describe
  both validation legs (synthetic DCR fixtures + real SFLLD), leads with the
  9.42x honest-backtest headline, lists six tabs, adds a Real Data bullet to
  the "Try:" list (AUC comparison + LSTM decomposition), links the live
  `/static/mdd/MDD.html`, and bumps the quoted test count 513 → 664.

## 5. Space upload

Uploaded via `huggingface_hub.HfApi` (token from `.env`, never printed) to
`Preetomsorkar/ifrs9-ecl-copilot` (repo_type=`space`):

- `Dockerfile`
- `README.md` (Space card, frontmatter version — separate content from the
  project README, see §4)
- `app/api/main.py`
- `app/ui/src/api.js`, `app.jsx`, `styles.css`
- `app/ui/src/tabs/FreddieTab.jsx` (new file)
- `docs/api_contract.md`
- `outputs/freddie/**` (63 files — was entirely absent from the Space repo
  before this upload)
- `outputs/mdd/**` (10 files — was entirely absent from the Space repo before
  this upload)

`tests/` and `docs/` are excluded from the **Docker build context** by
`.dockerignore` but are (and remain) tracked in the Space's **git repo** — the
distinction that matters here is repo vs image; `docs/api_contract.md` needed
uploading to the repo regardless of the Dockerfile's `COPY` list, which is
image-only.

### Build-queue diagnosis (in progress / see §6 for the outcome)

Each `upload_file`/`upload_folder` call is a separate commit, and the Space
auto-builds on every push — so the *first* commit (`Dockerfile` alone, at
05:12:11) queued a build referencing `COPY outputs/mdd ./outputs/mdd` before
that directory existed in the repo at all, and even the build queued against
the final commit (`0ab95c1`, which does contain all 10 `outputs/mdd/` files —
verified via `list_repo_files(..., revision='0ab95c1...')`) hit
`ERROR: failed to calculate checksum ... "/outputs/mdd": not found`.

This was **not** a one-off: it recurred across 5 consecutive build attempts
(`restart_space()` x3, a content-change re-push, and `restart_space(
factory_reboot=True)` x1), alternately failing on `COPY outputs/freddie
./outputs/freddie` or `COPY outputs/mdd ./outputs/mdd` — never both in the
same build, and every other `COPY` (including long-standing directories like
`outputs/hazard`) resolved `CACHED`/fine every time. Independently verified,
every time, that the failing path is **not actually missing**:
`list_repo_files` at the exact failing commit SHA shows every file present,
and the specific LFS-pointer-tracked PNGs under both directories (per
`.gitattributes` — `covid_calibration_comparison.png`,
`state_{uer,hpi_growth}_2000_2025.png`, five `outputs/mdd/assets/exhibit_*`
files) resolve correctly over HTTP (`.../resolve/main/<path>`, real PNG
bytes, correct byte counts matching the local files) throughout. This matches
a documented class of issue (HF community reports: "failed to calculate
checksum ... not found" on Spaces Docker builds referencing files that
genuinely exist, workaround "factory rebuild") and the Space's own commit
history already names one prior occurrence, `cc466315de "Retrigger stalled
build (queue wedge, content unchanged)"` — but this session's occurrence
proved more persistent: a `factory_reboot=True` (a stronger reset than the
plain `restart_space()` the task brief anticipated) did **not** clear it
either, so the working theory narrowed to backend replication lag specific to
brand-new top-level directories in the Space's git tree (both `outputs/freddie/`
and `outputs/mdd/` were entirely new to this repo — confirmed via
`list_repo_files` before the first upload), needing longer wall-clock time to
propagate to whatever store the Docker build's context-fetcher reads from,
not shorter cache-busting retries.

**A self-inflicted complication mid-diagnosis, found and fixed within this
session**: attempt #7 tried an atomic `CommitOperationDelete(is_folder=True)`
+ `CommitOperationAdd(...)` (delete-and-recreate both directories in one
commit, to rule out a stale/corrupted object as the cause). The commit
succeeded, but the folder-delete operations swept away the same-commit adds
under those paths too — `outputs/freddie/` and `outputs/mdd/` ended up
**entirely absent** from the Space repo (verified via `list_repo_files` on
the resulting commit, 195 files vs 268 expected) rather than merely
unbuilt. **Caught immediately** by comparing file counts before/after; fixed
by two follow-up `upload_folder` calls (using absolute local paths this
time — the working directory is not guaranteed stable across tool calls in
this environment) that restored both directories to their correct 63- and
10-file counts, verified via `list_repo_files` before touching the build
again. The build attempt on the restored commit (`bcf615f5e8`) hit the exact
same `outputs/mdd: not found` signature — confirming the checksum failure is
unrelated to this detour and really is specific to the two new COPY lines
regardless of which underlying commit/blobs back them.

**9 consecutive build attempts, 0 successes**, spanning ~29 minutes
(05:12–05:41), all with the identical signature on one or the other of the
two new `COPY` lines and no other line ever failing. Partway through, the
live Space itself went to HTTP 503 ("Your space is in error") — a Docker
Space does not keep serving a prior successful container once a new build
fails, so every retry attempt (all targeting a commit the site had never
successfully served before) left the site down, not merely un-updated.

**Resolution shipped this session**: rather than continue gambling with a
now-confirmed-persistent platform-side issue against a live, down site, the
two new `COPY outputs/freddie` / `COPY outputs/mdd` lines were commented out
of the Dockerfile (both directories remain fully present in the Space's git
repo — 63 + 10 files, verified — just not yet baked into the image) with a
detailed comment explaining why and how to re-enable. This build succeeded
immediately (no cache-miss on any new top-level directory, since there no
longer is one) and the Space reached `RUNNING` in the normal ~90s
(`BUILDING` 05:41:42 → `APP_STARTING` 05:42:33 → `RUNNING` 05:43:03).

## 6. Live verification

Against `https://preetomsorkar-ifrs9-ecl-copilot.hf.space` at commit
`7d6755efa8` (`RUNNING`):

| Check | Result |
|---|---|
| `GET /` | 200, SPA shell serves |
| SPA bundle hash | `/assets/index-DP9C4-QY.js` — matches this session's local `npm run build` output exactly, confirming the new UI code (including `FreddieTab.jsx` + the `freddie` tab entry) is the one actually deployed |
| `GET /api/health` | 200, `engine_warm: true`, warm-up 13.2s |
| `GET /api/ecl/summary` | 200, `weighted_allowance: 34046377...` — pre-existing tabs unaffected |
| `GET /api/model/coefficients` | 200 — pre-existing tabs unaffected |
| `GET /api/freddie/summary` | **500** — expected: `outputs/freddie` is not in this image (see §5's temporary-disable note) |
| `GET /static/mdd/MDD.html` | **404** — expected: `MDD_DIR.exists()` guard correctly skips the mount when `outputs/mdd` is absent from the image |

The verbatim-AUC-pair live-verify the task asked for (`/api/freddie/summary`
returning the `0.8536`/`0.6847` pair) and the `/static/mdd/MDD.html` serve
check **could not be completed** — both depend on the two disabled `COPY`
lines. Everything else shipped this session (the Real Data tab's UI code,
the `/api/freddie/*` and `/static/freddie` route handlers, the `/static/mdd`
mount logic, both READMEs, the contract doc, the 5 new contract tests) is
live and verified; only the two data directories are pending re-enablement
in the image.

## 7. Verdict

**PARTIAL.** Everything gate-able locally is green: 664/664 tests, clean UI
build (waterfall regression guard passing, correct bundle hash confirmed
live), Dockerfile fix authored and correct in principle (verified by way of
elimination — every *other* line in it, including two brand-new individual
files uploaded the same session, built and copied without incident). Both
READMEs are refreshed and shipped. The Space is **RUNNING and healthy** —
service was restored, not left down — but the Real Data tab and the live MDD
page are **not yet functional on the Space** pending re-enablement of two
`COPY` lines that hit a reproducible, platform-side build failure across 9
attempts and roughly 29 minutes, well past the 30-minute polling budget.

**Diagnosis for the next attempt (orchestrator watcher or a future
session)**: uncomment the two `COPY outputs/freddie` / `COPY outputs/mdd`
lines in `Dockerfile` (both directories are already present and correct in
the Space's git repo — no re-upload needed) and push; poll `space_info()`
for `RUNNING`. Given the failure was 100% reproducible across every
mitigation tried in a ~30-minute window but is specific to two *brand-new*
top-level Space directories (not present in the repo before this session)
and never recurred on a single individual-file path, the most likely fix is
simply elapsed wall-clock time (hours, not further minutes) for whatever
storage tier the Docker build's context-fetcher reads from to catch up —
try again after a longer gap before assuming an HF support ticket is
needed. `docker build .` locally (outside HF's infra) would sidestep this
entirely as a sanity check that the Dockerfile itself is correct, if that's
available to whoever picks this up.

**Files changed and confirmed on the Space at `RUNNING` commit
`7d6755efa8`**: `Dockerfile` (with the two lines disabled), `README.md`
(Space card), `app/api/main.py`, `app/ui/src/{api.js,app.jsx,styles.css,
tabs/FreddieTab.jsx}`, `docs/api_contract.md`, `outputs/freddie/**` (63
files, present but not imaged), `outputs/mdd/**` (10 files, present but not
imaged). Local project repo (this git working tree, separate from the
Space's own git history) has the matching Dockerfile with the two lines
commented out and a clear re-enable note — intentionally left this way
rather than silently diverging from what's actually live.
