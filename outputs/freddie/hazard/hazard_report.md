# SFLLD Champion Hazard Refit -- Monthly Discrete-Time Cloglog D90 Hazard
Fresh refit on the SFLLD loan-month panel (`panel_monthly.parquet`), state-level macro (`freddie.macro`), no left truncation (sampled from origination -- an upgrade over the DCR panel). Only the DEFAULT (D90) cause-specific hazard is fit (no competing-risk prepayment hazard in this refit -- SIMPLIFICATION). See `freddie/fit_hazard.py` module docstring for the full methodology.
## 1. Sample & split
- Champion train: performance month <= 2016-12 -- 17,703,723 loan-months, 26,284 D90 events (0.1485% monthly hazard).
- OOT: performance month >= 2017-01 -- 21,818,842 loan-months, 18,309 D90 events. COVID (2020-04..2021-09) lands entirely inside OOT, as recorded.
- Fit sample (WESML case-control): every train event row enters the sample (26,284), plus a 5% random subsample of non-event train rows; 83,680 NaN-covariate rows (events and controls alike) are then dropped, leaving 826,476 fit rows with 24,611 events. Controls are reweighted by `freq_weight = 1/rate` (Manski-Lerman WESML), events by `freq_weight = 1` -- valid for any GLM link, not just logit (see module docstring).
## 2. Coefficients vs the DCR champion
Coefficients (`outputs/freddie/hazard/coefficients.csv`) and the sign comparison against `engine/hazard.py`'s DCR champion (read-only reference; `outputs/variable_dictionary.md` consulted for the DCR expected-direction column):

| term | coef | hazard ratio | p-value | this-fit sign | DCR variable | DCR expected sign |
|---|---:|---:|---:|:---:|---|---|
| Intercept | -3.6043 | 0.027 | 0 | - |  |  |
| C(occupancy_status, Treatment(reference='P'))[T.I] | 0.0943 | 1.099 | 0.000469 | + |  |  |
| C(occupancy_status, Treatment(reference='P'))[T.S] | -0.1926 | 0.825 | 8.18e-09 | - |  |  |
| C(loan_purpose, Treatment(reference='P'))[T.C] | 0.4379 | 1.550 | 4.02e-184 | + |  |  |
| C(loan_purpose, Treatment(reference='P'))[T.N] | 0.2704 | 1.310 | 1.69e-50 | + |  |  |
| C(channel, Treatment(reference='R'))[T.B] | 0.1986 | 1.220 | 6.34e-09 | + |  |  |
| C(channel, Treatment(reference='R'))[T.C] | -0.2341 | 0.791 | 4.96e-14 | - |  |  |
| C(channel, Treatment(reference='R'))[T.T] | 0.3072 | 1.360 | 8.06e-109 | + |  |  |
| cr(loan_age, df=5)[0] | -1.9171 | 0.147 | 0 | - | cr(loan_age, df=5) | hump (DCR peak ~12 QUARTERS ~= 36 months) |
| cr(loan_age, df=5)[1] | -0.3428 | 0.710 | 1.53e-24 | - | cr(loan_age, df=5) | hump (DCR peak ~12 QUARTERS ~= 36 months) |
| cr(loan_age, df=5)[2] | -0.5917 | 0.553 | 5.32e-73 | - | cr(loan_age, df=5) | hump (DCR peak ~12 QUARTERS ~= 36 months) |
| cr(loan_age, df=5)[3] | 0.0449 | 1.046 | 0.225 | + | cr(loan_age, df=5) | hump (DCR peak ~12 QUARTERS ~= 36 months) |
| cr(loan_age, df=5)[4] | -0.7976 | 0.450 | 3.45e-10 | - | cr(loan_age, df=5) | hump (DCR peak ~12 QUARTERS ~= 36 months) |
| fico_s | -0.9257 | 0.396 | 0 | - | fico_s | - |
| dti_s | 0.2313 | 1.260 | 0 | + |  | n/a (DCR has no DTI field at this rung) |
| ltv10 | 0.3225 | 1.381 | 0 | + | ltv10 | + |
| uer_lag1 | 0.0950 | 1.100 | 1.42e-208 | + | uer_lag1 | + (net, level+momentum -- see DCR variable dictionary) |
| delta_uer_lag1 | 0.6671 | 1.949 | 2.97e-194 | + | uer_chg4_lag1 | + |
| hpi_growth_lag1 | -3.3442 | 0.035 | 2.1e-12 | - | hpi_growth_lag1 | - |

### Per-variable rationale (variable-dictionary style)
| variable | transform | timing | economic rationale | expected direction |
|---|---|---|---|---|
| `cr(loan_age, df=5)` | natural cubic spline of loan age | per-month | underwriting-quality burn-in -> peak default risk -> survivor selection (seasoning hump) | hump, peak then decay |
| `fico_s` | `credit_score`/100 | static (origination) | ability/willingness to pay | - |
| `dti_s` | `dti`/10 | static (origination) | debt-service cash-flow strain | + |
| `ltv10` | `updated_ltv`/10, winsorised at 300 | current-month state (collateral indexation, documented DCR-style exception) | equity cushion / negative-equity trigger | + |
| `occupancy_status` | Treatment(ref='P' owner-occ) | static | strategic-default propensity (investor/second-home = less skin in the game) | + for I/S |
| `loan_purpose` | Treatment(ref='P' purchase) | static | cash-out extracts equity (higher risk); no-cash-out refi selects seasoned/improved borrowers (lower risk) | + for C, - for N |
| `channel` | Treatment(ref='R' retail) | static | origination-control agency problem (broker/correspondent/TPO historically riskier than retail) | + for B/C/T |
| `uer_lag1` | state unemployment rate, lag 1 month | lag 1mo | cash-flow shock channel | + |
| `delta_uer_lag1` | 1-month change in state UER, lag 1 month | lag 1mo | labour-market momentum | + |
| `hpi_growth_lag1` | state HPI log-growth, lag 1 month | lag 1mo | collateral/equity-building channel | - |

**Fitted signs vs the priors above -- misses, stated rather than left for the reader to find**: `C(occupancy_status, Treatment(reference='P'))[T.S]` fitted -0.193 against a prior of +; `C(loan_purpose, Treatment(reference='P'))[T.N]` fitted +0.270 against a prior of -; `C(channel, Treatment(reference='R'))[T.C]` fitted -0.234 against a prior of +. All are CONDITIONAL effects (given FICO/DTI/updated-LTV/macro), so a flipped categorical sign reads as composition within this sample, not a causal claim -- e.g. second-home borrowers who clear the same FICO/LTV bar as owner-occupants default less here, and correspondent loans in this Freddie sample are not the pre-crisis wholesale book the prior describes. The core risk drivers (FICO -, DTI +, updated LTV +, UER +, delta-UER +, HPI growth -) all match their priors.

## 3. COVID / forbearance regime handling
The champion fit above (train <= 2016-12) never sees COVID rows, so it needs no regime handling by construction -- COVID lands in its OOT. To actually test regime treatments we extend the estimation window to performance month <= 2021-09-01 (train + pre-COVID OOT + the forbearance window itself) and fit three variants, all scored (never re-fit) on the identical, genuinely unseen OOT2 window (performance month > 2021-09-01):

| variant | estimation window | OOT2 AUC |
|---|---|---:|
| naive | <= 2021-09-01  | 0.7553 |
| additive | <= 2021-09-01  | 0.7547 |
| exclude | <= 2021-09-01 (covid rows excluded from likelihood) | 0.7509 |

What the fitted numbers actually show (`outputs/freddie/hazard/covid_coefficient_comparison.csv`, per-variant calibration CSVs, `covid_calibration_comparison.png`):
- **naive**: the forbearance window destroys the structural macro block -- `delta_uer_lag1` flips sign to -0.204 (champion +0.667) and `hpi_growth_lag1` collapses to +0.013 (champion -3.344). Unconditionally it is the best-calibrated variant on the true OOT2 years (obs/pred 1.31-1.44 across 2022-2025) -- but with inverted macro sensitivities it cannot be used for scenario-conditional (IFRS-9) projection.
- **additive**: the regime dummy fits +1.482 (hazard ratio 4.40) -- POSITIVE, i.e. it is absorbing the 2020 D90 spike the distorted macro terms fail to carry, not a clean 'forbearance suppression' lever. It has the best 2020 in-window calibration (obs/pred 1.22 vs naive 2.23), but the dummy does NOT repair the structural block: `delta_uer_lag1` stays sign-flipped at -0.130 and `hpi_growth_lag1` overshoots to -6.584 (exclude: -3.307). A calendar-level dummy cannot undo a joint covariate-outcome distortion (the UER spike and the forbearance-shielded delinquency ladder co-move inside the window).
- **exclude**: the only variant whose structural macro block survives -- `delta_uer_lag1` +0.774, `hpi_growth_lag1` -3.307, `uer_lag1` +0.108 (champion: +0.667 / -3.344 / +0.095). Scored THROUGH the window it saturates exactly like the champion (2020 obs/pred 0.06) because it never sees the regime.

**Recommendation (follows the numbers above)**: prefer **exclude** for any structural or scenario-conditional use -- it is the only treatment that preserves economically-signed macro coefficients, and it is consistent with the champion itself (whose train window pre-dates COVID by construction). The OOT2 AUC spread (naive 0.7553 / additive 0.7547 / exclude 0.7509) is too small to override that structural argument. The additive dummy is NOT recommended as previously argued: its own coefficient table shows the dummy fails to keep the structural terms near exclude's (the sign flip on `delta_uer_lag1` persists), so 'the dummy is doing its job' is contradicted by the fit. Handle any future forbearance-style regime as an explicit scoring overlay rather than an in-likelihood dummy. Residual caveat shared by ALL variants: 2022-2025 observed hazard runs ~1.62-1.79 times predictions (exclude variant) -- a post-COVID level shift to hand to the backtest/ECL-overlay stage, not something the regime treatment fixes.

## 4. Discrimination & seasoning
- Champion train AUC: **0.8536** (floor 0.65). OOT AUC: **0.6847**. McFadden pseudo-R2 (fit sample): 0.1197.
- Seasoning curve: `seasoning_curve.png` (natural cubic spline, other covariates held at champion-train medians / modal categories).
- State-macro effect: `state_uer_effect.png` + `.csv` -- predicted vs observed hazard by state `uer_lag1` quartile, scored on OOT rows.
- Calibration by calendar year (champion, full panel): `calibration_by_year.png` + `.csv`.
- **Seasoning caveat (checked against the raw panel)**: the EMPIRICAL train-window hazard-by-age profile is a single hump peaking in the 42-48mo bin (0.256% monthly), consistent with the DCR champion's ~12-quarter peak. The fitted reference-row curve shows an ADDITIONAL, higher peak near 108mo that the raw profile does not: train rows with age >= 96mo come exclusively from the 2005-2008 crisis vintages (later vintages are too young by 2016-12), so the spline's late-age rise is unobserved cohort quality absorbed into the age baseline, not a seasoning effect. Ages beyond 143mo (max train age) in the exhibit are natural-spline linear extrapolation with no train support. Treat the baseline beyond ~96mo with caution when projecting.
- **2020 calibration row** (observed 0.3570% vs predicted 4.1618% monthly): the champion scores straight through the forbearance window with pre-COVID coefficients; the April-2020 state UER jumps (~+10pp month-on-month) enter `delta_uer_lag1` (coef +0.667, i.e. ~+7 on the linear predictor) and saturate the cloglog. Macro extrapolation, not a data or code error -- the regime treatments in Section 3 exist precisely for this.

## 5. Stability check (second seed) & WESML inference caveat
Refit on an independent control-sample seed (1234 vs 42): sign flips = 0; max relative coefficient difference = 0.486, on `cr(loan_age, df=5)[3]` (a near-zero coefficient, where a relative measure overstates) (`outputs/freddie/hazard/seed_stability.csv`).

Macro-term absolute swings between seeds: `delta_uer_lag1` 0.128 vs nominal SE 0.0224 (~5.7x), `hpi_growth_lag1` 0.830 vs nominal SE 0.4759 (~1.7x). This is the expected WESML caveat, stated honestly: `freq_weights` scales the 5% control subsample back to population size, so the reported SEs/p-values approximate a FULL-population fit and exclude the Monte-Carlo noise of which controls were sampled (Manski-Lerman point estimates are consistent; their asymptotic variance needs a sandwich that this exhibit does not report). For macro terms, read `seed_stability.csv` -- not the nominal p-values -- as the operative uncertainty statement; all substantive conclusions here rest on signs and magnitudes that dwarf both noise measures.

## 6. Simplifications (declared)
- Only the DEFAULT (D90) cause-specific hazard is fit; no competing-risk prepayment hazard in this refit (unlike the DCR champion's dual-hazard framing).
- No double-trigger (LTV x UER) interaction term (the spec's covariate-family list for this refit omits it).
- Case-control (WESML) subsampling of control rows at 5% rather than a full-population fit (39.5M rows is impractical to fit directly in this environment's memory budget); every event row is always kept.
- Reference-row seasoning curve uses champion-train MEDIAN covariates, not a fitted population-average marginal effect.
- COVID three-way comparison uses an extended estimation window (through 2021-09) rather than the champion's train window, because COVID postdates champion-train entirely -- documented above.
