---
title: LGD Model
type: module
status: active
aliases: [lgd, loss given default model, cure severity model]
tags: [engine, lgd]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../engine/lgd.py
  - ../analysis/fit_lgd.py
  - ../tests/test_lgd.py
links:
  uses: [Loan Panel]
  used-by: [ECL Engine]
  derived-from: [IFRS9 Study Notes]
---

# LGD Model

`engine/lgd.py`: two-stage workout LGD (notes §10) — cure logit × fractional-logit severity
(Papke–Wooldridge), fit on **9,496 resolved train defaults** (11,420 train defaults − 1,921
unresolved workouts − 3 NaN rows). E[LGD] = (1−P(cure)) × (capped severity + excess loading).
Review verdict: fixed (documentation only).

## Key conventions (decision-register material)

- **Resolved workouts only** — unresolved `lgd_time` is not a realised outcome (58% coded 0).
  Selection bias documented: cures resolve faster, so fitted cure is biased up near window end.
- **Excess-loss loading**: 14.2% of train non-cure LGDs exceed 1 (max 3.17, real workout costs);
  capped at 1 inside the link, truncated-mean mass **+0.0255** added back explicitly — never
  clipped. OOT realised excess 0.0236 validates the loading.
- Cure = lgd ≤ 0.05 (labelling convention; decomposition near-invariant at 0.0/0.05/0.10).
- Honest anomaly: cure-stage `uer_lag1` is POSITIVE (+0.277) — conditional on updated LTV,
  stress-cohort defaulters cure more; robust in fixed-runway subsample; disclosed, not asserted.

## Fit quality

Cure AUC 0.837 train / 0.769 OOT. Calibration: train gap −0.0005; OOT +0.047 (conservative,
within 0.05 tolerance; decomposed honestly in `outputs/lgd/lgd_report.md`). Signs asserted at fit
time: cure ↓LTV (−0.764), severity ↑LTV (+0.107) — the collateral channel.
