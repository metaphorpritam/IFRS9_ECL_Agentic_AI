---
title: SFLLD Panel (Rung 3)
type: module
status: active
aliases: [freddie panel, rung 3, sflld, freddie mac data]
tags: [freddie, rung3, data, eda]
sources:
  - ../outputs/freddie/ingest/dq_report.md
  - ../outputs/freddie/eda/eda_report.md
  - ../outputs/freddie/gate_phaseA.md
code:
  - ../freddie/ingest.py
  - ../freddie/build_panel.py
  - ../freddie/macro.py
  - ../freddie/eda.py
  - ../tests/test_freddie_ingest.py
  - ../tests/test_freddie_macro.py
links:
  uses: [Master Plan]
  derived-from: [Loan Panel]
---

# SFLLD Panel (Rung 3)

Freddie Mac Single-Family Loan-Level Dataset, 17 sample vintages (2005-2010, 2014-2016,
2018-2025; 2011-2013 + 2017 not downloaded — documented gap). Real calendar dates, real
property states, real workout losses — the three upgrades over DCR. **Fully isolated
namespace** (`freddie/` package, `outputs/freddie/`, `data/processed/freddie/`,
`tests/test_freddie_*`): Phase-A gate verified frozen five NONE, DCR panel.parquet
untouched (sha recorded), 553/553 tests (513 baseline + 40 freddie).

## Panel (freddie/ingest.py, build_panel.py)

837,500 loans; 39,522,565 modeled loan-months. Default = **D90 absorbing** (first 90+ DPD
or straight-to-RA; panel truncates after the event month even if the raw tape later cures —
unit-tested on a real curing loan). Same-row D90/terminal-code tie-break: disposition wins
(~0.1-0.2% of loans). Liquidation codes + realized-loss fields kept on `loan_orig.parquet`
from the UN-truncated tape for competing-risks/LGD. Sentinels (9999/999/99/'9') → NaN,
each documented. Field layout verified against Freddie's live User Guide + empirically on
all 17 zips. Loan-level rates: D90 5.32%, prepay 58.93%. Review verdict *fixed*
(terminal-outcome fall-through guard; '06' repurchase absent from current spec — documented).

## State macro (freddie/macro.py)

FRED per state: {POSTAL}UR monthly + {POSTAL}STHPI quarterly (all-transactions), 54
states/territories in book; national fallback GU/VI (UR) and GU/PR/VI (HPI), documented.
108 cached CSVs → offline reruns. No-lookahead quarterly→monthly HPI fill; lag-1 columns
mirror the DCR timing convention; state-level `updated_ltv` (NV 2006 loan 80→114+ by 2009;
NV 2010 loan 44→~20 by 2019). Review verdict **clean** (live FRED spot-checks matched).

## EDA headlines (outputs/freddie/eda/)

- Vintage curves: 2007 cum-D90 **16.26%**, 2006 14.11%, 2008 9.14%; every recovery/modern
  vintage < 5.48%. Prepay curves show the 2020-21 refi wave.
- **COVID forbearance regime, quantified in roll rates**: 60→90+ WORSE than GFC (58.25%
  vs 47.43% — the ladder keeps climbing contractually under forbearance) while
  90+→liquidation collapses >10× (0.21% vs GFC 2.02% — CARES foreclosure moratorium);
  75.9% of COVID 60/90+ loans carry active borrower-assistance vs 15.6% calm.
- Combined D90-entry peak is the COVID spike (1.775% 2020-06, ~4.5× the GFC's 0.396%
  2009-10) — a naive dlq-based read calls COVID the bigger credit event; it wasn't a
  loss event. **Phase-B caution: COVID window needs exclusion/regime handling.**
- State heterogeneity (2006-07 vintages): NV 38.0% / FL 32.6% / AZ 27.9% vs VT 4.8%;
  drawdown-vs-default scatter = the collateral channel in real geography.
- Realized LGD first look: reviewer corrected the report's claimed "2008-2011 severity
  peak then decline" to match the code's actual yearly numbers (see eda_report.md).

## Phase B (not started)

Hazard/LGD refit on SFLLD with state macro, ALFRED-vintage honest backtest, LSTM
challenger candidate. COVID regime handling is the recorded design question.
