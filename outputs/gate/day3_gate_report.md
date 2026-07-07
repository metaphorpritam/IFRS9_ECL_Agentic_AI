# Day-3 GATE Report — Scenario Layer on a Frozen Engine

Date: 2026-07-07
Scope: Day-3 gate check. Verifies (1) the full test suite including the 133 golden
fixtures and all Day-2 tests, (2) the frozen-engine fingerprint tripwire established
at the Day-2 gate (`outputs/gate/gate_report.md` §3–4), (3) the working-tree change
inventory, and (4) the collected documented-simplifications registers for the Day-3
layers (vasicek, scenarios, scenario-ECL, challenger).

## 1. Test suite — GREEN

`uv run --no-sync pytest tests/ -q` → **278 passed, 0 failed** (1 pytest
deprecation warning on the fixture parametrize generator, non-blocking; 64.7s).

| Test file | Tests | Status | Notes |
|---|---|---|---|
| tests/test_fixtures.py | 133 | PASS | Golden fixture values — immutable, all green. |
| tests/test_ead.py | 16 | PASS | Day-2, frozen engine. |
| tests/test_ecl.py | 14 | PASS | Day-2, frozen engine. |
| tests/test_lgd.py | 8 | PASS | Day-2, frozen engine. |
| tests/test_staging.py | 16 | PASS | Day-2, frozen engine. |
| **Day-2 subtotal** | **187** | **PASS** | Matches the Day-2 gate count exactly. |
| tests/test_vasicek.py | 49 | PASS | Day-3 new. |
| tests/test_scenarios.py | 13 | PASS | Day-3 new. |
| tests/test_satellite.py | 16 | PASS | Day-3 new. |
| tests/test_challenger.py | 13 | PASS | Day-3 new. |
| **Day-3 subtotal** | **91** | **PASS** | |
| **Total** | **278** | **PASS** | |

## 2. Frozen-engine fingerprint verdict — NO BREACH

Re-ran the Day-2 tripwire the same way:

```
uv run --no-sync python .claude/skills/pageindex-plus/scripts/scan_code.py \
  --root /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI \
  --dirs engine data/panel analysis \
  --out knowledge/code_map.md \
  --fingerprints knowledge/code_fp.json
```

Result: `scanned 22 files | change levels: NEW=7, NONE=15`. Per frozen file
(classification vs the Day-2 baseline `struct_hash`, signatures/exports/imports —
not raw bytes):

| Frozen file | Classification | struct_hash | Verdict |
|---|---|---|---|
| engine/hazard.py | **NONE** | `1786dacea90bf08e` | UNBREACHED |
| engine/lgd.py | **NONE** | `d5a98c1dc6fc76d0` | UNBREACHED |
| engine/ead.py | **NONE** | `b120dc99602dd3f7` | UNBREACHED |
| engine/staging.py | **NONE** | `9354043a443a12d0` | UNBREACHED |
| engine/ecl.py | **NONE** | `7c7feef9c97494fe` | UNBREACHED |

Zero STRUCTURAL, zero COSMETIC on the frozen five. Belt-and-braces:
`git diff d3ea14f..HEAD -- engine/{hazard,lgd,ead,staging,ecl}.py` and the
working-tree diff on the same paths are both **empty** — the frozen files are
byte-identical to the Day-2 gate commit.

Remaining baseline files also NONE (panel unchanged, as expected):
`data/panel/build_panel.py`, `data/panel/__init__.py`, `engine/__init__.py`, and
all seven Day-2 `analysis/` exhibits (`ead_exhibits`, `eda_suite`, `fit_hazard`,
`fit_lgd`, `mpl_style`, `run_ecl`, `staging_exhibits`).

New files, classified NEW vs baseline (expected — Day-3 layers, no baseline entry):

| New file | Classification |
|---|---|
| engine/vasicek.py | NEW `2228076826c94a00` |
| engine/scenarios.py | NEW `6aafeb84b332544d` |
| engine/satellite.py | NEW `cab43402a5546d0b` |
| analysis/fit_vasicek.py | NEW `2d2825bd567b1bee` |
| analysis/run_scenarios.py | NEW `cfe7b28be2262445` |
| analysis/scenario_exhibits.py | NEW `362e2ea69a149517` |
| analysis/fit_challenger.py | NEW `5ee6cd72a620fb8a` |

**Gate verdict on the freeze: PASS — no STRUCTURAL or COSMETIC change to any
frozen engine file.**

## 3. Change inventory

`git status --short` at gate time (branch `main`, HEAD `bee207b`):

```
 M analysis/fit_challenger.py
 M analysis/run_scenarios.py
 M engine/satellite.py
 M knowledge/code_fp.json
 M knowledge/code_map.md
 M outputs/challenger/reliability.png
 M outputs/challenger/scorecard.md
 M outputs/satellite/satellite_report.md
 M outputs/scenario_ecl/jensen_gap.png
 M outputs/scenario_ecl/scenario_ecl_report.md
 M tests/test_challenger.py
 M wiki/memory/decisions.md
```

`git diff --stat`:

```
 analysis/fit_challenger.py                  |  34 ++-
 analysis/run_scenarios.py                   |  40 ++--
 engine/satellite.py                         |  12 +-
 knowledge/code_fp.json                      | 198 +++++++++++++++++
 knowledge/code_map.md                       | 317 ++++++++++++++++++++++++----
 outputs/challenger/reliability.png          | Bin 82917 -> 89023 bytes
 outputs/challenger/scorecard.md             |   2 +
 outputs/satellite/satellite_report.md       |  24 ++-
 outputs/scenario_ecl/jensen_gap.png         | Bin 103077 -> 103932 bytes
 outputs/scenario_ecl/scenario_ecl_report.md |  12 +-
 tests/test_challenger.py                    |  26 +++
 wiki/memory/decisions.md                    |   8 +
 12 files changed, 607 insertions(+), 66 deletions(-)
```

Notes:
* `knowledge/code_fp.json` and `knowledge/code_map.md` were modified **by this
  gate's own scan** (fresh fingerprints for the 7 NEW files added to the store;
  code map regenerated: 22 files, 21 local modules, 11 third-party libs, 300 call
  edges). Day-2 baseline backed up to the session scratchpad before the scan.
* All uncommitted edits sit in Day-3 layers (satellite/challenger/scenario-ECL
  polish), their outputs, tests, and the wiki decision log — **none touch a frozen
  file**.

## 4. Documented-simplifications registers (Day-3)

### 4.1 vasicek (engine/vasicek.py, analysis/fit_vasicek.py — outputs/vasicek/)

1. TTC anchor freezes only the four MACRO regressors (uer_lag1, uer_chg4_lag1,
   hpi_growth_lag1, gdp_lag1) at unweighted panel-period means; loan-state
   covariates stay actual — updated_ltv itself carries the HPI cycle, so the main
   anchor is only approximately TTC and the main Z is a damped cycle read (its
   trough lands 2008Q1 vs 2009Q2 for the variant).
2. Variant computed and reported per spec: updated_ltv frozen at origination LTV
   (pure-TTC collateral) → rho 0.0633, trough 2009Q2; but that anchor ignores
   genuine amortisation/equity build-up — truth between the two, both shipped in
   z_path.csv and the exhibit.
3. prepay_incentive stays actual in both variants (loan-state exception per the
   frozen hazard's timing convention; only the default hazard is used).
4. mean(Z) not recentred to zero — Belkin calibrates variance only; the -1.145
   level (Jensen anchor bias + structural offset + OOT drift/adverse survivor
   selection) is documented and left for the satellite model's intercept.
5. Hazard fit on train (t<=40) applied read-only to all 60 quarters; OOT quarters
   41-60 enter Z recovery unrefitted.
6. Finite-portfolio quarterly rate identified with PD_PIT (ASRF
   infinite-granularity approximation); early quarters thin (283 loans at t=1),
   no smoothing applied.
7. Macro means are a panel-period (2000Q2-2015Q1) average, not a true long-run
   TTC macro state.
8. hybrid_pd alpha<1 is Jensen-biased slightly below the E_Z anchor — flagged as
   presentation device, not an unbiased ECL input.
9. Exhibit keeps the project's fixed textbook palette (mpl_style) although the
   dataviz validator flags navy lightness/chroma on strict categorical rules; CVD
   separation passes (worst dE 61.6) and the orange contrast WARN is relieved with
   distinct linestyles, direct labels and the z_path.csv table view.

### 4.2 scenarios (engine/scenarios.py, analysis/run_scenarios.py — outputs/scenarios/)

1. Shape transplant, not a forecast: DFAST 2026 paths (2026Q1-2029Q1) are rebased
   as changes-from-jump-off onto the panel's t=60 (~2015Q1) macro levels; the
   supervisory value used is the coherent multivariate SHAPE, and the additive
   rebasing is applied uniformly to level concepts (uer, mortgage_rate) and
   quarterly growth concepts (hpi_growth, gdp_growth) alike.
2. Upside scenario is a judgmental damped mirror of the severely-adverse deltas
   (factor -0.35, UER floored at 3.5pp); the named enhancement is anchoring the
   upside (and weights) to Philadelphia-Fed SPF forecaster-distribution
   percentiles — documented in module docstring and scenarios_report.md, not
   implemented.
3. Scenario weights 50/25/25 are a governance-committee convention (plan 2.6):
   probabilities are not statistically identified; the deliverable is the
   documented rationale plus downstream weight-sensitivity, not the number.
4. Panel gdp_time is YEAR-OVER-YEAR growth (2009 trough -4.15 matches YoY, not
   the -8.5 SAAR trough); converted to a quarterly-equivalent geometric rate with
   the same fourth-root formula as the DFAST SAAR series — the intra-year
   quarterly profile is unidentified from YoY alone.
5. Panel mortgage-rate level uses the quarterly MEDIAN of rate_time (varies
   mildly across loans within a quarter) — same market-rate convention as the
   frozen engine.staging.build_macro_map.
6. All three scenarios revert to the SAME panel long-run means after the 13q R&S
   window (8q linear ramp, then hold to 40q): scenario differentiation is
   confined to the R&S window plus ramp, the standard PIT-then-TTC construction
   (notes 9.4).
7. First supervisory-quarter hpi_growth (2026Q1) is differenced against the last
   historic actual level (2025Q4, 323.4) rather than dropped.

### 4.3 scenario-ecl (engine/satellite.py scenario-ECL layer — outputs/scenario_ecl/scenario_ecl_report.md)

1. Vasicek transform applied at QUARTERLY-HAZARD level per projection quarter
   (standard practical approximation; the joint multi-period conditional law is
   not derived).
2. Only the default hazard is conditioned; PREPAYMENT stays on the frozen rung-1
   projection (scenario-conditional refinancing is a named enhancement).
3. LGD and EAD are NOT scenario-conditioned — scenario sensitivity enters through
   the PD leg only; a collateral-path LGD link is the standard next rung.
4. TTC baseline = frozen hazard at panel-mean macros with loan-state covariates
   (incl. HPI-indexed updated_ltv) at snapshot values: part of the collateral
   cycle sits in the baseline (conservative Z dial; vasicek report caveat).
5. Z beyond the 40q scenario horizon holds its final (long-run) value; macro
   paths already sit at long-run means from h=21.
6. STAGING fixed across scenarios (frozen rung-1 stages at the reporting date);
   the IASB two-step probability-weighted staging is the documented enhancement.
7. Static-OLS satellite with sign governance instead of the full ARDL/ECM
   production standard (outputs/satellite/ report; production standard is ARDL
   bounds testing with a negative significant ECM term, Johansen rank tests,
   structural-break tests around 2008-09, HAC SEs, OOT backtesting — on 57 usable
   quarters spanning a single credit cycle the static form is the honest choice).
8. Upside = damped mirror of the severe deltas (engine/scenarios.py convention;
   SPF-percentile anchoring is the documented enhancement) — source of the
   lifetime crossover reported in the scenario-ECL report.
9. Scenario weights 50/25/25 judgmental (governance convention), with
   weight-sensitivity reported.

### 4.4 challenger (analysis/fit_challenger.py — outputs/challenger/scorecard.md)

1. Challenger lifetime PDs clamp loan_age at the training support (max 80q;
   level-off tail, the plan's accepted default). The champion extrapolates its
   natural spline linearly. An MLP has no disciplined tail — one reason it stays
   challenger.
2. Early stopping consumes the t=33..40 window for validation; the final model is
   REFIT on the full training window for the early-stopped epoch count to restore
   data parity with the champion.
3. Staging swap compares the memoryless quantitative trigger at the snapshot (no
   probation window, no backstop — both identical machinery on both sides and
   inert/orthogonal to the PD swap).
4. Determinism: bitwise-reproducible on the same device/build (fixed seeds,
   deterministic algorithms, CUBLAS workspace pinned); results differ across CPU
   vs GPU and torch/CUDA versions.
5. Frozen-covariate projections on both lifetime-PD legs (rung-1 tail assumption
   inherited from the engine).

## 5. Gate verdict

**PASS.**

* Suite green: 278/278 (133 golden fixtures + all 187 Day-2 tests + 91 Day-3
  tests), 0 failures.
* Frozen five (`engine/{hazard,lgd,ead,staging,ecl}.py`): all **NONE** on the
  fingerprint tripwire and byte-identical to the Day-2 gate commit — no breach.
* Panel unchanged (NONE); the seven Day-3 files classify NEW as expected.
* All uncommitted changes are Day-3-layer polish plus this gate's own
  knowledge-store refresh; nothing touches the frozen engine.
