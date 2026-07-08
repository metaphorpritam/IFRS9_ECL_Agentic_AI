---
title: Hazard Model
type: module
status: active
aliases: [PD model, cloglog hazard, default hazard, PD, default probability]
tags: [engine, pd]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../engine/__init__.py
  - ../engine/hazard.py
  - ../analysis/fit_hazard.py
  - ../analysis/eda_suite.py
links:
  uses: [Loan Panel]
  implements: [Master Plan]
  derived-from: [IFRS9 Study Notes]
---

# Hazard Model

`engine/hazard.py`: discrete-time **cloglog** hazards (grouped-duration analogue of continuous-time
Cox), cause-specific competing risks (default + prepayment). API: `fit_default_hazard(panel)`,
`fit_prepay_hazard(panel)`, `predict_hazard(model, df)`, `pd_term_structure(models, profiles,
horizon)` → conditional λ_t, competing-risk survival S(t), marginal S(t−1)λ_t, cumulative PD.

## Fit (train t≤40; exhibits in outputs/hazard/)

- Default: train AUC 0.748, **OOT AUC 0.661** (OOT = the stress window — honest degradation).
  Prepay: 0.684 / 0.584. McFadden R² 0.076 / 0.050.
- Age baseline: natural spline; fitted seasoning peak 12q vs empirical 10q — hump reproduced.
- All economic signs pass: PD ↓FICO ↑LTV; net unemployment shock +1pp → hazard ratio **1.28**
  (level −0.367 + 4q-momentum +0.614 under 0.94 collinearity — quote the NET effect, never the
  level coefficient alone). Prepay ↑incentive (Spearman 0.95 in EDA).
- Double trigger (ltv × uer): −0.006 (p=.04) — slight in-sample substitution; main effects +
  momentum already carry the joint stress response. Reported honestly; interview story in
  `outputs/hazard/fit_stats.md`.

## TIMING CONVENTION (review-enforced)

Macro *regressors* are all lagged. Two deliberate current-quarter state variables: `updated_ltv`
(collateral indexation by current HPI) and `prepay_incentive` (real-time market rate — lagging
would misprice the option). Documented in the module docstring; any future covariate must follow
the same rule.

## EDA verification (outputs/eda/, 5 PASS / 0 FAIL / 1 INFO)

Seasoning hump peak age 10; vintage worst = HPI-peak cohorts (48.8% = 2.4× median); prepay
monotone in incentive; LGD bimodal (20.6% exact cures). Roll-rate/cure chart impossible at this
rung (no delinquency ladder) — deferred to Freddie rung 3.
