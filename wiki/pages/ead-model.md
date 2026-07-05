---
title: EAD Model
type: module
status: active
aliases: [ead, exposure at default, amortisation engine]
tags: [engine, ead]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../engine/ead.py
  - ../analysis/ead_exhibits.py
  - ../tests/test_ead.py
links:
  uses: [Loan Panel]
  used-by: [ECL Engine]
  derived-from: [IFRS9 Study Notes]
---

# EAD Model

`engine/ead.py`: **contractual** level-payment amortisation profiles (quarterly compounding from
the note rate; straight-line fallback for the `orig_rate_missing` loans and degenerate tiny rates —
review-hardened guard `1+r_q > 1`). `ead_matrix(snapshot, horizon)` → per-loan paths.
`ccf_ead(drawn, limit, ccf)` for revolvers reproduces the €14.0m fixture through the engine path.

**The double-counting rule (binding, stated in every consumer):** ECL survival S(t) already
includes prepayment survival, so EAD must be the CONTRACTUAL balance path — never prepay-scaled.
Review verdict: fixed (edge-case guard only). 16 tests green.
