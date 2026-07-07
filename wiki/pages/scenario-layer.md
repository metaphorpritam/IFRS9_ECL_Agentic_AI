---
title: Scenario Layer
type: module
status: active
aliases: [vasicek, satellite, scenarios, jensen exhibit, credit cycle]
tags: [engine, scenarios, day3]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
  - ../outputs/variable_dictionary.md
code:
  - ../engine/vasicek.py
  - ../engine/scenarios.py
  - ../engine/satellite.py
  - ../data/ingest/dfast.py
  - ../analysis/fit_vasicek.py
  - ../analysis/run_scenarios.py
  - ../challenger/mlp.py
  - ../analysis/fit_challenger.py
  - ../tests/test_vasicek.py
  - ../tests/test_scenarios.py
  - ../tests/test_satellite.py
  - ../tests/test_challenger.py
links:
  uses: [Hazard Model, ECL Engine, Loan Panel]
  implements: [Master Plan]
  derived-from: [IFRS9 Study Notes]
---

# Scenario Layer

Day-3 build (all adversarially reviewed; gate PASS 278/278, frozen five byte-identical to d3ea14f).

## Vasicek/Z (engine/vasicek.py — review clean)

Composition-adjusted Belkin: observed vs expected quarterly default RATES (frozen hazard, macro at
panel means) → invert → **ρ = 0.0227** (orig-LTV variant 0.0633; both far below 0.12 notes / 0.15
Basel — regulatory ρ is conservatism, not time-series fit). Z trough **2008Q1 (−2.74)**; anchor
E_Z[PD_PIT]=PD_TTC proven to 1e-17; mean(Z)=−1.145 level gap documented (absorbed by satellite
intercept). Credit-cycle exhibit with real calendar axis: `outputs/vasicek/credit_cycle.png`.

## Scenarios (engine/scenarios.py + data/ingest/dfast.py — review clean)

DFAST 2026 paths as **deltas rebased onto the 2015Q1 jump-off** (severe +5.5pp UER preserved
exactly); upside = damped mirror ×−0.35; reversion to long-run means by q21, 40q horizon; weights
50/25/25.

## Satellite + scenario ECL (engine/satellite.py — review FIXED report-integrity issues)

Z = −1.694 + 13.642·hpi_growth_lag1 + 0.730·gdp_growth_lag2 (n=57, AIC-selected from 26 specs, full
grid published after review). Scenario ECL (t=60 book, 7,849 exposures): upside $27.7m / base
$30.5m / severe $47.6m. **Jensen: weighted $34.0m vs $32.9m at averaged path = 1.035×** — direction
proven, magnitude honestly decomposed vs the notes' 1.9× toy (ρ 5× smaller, gentler Z spread,
PD-leg-only conditioning, lifetime dilution): `outputs/scenario_ecl/jensen_gap.png`.

## Challenger (challenger/mlp.py — review clean)

torch 2.12.1+cu130 on RTX 4060; like-for-like covariates (12/12 programmatic match). **Champion
wins OOT** (0.661 vs 0.642) though challenger wins in-sample (0.763 vs 0.748) — the empirical
justification for challenger-never-champion. Scorecard: `outputs/challenger/scorecard.md`.

See [[Variable Dictionary]] for every variable's source/transformation/window/sign.
