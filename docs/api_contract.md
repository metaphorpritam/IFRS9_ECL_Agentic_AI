# IFRS 9 ECL Copilot — API v2 Contract

**THIS FILE IS THE SINGLE SOURCE OF TRUTH.** The UI author codes ONLY
against the exact request/response JSON shapes documented here — never
against main.py source, never against a guess. If a field the UI needs is
missing from this file, that is an API bug: extend this contract first,
then the endpoint, then `tests/test_contract.py`, in that order. (Lesson
recorded from the Day-4 UI/API seam bug: the two were built in parallel
against imagined shapes and drifted.)

Every example below is a REAL response captured from the running app
(warm engine state, adopted 25/50/25 scenario weights), not an invented
placeholder. Numbers will drift slightly only if the frozen engine/model
inputs change; field names and types will not.

## Conventions

* **Base URL**: same-origin (`app/api/main.py` serves both the API and the
  built SPA on one origin — no CORS anywhere). All paths below are relative
  to that origin, e.g. `GET /api/ecl/summary`.
* **Money fields**: every dollar amount in every response is a **raw USD
  float** (e.g. `34046377.82`), NEVER pre-divided into millions. The
  response also carries `"amounts_in": "USD"` wherever a payload has money
  fields, as a machine-checkable reminder. **The UI divides by 1e6 itself**
  to render "$34.0m" — do not expect the API to do this. The one place a
  pre-formatted `$34.0m`-style string appears is inside a `headline` /
  `caption` / narration string, which is display-only prose, never parsed
  back into a number by the UI.
* **Percent fields**: fields named `*_pct` or `coverage` (a ratio, e.g.
  `0.0203` = 2.03%) — check the field name; `coverage`/`jensen_ratio` are
  **ratios in [0, ~2]**, not already-multiplied-by-100 percentages, while
  `*_pct` fields (e.g. `share_of_book_allowance_pct`, `stage2_share_pct`)
  ARE already in the 0–100 range. This is called out per-endpoint below.
  When in doubt: the field's own name and the worked example settle it.
  This api_contract file must call it out; it does not need to be memorised
  because every field's convention is written next to it below.
* **Errors**: malformed request bodies/params → `422` with
  `{"detail": [...]}` (FastAPI/pydantic validation errors) BEFORE any
  engine code runs. Unknown routes → `404`. One-at-a-time `/api/agent/ask`
  contention → `429`. A missing prerequisite exhibit file → `503`.
* **Static exhibits**: every PNG referenced by a `png_url` / `image_url`
  field is served read-only at `/static/exhibits/<relative-path-under-outputs/>`
  (e.g. `/static/exhibits/hazard/age_baseline.png` ==
  `outputs/hazard/age_baseline.png`). Fetch it directly with `<img src>`.

---

## 1. Engine data views (existing, unchanged by this doc — reproduced here
   because this file must cover EVERY endpoint the v2 UI consumes)

### `GET /api/health`

No params. Liveness + warm-up timing.

```json
{
  "status": "ok",
  "engine_warm": true,
  "warm_up_seconds": 4.73,
  "agent": "fallback"
}
```
`agent` is `"langgraph"` once the Day-4 router is resolved, else
`"fallback"` (deterministic keyword router, offline).

### `GET /api/ecl/summary`

No params. Headline stats + scenario table for the dashboard header
(Executive Overview tab).

```json
{
  "as_of": {"t": 60, "period": "2015Q1"},
  "n_loans": 7849,
  "balance": 1673746502.62,
  "weights": {"up": 0.25, "base": 0.5, "down": 0.25},
  "weighted_allowance": 34046377.82,
  "coverage": 0.02034141834854155,
  "allowance_at_average_path": 32886316.29,
  "jensen_ratio": 1.0352749002351027,
  "stage_mix": {
    "stage1": {"n_loans": 7803, "allowance": 27489620.86,
               "allowance_pct_of_total": 80.74169008498012},
    "stage2": {"n_loans": 3, "allowance": 486590.04,
               "allowance_pct_of_total": 1.429197669792072},
    "stage3": {"n_loans": 43, "allowance": 6070166.92,
               "allowance_pct_of_total": 17.829112245227805}
  },
  "scenarios": [
    {"name": "up", "weight": 0.25, "allowance": 27689413.56,
     "coverage": 0.01654337351589052, "zbar_13q": -0.8489346059784133,
     "uer_peak_pp": 6.388333333333333},
    {"name": "base", "weight": 0.5, "allowance": 30454080.65,
     "coverage": 0.018195157150911207, "zbar_13q": -0.8788198475771632,
     "uer_peak_pp": 6.388333333333333},
    {"name": "down", "weight": 0.25, "allowance": 47587936.42,
     "coverage": 0.02843198557645327, "zbar_13q": -1.5489269149154279,
     "uer_peak_pp": 11.2}
  ],
  "amounts_in": "USD"
}
```
`coverage` and `jensen_ratio` are ratios (not `*_pct`).
`stage_mix.*.allowance_pct_of_total` IS already 0–100.

### `GET /api/ecl/waterfall?t0=20&t1=40`

Query params `t0`, `t1` (ints, `1 <= t0 < t1 <= 60`; default `20`, `40`).
Movement decomposition between two rung-1 snapshots.

```json
{
  "tool": "decompose_waterfall",
  "t0": 20, "t1": 40,
  "period_t0": "2005Q1", "period_t1": "2010Q1",
  "opening_allowance": 24538544.76,
  "closing_allowance": 1032613371.19,
  "components": [
    {"component": "opening", "amount": 24538544.76, "n_loans": 8662, "kind": "level"},
    {"component": "stage_migration", "amount": 3879319.76, "n_loans": 498, "kind": "delta"},
    {"component": "remeasurement", "amount": 26010644.52, "n_loans": 1948, "kind": "delta"},
    {"component": "derecognitions", "amount": -21177011.65, "n_loans": 6714, "kind": "delta"},
    {"component": "new_loans", "amount": 999361873.81, "n_loans": 11915, "kind": "delta"},
    {"component": "closing", "amount": 1032613371.19, "n_loans": 13863, "kind": "level"}
  ],
  "identity_gap": 0.0,
  "amounts_in": "USD",
  "headline": "allowance waterfall t=20 (2005Q1) -> t=40 (2010Q1): opening $24.5m, stage migration +3.9m, remeasurement +26.0m, derecognitions -21.2m, new loans +999.4m, closing $1,032.6m",
  "tool_call_id": "tc-000001"
}
```
`components` where `kind == "delta"` sum exactly to
`closing_allowance - opening_allowance` (`identity_gap ~ 0`). Bad params
(inverted/out-of-range/non-int `t0`/`t1`) → `422`.

### `GET /api/exhibits/credit_cycle`

No params. The recovered credit-cycle series (Z_t) with calendar labels.

```json
{
  "rho": 0.02270852403709047,
  "n_quarters": 60,
  "points": [
    {"t": 1, "calendar": "2000Q2", "z": 1.05067609,
     "observed_dr": 0.01060071, "ttc_pd": 0.01701426, "pit_pd": 0.0082523},
    {"t": 2, "calendar": "2000Q3", "z": 1.33658745,
     "observed_dr": 0.0094518, "ttc_pd": 0.01703656, "pit_pd": 0.0073204}
  ]
}
```
(60 points total, `t=1..60`.)

### `POST /api/tools/{shock_macro|reweight_scenarios|rerun_ecl|decompose_waterfall}`

The four Tier-1 tools, pydantic-guarded (bad args → `422` before the engine
runs; nothing bad is ever logged to the audit trail). Bodies/shapes are
unchanged from Day 4 — reproduced here for completeness.

`POST /api/tools/shock_macro` body `{"var": "UER", "shock": 2.0}` (optional
`"shape": "parallel"|"peak_revert"`, default `"parallel"`):

```json
{
  "tool": "shock_macro", "var": "UER", "shock": 2.0, "shape": "parallel",
  "shock_units": "percentage points on the unemployment level",
  "applied_peak_deltas_pp": {"uer": 2.0, "hpi_growth": -0.8258713077987423,
                            "gdp_growth": -0.10903259391827495},
  "baseline_allowance": 30454080.65, "shocked_allowance": 31694012.25,
  "delta": 1239931.6, "delta_pct": 4.071479338705607,
  "baseline_coverage": 0.018195157150911207, "coverage": 0.018935969214955575,
  "stage_mix": {"stage1": {"n_loans": 7803, "allowance": 25138208.67,
                           "allowance_pct_of_total": 79.31532452794009},
               "stage2": {"n_loans": 3, "allowance": 485636.66,
                         "allowance_pct_of_total": 1.532266274180116},
               "stage3": {"n_loans": 43, "allowance": 6070166.92,
                         "allowance_pct_of_total": 19.15240919787979}},
  "waterfall_vs_baseline": [ /* same 6-row shape as /api/ecl/waterfall */ ],
  "amounts_in": "USD",
  "headline": "UER +2pp (parallel) coherent shock of the base scenario: reported allowance $30.5m -> $31.7m (delta +1.2m, +4.1%), shocked coverage 1.89%",
  "tool_call_id": "tc-000002"
}
```

`POST /api/tools/reweight_scenarios` body
`{"w_up": 0.25, "w_base": 0.5, "w_down": 0.25}` (must sum to 1 within
1e-6) → `{weights, per_scenario, weighted_allowance,
allowance_at_average_path, jensen_ratio, coverage, adopted_weights,
adopted_weighted_allowance, delta_vs_adopted_pct, amounts_in, headline,
tool_call_id}` (`delta_vs_adopted_pct` is already 0–100-scale).

`POST /api/tools/rerun_ecl` body `{"segment": "stage3"}` (one of `all`,
`stage1`, `stage2`, `stage3`, `investor`, `high_ltv`, default `all`) →
`{tool, segment, segment_definition, weights, n_loans, balance,
weighted_allowance, coverage, share_of_book_allowance_pct,
per_scenario_allowance, stage_mix, amounts_in, headline, tool_call_id}`.

`POST /api/tools/decompose_waterfall` body `{"t0": 20, "t1": 40}` → same
shape as `GET /api/ecl/waterfall`.

### `POST /api/agent/ask`

Body `{"question": "..."}` (1–2000 chars, `extra="forbid"`) →
`{"answer": str, "route": str, "mode": str, "trace": [{"node": ..., ...}, ...]}`.
`route` is one of the six tool/retriever names, `"REASONED"`, or a refusal
spelling (`"REFUSE"` from the live LangGraph router, `"refusal"` from the
offline fallback router — match either, case-insensitively). `429` if
another question is mid-flight (single-worker demo limit).

`mode` (added additively; every prior field is unchanged) is the UI's
status-indicator classification of `answer`:

| `mode` | when | UI status word (§5.5) |
|---|---|---|
| `"grounded"` | a numeric tool ran, or the cited docs retriever (`query_model_docs`) answered | `GROUNDED` |
| `"reasoned"` | the REASONED route — a cited, number-disciplined LLM interpretation grounded in retrieved passages + the engine's own baseline snapshot, but NOT a fresh engine computation | `REASONED` |
| `"refusal"` | the question was out of scope | `OUT OF SCOPE` |

Every `"reasoned"` answer's `answer` string is ALSO prefixed with the
literal marker `"[REASONED — interpretation, not engine output] "` — a
second, redundant signal (never the UI's only one; branch on `mode`,
treat the prefix as display text like any other narration) in case the
answer is ever rendered somewhere that has only the raw string.

### `GET /api/agent/stream`

No params. `text/event-stream` SSE: replays the most recent `/ask` trace,
then streams live events as `data: {...}\n\n` JSON lines, with `: keep-alive`
comments every 15s.

**Trace event shape** (same dicts as `POST /api/agent/ask`'s `trace` array;
the UI must key off `node`, not any other field): every event is a JSON
object with a `"node"` string — one of `"router"`, `"narrator"`,
`"REASONED"`, `"refusal"`, or a tool name (`"shock_macro"`,
`"reweight_scenarios"`, `"rerun_ecl"`, `"decompose_waterfall"`,
`"query_model_docs"`, `"analyze_data"`; the offline fallback router emits
the generic `"tool"`) — plus node-dependent optional fields. The ones the
UI may render:

| field | on | meaning |
|---|---|---|
| `ts` | live router events | ISO-8601 UTC timestamp |
| `route`, `args`, `model`, `detail` | `router` | chosen route + validated args |
| `status` (`"ok"`/`"error"`), `tool_call_id`, `headline`, `detail` | tool nodes | execution outcome |
| `mode`, `model`, `number_check_passed` / `citation_check_passed` | `narrator` | grounding-check outcome (a PER-EVENT diagnostic — `"llm"` / `"template_*"` — distinct from the top-level response's `mode` field above, which classifies the whole answer for the UI status indicator) |
| `mode`, `model`, `number_check_passed`, `attempts` | `"REASONED"` | same per-event diagnostic, plus `"llm_repaired"` when the one regeneration attempt fixed an ungrounded number |
| `message` / `answer` | `refusal`, fallback events | display text |
| `label`, `tool`, `answer` | fallback-router events | display text |
| `_id` | every streamed event | monotonic replay-dedup id (ignore) |

No event field is ever parsed back into a number by the UI — trace text is
display-only.

---

## 2. NEW: The Model tab

### `GET /api/model/coefficients`

Hazard-ratio families parsed from `outputs/hazard/hazard_ratios.md`, plus
fit statistics from `outputs/hazard/fit_stats.md`. No params.

```json
{
  "models": {
    "default": {
      "n_fit": 418418, "events": 11354, "mcfadden_r2": 0.0761,
      "coefficients": [
        {"variable": "Intercept", "family": "baseline", "hazard_ratio": 0.2658,
         "ci": [0.1534, 0.4608], "p": 2.35e-06, "p_display": "2.35e-06",
         "story": "Seasoning: hazard climbs over the first ~2-3 years on book, then burns out (spline coefficients are basis weights, not individually interpretable -- see age_baseline.png)."},
        {"variable": "FICO at orig. (per 100 pts)", "family": "borrower",
         "hazard_ratio": 0.6314, "ci": [0.613, 0.6505],
         "p": 1e-16, "p_display": "<1e-16",
         "story": "Borrower quality: cleaner credit at origination defaults less; investors walk away from underwater rentals faster than owner-occupiers.",
         "unit_meaning": "1 unit = 100 points of FICO score at origination (fico_s = FICO_orig_time / 100).",
         "transformation": "level, static at origination, scaled /100",
         "lag": "static (origination) -- no lag, not time-varying",
         "fred_series": null,
         "economic_channel": "Ability/willingness-to-pay channel: cleaner credit history at origination signals lower baseline default propensity, independent of the macro cycle.",
         "hazard_ratio_per_unit": 0.6314,
         "worked_example": "+100 FICO points => hazard x 0.6314 (-36.9%, a 36.9% decrease in the monthly/quarterly default hazard)."}
        /* ... 13 rows total for "default": Intercept, FICO, Updated LTV,
           Rate incentive, Investor loan, Condo, Planned urban dev.,
           Single family, Unemployment level (lag 1), Unemployment 4q
           change (lag 1), HPI growth (lag 1), GDP growth (lag 1),
           DOUBLE TRIGGER: LTV(10pp) x UER (centered) */
      ]
    },
    "prepay": {
      "n_fit": 418418, "events": 22734, "mcfadden_r2": 0.0503,
      "coefficients": [ /* same 13-row shape, prepayment-hazard values */ ]
    }
  },
  "fit_stats": {
    "default": {"n_fit": 418418, "events": 11354, "train_auc": 0.7476,
               "oot_auc": 0.6609, "mcfadden_r2": 0.0761},
    "prepay": {"n_fit": 418418, "events": 22734, "train_auc": 0.6839,
              "oot_auc": 0.5841, "mcfadden_r2": 0.0503},
    "seasoning_peak": {"fitted_q": 12, "empirical_q": 10, "tolerance_q": 8,
                       "plausible_window_q": [4, 18]},
    "net_uer_effect_note": "A 1pp labour-market shock moves the unemployment level and its 4-quarter change one-for-one, so its hazard effect at mean LTV is beta(uer_lag1) + beta(uer_chg4_lag1) = -0.3668 + +0.6135 = +0.2467 (hazard ratio 1.280 per pp) -- PD RISES in unemployment. The negative level coefficient in isolation is the level-vs-momentum decomposition under 0.94 collinearity, not an economic sign.",
    "double_trigger_note": "beta(centered ltv10 x centered uer_lag1) = -0.00597 (p = 3.75e-02, significant at 5%; identical to the uncentered x*y coefficient -- centering only reparametrises the main effects). Negative: the LTV slope flattens slightly at high unemployment -- in-sample the two triggers partially substitute (the main effects and momentum term already carry the joint stress response, and the worst-LTV loans default early in the stress window). Reported either way, per spec. Marginal LTV effect per 10pp: +0.2029 at mean UER (5.6%); +0.1766 at UER 10%."
  },
  "source_files": ["outputs/hazard/hazard_ratios.md", "outputs/hazard/fit_stats.md"]
}
```

Field notes:
* `models.{default,prepay}.coefficients[].family` is one of `baseline`,
  `borrower`, `collateral`, `macro`, `incentive` — `story` is that
  family's narrative (repeated per row for the family, so the UI never
  needs a second lookup to group-and-annotate).
* `p` is always a **float**: for a table cell like `<1e-16` it is the
  numeric bound `1e-16` (use `p_display` — the original string, e.g.
  `"<1e-16"` or `"2.35e-06"` — for display; never format `p` yourself and
  claim exactness beyond the bound).
* `ci` is `[low, high]`.
* `hazard_ratio > 1` = risk-increasing; `< 1` = risk-reducing (it is
  `exp(coef)` of a cloglog hazard).

**Requirement 12 interpretation fields** (every coefficient row, both
`default` and `prepay`, all 13 rows) — content curated/transcribed from
`outputs/variable_dictionary.md` + `outputs/hazard/hazard_ratios.md`, the
two computed numbers (`hazard_ratio_per_unit`, `worked_example`) derived
mechanically from the row's own `hazard_ratio`/coef, never hand-typed:
* `unit_meaning` (string) — what "1 unit" of this covariate actually is
  (e.g. "100 points of FICO", "10pp of updated LTV", "1pp of national
  UER level").
* `transformation` (string) — the exact source-column transform (level /
  delta / log-growth / static flag / spline / interaction).
* `lag` (string) — the lag window and, for the two documented
  current-period exceptions (`ltv10`, `prepay_incentive`), a note why.
* `fred_series` (string, always **null** on this endpoint) — the DCR
  panel's macro columns (UER, HPI, GDP) are a vendor-premerged national
  series on the panel's own ANONYMIZED quarterly clock
  (`data/panel/build_panel.py`: "macros pre-merged"), not a live FRED
  pull, so no FRED series id is claimed here. The clock's CALENDAR
  alignment to real quarters was independently verified via correlation
  against FRED UNRATE (corr 0.996) — an anchoring check, not a sourcing
  claim (see each macro row's `transformation` text for the citation).
  Genuinely FRED-sourced rows (state UER/HPI, live-pulled by
  `freddie/macro.py`) carry a real id on `GET /api/freddie/hazard` below.
* `economic_channel` (string) — the one-paragraph causal story (labour-
  income / collateral-equity / refinancing-incentive / strategic-default
  channel), including a stated MISS where the fit disagrees with the
  prior (never smoothed over).
* `hazard_ratio_per_unit` (float, **nullable**) — `exp(beta · unit_delta)`
  for the row's OWN economically-legible unit. For the two log-growth
  macro rows (`HPI growth (lag 1)` in both models) this is **NOT** the
  same number as `hazard_ratio` — the table's `hazard_ratio` is scaled to
  a full 1.0 log-unit (~100% quarterly growth, never observed);
  `hazard_ratio_per_unit` is the same coefficient re-expressed per 1%
  growth (`hazard_ratio ** 0.01`) — the classic **0.01-vs-1pp misread**
  this field exists to prevent. `null` for the DOUBLE TRIGGER interaction
  row (a per-unit read of a product term is misleading — see
  `worked_example` / `fit_stats.double_trigger_note` instead).
* `worked_example` (string) — one computed sentence, e.g.
  `"+1pp of national UER level => hazard x 0.6930 (-30.7%, a 30.7%
  decrease in the monthly/quarterly default hazard)."` For categorical
  rows (Investor loan, Condo, …) it reads "A loan that is X => hazard x
  HR (…% higher/lower than the reference)." For the Intercept it reads
  as a baseline-multiplier sentence. For the DOUBLE TRIGGER interaction
  row a single per-unit number would mislead (it is a product term), so
  the string instead points at `fit_stats.double_trigger_note` for the
  marginal-effect decomposition — always a string, never `null`, on rows
  that carry a coefficient at all (see `/api/model/variable_dictionary`
  below for the 4 rows that carry none).

### `GET /api/model/variable_dictionary`

Parsed from `outputs/variable_dictionary.md`. No params.

```json
{
  "preamble": "Data window: panel quarters t=1..60 ≙ **2000Q2–2015Q1** (calendar anchoring verified vs FRED UNRATE, corr 0.996).\nTrain = t≤40 (2000Q2–2010Q1); OOT = t=41–60 (2010Q2–2015Q1, the stress aftermath). All fits on train only.\nMacro series are US **national** (state-level upgrade = Freddie rung 3). Timing convention: every macro\n*regressor* is lagged; the two deliberate current-quarter **state variables** are flagged ⚡ below.",
  "rows": [
    {"variable": "`fico_s`", "source_transformation": "`FICO_orig_time` / 100",
     "lag_window": "static (origination)",
     "economic_rationale": "Ability/willingness to pay",
     "expected_sign": "PD ↓", "fitted_verified": "✓ negative",
     "consumed_by": "default hazard; LGD cure"},
    {"variable": "`ltv10` ⚡",
     "source_transformation": "`updated_ltv`/10 = LTV_orig × (bal_t/bal_orig) × (hpi_orig/hpi_t), winsor 300",
     "lag_window": "current-quarter state (collateral indexation, documented exception)",
     "economic_rationale": "Equity cushion / strategic-default trigger; = vendor `LTV_time` to 5e-9",
     "expected_sign": "PD ↑, severity ↑, cure ↓",
     "fitted_verified": "✓ all three (sev +0.107/10pp, cure −0.764)",
     "consumed_by": "default hazard; LGD both stages; staging legs",
     "unit_meaning": "1 unit = 10 percentage points of updated LTV (ltv10 = updated_ltv / 10; updated_ltv winsorised at 300%).",
     "transformation": "updated_ltv = LTV_orig x (balance_t/balance_orig) x (hpi_orig/hpi_t) -- a documented CURRENT-period exception to the lag convention, because collateral value is a real-time state, not a forecast.",
     "lag": "current period (documented exception, flagged with a lightning-bolt in the variable dictionary)",
     "fred_series": null,
     "economic_channel": "Collateral / negative-equity channel: as updated LTV rises the borrower's equity cushion shrinks, removing both the option to sell out of trouble and (past 100% LTV) adding a strategic-default incentive.",
     "hazard_ratio_per_unit": 1.225,
     "worked_example": "+10pp of updated LTV => hazard x 1.2250 (+22.5%, a 22.5% increase in the monthly/quarterly default hazard)."}
    /* ... 13 rows total, in file order: fico_s, ltv10, loan_age,
       prepay_incentive, investor/RE-type flags, uer_lag1, uer_chg4_lag1,
       hpi_growth_lag1, gdp_lag1/gdp_growth_lag2, dt_ltv_uer,
       lgd_time (target), Z_t (recovered), Scenario paths */
  ],
  "notes": "Model equations live in the module docstrings (cloglog hazard; two-stage LGD; ECL sum; Vasicek PIT\ntransform with the Gauss-Hermite anchor proof; satellite Z = −1.694 + 13.642·hpi_growth_lag1 +\n0.730·gdp_growth_lag2, n=57, with ADF/KPSS/DW/AIC and the GFC-dummy sensitivity in\noutputs/satellite/satellite_report.md). Coefficient tables with CIs: outputs/hazard/hazard_ratios.md,\noutputs/lgd/lgd_report.md."
}
```
`rows[].*` original keys (`variable`, `source_transformation`,
`lag_window`, `economic_rationale`, `expected_sign`, `fitted_verified`,
`consumed_by`) are all strings (raw source cells, including the ✓/⚡/↑/↓
glyphs and backtick-quoted variable names — the UI renders them as-is,
markdown-lite).

**Requirement 12 interpretation fields**, joined onto every row (same
`unit_meaning` / `transformation` / `lag` / `fred_series` / `economic_channel`
/ `hazard_ratio_per_unit` / `worked_example` shape as `/api/model/coefficients`
above, described there field-by-field — including `fred_series` always
being **null** here too, for the same reason: every row on this endpoint
is a DCR/national concept, never a live FRED pull): the hazard-ratio-bearing
fields are **reused from the DCR default-hazard table**, never re-derived,
so the two exhibits cannot silently disagree. Four rows have **no** hazard
ratio at all and get `hazard_ratio_per_unit: null, worked_example: null`
(still carry `unit_meaning`/`transformation`/`economic_channel`):
`loan_age` (spline basis, not individually interpretable),
`` `lgd_time` (target) `` (an LGD target, not a hazard regressor),
`` `Z_t` (recovered) `` (the satellite's dependent variable, not a
regressor), and `Scenario paths` (a set of forward paths, not one
coefficient). A fifth row, `` `dt_ltv_uer` ``, DOES carry a hazard ratio
but still gets `hazard_ratio_per_unit: null` — it is the same DOUBLE
TRIGGER interaction term as `/api/model/coefficients` above, and a
per-unit read of a product term would mislead the same way there;
`worked_example` stays a non-null string pointing at
`fit_stats.double_trigger_note`.

### `GET /api/model/macro_glossary`

**NEW (Requirement 12).** Every macro series used anywhere in the app —
DCR (national), SFLLD (state, Freddie rung 3), and the satellite Z
regression — one entry per (series, model) pairing where the
transformation or lag genuinely differs. Curated from
`outputs/variable_dictionary.md`, `outputs/hazard/hazard_ratios.md`,
`outputs/freddie/hazard/hazard_report.md`,
`outputs/satellite/satellite_report.md` and `freddie/macro.py`'s
docstrings. No params.

```json
{
  "series": [
    {"id": "dcr_uer_level", "label": "National UER -- level",
     "fred_series": null, "geography": "US national",
     "frequency": "monthly (matched to the panel's quarterly clock)",
     "transformation": "level (pp)", "lag": "1 quarter",
     "lag_rationale": "Publication-lag realism + the model's own timing convention: only past values (t-k, k>=1) are ever referenced, so scoring never looks ahead. NOT a live FRED pull -- vendor-premerged on the DCR panel's anonymized clock; only the clock's calendar alignment was verified against FRED UNRATE (corr 0.996).",
     "which_models": ["DCR default hazard"]},
    "... 9 more rows: dcr_uer_momentum, dcr_hpi_growth, dcr_gdp_growth,",
    "sflld_uer_level, sflld_uer_momentum, sflld_hpi_growth,",
    "satellite_hpi_growth, scenario_paths, coherent_shock_convention",
    "(10 rows total) ..."
  ],
  "source_files": ["outputs/variable_dictionary.md", "outputs/hazard/hazard_ratios.md",
                   "outputs/freddie/hazard/hazard_report.md", "outputs/satellite/satellite_report.md",
                   "freddie/macro.py"]
}
```
Field notes:
* `id` (string) — stable row key, e.g. `dcr_uer_level`, `sflld_hpi_growth`.
* `fred_series` (string, **nullable**) — the FRED series ID, populated
  ONLY for the two SFLLD/state rows that are genuinely live-pulled from
  FRED by `freddie/macro.py`: `{POSTAL}UR`, `{POSTAL}STHPI` (a literal
  `{POSTAL}` template, not a specific state — FRED mints one series per
  state postal code). `null` for every `dcr_*` and `satellite_hpi_growth`
  row (the DCR panel's macro columns are a vendor-premerged national
  series on an ANONYMIZED clock, not a live FRED pull — only the clock's
  calendar alignment was checked against FRED UNRATE, see each row's
  `lag_rationale`) and for the two non-series rows: `scenario_paths`
  (a DFAST supervisory-scenario CSV pull, not a FRED series) and
  `coherent_shock_convention` (a modelling-convention note, not a series
  at all).
* `which_models` (array of strings) — every consumer, e.g.
  `["DCR default hazard", "DCR prepayment hazard"]`,
  `["DCR default hazard", "satellite (Z regression)"]` (GDP growth is the
  one series consumed at two different lags by two different models —
  `lag`/`lag_rationale` state both).
* `coherent_shock_convention` is the one entry with no series-level
  facts (`fred_series`/`geography`/`frequency`/`lag` are all `n/a` or
  `null`): it documents that the satellite is
  `Z = f(hpi_growth_lag1, gdp_growth_lag2)` with **no unemployment
  term** (sign-governance excluded it — every spec pairing duer with
  gdp_growth fit a wrong-signed, collinearity-driven duer coefficient),
  so `shock_macro` projects any univariate agent shock onto the DFAST
  severe-minus-base direction to still reach Z. Matches
  `wiki/pages/agent-layer.md`'s "THE COHERENT-SHOCK CONVENTION" note —
  reported here for the UI, not duplicated logic.

### `GET /api/model/lgd`

Key numbers + exhibit paths parsed from `outputs/lgd/lgd_report.md`. No
params.

```json
{
  "cure_rate": 0.122,
  "cure_auc": {"train": 0.837, "oot": 0.769},
  "excess_loss_loading": 0.0255,
  "oot_calibration": {
    "mean_realised_lgd": {"train": 0.5995, "oot": 0.6113},
    "mean_predicted_lgd": {"train": 0.599, "oot": 0.6583},
    "gap_pred_minus_real": {"train": -0.0005, "oot": 0.0471},
    "cure_rate_realised": {"train": 0.1224, "oot": 0.0716},
    "cure_rate_predicted": {"train": 0.1224, "oot": 0.0499},
    "mean_sev_noncure_realised": {"train": 0.6825, "oot": 0.6581},
    "mean_sev_noncure_predicted": {"train": 0.6825, "oot": 0.6926},
    "decile_mae_lgd": {"train": 0.0203, "oot": 0.0571}
  },
  "cure_stage_coefficients": [
    {"variable": "Intercept", "coef": 4.4489, "se": 0.3402, "z": 13.0783,
     "p": 0.0, "odds_ratio": 85.5337},
    {"variable": "ltv10", "coef": -0.764, "se": 0.0252, "z": -30.2588,
     "p": 0.0, "odds_ratio": 0.4658},
    {"variable": "uer_lag1", "coef": 0.2774, "se": 0.0334, "z": 8.3086,
     "p": 0.0, "odds_ratio": 1.3197},
    {"variable": "fico_s", "coef": -0.1402, "se": 0.0555, "z": -2.528,
     "p": 0.0115, "odds_ratio": 0.8692},
    {"variable": "loan_age", "coef": -0.0727, "se": 0.0064, "z": -11.4393,
     "p": 0.0, "odds_ratio": 0.9299}
  ],
  "severity_stage_coefficients": [
    {"variable": "Intercept", "coef": 1.4274, "se_hc1": 0.1347, "z": 10.601, "p": 0.0},
    {"variable": "ltv10", "coef": 0.1074, "se_hc1": 0.0082, "z": 13.1763, "p": 0.0},
    {"variable": "uer_lag1", "coef": -0.0416, "se_hc1": 0.0104, "z": -4.0031, "p": 0.0001},
    {"variable": "fico_s", "coef": -0.2532, "se_hc1": 0.0202, "z": -12.5228, "p": 0.0},
    {"variable": "loan_age", "coef": 0.0093, "se_hc1": 0.0036, "z": 2.5417, "p": 0.011}
  ],
  "exhibits": [
    {"id": "lgd_calibration_ltv", "png_url": "/static/exhibits/lgd/calibration_ltv.png"},
    {"id": "lgd_cure_by_ltv", "png_url": "/static/exhibits/lgd/cure_by_ltv.png"},
    {"id": "lgd_distribution", "png_url": "/static/exhibits/lgd/lgd_distribution.png"}
  ]
}
```
`cure_rate` is a ratio (0.122 = 12.2%). `p` here is the raw table value
(already rounded to 4dp in the source; `0.0` means "< 0.00005", not
literally zero).

---

## 3. NEW: The Policy tab

### `GET /api/policy/staging_sensitivity`

The SICR ratio-threshold vs Stage-2-share governance curve, parsed from
`outputs/staging/staging_report.md`. No params.

```json
{
  "add_on_pp": 0.5,
  "thresholds": ["1.5x", "2.0x", "3.0x", "4.0x"],
  "rows": [
    {"t": 20, "period": "2005Q1",
     "stage2_share_pct": {"1.5x": 0.0, "2.0x": 0.0, "3.0x": 0.0, "4.0x": 0.0}},
    {"t": 40, "period": "2010Q1",
     "stage2_share_pct": {"1.5x": 85.1, "2.0x": 75.76, "3.0x": 30.25, "4.0x": 3.32}}
  ],
  "reading": "in the calm quarter the relative test stages (almost) nobody at any threshold -- deterioration since origination simply has not happened -- while in the stress quarter the doubling convention (2x) moves roughly three quarters of the live book to lifetime ECL, and the choice between 2x and 4x swings the Stage-2 population by tens of percentage points of the book. The threshold is the single loudest governance dial in the impairment estimate (notes section 2.2 pitfall).",
  "image_url": "/static/exhibits/staging/stage2_sensitivity.png"
}
```
`stage2_share_pct` values are already 0–100 (percent, not a ratio). The
governance decision this exhibit informs (pairs "exhibit ↔ decision", per
the Policy tab's design mandate): **which multiple of origination PD
triggers Stage 2** — the 2.0x adopted convention vs alternatives shown.

### `GET /api/policy/weights_table`

Scenario table + the weighted allowance under 3 canned scenario-weight
sets, computed by calling the real `reweight_scenarios` tool (reused, not
re-derived). No params.

**GOVERNANCE NOTE**: every call to this endpoint appends **three** lines
to `outputs/agent_log/tool_calls.jsonl` (one per canned weight set) — this
is deliberate: the audit trail records every reweighting the app has ever
shown a user, including from this Policy tab convenience table, not only
from Copilot chat.

```json
{
  "amounts_in": "USD",
  "scenario_totals": [
    {"name": "up", "allowance": 27689413.56, "coverage": 0.01654337351589052},
    {"name": "base", "allowance": 30454080.65, "coverage": 0.018195157150911207},
    {"name": "down", "allowance": 47587936.42, "coverage": 0.02843198557645327}
  ],
  "weight_sets": [
    {"id": "adopted", "label": "Adopted (25/50/25)",
     "weights": {"up": 0.25, "base": 0.5, "down": 0.25},
     "weighted_allowance": 34046377.82, "coverage": 0.02034141834854155,
     "jensen_ratio": 1.0352749002351027, "delta_vs_adopted_pct": 0.0},
    {"id": "equal_thirds", "label": "Equal-thirds (33/33/33)",
     "weights": {"up": 0.3333333333333333, "base": 0.3333333333333333, "down": 0.3333333333333333},
     "weighted_allowance": 35243810.21, "coverage": 0.021056838747751664,
     "jensen_ratio": 1.0436799985368514, "delta_vs_adopted_pct": 3.5170625123169375},
    {"id": "downside_tilt", "label": "Downside-tilted (15/35/50)",
     "weights": {"up": 0.15, "base": 0.35, "down": 0.5},
     "weighted_allowance": 38606308.47, "coverage": 0.023065803818429133,
     "jensen_ratio": 1.042572998763202, "delta_vs_adopted_pct": 13.393291574886245}
  ]
}
```
`weight_sets[].id` is a stable identifier for the UI (`"adopted"` is the
book's actual reported basis; the other two are illustrative policy
alternatives). `delta_vs_adopted_pct` is already 0–100-scale (percent
deviation of that set's weighted allowance from the adopted basis).

### `GET /api/exhibits/list`

id → `{title, png_url, caption}` for all 17 servable exhibit PNGs
(the consultant-curated subset used across The Model / Policy tabs — not
every PNG under `outputs/`). No params.

```json
{
  "exhibits": [
    {"id": "hazard_age_baseline", "title": "Seasoning (age) baseline hazard",
     "png_url": "/static/exhibits/hazard/age_baseline.png",
     "caption": "Fitted natural-cubic-spline age baseline of the default hazard."},
    {"id": "hazard_pd_term_structure", "title": "PD term structure",
     "png_url": "/static/exhibits/hazard/pd_term_structure.png",
     "caption": "Lifetime PD term structure implied by the fitted hazards."},
    {"id": "lgd_calibration_ltv", "title": "LGD calibration by updated LTV",
     "png_url": "/static/exhibits/lgd/calibration_ltv.png",
     "caption": "Realised vs predicted LGD by updated-LTV decile, train vs OOT."},
    {"id": "lgd_cure_by_ltv", "title": "Cure rate by updated LTV",
     "png_url": "/static/exhibits/lgd/cure_by_ltv.png",
     "caption": "Realised vs predicted cure rate by updated-LTV decile."},
    {"id": "lgd_distribution", "title": "Realised LGD distribution",
     "png_url": "/static/exhibits/lgd/lgd_distribution.png",
     "caption": "Bimodal shape of realised workout LGD motivating the two-stage model."},
    {"id": "staging_stage2_sensitivity", "title": "Stage-2 share vs SICR threshold",
     "png_url": "/static/exhibits/staging/stage2_sensitivity.png",
     "caption": "Stage-2 share of the book at t=20 and t=40 across SICR ratio thresholds."},
    {"id": "staging_stage_distribution", "title": "Stage distribution over time",
     "png_url": "/static/exhibits/staging/stage_distribution.png",
     "caption": "Stage 1/2/3 population shares at each reporting snapshot."},
    {"id": "scenario_jensen_gap", "title": "Jensen gap",
     "png_url": "/static/exhibits/scenario_ecl/jensen_gap.png",
     "caption": "Weighted-scenario allowance vs allowance at the weighted-average macro path."},
    {"id": "scenario_ecl_bars", "title": "Scenario ECL comparison",
     "png_url": "/static/exhibits/scenario_ecl/scenario_ecl_bars.png",
     "caption": "Reported allowance under the up / base / down scenarios."},
    {"id": "scenario_z_paths", "title": "Scenario Z paths",
     "png_url": "/static/exhibits/scenario_ecl/z_paths.png",
     "caption": "Recovered credit-cycle factor Z under each scenario's macro path."},
    {"id": "vasicek_credit_cycle", "title": "Credit cycle (PIT vs TTC)",
     "png_url": "/static/exhibits/vasicek/credit_cycle.png",
     "caption": "Recovered systematic factor Z_t and the PIT-vs-TTC PD gap through the cycle."},
    {"id": "eda_default_rate_vs_macro", "title": "Default rate vs macro",
     "png_url": "/static/exhibits/eda/default_rate_vs_macro.png",
     "caption": "Quarterly default rate against the macro series (EDA)."},
    {"id": "eda_hazard_by_loan_age", "title": "Hazard by loan age",
     "png_url": "/static/exhibits/eda/hazard_by_loan_age.png",
     "caption": "Empirical default hazard by loan age (EDA)."},
    {"id": "eda_lgd_realised_bimodal", "title": "Realised LGD (EDA)",
     "png_url": "/static/exhibits/eda/lgd_realised_bimodal.png",
     "caption": "Raw bimodal realised-LGD histogram, before modelling."},
    {"id": "eda_origination_quality", "title": "Origination quality over vintages",
     "png_url": "/static/exhibits/eda/origination_quality.png",
     "caption": "FICO / LTV origination quality drift across vintages."},
    {"id": "eda_prepay_vs_rate_incentive", "title": "Prepayment vs rate incentive",
     "png_url": "/static/exhibits/eda/prepay_vs_rate_incentive.png",
     "caption": "Empirical prepayment rate against the note-vs-market rate incentive."},
    {"id": "eda_vintage_cumulative_default", "title": "Cumulative default by vintage",
     "png_url": "/static/exhibits/eda/vintage_cumulative_default.png",
     "caption": "Cumulative default curves by origination vintage."}
  ]
}
```

---

## 4. NEW: The 'Real Data' tab (Freddie Mac SFLLD Phase A/B)

`freddie/` (read-only, FROZEN like the engine) built a second, REAL-data
pipeline alongside the DCR-synthetic engine above — a champion hazard/LGD
refit on the real Freddie Mac Single-Family Loan-Level Dataset (SFLLD, 17
vintages), an ALFRED-vintage backtest, and an LSTM path-dependence
challenger. The four endpoints below parse `outputs/freddie/**`'s
already-written reports/CSVs/JSON into JSON on every request — no engine
state is touched and every number is read off those artifacts VERBATIM,
never recomputed. Every PNG referenced by a `png_url` below is served at
`/static/freddie/<relative-path-under-outputs/freddie/>` (a second, more
convenient mount over the same files `/static/exhibits/freddie/*` already
serves via the whole-`outputs/` mount above).

### `GET /api/freddie/summary`

Panel scale + the headline numbers for the tab's hero panel. No params.

```json
{
  "panel": {
    "n_loans": 837500,
    "n_loan_months": 39522565,
    "n_vintages": 17,
    "overall_d90_rate_pct": 5.32,
    "overall_prepay_rate_pct": 58.93,
    "vintages": [
      {"vintage": "2005", "n_loans": 50000, "n_loan_months": 3588153,
       "d90_rate_pct": 10.75, "prepay_rate_pct": 87.21,
       "other_terminal_rate_pct": 0.15, "censored_rate_pct": 1.89,
       "perf_window_end": "2025-09"},
      "... 15 more rows (one per vintage: 2005-2010, 2014-2016, 2018-2025 —",
      "2011-2013/2017 are a documented coverage gap, never downloaded) ...",
      {"vintage": "2025", "n_loans": 37500, "n_loan_months": 153366,
       "d90_rate_pct": 0.04, "prepay_rate_pct": 1.79,
       "other_terminal_rate_pct": 0.03, "censored_rate_pct": 98.14,
       "perf_window_end": "2025-09"}
    ]
  },
  "hazard": {
    "train_auc": 0.8535911902958723, "oot_auc": 0.6847251436480823,
    "train_n": 17703723, "train_events": 26284,
    "oot_n": 21818842, "oot_events": 18309,
    "mcfadden_r2": 0.11966452683311235,
    "dcr_train_auc": 0.7476, "dcr_oot_auc": 0.6609
  },
  "covid": {
    "verdict": "exclude",
    "window": "2020-04..2021-09",
    "naive_oot2_auc": 0.7553126379930407,
    "additive_oot2_auc": 0.7546806708472524,
    "exclude_oot2_auc": 0.7509195241784803,
    "recommendation": "prefer **exclude** for any structural or scenario-conditional use -- it is the only treatment that preserves economically-signed macro coefficients, ... (full paragraph, verbatim from hazard_report.md section 3)"
  },
  "lgd": {
    "mean_realized_lgd_train": 0.2715010941028595,
    "mean_realized_lgd_oot": 0.0073627401143312,
    "cure_auc_train": 0.6991, "cure_auc_oot": 0.4769,
    "excess_loading_sflld": 0.0148, "excess_loading_dcr": 0.0255
  },
  "backtest_headline": {
    "worst_asof": "2007-12", "worst_miss_ratio_frozen": 9.423568161519073,
    "worst_miss_ratio_actual": 1.8965807743337444,
    "saturation_asof": "2019-12", "saturation_miss_ratio_actual": 0.06433186245201551
  },
  "lstm": {
    "oot_champion_auc": 0.6847251436480823, "oot_lstm_auc": 0.9924998553122111,
    "prior_dlq_champion_auc": 0.5698246326781929, "prior_dlq_lstm_auc": 0.9570336218094414,
    "clean_champion_auc": 0.5385541163579888, "clean_lstm_auc": 0.5287356531754855
  },
  "gate_verdict": "PASS",
  "source_files": ["outputs/freddie/gate_phaseA.md", "... 8 more"]
}
```
Notes: `hazard.dcr_*_auc` is the DCR-synthetic champion's own AUC (reused
from `outputs/hazard/fit_stats.md` via the existing `/api/model/coefficients`
parser — never re-derived), for the DCR-vs-SFLLD comparison stat tiles.
`*_pct` fields are already 0–100 scale. `covid.verdict` is always
`"exclude"` (the reviewed recommendation — the additive-dummy variant was
overturned on review: it fits POSITIVE but fails to repair the
sign-flipped structural macro terms). `lgd.mean_realized_lgd_oot` is
COVID-cure-dominated, not a like-for-like regime comparison (see
`/api/freddie/summary`'s `lgd` source report). `backtest_headline.worst_*`
is the row with the largest `miss_ratio_frozen` across all 5 reporting
dates (currently 2007-12, the GFC); `saturation_*` is the row with the
smallest `miss_ratio_actual` (currently 2019-12, the hindsight-macro
saturation). `gate_verdict` is the Phase B gate's own PASS/FAIL line.

### `GET /api/freddie/hazard`

Coefficients + the DCR sign comparison + AUCs + the COVID regime verdict —
the same `covid` object as `/api/freddie/summary`, plus the full
coefficient tables. No params.

```json
{
  "coefficients": [
    {"term": "Intercept", "coef": -3.604265652756619, "std_err": 0.0659238765215353,
     "z": -54.67314488976103, "p_value": 0.0,
     "ci_low": -3.733474076460094, "ci_high": -3.475057229053144,
     "hazard_ratio": 0.0272074171706316,
     "unit_meaning": "reference-row hazard multiplier: owner-occupied / purchase-money / retail-channel / loan-age-spline reference, all continuous covariates at 0 on their raw scale.",
     "transformation": "model constant", "lag": "n/a", "fred_series": null,
     "economic_channel": "Not an economic channel -- the baseline hazard level the other coefficients multiply.",
     "hazard_ratio_per_unit": 0.027207,
     "worked_example": "Reference/mean-covariate baseline hazard multiplier: x0.0272 -- not a marginal per-unit effect."},
    {"term": "uer_lag1", "coef": 0.09496308546677008, "std_err": 0.003081229955925172,
     "z": 30.81986311477892, "p_value": 1.42e-208,
     "ci_low": 0.0889239857250708, "ci_high": 0.10100218520846936,
     "hazard_ratio": 1.0996182624819877,
     "unit_meaning": "1 unit = 1 percentage point of the property state's own unemployment rate LEVEL, lagged 1 month.",
     "transformation": "level (pp), state-level, lagged 1 month", "lag": "1 month",
     "fred_series": "{POSTAL}UR",
     "economic_channel": "Cash-flow / labour-income channel, same mechanism as the DCR national UER level -- state resolution replaces the national anchor with the borrower's own local labour market.",
     "hazard_ratio_per_unit": 1.099618,
     "worked_example": "+1pp of state UER level => hazard x 1.0996 (+10.0%, a 10.0% increase in the monthly/quarterly default hazard)."},
    "... 17 more rows (19 total: intercept, occupancy/purpose/channel",
    "categoricals, the 5-knot loan-age spline, fico_s, dti_s, ltv10,",
    "uer_lag1, delta_uer_lag1, hpi_growth_lag1) ..."
  ],
  "dcr_sign_comparison": [
    {"variable": "fico_s", "dcr_variable": "fico_s", "dcr_expected_sign": "-"},
    {"variable": "dti_s", "dcr_variable": null, "dcr_expected_sign": "n/a (DCR has no DTI field at this rung)"},
    {"variable": "ltv10", "dcr_variable": "ltv10", "dcr_expected_sign": "+"},
    {"variable": "uer_lag1", "dcr_variable": "uer_lag1", "dcr_expected_sign": "+ (net, level+momentum -- see DCR variable dictionary)"},
    {"variable": "delta_uer_lag1", "dcr_variable": "uer_chg4_lag1", "dcr_expected_sign": "+"},
    {"variable": "hpi_growth_lag1", "dcr_variable": "hpi_growth_lag1", "dcr_expected_sign": "-"},
    {"variable": "cr(loan_age, df=5)", "dcr_variable": "cr(loan_age, df=5)", "dcr_expected_sign": "hump (DCR peak ~12 QUARTERS ~= 36 months)"}
  ],
  "metrics": { "...": "identical shape to /api/freddie/summary's hazard object" },
  "covid": { "...": "identical shape to /api/freddie/summary's covid object" },
  "source_files": ["outputs/freddie/hazard/coefficients.csv", "... 5 more"]
}
```
`dcr_variable` is `null` when the SFLLD term has no DCR counterpart (only
`dti_s` today — the DCR engine has no DTI field at this rung).
`dcr_sign_comparison` covers the 7 continuous/structural terms only (not
the categorical occupancy/purpose/channel dummies, which have no DCR
counterpart at all).

**Requirement 12 interpretation fields**, joined onto every one of the 19
`coefficients[]` rows — same shape/semantics as `/api/model/coefficients`
(`unit_meaning`, `transformation`, `lag`, `fred_series`, `economic_channel`,
`hazard_ratio_per_unit`, `worked_example`), curated from
`outputs/freddie/hazard/hazard_report.md`'s per-variable rationale table.
Two differences from the DCR endpoint, both because this endpoint carries
the raw fitted `coef` (DCR's markdown table only ever publishes `HR =
exp(coef)`):
* `hazard_ratio_per_unit` for the two log-growth macro rows
  (`hpi_growth_lag1`) is computed as `exp(coef * 0.01)` from the **raw**
  `coef` column, not derived from `hazard_ratio` — the tightest possible
  "computed mechanically, never invented" reading, and exactly what
  `tests/test_contract.py` recomputes and asserts against.
* The 8 categorical dummy rows (occupancy/purpose/channel) and the 5
  loan-age spline rows get the SAME `unit_kind` treatment as their DCR
  categorical/spline counterparts, including 3 explicitly STATED misses
  vs the DCR sign prior (`occupancy_status[T.S]`, `loan_purpose[T.N]`,
  `channel[T.C]` — see `economic_channel` on those three rows, verbatim
  from `hazard_report.md`'s "Fitted signs vs the priors" paragraph).

### `GET /api/freddie/backtest`

The ALFRED-vintage backtest: per-reporting-date predicted-vs-realized D90
+ miss ratios (the honesty exhibit), plus 3 verbatim narrative notes. No
params.

```json
{
  "rows": [
    {"asof": "2007-12", "fit_n": 86188, "fit_events": 610, "n_active_loans": 124235,
     "realized_cum_d90": 0.08749547229041735, "predicted_cum_d90_frozen": 0.009284749766834936,
     "miss_ratio_frozen": 9.423568161519073, "predicted_cum_d90_actual": 0.046133269657947416,
     "miss_ratio_actual": 1.8965807743337444},
    {"asof": "2009-12", "fit_n": 264774, "fit_events": 6843, "n_active_loans": 165978,
     "realized_cum_d90": 0.06568942871946884, "predicted_cum_d90_frozen": 0.05553775223045237,
     "miss_ratio_frozen": 1.182788753259087, "predicted_cum_d90_actual": 0.04657626110967737,
     "miss_ratio_actual": 1.4103628576966267},
    {"asof": "2015-12", "fit_n": 713027, "fit_events": 23732, "n_active_loans": 121861,
     "realized_cum_d90": 0.013974938659620387, "predicted_cum_d90_frozen": 0.01856748237465763,
     "miss_ratio_frozen": 0.752656627195429, "predicted_cum_d90_actual": 0.018546140130412742,
     "miss_ratio_actual": 0.753522757908191},
    {"asof": "2019-12", "fit_n": 1067328, "fit_events": 26491, "n_active_loans": 193308,
     "realized_cum_d90": 0.04600947710389637, "predicted_cum_d90_frozen": 0.009198148398939846,
     "miss_ratio_frozen": 5.00203683484812, "predicted_cum_d90_actual": 0.7151895709255173,
     "miss_ratio_actual": 0.06433186245201551},
    {"asof": "2021-12", "fit_n": 1298615, "fit_events": 35707, "n_active_loans": 173838,
     "realized_cum_d90": 0.011608509071664424, "predicted_cum_d90_frozen": 0.01733963868732328,
     "miss_ratio_frozen": 0.6694781408652541, "predicted_cum_d90_actual": 0.012290078358215651,
     "miss_ratio_actual": 0.944543129288056}
  ],
  "central_honesty_note": "miss ratio (frozen) = 9.42x (realized 8.750% vs predicted 0.928%) -- **UNDERPREDICTS the GFC, as expected**: a model fit on pre-2008 data with macro frozen at 2007-12 levels cannot see the crisis coming; this is the exhibit's central honesty result, not a defect.",
  "overlay_narrative": "The DCR champion (`engine/hazard.py`) is a point-in-time (PIT) hazard; IFRS-9 compliance requires pairing it with a forward-looking scenario overlay ... (full paragraph, verbatim from backtest_report.md section 1)",
  "covid_panel_note": "The 2019-12 model (fit on pre-COVID data, macro frozen at 2019-12 levels or even the hindsight-actual path) projects forward straight through the 2020-04..2021-09 forbearance window it never saw ... (full paragraph, verbatim from backtest_report.md section 3)",
  "source_files": ["outputs/freddie/backtest/all_metrics.json", "outputs/freddie/backtest/backtest_report.md"]
}
```
Exactly 5 rows (the 5 pseudo-reporting dates: 2007-12, 2009-12, 2015-12,
2019-12, 2021-12), always in that order. `realized_cum_d90` /
`predicted_cum_d90_*` are ratios (e.g. `0.0875` = 8.75%), not `*_pct`
fields. `miss_ratio_*` is `realized / predicted` (>1 = the model
underpredicted; <1 = overpredicted) — **2007-12's `miss_ratio_frozen`
9.42× is the centerpiece finding**: a pre-crisis model with macro frozen
at 2007-12 levels cannot see the GFC coming.

### `GET /api/freddie/exhibits`

id → `{title, png_url, caption, source}` for the 13 curated Freddie SFLLD
exhibit PNGs (vintage curves, roll-rate/COVID anomaly, state heterogeneity,
severity cycle, hazard calibration/seasoning/COVID-regime, the backtest
honesty panels, and the LSTM calibration/lift charts). No params.

```json
{
  "exhibits": [
    {"id": "freddie_vintage_curves", "title": "Vintage curves -- cumulative D90 by months on book",
     "png_url": "/static/freddie/eda/exhibit1_vintage_curves.png",
     "caption": "2007 vintage reaches 16.26% cumulative D90 by month 225 vs 14.11% (2006) and 9.14% (2008) -- the pre-crisis-vintage hump; every 2018-2025 modern vintage tops out below 5.48%.",
     "source": "outputs/freddie/eda/eda_report.md#Exhibit 1"},
    {"id": "freddie_backtest_200712", "title": "Backtest honesty panel -- 2007-12 GFC miss",
     "png_url": "/static/freddie/backtest/predicted_vs_realized_200712.png",
     "caption": "A model refit through 2007-12 with macro frozen at then-current levels predicts 0.928% 36-month D90 vs a realized 8.750% -- a 9.42x underprediction of the GFC it could not see coming.",
     "source": "outputs/freddie/backtest/backtest_report.md#2"},
    "... 11 more (see app/api/main.py FREDDIE_EXHIBITS for the full curated list) ..."
  ]
}
```
`source` (unique to this endpoint vs `/api/exhibits/list`'s `caption`-only
shape) names the report/section the caption's numbers were read from.

---

## 5. NEW: Copilot / Scenario Lab auto-interpretation

### `POST /api/agent/interpret`

Body: `{"tool": "<one of the 5 route names>", "result": {<the exact JSON
that tool/route returned>}}`.

`tool` must be one of `"shock_macro"`, `"reweight_scenarios"`,
`"rerun_ecl"`, `"decompose_waterfall"`, `"query_model_docs"` (`422` if
not). `result` must be the tool's own returned JSON verbatim — for the
four Tier-1 tools it must at minimum contain `headline` and
`tool_call_id`; for `query_model_docs` it must contain `passages` (a
`422` with a `"missing required field(s)"` detail is returned otherwise,
BEFORE any LLM call).

Request example (after a Scenario Lab run of `rerun_ecl`):

```json
{
  "tool": "rerun_ecl",
  "result": {
    "tool": "rerun_ecl", "segment": "all",
    "weighted_allowance": 34046377.82,
    "headline": "segment 'all' (entire non-payoff book at the t=60 reporting date): 7,849 loans, balance $1,673.7m, scenario-weighted allowance $34.0m (100.0% of the book allowance), coverage 2.03%",
    "tool_call_id": "tc-000123"
  }
}
```

Response:

```json
{
  "interpretation": "The book carries a scenario-weighted allowance of $34.0m against $1,673.7m of balance (2.03% coverage), computed across all 7,849 loans on the book. [engine-computed; audit ref tc-000123]",
  "grounded": false,
  "mode": "template_number_check_failed"
}
```

* `interpretation` (string): the narration to show under the Scenario Lab
  result card. Non-empty, always safe to render as plain text.
* `grounded` (bool): `true` iff the LLM's own prose passed the mechanical
  verbatim-number/citation check (agent/graph.py's `narration_numbers_ok`
  / `docs_answer_ok`, reused, not duplicated) and is being shown as-is.
  `false` means the LLM's narration either errored or invented a number
  outside the tool result, and `interpretation` therefore fell back to
  the engine's own deterministic text (the tool's `headline` for
  Tier-1 tools, or a cited passage listing for `query_model_docs`) — this
  is a normal, expected outcome under the project's anti-hallucination
  governance, not a bug the UI should surface as an error. A small "AI
  interpretation" vs "engine summary" badge is the recommended UI
  treatment of `grounded`.
* `mode` (string, informational/debug only — do not branch UI logic on
  its exact value beyond the `grounded` bool): `"llm"` on success, else
  one of `"template_number_check_failed"`,
  `"template_citation_check_failed"`, or `"template_llm_error:<ExceptionType>"`.

For `query_model_docs`, `result` must look like the Tier-3 tool's own
output shape:
`{"tool": "query_model_docs", "question": "...", "passages": [{"source":
"wiki"|"notes", "citation": "...", "text": "..."}], "reading_list": [...],
"headline": "...", "tool_call_id": "tc-..."}`.

---

## 6. NEW: UI v3 AI-explain question-prefix conventions

Both conventions below are **UI-side wire-text conventions layered on top of
the existing `POST /api/agent/ask`** (§1) — they add ZERO new endpoints and
change no response shape. `POST /api/agent/ask` already accepts any
1–2000 char free-text `question`; these are simply two disciplined ways the
v3 UI composes that string so an "explain" click gets the exact same
tools/Tier-2/Tier-3/refusal governance as a typed question (FINAL_SPEC.md
§7.5, design-judge grafts 4). The router sees ordinary text — a bracketed
tag, a colon, and a trailing question — and is free to route it to any of
the five paths, including `REFUSE`, exactly as it would any other message.

### 6.1 Panel/tile explain prefix

Every panel/tile heading in the UI carries a small AI-explain icon
(`app/ui/src/components/ExplainButton.jsx`). Clicking it composes:

```
[explain:<panel_id> <live params>] <Exhibit label> — <panel title>: <CODE-GENERATED
recap of the exact figures the panel is showing right now> What should I take
from this?
```

* `<panel_id>` is a short stable slug (e.g. `waterfall`, `hazard_coefficients`,
  `kpi_coverage`) — never free text, always the same value for the same
  panel across renders.
* `<live params>` (when present) are `key=value` pairs reflecting the
  panel's CURRENT inputs (e.g. `t0=59 t1=60`), space-separated inside the
  same brackets.
* `<Exhibit label>` is omitted for un-numbered panels (KPI tiles, control
  panels, guides).
* The recap sentence is built from the SAME payload object that rendered
  the panel — never hand-typed prose — so the router/narrator always has
  the rendered numbers in front of it.

Example (`app/ui/src/api.js`'s `explainPanelQuestion`, used by
`WaterfallChart.jsx`):

```
[explain:waterfall t0=59 t1=60] Exhibit 1 — Allowance bridge: opening $X.Xm,
stage migration +$X.Xm, remeasurement +$X.Xm, derecognitions −$X.Xm, new
loans +$X.Xm, closing $X.Xm. What should I take from this?
```

### 6.2 Selection-explain prefix

Highlighting any text in the main app area (outside inputs and both chat
surfaces) shows a floating "Explain with AI" chip
(`app/ui/src/components/SelectionExplain.jsx`); clicking it composes:

```
Explain, in the context of the <tab label> tab: "<selected text, trimmed, <=300 chars>"
```

`<tab label>` is one of the five tab names (`Executive Overview`, `The
Model`, `Scenario Lab`, `Policy`, `Copilot`). The selected text is quoted
verbatim (truncated, never paraphrased) so the router sees exactly what the
user highlighted.

Both builders live in `app/ui/src/api.js` (`explainPanelQuestion`,
`explainSelectionQuestion`) as the single source of the exact wire text, so
the UI and `tests/test_contract.py`'s router-wiring test stay
byte-identical with this doc.

---

## Summary table (every endpoint the v2 UI may call)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness + warm-up timing |
| GET | `/api/ecl/summary` | headline stats + scenario table |
| GET | `/api/ecl/waterfall` | movement decomposition between two snapshots |
| GET | `/api/exhibits/credit_cycle` | recovered Z_t series |
| POST | `/api/tools/shock_macro` | Tier-1 tool |
| POST | `/api/tools/reweight_scenarios` | Tier-1 tool |
| POST | `/api/tools/rerun_ecl` | Tier-1 tool |
| POST | `/api/tools/decompose_waterfall` | Tier-1 tool |
| POST | `/api/agent/ask` | route a free-text question through the copilot |
| GET | `/api/agent/stream` | SSE trace feed of the latest `/ask` |
| GET | `/api/model/coefficients` | hazard-ratio families + fit stats (The Model) |
| GET | `/api/model/variable_dictionary` | every modelled variable (The Model) |
| GET | `/api/model/macro_glossary` | every macro series across DCR+SFLLD+satellite (The Model) |
| GET | `/api/model/lgd` | LGD key numbers + exhibits (The Model) |
| GET | `/api/policy/staging_sensitivity` | SICR threshold governance curve (Policy) |
| GET | `/api/policy/weights_table` | scenario weights sensitivity (Policy) |
| GET | `/api/exhibits/list` | every servable exhibit PNG, with captions |
| GET | `/api/freddie/summary` | SFLLD panel scale + headline numbers (Real Data hero) |
| GET | `/api/freddie/hazard` | SFLLD hazard coefficients + DCR sign comparison + AUCs |
| GET | `/api/freddie/backtest` | ALFRED-vintage predicted-vs-realized table (Real Data) |
| GET | `/api/freddie/exhibits` | every servable Freddie SFLLD exhibit PNG, with captions |
| POST | `/api/agent/interpret` | auto-interpretation of an already-run tool result |
| GET | `/static/exhibits/*` | the exhibit PNGs themselves (read-only static mount) |
| GET | `/static/freddie/*` | the Freddie SFLLD exhibit PNGs (read-only static mount) |
| GET | `/static/mdd/MDD.html` | the Model Development Document (read-only static mount) |
