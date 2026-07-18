---
title: SFLLD Models (Phase B)
type: module
status: active
aliases: [freddie models, rung 3 phase b, sflld hazard, sflld lgd, alfred backtest, lstm challenger]
tags: [freddie, rung3, hazard, lgd, backtest, lstm]
sources:
  - ../outputs/freddie/hazard/hazard_report.md
  - ../outputs/freddie/lgd/lgd_report.md
  - ../outputs/freddie/backtest/backtest_report.md
  - ../outputs/freddie/gate_phaseB.md
code:
  - ../freddie/fit_hazard.py
  - ../freddie/lgd.py
  - ../freddie/fit_lgd.py
  - ../freddie/backtest.py
  - ../freddie/lstm.py
  - ../freddie/fit_lstm.py
  - ../tests/test_freddie_hazard.py
  - ../tests/test_freddie_lgd.py
  - ../tests/test_freddie_backtest.py
  - ../tests/test_freddie_lstm.py
links:
  uses: [SFLLD Panel (Rung 3)]
  derived-from: [Hazard Model, LGD Model]
---

# SFLLD Models (Phase B)

Four reviewed models on the 837k-loan/39.5M-loan-month SFLLD panel. Gate: **659/659**
(582 baseline + 77 freddie), frozen five NONE, DCR panel sha-identical. Fits survived a
WSL crash storm via checkpointed stages + `_fast_local` ext4 mirroring + per-vintage
chunked frame build (OOM fix at the 12GB VM cap) — all reusable patterns in fit_hazard.py.

## Champion hazard (monthly cloglog, state macro)

Train **AUC 0.8536** / OOT **0.6847** (DCR: 0.748/0.661), McFadden 0.1197. WESML 5%
case-control (Manski-Lerman weights; point estimates re-derived correct; **inference
caveat**: seed A/B macro-coefficient swing up to 5.7× nominal SE — seed_stability.csv is
the honest uncertainty). Seasoning: empirical hump peaks 42–48mo (corroborates DCR's
~12-quarter peak); the spline's late second peak is 2005-08 cohort confounding (documented).
**COVID verdict — EXCLUDE, an overturn**: the author recommended the additive dummy; the
Fable review showed the report contradicted its own numbers (dummy +1.482 didn't repair the
macro block — delta_uer stayed sign-flipped, hpi_growth overshot −6.58 vs exclude −3.31) and
rewrote Section 3 numbers-driven: exclude for structural/scenario use, forbearance as a
scoring overlay. Checkpoint pickles fixed for cross-module loading (_CheckpointUnpickler).

## Realized-loss LGD

Cure AUC train 0.699 / **OOT 0.477 (honest: near-random out-of-time)**; population train
mean realized LGD 0.2715; excess-loss loading **0.0148 vs DCR's 0.0255** — cycle dependence
of severity (2008-12 peak) dominates a constant loading on real workouts. COVID-era D90s
heavily unresolved (selection documented by era).

## ALFRED-vintage honest backtest (the model-risk centerpiece)

As-of fits at 2007-12/2009-12/2015-12/2019-12/2021-12 with real-time macro vintages.
**2007-12: frozen-macro model underpredicted realized 36mo cum-D90 by 9.42×** (0.93% vs
8.75%); hindsight-macro ceiling still 1.90× under — the IFRS9 argument for forward-looking
scenario overlays in one exhibit. 2019-12 hindsight run is degenerately conservative
(0.06× = 71.5% predicted vs 4.6% realized): the +10.6pp April-2020 UER spike × a
coefficient fit on ±0.5pp moves = linear-extrapolation saturation, the twin caveat to the
COVID-exclude verdict. Review fixed a CRITICAL realized-outcome timing bug (disposition
month, not D90 month) and asymmetric zero-risk booking for unscoreable loans.

## LSTM challenger (challenger-never-champion)

OOT AUC **0.9925** vs champion 0.6847 — but the honest decomposition is the story:
loans with a prior-24mo delinquency spell (99.7% of OOT events): LSTM 0.957 vs champion
0.570; clean-history loans: **both near-random** (0.529 vs 0.539, 40 events). Path memory
is delinquency-state memory; it does not see farther ahead on clean books. 2020: champion
overshoots (4.16% vs 0.35% — macro saturation), LSTM undershoots (0.12% — forbearance
shields the ladder it reads). 19/19 tests; GPU (RTX 4060); review: no correctness bugs.
