---
title: Staging Model
type: module
status: active
aliases: [staging, SICR, stage allocation]
tags: [engine, staging, sicr]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../engine/staging.py
  - ../tests/test_staging.py
links:
  uses: [Loan Panel, Hazard Model]
  used-by: [ECL Engine]
  derived-from: [IFRS9 Study Notes]
---

# Staging Model

`engine/staging.py`: genuinely **relative** SICR — lifetime PD *now* vs lifetime PD *at
origination* over the **same remaining life** (review confirmed both legs to 1e-10 against
independent term-structure runs; the classic lifetime-from-origination bug explicitly refuted).
Configurable `StagingConfig`: ratio threshold (default 2×), absolute add-on (0.5pp annualised),
probation 2q, 30 DPD backstop hook (**inert here — DCR has no delinquency ladder**; documented).

## Findings (t-snapshots; exhibits in outputs/staging/)

- t=20 (calm): Stage 1 98.9%, **Stage 2 0.0%**, Stage 3 1.1% (= default incidence exactly).
  Stage 2 empty at the 2×+0.5pp config in calm conditions — a threshold-sensitivity insight, not a
  bug; the sensitivity exhibit (1.5/2/3/4×) is the governance dial.
- t=40 (stress): Stage 1 21.0%, **Stage 2 75.8%**, Stage 3 3.25% — the relative test fires
  book-wide when lifetime PDs re-mark against origination.
- Book size grows toward mid-panel (8,662 staged loans at t=20 vs 13,863 at t=40) — vintage
  concentration near the HPI peak, consistent with EDA.

Review verdict: fixed (custom dpd_col config plumbing bug + a docstring overclaim). 16 tests green.
