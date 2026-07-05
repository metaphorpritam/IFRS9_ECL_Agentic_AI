---
title: Golden Fixtures
type: module
status: active
aliases: [fixture scripts, compute scripts, gate tests]
tags: [testing, engine, gate]
sources:
  - ../knowledge/corpus/ifrs9_credit_risk_notes.md.md
code:
  - ../tests/test_fixtures.py
  - ../tests/__init__.py
  - ../tests/fixtures/__init__.py
  - ../tests/fixtures/compute_ecl.py
  - ../tests/fixtures/compute_pd.py
  - ../tests/fixtures/compute_vasicek.py
  - ../tests/fixtures/compute_scenarios.py
  - ../tests/fixtures/compute_grossup.py
  - ../tests/fixtures/compute_ncl.py
  - ../tests/fixtures/compute_rollrate.py
  - ../tests/fixtures/compute_validation.py
links:
  derived-from: [IFRS9 Study Notes]
  implements: [Master Plan]
---

# Golden Fixtures

The eight `compute_*.py` verification scripts the [[IFRS9 Study Notes]] cite but never shipped,
recreated 2026-07-05 from the notes' worked examples (8 author + 8 adversarial-review agents; all
verdicts clean, no hardcoding). **133/133 values reproduce** via `uv run pytest tests/`.

Interface: each module derives `RESULTS: dict[str, float]` from the worked example's stated inputs
and holds the notes' printed values in `TARGETS`; `tests/test_fixtures.py` asserts agreement within
one unit of the last displayed digit (the notes round or truncate for print).

## Coverage (script → worked example → headline values)

- **compute_ecl** — §3 12m-vs-lifetime ECL (12m = €4,952.83, lifetime = €16,571.39, ratio 3.35);
  §10 workout LGD (31.0% discounted vs 22% undiscounted); §12 revolver EAD (5 + 0.6×15 = €14.0m).
- **compute_pd** — §6 WOE/IV for LTV (IV = 0.4403); §7 Merton (DD = 1.2116 → PD 11.28%).
- **compute_vasicek** — §8 PIT conditioning at ρ=0.12, TTC 2% (7.34% @ Z=−2, 1.43% @ Z=0,
  0.17% @ Z=+2) + numerical anchor check E_Z[PD_PIT] = PD_TTC.
- **compute_scenarios** — §9 probability-weighted ECL €1.74m ≈ 1.9× the average-scenario €0.90m.
- **compute_grossup** — §9 lifetime gross-up ×1.29 (60m PD 9.4% → lifetime 12.1%).
- **compute_ncl** — §11 discounting a realised loss (face 12.5% UPB → 20.2% EIR-discounted).
- **compute_rollrate** — §11 D180→D90 bridge R = 0.60 (PD ×1.66 up, LGD down, EL ≈ preserved).
- **compute_validation** — §13 binomial/Jeffreys grade backtest + PSI over five bands.

**Gate rule:** the Phase-3 engine is frozen only when `pytest tests/` is green; any engine change
after the freeze re-runs this suite.
