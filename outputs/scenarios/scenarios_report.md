# Scenario set — DFAST 2026 ingestion and the base/down/up paths

Reporting date: panel t=60 ~ 2015Q1 (calendar anchoring verified
vs FRED UNRATE, corr 0.9963). Horizon: 40 quarters
(2015Q2 .. 2025Q1).
R&S window: 13 quarters (the DFAST 2026 path length);
reversion: 8 quarters, linear, to the panel long-run means; hold thereafter.

## DFAST column -> panel concept -> transformation

| DFAST column | Panel concept | Transformation |
|---|---|---|
| Unemployment rate | `uer` (pp) | level, as-is |
| House Price Index (Level) | `hpi_growth` (decimal/q) | quarterly log-diff; 2026Q1 differenced against the last historic actual (2025Q4 level 323.4) |
| Real GDP growth (SAAR %) | `gdp_growth` (%/q) | `100*((1+g/100)^(1/4)-1)` — SAAR de-annualised to a plain quarterly rate |
| Mortgage rate | `mortgage_rate` (pp) | level, as-is |

Panel-side concept construction: `uer_time` / `hpi_time` / `gdp_time` are
national series (constant within quarter); `rate_time` varies mildly across
loans, so its quarterly MEDIAN is the market-rate level (the
`engine.staging.build_macro_map` convention). The panel's `gdp_time` is
YEAR-OVER-YEAR growth (2009 trough -4.15, matching YoY, not the -8.5 SAAR
trough) and is converted with the same fourth-root formula — the intra-year
quarterly profile is unidentified from YoY alone (documented simplification).

## Rebasing convention (shape transplant)

The panel ends ~2015Q1; the DFAST 2026 paths run 2026Q1-2029Q1. DFAST's value
is the supervisor-designed COHERENT multivariate shape, so each variable's
change-from-jump-off (jump-off = 2025Q4 actuals) is added to the panel's t=60
level:  `scenario_h(c) = panel_t60(c) + (dfast_h(c) - dfast_2025Q4(c))`,
uniformly across level and growth concepts. This preserves DFAST co-movement
exactly (severe UER peak-minus-jump-off stays +5.5pp) while anchoring at the
reporting-date macro state. It is a shape transplant, not a 2015-vintage forecast.

| Concept | Jump-off (t=60) | Long-run panel mean (reversion target) |
|---|---|---|
| uer (pp) | 5.70 | 6.39 |
| hpi_growth (%/q) | 1.15 | 0.96 |
| gdp_growth (%/q) | 0.70 | 0.46 |
| mortgage_rate (pp) | 4.62 | 4.63 |

## Scenarios and weights

| Scenario | Construction | Weight |
|---|---|---|
| base | DFAST Supervisory Baseline deltas, rebased | 0.50 |
| down | DFAST Severely Adverse deltas, rebased | 0.25 |
| up | judgmental damped mirror of the severely-adverse deltas, factor -0.35; UER floored at 3.5pp | 0.25 |

**Why 50/25/25 is judgmental and why that is fine (plan section 2.6):**
scenario probabilities are not statistically identified — there is no dataset
of "how likely was the severe scenario". Banks set them by governance
committee and document the rationale; auditors test the documentation, not
the number. The deliverable is this rationale plus weight-sensitivity
exhibits downstream, not the number itself. **Named enhancement:** anchor the
weights (and the upside path itself) to Philadelphia-Fed SPF forecaster-
distribution percentiles — e.g. take the upside from the 25th percentile of
the SPF unemployment distribution instead of the -0.35 mirror.

**Upside convention:** DFAST publishes no upside. The damped mirror
(-0.35 x severe deltas) inherits DFAST's multivariate coherence; damping
encodes the empirical asymmetry of the cycle (booms are shallower than
busts). Result: a mild boom — UER drifts to ~3.78pp
(floor 3.5pp, not binding), HPI appreciates ~3.6%/q at peak.

**Beyond the R&S window (notes section 9.4):** macro paths are reasonable and
supportable only over the 13q DFAST window; each path then reverts linearly
over 8 quarters to the panel's own long-run means and holds — the standard
"PIT over the R&S window, revert to TTC" construction. All three scenarios
share the same long-run tail, so scenario differentiation lives entirely in
the 13q path + 8q ramp. Jensen caution (notes section 9.2): downstream ECL is
the weighted average of per-scenario ECLs, never the ECL of the weighted path.

## Exhibits

* `fan_uer.png` — unemployment fan; severe peak 11.2pp (+5.5pp vs jump-off).
* `fan_hpi_growth.png` — quarterly HPI-growth fan; severe trough -5.8%/q.
