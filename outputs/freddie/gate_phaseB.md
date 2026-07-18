# Rung 3 Phase B Gate — SFLLD Hazard/LGD Refit + ALFRED Backtest + LSTM Challenger

Baseline `HEAD` = `7adc2af08e498ee4185cc919546621cb2ccd6f34` ("Agent REASONED route: labeled,
number-guarded interpretation for conceptual questions"). Gate run 2026-07-18.

## 1. Test suite — GREEN, 659/659

```
uv run --no-sync pytest tests/ -q
...
659 passed, 29 warnings in 260.19s (0:04:20)
```

- Baseline (pre-Phase-B): 582/582.
- New Phase-B tests: `tests/test_freddie_hazard.py` + `tests/test_freddie_lgd.py` +
  `tests/test_freddie_backtest.py` + `tests/test_freddie_lstm.py` = **77 tests**
  (`pytest --collect-only -q` on the four files independently confirms 77 collected).
- 582 + 77 = **659** — matches the full-suite run exactly. Zero failures, zero errors,
  zero skips. (29 warnings are all pre-existing/environmental — `httpx`/Starlette
  deprecation and a `multiprocessing.fork()` warning from `tests/test_tier2.py` — none
  touch Phase-B code.)

## 2. Isolation — CLEAN

`git status --porcelain=v1 -uall` outside the declared Phase-B footprint is empty. Full
change set:

- Modified (tracked): `wiki/memory/log.md` only (4 lines added — project memory, expected).
- New, in-scope: `freddie/{fit_hazard,fit_lgd,fit_lstm,lgd,lstm}.py`;
  `tests/test_freddie_{hazard,lgd,backtest,lstm}.py`;
  `outputs/freddie/{hazard,lgd,backtest,lstm}/**` (reports + exhibits + metrics.json).
- New, operator files (expected per task brief): `WSL_CRASH_FIXES.md`, `wsl_fix/`.
- `git diff --stat` for the whole tree: only `wiki/memory/log.md` (4 insertions) — every
  other change is an untracked new file, nothing pre-existing was edited.
- `git status`/`git diff --stat` restricted to `engine/ data/panel/ analysis/ agent/ app/`:
  **empty** — zero touches anywhere in the DCR core or the app/agent layer this session.
- `data/processed/panel.parquet`: sha256 `e124b856…8213b1c`, mtime 2026-07-05 06:31 —
  byte-identical to the Phase-A-recorded value, untouched.
- `data/processed/freddie/`: only Phase-A/Phase-B artifact subdirs present
  (`alfred/`, `backtest/`, `hazard/`, `lgd/`, `logs/`, `lstm/`, `macro/`,
  `loan_orig.parquet`, `panel_monthly.parquet`) — no writes outside the freddie namespace.

**Verdict: isolation intact.**

**Gate-tooling note (declared, not hidden)**: running `scan_code.py --fingerprints
knowledge/code_fp.json` for section 3 below mutates `knowledge/code_fp.json` IN PLACE as
a side effect (it does not treat `--fingerprints` as read-only baseline input despite
also writing the requested `--out` report) — this briefly modified a tracked file
outside the declared Phase-B footprint. Caught immediately via a post-scan
`git status` sweep and reverted with `git checkout -- knowledge/code_fp.json` before
this gate was finalized; `git diff --stat` and a git-blob sha256 both confirm
`knowledge/code_fp.json` is byte-identical to `HEAD` in the final state reported here.

## 3. Fingerprint scan — frozen five NONE

`scan_code.py --dirs engine agent app analysis --fingerprints knowledge/code_fp.json`:

| frozen file | struct_hash | verdict |
|---|---|---|
| `engine/hazard.py` | `1786dacea90bf08e` | **NONE** |
| `engine/lgd.py` | `d5a98c1dc6fc76d0` | **NONE** |
| `engine/ead.py` | `b120dc99602dd3f7` | **NONE** |
| `engine/staging.py` | `9354043a443a12d0` | **NONE** |
| `engine/ecl.py` | `7c7feef9c97494fe` | **NONE** |

Belt-and-braces git-blob sha256 (working tree vs `HEAD`) on all five files is
byte-identical:

```
engine/hazard.py  cfd768f0...   (workdir == HEAD)
engine/lgd.py     7c0c275f...   (workdir == HEAD)
engine/ead.py     27b8275d...   (workdir == HEAD)
engine/staging.py 92880a1b...   (workdir == HEAD)
engine/ecl.py     65519b7f...   (workdir == HEAD)
```

**Verdict: frozen five all NONE.** (The same scan reports pre-existing `STRUCTURAL` on
`agent/graph.py` / `app/api/main.py` — an artifact of `knowledge/code_fp.json` predating
the last `agent/graph.py` commit (`7adc2af`, before this session); `git diff` on `agent/`
and `app/` for this session is empty, so this is not a Phase-B change and outside the
frozen-five scope.)

## 4. Headline numbers (pulled from the four module reports)

### 4a. Hazard refit (`freddie/fit_hazard.py`, `outputs/freddie/hazard/`)
- Champion train: 17,703,723 loan-months, 26,284 D90 events (0.1485% monthly hazard);
  OOT: 21,818,842 loan-months, 18,309 events. WESML fit sample: 826,476 rows / 24,611
  events.
- **Train AUC 0.8536 / OOT AUC 0.6847**, McFadden pseudo-R² (fit sample) 0.1197.
- Core risk drivers match DCR priors: FICO −0.9257, updated-LTV(10) +0.3225, `uer_lag1`
  +0.0950, `delta_uer_lag1` +0.6671, `hpi_growth_lag1` −3.3442 (all economically signed).
  Three categorical misses declared and explained as composition, not defect
  (occupancy[S], loan_purpose[N], channel[C]).
- COVID/forbearance regime comparison (extended window ≤2021-09, scored on genuinely
  unseen OOT2 >2021-09): naive OOT2 AUC 0.7553, additive 0.7547, **exclude 0.7509**
  (recommended — only variant preserving economically-signed macro coefficients:
  `delta_uer_lag1` +0.774, `hpi_growth_lag1` −3.307 vs champion +0.667/−3.344).
  Residual caveat shared by all variants: 2022-2025 observed hazard runs ~1.62–1.79×
  predictions.
- Seed stability (seed 1234 vs 42): 0 sign flips; max relative coefficient diff 0.486 on
  a near-zero spline term.
- 2020 calibration row: observed 0.357% vs predicted 4.162% monthly (champion scoring
  straight through the forbearance window with pre-COVID coefficients — extrapolation,
  not a defect, per section 3 of the report).

### 4b. LGD refit (`freddie/fit_lgd.py`, `outputs/freddie/lgd/`)
- 44,593 `had_d90_event` loans partitioned cure/liquidation/unresolved: train 12,429 /
  14,480 / 1,228; OOT 14,141 / 430 / 1,885.
- **Cure-stage AUC**: train 0.6991, OOT 0.4769 (OOT below random — explained by the
  `modern 2018-2025` era fixed effect being fit on only 9 train rows, a mechanical
  consequence of the calendar train/OOT split; not a coding defect).
- **Severity-stage** (fractional logit, HC1 robust SEs, n=13,444 train liquidations):
  `ltv10` +0.0307, `is_judicial` +0.5199, liquidation-year-bucket hump peaking
  2010-12 (+1.7275).
- Overall constant excess-loading: **0.0148** (vs DCR's 0.0255); 7.8% of liquidations
  have severity > cap, 2.3% < 0 (both real, never discarded).
- Portfolio LGD summary: train mean realized LGD 0.2715 (n_resolved 26,896, 1,035
  liquidations excluded for no populated loss field — FOUND-AND-FIXED during audit, see
  simplification register below); OOT mean realized LGD 0.0074 (OOT dominated by COVID
  cures, not a like-for-like regime test — declared).
- Denominator reconciliation (`upb_at_default` vs `zero_balance_removal_upb`, n=13,840):
  corr 0.9948, mean ratio 1.0018.
- Selection-bias-by-default-year table (new, section 2): 2020 D90 unresolved rate 2.2%
  (n=8,698) — BELOW the 2005-2019 average (4.4%); the exposure is RECENCY (2025 default
  year 54.2% unresolved), not COVID — corrects the task brief's assumed premise against
  the module's own measured data.

### 4c. ALFRED-vintage backtest (`freddie/backtest.py`, `outputs/freddie/backtest/`)
Champion spec refit-in-time at 5 pseudo-reporting dates, projected 36 months, scored vs
realized:

| T | realized D90 (36mo) | predicted (frozen) | miss (frozen) | predicted (hindsight-actual) | miss (actual) |
|---|---:|---:|---:|---:|---:|
| 2007-12 | 8.750% | 0.928% | **9.42×** | 4.613% | 1.90× |
| 2009-12 | 6.569% | 5.554% | 1.18× | 4.658% | 1.41× |
| 2015-12 | 1.397% | 1.857% | 0.75× | 1.855% | 0.75× |
| 2019-12 | 4.601% | 0.920% | 5.00× | 71.519% | 0.06× |
| 2021-12 | 1.161% | 1.734% | 0.67× | 1.229% | 0.94× |

- **2007-12 spec check**: 9.42× underprediction of the GFC — the exhibit's central
  honesty result (a pre-crisis model with macro frozen at 2007-12 levels cannot see the
  crisis coming).
- **2019-12 hindsight panel**: the 71.5% hindsight-actual prediction is faithful linear
  extrapolation of `delta_uer_lag1` fed the real April-2020 +10.6pp UER print (~20 SDs
  outside training support) — declared as the exhibit's point (spec/parameter model
  risk no macro overlay can fix), cross-referenced against the LGD module's finding that
  the modern-era OOT cure rate is 97.9% (COVID D90 spike resolved as cures, not losses —
  connective finding between the PD-hazard miss and the realized-loss non-event).
- ALFRED coverage: FHFA STHPI has no ALFRED vintage archive at all (empirically
  verified); HPI-as-known-at-T is a publication-lag truncation, not a genuine revision —
  declared, not hidden.

### 4d. LSTM path-dependence challenger (`freddie/fit_lstm.py`, `outputs/freddie/lstm/`)
Scored on the identical champion train/OOT split (no NaN-row exclusion difference):

| split | n | events | champion AUC | LSTM AUC | Δ |
|---|---:|---:|---:|---:|---:|
| TRAIN | 16,059,126 | 24,611 | 0.8536 | 0.9964 | +0.1429 |
| OOT | 20,621,912 | 16,832 | 0.6847 | 0.9925 | +0.3078 |

Lift split (the path-dependence test, OOT, by prior-24mo-delinquency flag):

| group | n | events | champion AUC | LSTM AUC | Δ |
|---|---:|---:|---:|---:|---:|
| Clean history | 19,643,934 | 40 | 0.5386 | 0.5287 | −0.0098 |
| Prior delinquency spell | 977,978 | 16,792 | 0.5698 | 0.9570 | **+0.3872** |

The LSTM's lift concentrates almost entirely on the prior-delinquency-spell group
(+0.387 AUC) vs essentially zero (−0.010) on clean-history loans — direct evidence for
the path-dependence hypothesis (the champion's current-state-only view under-serves
loans with delinquency history), with the report's own caveat that the forbearance-era
delinquency-ladder distortion (Phase-A finding) may inflate part of this in the 2020-21
window — flagged, not resolved, via `calibration_comparison.png`'s shaded window.
Best epoch 3/9 (time-based validation split, cutoff 2015-12-01), best val AUC 0.9963.

## 5. Simplification registers (embedded verbatim, as supplied)

### LGD (`freddie/lgd.py` / `freddie/fit_lgd.py`)
1. Pre-existing (documented in lgd.py/fit_lgd.py already, verified correct on audit, not
   changed): `JUDICIAL_STATES` is a single static classification with no within-sample
   regime changes; `zero_balance_code==16` treated as cure by judgement;
   code-15 loss-bearing subset (853/922, 92.5%) treated as liquidation-equivalent NPL
   sale, correction vs an earlier draft; no downturn add-on (point-in-time LGD);
   `predict_components`/`predict_lgd` are diagnostic tools scored on already-resolved
   history only, not a forward-scoring API.
2. FOUND AND FIXED during audit: `population_lgd_summary()` previously zero-filled
   liquidation rows with no populated `actual_loss_calculation` ("loss not yet
   finalized") when computing `mean_realized_lgd`, silently conflating "loss not yet
   known" with "no loss" and biasing the reported aggregate LGD down (affects ~7% of
   liquidations nationally, 1,035 train rows). Fixed to exclude them and report the
   excluded count (`n_liq_excluded_no_loss_data`), consistent with the module's own
   "never silently zero-fill" philosophy used everywhere else.
3. FOUND AND FIXED during audit: `_df_to_md()`'s markdown-table writer used
   `DataFrame.iterrows()`, which silently upcasts an all-numeric row (int64 + float64
   columns) to float64 whenever the table has no string column to force per-value
   object dtype — rendered years/counts as "2020.0000" instead of "2020" in
   `severity_by_liq_year` and the new `unresolved_rate_by_default_year` tables. Fixed by
   checking each column's original dtype instead of the upcast row.
4. FOUND AND CORRECTED an assumption, not a code bug: the task brief's premise
   "COVID-era D90s heavily unresolved" does not hold empirically — 2020 D90s have the
   SECOND-LOWEST unresolved rate in the whole panel (2.2%) because forbearance-driven
   D90s cure fast within a few years. The report was written to state the measured
   finding (recency, not COVID, drives the unresolved-rate gap) rather than force the
   assumed narrative — added a new by-default-year quantification table + honest
   write-up to `outputs/freddie/lgd/lgd_report.md` section 2.
5. `predict_components`' docstring was clarified (not behaviorally changed) to state
   explicitly that `df` must be liquidation-outcome rows only, since a cure row's
   `disposition_type` is a real, non-NaN value that is nonetheless an untrained
   categorical level for the severity GLM and raises a PatsyError — caught this via my
   own test design and fixed the test rather than papering over it with a broader
   dropna.
6. Test suite design choice: the single-vintage (2007) fixture is authoritative for fast
   outcome-partition/sign-convention checks, but is genuinely too thin for the severity
   stage's LTV coefficient to reliably reproduce the population sign (`fit_lgd_models`
   correctly rejects that thin fit via its own economic-sign guard, exercised and
   asserted in a dedicated test). Economic-sign and predict_components/population-summary
   tests instead use the cached FULL 44,593-loan production sample (fast to load, no
   re-read cost) via a `full_sample`/`full_models` fixture pair.
7. Two transient `OSError('Cannot allocate memory')` failures during the session were
   caused by an EXTERNAL concurrent process (a second `freddie.fit_hazard` run, PID
   11881, apparently a separate orchestrator subagent) competing for the shared ~11GB
   WSL VM memory cap — not code defects; waited for it to exit (Bash run_in_background +
   until-loop) both times and re-ran cleanly.

### Backtest (`freddie/backtest.py`)
1. HPI "as known at T" is a publication-lag TRUNCATION (`HPI_PUBLICATION_LAG_MONTHS=5`)
   of the single current-vintage FHFA STHPI series, not a genuine ALFRED historical
   revision — FHFA STHPI (state AND national) has NO ALFRED vintage archive on FRED at
   all (empirically verified: HTTP 400 "does not exist in ALFRED" for every
   `realtime_start` tried, both CASTHPI/NDSTHPI and national USSTHPI).
2. `updated_ltv` (and `ltv10`) is held FROZEN at its last-known-at-T value for the
   entire 36-month projection in BOTH macro scenarios — no amortisation/prepayment path
   is re-derived for `current_upb`, so the two scenarios differ only in the macro-path
   assumption.
3. Projection base covariates (`active_loans_at`) use a per-state forward-filled
   ("last published print") macro snapshot rather than the exact-month-T merge, because
   publication lag means the exact reporting month's own macro is itself usually still
   NaN/unknown at T — documented as standard real-world practice (analysts use the last
   published index), not a lookahead violation (only ever fills NaN with an earlier
   known value). The as-of-T FIT frame is deliberately NOT patched this way, so its
   tail-of-window rows with genuinely-unpublished macro are honestly dropped by
   `fh.fit_hazard`'s dropna.
4. Projection is expected-value hazard roll-forward (cumulative survival product), not a
   stochastic/Monte-Carlo simulation.
5. State UER ALFRED pulls that come back empty/unsupported fall back to the national
   UNRATE vintage for that reporting date (documented per-date in
   `alfred_coverage_*.json`).
6. Case-control (WESML) subsampling reuses `freddie.fit_hazard.CONTROL_SAMPLE_RATE`
   (0.05) unchanged for every as-of-T refit.

### LSTM (`freddie/lstm.py` / `freddie/fit_lstm.py`)
1. Sequence lag computed by SAME-LOAN POSITION not calendar offset (a rare reporting gap
   would misalign the true calendar lag) — declared in `freddie/lstm.py` module
   docstring and `lstm_report.md`.
2. `dlq_num` capped at 6 before scaling (rare tail winsorised).
3. "Prior delinquency spell" (lift-split grouping) is defined over the SAME 24-month
   window the model sees, not the loan's full lifetime history.
4. Class imbalance / case-control bias handled via a single scalar
   `pos_weight = CONTROL_SAMPLE_RATE (0.05)` in `BCEWithLogitsLoss` — changed from the
   pre-existing code's `pos_weight=n_neg/n_pos` (sample's own ratio), which I found and
   fixed as a genuine calibration bug: analytically (and verified in
   `tests/test_freddie_lstm.py::test_pos_weight_rate_recovers_calibration`)
   `pos_weight=rate` makes the network's raw sigmoid a population-calibrated
   probability, while `pos_weight=n_neg/n_pos` collapses predictions towards ~0.5 (pure
   sample-rebalancing, useless for calibration). This is NOT the champion's per-row
   WESML `freq_weight` inside a GLM likelihood (an SGD mini-batch loss has no
   equivalent), but lands at the same INTENT.
5. Case-control subsample (same 5% rate/seed as the champion's own fit sample) used for
   TRAINING only; headline/lift AUCs and calibration are scored on the FULL,
   un-subsampled train/OOT populations (matching the champion's own `score_by_year`
   methodology exactly) — vintage-chunked, checkpointed per vintage under
   `data/processed/freddie/lstm/scored/`.
6. Left-padding with no `pack_padded_sequence`: the recurrent core processes zero-padded
   early time-steps for young loans rather than being masked out of the recurrence
   entirely; an explicit per-step `is_valid` channel + static `hist_len_frac` feature
   compensate.
7. Modest architecture (1 LSTM layer, 64 hidden units, 2-layer MLP head), single
   seed/run — no hyperparameter search, no ensembling, no second-seed stability check
   (unlike the champion's `seed_stability.csv`).
8. No competing-risk prepayment head, no LGD/EAD integration — discrimination question
   only, matching the champion hazard's own scope.
9. Environment workaround (not a modeling simplification, but declared): this
   WSL2/RTX4060 build's cuDNN RNN kernel reproducibly throws "CUDA driver error: out of
   memory" on a trivial ~19MB LSTM forward pass (verified via minimal repro) —
   `torch.backends.cudnn.enabled=False` is set as a documented workaround in
   `freddie/lstm.py`'s `set_determinism()`/`predict_lstm()`; GPU training remains fully
   used (not a CPU/sklearn fallback), benchmarked at ~28ms/4096-row batch with cuDNN
   disabled.

## 6. Verdict

**PASS.** 659/659 tests green (582 baseline + 77 Phase-B, zero regressions); isolation
fully intact (only `freddie/`, `tests/test_freddie_*`, `outputs/freddie/`,
`wiki/memory/log.md`, plus expected operator files `WSL_CRASH_FIXES.md`/`wsl_fix/`
touched); frozen five (`engine/{hazard,lgd,ead,staging,ecl}.py`) sha-identical to `HEAD`
and fingerprint-scanner NONE; `data/processed/panel.parquet` byte-identical to the
Phase-A-recorded sha256, untouched.
