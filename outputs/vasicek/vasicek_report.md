# Vasicek / Belkin Z conditioning - calibration report

## Method (notes section 8; engine/vasicek.py)

One-factor conditioning `PD_PIT(Z) = Phi((Phi^-1(PD_TTC) - sqrt(rho) Z)/sqrt(1-rho))`; per-quarter inversion `Z_t = invert_z(observed_t, expected_t, rho)`; rho calibrated so `Var(Z_t) = 1` (Belkin), sample variance (ddof=1) over all 60 panel quarters, 2000Q2..2015Q1.

**Composition adjustment (the vintage caution).** The book grows toward mid-panel, so raw default COUNTS (and the raw rate) mix vintage composition with the cycle. The TTC anchor is therefore recomputed EVERY quarter as the mean predicted hazard of that quarter's actual at-risk rows under cycle-neutral macros - the frozen rung-1 default hazard (fit on train, t<=40, applied read-only to all 60 quarters) scored with the four macro regressors held at panel-period means:

    uer_lag1=6.4000, uer_chg4_lag1=0.1600, hpi_growth_lag1=0.0096, gdp_lag1=1.8281

Loan-state covariates (age, FICO, updated_ltv, prepay_incentive, occupancy/property flags) stay ACTUAL, so the anchor reprices the live book, not a synthetic one. Observed-vs-expected then isolates the systematic surprise.

## Calibration

| quantity | main | variant (orig-LTV) |
|---|---|---|
| calibrated rho (Var(Z)=1) | **0.0227** | 0.0633 |
| mean(Z_t) | -1.145 | -0.861 |
| Var(Z_t) (ddof=1) | 1.000000 | 1.000000 |
| quarters used | 60 | 60 |
| Z trough | 2008Q1 (Z=-2.74) | 2009Q2 (Z=-2.64) |

**rho vs conventions:** calibrated rho = 0.0227 sits well below both the notes' worked-example convention rho = 0.12 and the Basel IRB residential-mortgage supervisory value rho = 0.15 (CRE31.10). That ordering is the expected one: empirical asset correlations estimated from default-rate time series are routinely a fraction of the regulatory convention (the Basel figures are calibrated to capital conservatism, not to time-series fit), and composition-adjusting the anchor absorbs part of the systematic variance into the quarter-specific TTC rate, damping Z further. The orig-LTV variant (rho = 0.0633) shows exactly this mechanism in reverse: freezing collateral at origination pushes the HPI cycle OUT of the anchor and INTO Z, so the recovered factor swings wider and needs a larger rho to standardise.

## Anchor + round-trip checks

* Gauss-Hermite anchor `E_Z[PD_PIT] = PD_TTC` at (flat TTC = 0.013488, rho = 0.0227): |error| = 1.91e-17 ( < 1e-6 gate; the golden fixture pins the same identity at (2%, 0.12) ).
* PIT <-> Z round trip on the recovered path: max |error| = 6.00e-15 ( < 1e-9 gate; fixed-conventions answer to the Basson & van Vuuren caveat).
* Hump timing: PIT PD peaks 2008Q1 (3.44% quarterly vs 1.35% anchor), Z troughs 2008Q1 - inside the required 2008-10 window, i.e. the recovered cycle lands the GFC where history put it.

## Exhibit

`credit_cycle.png`: top panel shows the Z-implied portfolio PIT PD path `pit_pd(flat_ttc, Z_t, rho)` against the flat TTC anchor (1.35%, the unweighted mean of the 60 composition-adjusted quarterly anchors) with the damped hybrid (alpha = 0.5, Z scaled by alpha - the Aguais/Forest PIT-ness dial; note alpha < 1 is Jensen-biased slightly below the anchor on average, a presentation device, not an ECL input). Bottom panel: the recovered Z_t itself, with the orig-LTV variant dashed. GFC (NBER 2007Q4-2009Q2) shaded. Calendar axis anchored t=1 ~ 2000Q2 (verified vs FRED UNRATE, corr 0.9963).

## Limits (documented, not hidden)

* **updated_ltv carries the cycle** (HPI indexation), so the main anchor is only approximately TTC: part of the 2008-10 stress is absorbed into collateral marks, making the main Z a conservative (damped) cycle read. The orig-LTV variant brackets the effect from the other side (pure-TTC collateral, but then the anchor ignores genuine amortisation and equity build-up). Truth lies between; both are reported.
* prepay_incentive stays actual in both variants (loan-state exception per the frozen hazard's timing convention; it prices the borrower's option, and only the DEFAULT hazard is used here).
* Macro means are unweighted over the 60 quarters - a panel-period average, not a true long-run TTC macro state (the window is one cycle plus a boom tail).
* **mean(Z) = -1.145 is NOT forced to zero** (Belkin calibrates the VARIANCE only, and sample variance is mean-invariant). The negative mean is a LEVEL gap - observed rates average 2.12% vs 1.35% for the frozen-macro anchor - with three identifiable causes: (i) Jensen/convexity of the cloglog inverse link: the hazard AT mean macros is below the macro-AVERAGED hazard, so freezing macros at means biases the anchor low; (ii) a small structural inversion offset (even obs == anchor maps to Z < 0 because sqrt(1-rho) < 1); (iii) OOT calibration drift plus adverse survivor selection - post-2010 at-risk loans are the ones that could not refinance, and they default above the anchor even in recovery, holding Z near -1.7 through 2013. The CYCLE read is the SHAPE (trough in the GFC, monotone climb after 2010); the satellite model (next rung) regresses Z_t as-is, so the level piece is absorbed by its intercept.
* Early quarters are thin (283 at-risk loans at t=1), inflating |Z_t| noise there; no smoothing applied.
* Identifying the finite-portfolio quarterly rate with PD_PIT is the ASRF infinite-granularity approximation.

## Model provenance

* Default hazard: engine/hazard.py (FROZEN), fit on train rows, n_obs = 418,418, events = 11,354; scored read-only over all 621,736 panel rows per variant.
* Data behind the exhibit: `z_path.csv` (per-quarter n, defaults, observed rate, both anchors, both Z paths, PIT/hybrid paths).