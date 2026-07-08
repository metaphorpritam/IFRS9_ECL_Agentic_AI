---
title: ECL Engine
type: module
status: active
aliases: [ecl, allowance engine, movement decomposition, waterfall, provision, reserve]
tags: [engine, ecl, gate]
sources:
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
code:
  - ../engine/ecl.py
  - ../analysis/run_ecl.py
  - ../tests/test_ecl.py
links:
  uses: [Hazard Model, LGD Model, EAD Model, Staging Model]
  implements: [Master Plan]
  derived-from: [IFRS9 Study Notes, Golden Fixtures]
---

# ECL Engine

`engine/ecl.py`: ECL = Σ S(t−1)·λ_t·LGD_t·EAD_t·(1+EIR_q)^−t through ONE shared survival/marginal
kernel used by both the fixture-facing `ecl_schedule` and the vectorised snapshot path — so the
golden-fixture test **pins the production algebra** (12m €4,952.83 / lifetime €16,571.39 matched to
rel 1e-12 through engine functions). Both 12m and lifetime always computed; reported allowance =
12m (S1) / lifetime (S2/3). Review verdict: **clean**.

## Headline numbers (outputs/ecl/)

- t=20 calm: 8,662 loans, EAD $1.92bn, allowance $24.5m, coverage 1.28%.
- t=40 stress: 13,863 loans, EAD $3.64bn, allowance **$1,032.6m, coverage 28.4%** (22× calm).
  Coverage gradient S1 3.55% < S2 31.27% < S3 63.65% — sanity gates pass.
- Movement waterfall t=20→t=40 ($m): opening 24.5 → stage migration +3.9 → remeasurement +26.0 →
  derecognitions −21.2 → new loans +999.4 → closing 1,032.6; **identity residual < $0.01**.
- Cross-check gates: ECL marginal-PD grid == staging lifetime PD on every loan (4e-16); LGD grid ==
  predict_components (2e-16). Full book runs in under a second per snapshot.

## GATE (frozen 2026-07-05)

**PASSED**: 187/187 tests (133 golden fixtures + 16 EAD + 8 LGD + 16 staging + 14 ECL); fingerprint
tripwire baselined and verified (`knowledge/code_fp.json`, re-scan all NONE); `outputs/gate/
gate_report.md` records the frozen-engine rule: any post-gate STRUCTURAL change to `engine/`
requires the full suite re-run plus a decision entry.
