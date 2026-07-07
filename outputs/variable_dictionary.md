# Variable Dictionary — every modelled variable: source, transformation, window, rationale, fitted sign

Data window: panel quarters t=1..60 ≙ **2000Q2–2015Q1** (calendar anchoring verified vs FRED UNRATE, corr 0.996).
Train = t≤40 (2000Q2–2010Q1); OOT = t=41–60 (2010Q2–2015Q1, the stress aftermath). All fits on train only.
Macro series are US **national** (state-level upgrade = Freddie rung 3). Timing convention: every macro
*regressor* is lagged; the two deliberate current-quarter **state variables** are flagged ⚡ below.

| Variable (model name) | Source → transformation | Lag / window | Economic rationale | Expected sign | Fitted (verified) | Consumed by |
|---|---|---|---|---|---|---|
| `fico_s` | `FICO_orig_time` / 100 | static (origination) | Ability/willingness to pay | PD ↓ | ✓ negative | default hazard; LGD cure |
| `ltv10` ⚡ | `updated_ltv`/10 = LTV_orig × (bal_t/bal_orig) × (hpi_orig/hpi_t), winsor 300 | current-quarter state (collateral indexation, documented exception) | Equity cushion / strategic-default trigger; = vendor `LTV_time` to 5e-9 | PD ↑, severity ↑, cure ↓ | ✓ all three (sev +0.107/10pp, cure −0.764) | default hazard; LGD both stages; staging legs |
| `loan_age` | `time − orig_time` → natural cubic spline (hazard) / linear (LGD) | per-quarter | Seasoning baseline; underwriting → trouble → survivor selection | hump | ✓ peak 12q fitted vs 10q empirical | both hazards; LGD |
| `prepay_incentive` ⚡ | `interest_rate_time − rate_time` (note − market rate) | current-quarter state (option value is real-time) | Refinancing incentive (competing risk) | prepay ↑ | ✓ (Spearman +0.95) | prepay hazard |
| `investor_orig_time`, RE-type flags | raw origination flags | static | Strategic default propensity (no home to lose) | PD ↑ (investor) | ✓ | default hazard |
| `uer_lag1` | `uer_time` (national level, pp) via within-loan shift | lag 1q | Cash-flow channel (job loss → arrears) | net shock ↑ | ✓ net +1pp → HR 1.28 (level −0.367 + momentum +0.614 under 0.94 collinearity — quote the NET effect) | default hazard; LGD cure (+0.277 disclosed anomaly) |
| `uer_chg4_lag1` | 4-quarter change of `uer_time`, lagged | lag 1q over 4q window | Labour-market momentum | ↑ | ✓ +0.614 | default hazard |
| `hpi_growth_lag1` | Δlog `hpi_time` (national index) | lag 1q | Collateral macro channel | PD ↓ | ✓ | default hazard; satellite (+13.64) |
| `gdp_lag1` / `gdp_growth_lag2` | `gdp_time` growth | lag 1q / 2q | Activity channel | PD ↓ / Z ↑ | ✓ (+0.730 satellite) | default hazard; satellite |
| `dt_ltv_uer` | center(`ltv10`) × center(`uer_lag1`) | mixed | Double trigger (can't pay AND negative equity) | ↑ | −0.006 (p=.04): in-sample substitution; main effects + momentum carry the joint stress — honest finding, see fit_stats.md | default hazard |
| `lgd_time` (target) | vendor realised workout LGD, **resolved workouts only** (`res_time` non-null): 9,496 of 11,420 train defaults | resolution window | Two-stage: cure (≤0.05) × severity; LGD>1 tail (14.2% of non-cures, max 3.17) = constant excess loading +0.0255, never clipped | — | OOT calibration +0.047 (conservative) | LGD |
| `Z_t` (recovered) | Vasicek inversion of observed vs composition-adjusted expected quarterly default rates (frozen hazard, macro at panel means) | 60 quarters | Systematic credit-cycle factor; ρ via Belkin Var(Z)=1 → **ρ=0.0227** (vs 0.12 notes / 0.15 Basel — regulatory ρ is conservatism, not time-series fit); mean(Z)=−1.145 level gap documented | trough in GFC | ✓ trough 2008Q1 (Z=−2.74) | satellite target; PIT conditioning |
| Scenario paths | DFAST 2026 CSVs: UER (pp), HPI level → Δlog, GDP SAAR → quarterly, mortgage rate | 2026Q1–2029Q1 (13q) rebased as **deltas onto the 2015Q1 jump-off**, reversion to panel long-run means by q21, hold to 40q | Coherent supervisory multivariate shapes; upside = damped mirror (×−0.35), weights 50/25/25 (SPF anchoring = named enhancement) | severe ECL > base > upside | ✓ ($47.6m / $30.5m / $27.7m) | scenario ECL |

Model equations live in the module docstrings (cloglog hazard; two-stage LGD; ECL sum; Vasicek PIT
transform with the Gauss-Hermite anchor proof; satellite Z = −1.694 + 13.642·hpi_growth_lag1 +
0.730·gdp_growth_lag2, n=57, with ADF/KPSS/DW/AIC and the GFC-dummy sensitivity in
outputs/satellite/satellite_report.md). Coefficient tables with CIs: outputs/hazard/hazard_ratios.md,
outputs/lgd/lgd_report.md.
