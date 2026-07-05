# EDA verification suite — expected-vs-observed verdicts

Generated 2026-07-05T06:50:12+00:00 by `analysis/eda_suite.py` on `data/processed/panel.parquet` (621,736 loan-quarter rows, 49,974 loans, 15,147 defaults, 26,580 payoffs, time 1..60 abstract quarterly clock).

Every chart is a TEST with a pre-registered expected shape. Result: **5 PASS, 0 FAIL, 1 INFO** (INFO = report-only expectation, no hard assertion by design).

| Exhibit (PNG) | Expected | Observed | Verdict |
|---|---|---|---|
| 1 default_rate_vs_macro | default rate co-moves with unemployment / HPI stress: corr(default rate, uer level) > 0 AND the default-rate peak quarter falls inside the HPI-drawdown stress window | corr = +0.362; default rate peaks 5.07%/qtr at t=37 inside the stress window t=31..60 (contiguous; uer peak 10.0% at t=39, max HPI drawdown -35.3% at t=48) | **PASS** |
| 2 hazard_by_loan_age | hump shape: peak in mid-life, i.e. NOT in the first two nor the last five age quarters of the exposure-credible grid | peak at age 10 (grid position 11 of 50, ages 0..49); hazard rises 1.11% -> 4.13% then declines to 1.37% | **PASS** |
| 3 vintage_cumulative_default | cohort separation asserted: worst cohort >= 1.5x the median cohort's terminal incidence; worst cohorts originated just before the stress episode (HPI peak t=25, stress window from ~t=29) | worst cohort = orig t 25..29 with 48.8% cumulative default incidence = 2.4x the median cohort (20.8%); ranking: t25..29=48.8%, t30..34=48.8%, t20..24=31.4%, t0..4=24.1% (pre-window cohorts are left-truncated; incidence = defaults / cohort loans, competing payoff risk not removed) | **PASS** |
| 4 prepay_vs_rate_incentive | monotone-increasing prepayment hazard in the incentive: strong rank correlation across ordered bins (Spearman rho >= 0.7, not merely > 0) AND top bin hazard above bottom bin hazard | Spearman rho = +0.952 (p = 2.3e-05) across 10 bins; hazard 0.78% -> 5.85%/qtr from deepest out-of-the-money to deepest in-the-money bin (mild local dip over incentives 1.0-2.0pp; ranking otherwise clean) | **PASS** |
| 5 origination_quality | FICO left-skewed within 400-840; LTV massed near 80 with a tail above 100 (max 218.5 exists); rates in plausible range — anomalies reported rather than hard-asserted | FICO in [400, 834] (within 400-840), skew -0.17 (left-skewed); LTV mode 80, 57% of loans in [75, 85], 99 loans (0.20%) above 100, max 218.5 (the documented 218.5); positive origination rates in [0.95, 19.75]%. ANOMALY reported (not asserted): 10,713 loans (21.4%) have Interest_Rate_orig_time missing-coded as 0 — retained upstream with flag orig_rate_missing; the current note rate drives the prepay incentive instead | **INFO** |
| 6 lgd_realised_bimodal | bimodal (cure spike near 0, write-off hump at high loss; notes Fig 8): meaningful mass below 0.1 AND above 0.4 (>= 10% each); values outside [0,1] reported, not clipped | 25.6% of 15,147 defaults below 0.1 (20.6% exactly 0) and 59.7% above 0.4; out-of-[0,1]: 0 negative, 1,478 rows (9.8%) above 1 (max 8.52) — plotted range truncated at 1.5 for readability with the 100-row tail annotated, underlying data untouched. Panel has 15,147 default rows vs 15,158 raw: 11 rows removed by the reviewed eligibility waterfall (duplicate copies + id collisions + zero-balance-origination loans; see outputs/panel/waterfall.md) | **PASS** |

## Out of scope at this rung

**Roll-rate / cure-rate chart: OUT OF SCOPE.** The DCR panel carries no delinquency ladder — `status_time` takes only 0 (performing), 1 (default) and 2 (payoff), so current -> 30 -> 60 -> 90+ roll rates and cure transitions are unobservable here. Documented simplification (see `data/panel/build_panel.py` docstring and MASTER_PLAN.md); deferred to the Freddie Mac rung (rung 3), whose monthly performance file has the full delinquency ladder.

## Method notes

- Default/payoff hazards are computed on at-risk loan-quarter rows (discrete-time hazard convention, notes §6.2); the panel is already truncated at each loan's first terminal event by the build waterfall.
- Left truncation (orig_time down to -40) and right censoring (loans alive at t=60) are first-class: vintage curves flag that pre-window cohorts miss their earliest ages; the seasoning grid is restricted to ages with >= 500 at-risk rows so sparse old ages cannot fake a peak.
- Vintage cumulative incidence = cohort defaults by age / cohort loans (competing payoff risk not removed — standard vintage exhibit, stated on the chart caption side).
- Chart 1 uses stacked shared-x panels instead of a dual y-axis (one-axis rule); the stress band is HPI drawdown < -10%.
- No values were clipped or dropped by this suite; LGD > 1 and the missing-coded origination rates are reported as findings.

Exit code contract: 0 iff no FAIL row above.