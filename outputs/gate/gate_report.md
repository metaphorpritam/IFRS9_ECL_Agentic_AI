# Day-2 GATE Report — Deterministic Engine Freeze

Date: 2026-07-05
Scope: MASTER_PLAN §5 gate. Freezes `engine/` (hazard, ead, lgd, staging, ecl) plus the
panel builder and analysis exhibits behind a structural-fingerprint tripwire.

## 1. Test suite — GREEN

`uv run pytest tests/ -q` → **187 passed, 0 failed** (1 pytest deprecation warning, non-blocking).

| Test file | Tests | Notes |
|---|---|---|
| tests/test_fixtures.py | 133 | Golden fixture values (formula conventions: ECL sum §3, workout LGD §10, CCF EAD §12). Untouched, all green. |
| tests/test_ead.py | 16 | Contractual amortisation profiles, matrix, revolver CCF. |
| tests/test_ecl.py | 14 | ECL schedule/totals, snapshot runner, movement decomposition. |
| tests/test_staging.py | 16 | SICR relative test, add-on, probation, backstop hook. |
| tests/test_lgd.py | 8 | Cure logit + fractional-logit severity + excess-loss loading. |
| **Total** | **187** | **All passing.** |

## 2. Per-module status

| Module | Status (this gate run) |
|---|---|
| engine/hazard.py | FROZEN-GREEN — Day-1 cloglog competing-risk hazard engine; TIMING CONVENTION docstring is binding for all downstream covariate use; exercised by fixtures + test_ecl/test_staging. |
| engine/lgd.py | FROZEN-GREEN — two-stage workout LGD (cure logit × Papke-Wooldridge fractional-logit severity, HC1 SEs) with explicit constant excess-loss loading (truncated-mass 0.0255 added back, never silently clipped); resolved-workouts-only fit with selection bias documented; 8/8 tests. |
| engine/ead.py | FROZEN-GREEN — contractual level-payment annuity EAD (deliberately NOT prepay-scaled; S(t) carries prepayment — see §5 double-counting rule), straight-line fallback, revolver ccf_ead engine-completeness; 16/16 tests; EUR 14.0m revolver fixture matches. |
| engine/staging.py | FROZEN-GREEN — relative lifetime-PD SICR test with doubling-ratio trigger + annualised 0.5pp add-on, stateless probation window, structurally-inert (loudly documented) 30-DPD backstop hook; 16/16 tests. |
| engine/ecl.py | FROZEN-GREEN — ECL = Σ_t S(t−1)·λ_t·LGD_t·EAD_t·(1+EIR)^−t per compute_ecl §3 golden convention; 12m and lifetime always computed, reported per stage; movement decomposition sequential; 14/14 tests + 133 fixture values green. |
| data/panel/build_panel.py | FROZEN-GREEN — 621,736 loan-quarter rows, 49,974 loans, 46 cols, t=1..60, train (t≤40) / oot (t=41..60). |
| analysis/* | GREEN — exhibits regenerate deterministically (apply_textbook_style, Agg backend, PNGs under outputs/<module>/). |

## 3. Freeze tripwire — fingerprint store

- Code map: `/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI/knowledge/code_map.md`
  (15 files scanned | 14 local modules | 8 third-party libs | 166 call edges;
  structural fingerprints in its final section).
- **Fingerprint store: `/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI/knowledge/code_fp.json`**
  — baseline established this run (all 15 files classified NEW). Re-running
  `scan_code.py --fingerprints knowledge/code_fp.json` classifies every file
  NONE / COSMETIC / STRUCTURAL against this baseline. This is the freeze tripwire.

## 4. Frozen-engine rule

> **Any post-gate STRUCTURAL change to `engine/` requires re-running the full test
> suite (`uv run pytest tests/ -q`, all 187 must pass) and a decision entry.**
> STRUCTURAL is as classified by the fingerprint tripwire (exports / signatures /
> imports changed — not comments or formatting). COSMETIC changes still warrant a
> suite run before commit; NONE requires nothing. `tests/fixtures/*` and
> `tests/test_fixtures.py` are immutable.

Standing invariant (reviewer-checked, restated at the gate): the ECL survival
S(t) = Π(1 − λ_def − λ_pre) already includes prepayment survival (competing risk);
**EAD_t must remain the CONTRACTUAL amortisation balance and must never be
prepay-scaled** — doing both double-counts prepayment.

## 5. Documented-simplifications register

### LGD (engine/lgd.py, analysis/fit_lgd.py)

1. RESOLVED workouts only (res_time notna): unresolved lgd_time is not a realised outcome (58% coded exactly 0; mean 0.19 vs 0.60 resolved; 48% of OOT defaults open vs 17% train). Residual selection bias documented: resolved-only over-represents fast workouts, cures resolve faster (median 3q vs 5q), so fitted cure is biased up near the window end; completion model for open workouts is documented future work.
2. LGD_cure = 0: realised mean LGD among train cures is 0.0036, understates expected LGD by ~0.04pp of EAD (reported, not modelled).
3. Excess-loss loading is a CONSTANT, not covariate-driven: the >1 tail (9.8% of realised LGDs, max 8.5) is real workout-cost data, capped at 1 only inside the fractional-logit link and the truncated mean mass (0.0255) added back explicitly — never silently clipped.
4. lgd_time taken as the vendor's realised workout LGD; EIR discounting of notes section 10.1 assumed embedded (no post-default cash-flow detail in panel).
5. Severity is a conditional-mean model (Papke-Wooldridge fractional logit, HC1 SEs), not a density; ECL only consumes the mean.
6. Point-in-time, no downturn add-on; cyclicality enters via uer_lag1 and HPI-indexed updated_ltv; scenario conditioning is a later rung.
7. Cure-stage uer_lag1 coefficient is POSITIVE (+0.277) — reported honestly, not sign-asserted: conditional on updated_ltv (which carries the HPI collapse), stress-cohort defaulters cure more; robust in a fixed-28q-resolution-runway subsample (coef +1.02), so not a censoring artefact; the mandated collateral-channel signs hold and are asserted.

### EAD (engine/ead.py, analysis/ead_exhibits.py)

1. CRITICAL convention (documented in module docstring, ead_profile docstring, chart annotation, and report): EAD_t is the CONTRACTUAL amortisation balance, deliberately NOT prepay-scaled — the ECL survival S(t)=prod(1-lambda_def-lambda_pre) from engine/hazard.py already removes prepaid exposure; scaling EAD too would double-count.
2. EAD_t = balance ENTERING period t (after t-1 scheduled payments), matching compute_ecl §3; so EAD_1 = snapshot balance and EAD_t <= balance always (a fortiori <= balance*(1+r_q)).
3. Amortisation: level-payment annuity closed form B_k = B_0*((1+r_q)^n-(1+r_q)^k)/((1+r_q)^n-1) with quarterly compounding of the nominal annual note rate in percent (r_q = interest_rate_time/400); guarantees exact zero at maturity.
4. rate <= 0 or NaN -> straight-line fallback B_k = B_0*(1-k/n); defensive only — every panel row has interest_rate_time > 0 (zero-coded rates dropped in the panel waterfall; orig_rate_missing concerns the origination-rate snapshot, not the current note rate).
5. Remaining term = mat_time - time (same convention as build_panel.py line 359 time_to_mat), floored at 1 quarter: at/past-maturity loans are due in full within one quarter.
6. Original contractual maturity only — no modification/payment-holiday reprofiling (no such data in the panel).
7. All term loans level-pay to zero: no balloon or interest-only structures modelled (panel has no amortisation-type field; disciplined default for US fixed-rate mortgages).
8. Note rate frozen at snapshot over the projection (ARM resets out of scope at this rung).
9. Revolver ccf_ead is engine-completeness only (DCR book has no revolvers); undrawn headroom floored at 0 for overlimit facilities, CCF deliberately not clamped above 1.

### Staging (engine/staging.py, analysis/staging_exhibits.py)

1. Frozen-covariate lifetime PDs on BOTH legs (pd_term_structure rung-1 convention): no macro path, no LTV amortisation along the projection; scenario conditioning is a later rung. Both views share the assumption so the relative test is internally consistent.
2. 30-DPD backstop STRUCTURALLY INERT: DCR has no delinquency ladder (status only performing/default/payoff); the hook (config.dpd_col) is implemented and tested but can never fire here — Stage-2 populations are quantitative-trigger-only and would be strictly larger with a live backstop.
3. Origination macro for pre-window vintages (orig_time-5 < 1): referenced quarters clamped to earliest observed quarter => earliest macro level + ~zero momentum; flagged per loan orig_macro_approx (2.6% of t=40 book).
4. Origination market rate = per-quarter MEDIAN of loan-matched rate_time (within-quarter std ~0.5pp); zero-coded origination note rates fall back to the current note rate, flagged orig_rate_proxy (9.6% at t=40).
5. Add-on conversion: 0.5pp add-on applied on annualised scale, ann = 1 - (1 - PD_life)^(4/R) (R quarters = R/4 years), horizon-independent.
6. Probation implemented as the exactly-equivalent stateless window rule (trigger fired at any of t..t-(cure_quarters-1) => Stage 2, reason sicr_probation); consecutive means consecutive observations for gap loans; degrades gracefully to the raw trigger on a pure single-quarter frame.
7. Payoff-quarter rows are derecognitions, excluded from the staged book in exhibits; loans at/past maturity get a floored one-quarter window; no low-credit-risk exemption, no qualitative/watchlist triggers (fields absent).
8. Models fitted once on full training window; t=20 staging is an in-sample calm-quarter illustration, not walk-forward.

## 6. Gate verdict

**PASS.** 187/187 tests green; fingerprint baseline written; engine/ is frozen under
the rule in §4. Post-gate work (scenario conditioning, LLM orchestration) builds on
top of — not inside — engine/.
