---
title: Loan Panel
type: module
status: active
aliases: [panel builder, loan-month panel, build_panel]
tags: [engine, data]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../data/panel/build_panel.py
links:
  implements: [Master Plan]
  derived-from: [IFRS9 Study Notes]
  used-by: [Hazard Model]
---

# Loan Panel

`data/panel/build_panel.py` → `data/processed/panel.parquet`: 622,489 raw DCR rows → **621,736
eligible loan-quarters** (49,974 loans, 46 cols), with every one of the 753 dropped rows itemized in
`outputs/panel/waterfall.md` (7 steps: verbatim duplicates, 5 id-collision loans, same-quarter
status conflicts, post-terminal guard (0), missing-key, 18 zero-origination-balance loans, range
checks). Events reconciled exactly: 15,147 defaults + 26,580 payoffs kept; every lost event is a
counted waterfall line.

Key facts (adversarially re-verified, review clean):

- **Updated LTV** = LTV_orig × (bal_t/bal_orig) × (hpi_orig/hpi_t) — derived from first principles
  and equal to the vendor's `LTV_time` to 5e-9 (the vendor column is exactly this formula).
- **Macro lags** (uer_lag1/2, uer_chg4_lag1, gdp_lag1, hpi_growth_lag1) built with zero lookahead;
  groupby-shift agreement asserted to 1e-9; 3,343 warm-up rows flagged.
- **Split**: train t≤40 (421,761 rows, 11,420 defaults) / OOT t=41–60 (199,975 rows, 3,727
  defaults) — OOT is the stress window by construction.
- Flags kept, not dropped: `orig_rate_missing` (21.4% of loans, rate coded 0), 2,829 missing-state
  rows. Left truncation: first observed quarter == first_time for every loan.
- `lgd_time` populated iff default row (15,147); 9.8% of realised LGDs exceed 1 (max 8.52) — kept
  raw for [[LGD Model]] to handle explicitly.
