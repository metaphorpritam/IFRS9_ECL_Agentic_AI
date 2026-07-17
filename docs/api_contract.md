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
         "story": "Borrower quality: cleaner credit at origination defaults less; investors walk away from underwater rentals faster than owner-occupiers."}
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
     "consumed_by": "default hazard; LGD both stages; staging legs"}
    /* ... 13 rows total, in file order: fico_s, ltv10, loan_age,
       prepay_incentive, investor/RE-type flags, uer_lag1, uer_chg4_lag1,
       hpi_growth_lag1, gdp_lag1/gdp_growth_lag2, dt_ltv_uer,
       lgd_time (target), Z_t (recovered), Scenario paths */
  ],
  "notes": "Model equations live in the module docstrings (cloglog hazard; two-stage LGD; ECL sum; Vasicek PIT\ntransform with the Gauss-Hermite anchor proof; satellite Z = −1.694 + 13.642·hpi_growth_lag1 +\n0.730·gdp_growth_lag2, n=57, with ADF/KPSS/DW/AIC and the GFC-dummy sensitivity in\noutputs/satellite/satellite_report.md). Coefficient tables with CIs: outputs/hazard/hazard_ratios.md,\noutputs/lgd/lgd_report.md."
}
```
`rows[].*` keys are all strings (raw source cells, including the ✓/⚡/↑/↓
glyphs and backtick-quoted variable names — the UI renders them as-is,
markdown-lite).

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

## 4. NEW: Copilot / Scenario Lab auto-interpretation

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

## 5. NEW: UI v3 AI-explain question-prefix conventions

Both conventions below are **UI-side wire-text conventions layered on top of
the existing `POST /api/agent/ask`** (§1) — they add ZERO new endpoints and
change no response shape. `POST /api/agent/ask` already accepts any
1–2000 char free-text `question`; these are simply two disciplined ways the
v3 UI composes that string so an "explain" click gets the exact same
tools/Tier-2/Tier-3/refusal governance as a typed question (FINAL_SPEC.md
§7.5, design-judge grafts 4). The router sees ordinary text — a bracketed
tag, a colon, and a trailing question — and is free to route it to any of
the five paths, including `REFUSE`, exactly as it would any other message.

### 5.1 Panel/tile explain prefix

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

### 5.2 Selection-explain prefix

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
| GET | `/api/model/lgd` | LGD key numbers + exhibits (The Model) |
| GET | `/api/policy/staging_sensitivity` | SICR threshold governance curve (Policy) |
| GET | `/api/policy/weights_table` | scenario weights sensitivity (Policy) |
| GET | `/api/exhibits/list` | every servable exhibit PNG, with captions |
| POST | `/api/agent/interpret` | auto-interpretation of an already-run tool result |
| GET | `/static/exhibits/*` | the exhibit PNGs themselves (read-only static mount) |
