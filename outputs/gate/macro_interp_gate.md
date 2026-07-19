# Macro/FRED Interpretation Feature — Ship Gate

Ships requirement 12's app-side deliverable (`notes/plan/requirement_12_macro_interpretation.md`):
per-variable coefficient interpretation (`unit_meaning`, `transformation`, `lag`,
`fred_series`, `economic_channel`, `hazard_ratio_per_unit`, `worked_example`) added to
`/api/model/variable_dictionary`, `/api/model/coefficients`, `/api/model/macro_glossary`
and `/api/freddie/hazard`, plus the matching UI (hazard-ratio column, expandable
per-row interpretation panel, FRED-source badges, "How to read these coefficients"
intro panels on the Model and Real Data tabs, and a one-line coherent-shock-convention
note on the satellite/scenario panels). This session shipped the already-authored,
already-reviewed feature to the live Space. Gate run 2026-07-19.

A prior review pass (recorded in this session's transcript) fixed three issues before
this ship: (1) `_hazard_ratio_per_unit()` grouped `"interaction"` with `"none"` so
DOUBLE TRIGGER / `dt_ltv_uer` rows correctly return `null` instead of leaking a
product-term coefficient as a marginal per-unit read; (2) the 6 DCR/national
`_CONCEPTS` entries and 5 `_MACRO_GLOSSARY` rows had `fred_series` set to `null` (DCR's
national macro is a vendor-premerged series on the panel's own anonymized clock, not a
live FRED pull — the FRED-UNRATE calendar-anchoring correlation fact, corr 0.996, was
moved into each row's `transformation`/`lag_rationale` prose instead of misrepresenting
it as a live series pointer); (3) `docs/api_contract.md` and `tests/test_contract.py`
were updated to match this corrected always-null-for-DCR semantics, with a new
regression asserting `double_trigger`/`dt_ltv_uer`'s `hazard_ratio_per_unit is None` on
both `/api/model/coefficients` and `/api/model/variable_dictionary`.

## 1. Test suite — GREEN, 665/665

```
uv run --no-sync pytest -q
...
665 passed, 29 warnings in 290.31s (0:04:50)
```

- Baseline (pre-this-feature): 664/664 (`mdd_freddie_gate.md`).
- Net +1 test this session (the DOUBLE TRIGGER / `dt_ltv_uer` null-hazard-ratio
  regression added alongside the corrected `fred_series` assertions — most of this
  feature's contract coverage was authored and counted in the 664 baseline; this ship
  only added the fix-driven regression). Zero failures, zero errors, zero skips. The
  29 warnings are all pre-existing/environmental (`httpx`/Starlette deprecation, a
  `parametrize` iterator deprecation, a `multiprocessing.fork()` warning from
  `tests/test_tier2.py`) — none touch this session's code.

## 2. UI build — GREEN

```
cd app/ui && npm run build
```

- `prebuild` → `verify:waterfall` regression: **10/10 PASS** (the historical-mode
  adapter + `buildWaterfallOption` check stays green — required, unrelated to this
  feature, and never allowed to regress).
- `vite build`: 591 modules transformed, built in 5.54s.
- Output bundle: `dist/assets/index-BfC8ZvYF.js` (101.73 kB, gzip 32.86 kB) +
  `dist/assets/echarts-Bjbsz_mz.js` (vendor chunk, unchanged content hash — echarts
  itself wasn't touched) + `dist/assets/index-2gdYZ48n.css` (27.75 kB, gzip 5.85 kB).

## 3. Files shipped to the Space

Uploaded via `huggingface_hub.HfApi.create_commit` (one atomic commit, token from
`.env`, never printed) to `Preetomsorkar/ifrs9-ecl-copilot` (repo_type=`space`):

- `app/api/main.py` — the interpretation fields, `_CONCEPTS`/`_MACRO_GLOSSARY` tables,
  `_hazard_ratio_per_unit`/`_worked_example`/`_variable_interpretation` helpers.
- `app/ui/src/api.js`, `styles.css`
- `app/ui/src/tabs/ExecutiveTab.jsx`, `FreddieTab.jsx`, `ModelTab.jsx`,
  `ScenarioLabTab.jsx`
- `app/ui/src/components/CoefficientInterpretation.jsx` (new, 77 lines),
  `app/ui/src/components/HowToReadCoefficients.jsx` (new, 53 lines)
- `docs/api_contract.md`
- `tests/test_contract.py` (tracked in the Space's git repo per the established
  convention — excluded from the Docker build context by `.dockerignore`, but kept in
  the repo for parity with local source)

Commit: `66752373640370436d626296d53930daff1d0a0f`
(https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot/commit/66752373640370436d626296d53930daff1d0a0f).
No `Dockerfile` change was needed — the UI is built from source inside the Docker
build's `ui` stage (`COPY app/ui/src ./src` + `npm run build`), so no separate `dist/`
upload was required either.

## 4. Space build + live verification

Polled `HfApi.space_info(..., expand=["runtime"])` from commit push to `RUNNING`:

```
[08:17:47] stage=RUNNING_BUILDING   sha=6675237...
[08:18:03] stage=RUNNING_APP_STARTING
[08:18:47] stage=RUNNING_BUILDING   (rebuild churn, same commit)
[08:19:02] stage=RUNNING
```

RUNNING reached ~75s after push (well inside the 30-minute budget; no queue stall this
time — contrast the multi-attempt `outputs/freddie`/`outputs/mdd` COPY wedge documented
in `mdd_freddie_gate.md`, not reproduced here since this ship touched no new top-level
`COPY` directories).

Live-verify (`GET` against `https://preetomsorkar-ifrs9-ecl-copilot.hf.space`):

- **`/api/model/macro_glossary` → 200.** All 4 DCR rows (`dcr_uer_level`,
  `dcr_uer_momentum`, `dcr_hpi_growth`, `dcr_gdp_growth`) plus `satellite_hpi_growth`
  confirmed `fred_series: null`; the 3 SFLLD rows confirmed non-null
  (`sflld_uer_level`/`sflld_uer_momentum` → `"{POSTAL}UR"`, `sflld_hpi_growth` →
  `"{POSTAL}STHPI"`) — the DCR-vs-SFLLD contrast the fix targeted is live and correct.
- **`/api/freddie/hazard` → 200**, `coefficients` rows carry the new interpretation
  fields. Recomputed `hazard_ratio_per_unit` independently in the verify script (not
  just diffed against the server's own `hazard_ratio` field) as `round(exp(coef), 6)`
  for 3 sampled rows — exact match every time:
  - `Intercept`: coef=-3.604265652756619 -> exp(coef)=0.027207 == served
    hazard_ratio_per_unit=0.027207
  - `occupancy_status[T.I]` (investor): coef=0.094295175693194 -> exp(coef)=1.098884
    == served hazard_ratio_per_unit=1.098884
  - `occupancy_status[T.S]` (second home): coef=-0.1925821350206147 ->
    exp(coef)=0.824827 == served hazard_ratio_per_unit=0.824827
  - (No `DOUBLE TRIGGER`/interaction term exists in the SFLLD `coefficients.csv` term
    set — that interaction only appears in the DCR model's `/api/model/coefficients`
    and `variable_dictionary`; its null-hazard-ratio regression is covered by the
    665-test suite above, not re-checked live here.)
- **SPA bundle hash changed and matches the local build.** `curl` of the live `/` shows
  `assets/index-BfC8ZvYF.js`, identical to this session's local `npm run build` output
  — confirms the Space is serving the freshly built bundle, not a stale cached one.

## 5. Verdict

**SHIP COMPLETE.** 665/665 tests green, UI build green (waterfall regression intact),
Space reached `RUNNING` ~75s after push, and all three live-verify legs (macro_glossary
DCR/SFLLD contrast, freddie/hazard mechanical hazard-ratio recompute, SPA bundle hash)
passed against the public URL:
https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot.
