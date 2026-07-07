---
title: Variable Dictionary
type: concept
status: active
aliases: [feature dictionary, variable rationale, feature glossary]
tags: [documentation, mdd, features]
sources:
  - ../outputs/variable_dictionary.md
links:
  relates: [Hazard Model, LGD Model, Staging Model, Scenario Layer, Loan Panel]
---

# Variable Dictionary

The consolidated per-variable exhibit required by the operator's documentation standard (decision
2026-07-05): **source column → transformation → lag/window → economic rationale → expected vs
fitted sign → consuming model**, for every variable in the hazard, LGD, staging, satellite, and
scenario models. Canonical table: [`outputs/variable_dictionary.md`](../../outputs/variable_dictionary.md).

Key conventions it encodes: data window 2000Q2–2015Q1 (train ≤2010Q1); all macro regressors lagged;
two flagged current-quarter state variables (updated LTV = collateral indexation, prepay incentive
= real-time option value); national-macro limitation with the rung-3 state-level upgrade path;
every fitted sign verified against the expectation at fit time or disclosed as an anomaly (the
positive cure-stage unemployment coefficient, the double-trigger substitution effect).
