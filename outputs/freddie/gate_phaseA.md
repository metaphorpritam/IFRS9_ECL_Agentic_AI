# Rung-3 Phase A gate — freddie/ (SFLLD ingest, state macro, EDA)

Date: 2026-07-17
Scope: `freddie/` (ingest.py, macro.py, build_panel.py, eda.py), `tests/test_freddie_ingest.py`,
`tests/test_freddie_macro.py`, `outputs/freddie/`, `data/processed/freddie/`.

## 1. Test suite — GREEN

```
uv run --no-sync pytest tests/ -q
```

**553 passed**, 0 failed, 29 warnings, 132.75s.

| slice | count | verdict |
|---|---|---|
| Pre-existing suite (DCR engine/agent/app, UI v3 baseline) | 513 | PASS — unchanged from the last recorded baseline (`uiv3_gate_report.md`: 513/513) |
| `tests/test_freddie_ingest.py` (new) | run standalone: 40 collected across both freddie files combined | PASS |
| `tests/test_freddie_macro.py` (new) | | PASS |
| **Total** | **553** | **PASS** |

Standalone re-run for isolation:

```
uv run --no-sync pytest tests/test_freddie_ingest.py tests/test_freddie_macro.py -q
40 passed in 45.25s
```

553 (full) − 40 (freddie-only) = 513, exactly matching the pre-existing baseline count with
zero regressions and zero collection errors introduced by the new modules.

## 2. Contamination check — CLEAN

`git status --porcelain` at the start of this gate:

```
 M .gitignore
?? freddie/
?? outputs/freddie/
?? tests/test_freddie_ingest.py
?? tests/test_freddie_macro.py
```

Everything untracked falls inside the approved freddie footprint. The one tracked-file
change is `.gitignore`:

```diff
 data/raw/
 data/processed/
 data/scenarios/
+data/SFLLD/
 !data/**/.gitkeep
 !data/**/README.md
```

Verdict: **in-scope, not a breach.** This adds the raw SFLLD download directory to the
existing block of gitignored raw/processed data roots — it does not touch any tracked
source file, config, or engine/app code. Flagged here for visibility since it is technically
outside the four named directories, but it is a one-line data-hygiene addition required by
the freddie ingest work itself, not a scope leak.

**`data/processed/panel.parquet` (the DCR modeling panel) — untouched:**

- `git diff --stat HEAD -- data/panel/build_panel.py` → empty (the DCR panel builder was not
  touched this session).
- `stat` mtime: `2026-07-05 06:31:56` — unchanged from before this freddie work began (today
  is 2026-07-17); no write has occurred to this file this session.
- `sha256sum data/processed/panel.parquet` = `e124b856…8213b1c` (recorded here as the
  reference for future gates — no prior gate report had recorded this hash to diff against,
  so mtime + the empty diff on its sole producer (`data/panel/build_panel.py`) is the
  corroborating evidence of non-interference).

**Frozen five (`engine/{hazard,lgd,ead,staging,ecl}.py`) — byte-identical to HEAD:**

| file | working-tree sha256 | HEAD blob sha256 | verdict |
|---|---|---|---|
| engine/hazard.py  | `d862e636c3078362…` | `d862e636c3078362…` | UNBREACHED |
| engine/lgd.py     | `8b16df7ef06ab2c0…` | `8b16df7ef06ab2c0…` | UNBREACHED |
| engine/ead.py     | `caff4dc715ca0992…` | `caff4dc715ca0992…` | UNBREACHED |
| engine/staging.py | `c424882ad5ca2d8c…` | `c424882ad5ca2d8c…` | UNBREACHED |
| engine/ecl.py     | `bdf463250956398d…` | `bdf463250956398d…` | UNBREACHED |

`git diff --stat HEAD -- engine/hazard.py engine/lgd.py engine/ead.py engine/staging.py
engine/ecl.py` is empty. `git status --porcelain` shows no path under `engine/`, `data/panel/`,
`analysis/`, `agent/`, or `app/` as modified or untracked.

**Verdict: contamination check PASSES.** Nothing changed outside the freddie footprint that
constitutes a real code/data change; the one tracked diff (`.gitignore`) is an in-scope,
necessary, non-functional addition.

## 3. Fingerprint scan — frozen five NONE

```
uv run --no-sync python .claude/skills/pageindex-plus/scripts/scan_code.py \
  --root /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI \
  --dirs engine data/panel analysis agent app \
  --out knowledge/code_map.md --fingerprints knowledge/code_fp.json
```

Result: `scanned 31 files | change levels: NONE=31`.

`git diff knowledge/code_fp.json` after the scan: **empty** — every `content_hash` and
`struct_hash` in the baseline fingerprint store, including all five frozen engine files,
round-tripped identically. (`knowledge/code_map.md` is a derived/regenerated doc; its diff
from this scan run was reverted with `git checkout -- knowledge/code_map.md` after
confirming the fingerprint store itself was unaffected, so this gate leaves no side effects
outside the freddie footprint.)

**Verdict: frozen five all NONE.** No STRUCTURAL, no COSMETIC.

## 4. Per-vintage panel stats (from `outputs/freddie/ingest/dq_report.md`)

Coverage note: vintages 2011, 2012, 2013, 2017 were never downloaded for this project
(documented gap, not an ingestion failure — see `freddie/ingest.py` `MISSING_VINTAGES`).

| vintage | n_loans | n_loan_months (modeled) | d90 rate | prepay rate | other-terminal rate | censored rate | perf. window end |
|---|---|---|---|---|---|---|---|
| 2005 | 50,000 | 3,588,153 | 0.1075 | 0.8721 | 0.0015 | 0.0189 | 2025-09 |
| 2006 | 50,000 | 2,833,990 | 0.1411 | 0.8395 | 0.0033 | 0.0161 | 2025-09 |
| 2007 | 50,000 | 2,592,669 | 0.1626 | 0.8158 | 0.0034 | 0.0182 | 2025-09 |
| 2008 | 50,000 | 2,224,103 | 0.0914 | 0.8885 | 0.0023 | 0.0178 | 2025-09 |
| 2009 | 50,000 | 3,078,747 | 0.0307 | 0.9231 | 0.0028 | 0.0434 | 2025-09 |
| 2010 | 50,000 | 3,363,401 | 0.0316 | 0.9026 | 0.0016 | 0.0643 | 2025-09 |
| 2014 | 50,000 | 3,265,018 | 0.0378 | 0.7921 | 0.0019 | 0.1683 | 2025-09 |
| 2015 | 50,000 | 3,317,071 | 0.0400 | 0.7370 | 0.0007 | 0.2223 | 2025-09 |
| 2016 | 50,000 | 3,201,194 | 0.0466 | 0.6840 | 0.0013 | 0.2681 | 2025-09 |
| 2018 | 50,000 | 1,901,886 | 0.0536 | 0.7636 | 0.0018 | 0.1810 | 2025-09 |
| 2019 | 50,000 | 1,750,978 | 0.0548 | 0.6756 | 0.0020 | 0.2676 | 2025-09 |
| 2020 | 50,000 | 2,306,271 | 0.0208 | 0.3620 | 0.0018 | 0.6155 | 2025-09 |
| 2021 | 50,000 | 2,272,716 | 0.0180 | 0.1709 | 0.0020 | 0.8091 | 2025-09 |
| 2022 | 50,000 | 1,766,601 | 0.0302 | 0.1566 | 0.0041 | 0.8091 | 2025-09 |
| 2023 | 50,000 | 1,214,980 | 0.0185 | 0.1801 | 0.0033 | 0.7981 | 2025-09 |
| 2024 | 50,000 | 691,421 | 0.0063 | 0.0937 | 0.0028 | 0.8972 | 2025-09 |
| 2025 | 37,500 | 153,366 | 0.0004 | 0.0179 | 0.0003 | 0.9814 | 2025-09 |

**Totals**: 837,500 loans, 39,522,565 modeled loan-months, overall D90 rate 0.0532, overall
prepay rate 0.5893.

Sentinel-code and validation-message details (first_payment_date drift, mi_cancellation,
eltv, property_valuation_method, special_eligibility_program coverage by vintage) are in the
full `outputs/freddie/ingest/dq_report.md` and are unchanged from the ingest module's own
self-report.

## 5. Simplifications register

```json
[
  {
    "key": "sflld-ingest",
    "simplifications": [
      "Default definition = D90 (first 90+ DPD, dlq_num>=3, or straight-to-REO-acquisition 'RA'), modeled as an ABSORBING event: the modeling panel (panel_monthly.parquet) drops every loan-month after a loan's first D90 month, even if the servicer later reports the loan curing back below 90 DPD -- documented and unit-tested (loan F07Q10000581, 2007 vintage, cures for years afterward in raw data but the panel stops at the event month).",
      "D90 chosen over D180 or 'wait for liquidation' as the primary default trigger: D180 would push the event out and undercount early risk; liquidation (zero_balance_code 02/03/09/96) is a strictly later, servicer-dependent event that many D90 loans never reach within the performance window, which would understate risk if used as the modeling target. Liquidation/zero-balance codes are preserved as columns on loan_orig.parquet for competing-risk/LGD work instead.",
      "Same-row tie-break (empirically real, ~0.1-0.2% of loans/vintage): when a loan's first D90 month lands on the exact same reporting row as a terminal zero_balance_code (most often '01' Prepaid/Matured -- a DDLPI/MBA-method delinquency artifact at final payoff), the zero-balance disposition code wins and d90_event is suppressed that row, keeping d90_event and prepay_event/other terminal flags strictly mutually exclusive as modeled (unit-tested with loans F07Q10009844 and F07Q40358784).",
      "first_payment_date is allowed to drift outside vintage+/-1 up to a 1% budget per vintage (construction-to-perm / seller-owned modified mortgages report the modified first-payment date per the User Guide's own footnote 3); flagged as informational, not a hard validation failure, since it's real documented SFLLD behavior at 0.01-0.1% empirically.",
      "Sentinel-to-NaN mapping covers the documented 'Not Available'/'Not Applicable' codes (credit_score=9999, mi_pct/cltv/dti/orig_ltv=999, num_units/num_borrowers/property_type=99, first_time_homebuyer_flag/occupancy_status/channel/loan_purpose/special_eligibility_program='9', property_valuation_method='7', mi_cancellation_indicator='9' only -- '7' Not-Applicable is deliberately kept, not nulled, since it's a real 'no MI to cancel' value; eltv=999, net_sale_proceeds='U'). Postal code's masking (last two digits always zeroed) is documented but left as-is, not treated as missing.",
      "Category dtypes assigned per-vintage upcast to object on the final 17-vintage pd.concat (different vintages populate different category sets, e.g. seller/servicer names, property_valuation_method) -- functionally correct, just not category dtype in the final parquet; not a correctness issue, only a minor memory/dtype note.",
      "Realized-loss fields and terminal_outcome on loan_orig.parquet are taken from the loan's true terminal row in the FULL (un-truncated) servicing history, not from the absorbing-D90-censored monthly panel, since loss components (actual_loss_calculation, net_sale_proceeds, etc.) only populate at the real disposition row, which can occur after the D90 truncation point used for the modeling panel."
    ]
  },
  {
    "key": "state-macro",
    "simplifications": [
      "HPI quarterly->monthly: step-function forward-fill (each quarter's print held flat across its 3 months), matching MASTER_PLAN.md's documented rung-3 default over interpolation (which would leak intra-quarter information). Side effect documented in the module docstring: monthly hpi_growth is ~0 in 2 of every 3 months; exhibits use trailing-12m log growth (YoY) specifically to avoid this reading as noise.",
      "Territory fallback: GU/VI have no FRED state UR or STHPI series and PR has no STHPI series -- all three fall back to the national anchor (UNRATE/USSTHPI) for the missing series only, with boolean uer_is_national_fallback/hpi_is_national_fallback flags carried on every row so the approximation is never silently blended into a 'state' number.",
      "updated_ltv uses first_payment_date (the field the SFLLD orig layout actually exposes) as a one-month proxy for the true origination/closing month, since the public layout carries no exact closing date -- documented as a small, known approximation, not an estimate of unknown data.",
      "Lag-1 (TIMING CONVENTION) columns are built at the panel's native monthly frequency via a continuous per-state monthly reindex + shift(1), mirroring the DCR panel's 'only past values referenced, no lookahead' convention but at monthly rather than quarterly granularity.",
      "HPI rebase base is Jan-2000 per state; if a state's series doesn't reach that far back (none actually do, verified empirically) the code falls back to that state's first available observation and flags hpi_rebase_used_first_available.",
      "merge_macro's updated_ltv computation does not guard against orig_upb<=0 (division by zero/inf) -- mirrors DCR's build_panel.py step 5, which drops such loans upstream; that exclusion is left to the (separate, concurrently-built) freddie ingest/panel module, not this merge helper.",
      "'no NaNs after merge' test uses a synthetic (state, month) grid rather than a full ingested panel, since building the full loan-month panel is a separate rung-3 module's responsibility (freddie/ingest.py + freddie/build_panel.py, built concurrently by a sibling task in this same session) -- macro.py's own contract is validated directly.",
      "The spec's illustrative '2012 NV loan' sanity check uses the nearest available vintage (2010) instead, since SFLLD vintages 2011-2013 were not downloaded (documented coverage gap, not an error) -- explicitly noted in the test docstring."
    ]
  },
  {
    "key": "freddie-eda",
    "simplifications": [
      "Vintage curves are MARGINAL cumulative-incidence curves (count of events by MOB / original cohort size), not censoring-adjusted Kaplan-Meier -- standard mortgage-industry 'vintage curve' convention, documented in-code, but understates true hazard for young/still-censored vintages",
      "Roll-rate matrices deliberately re-read freddie.ingest.read_svcg_vintage() directly (bypassing panel_monthly.parquet) because the panel's absorbing-D90 truncation destroys post-90+ cure transitions and drops borrower_assistance_status_code -- documented at length in the module docstring as the one deliberate deviation from 'just consume the parquets'; result is cached so reruns are fast",
      "Roll-rate buckets fold whole-loan-sale/RPL-securitization (zero_balance_code 15/16) into an excluded 'other_removed' bucket -- dropped from both the row and column of the reported matrices as a securitization/servicing-transfer artifact, not a credit transition",
      "State HPI peak-to-trough drawdown uses a fixed 2006-2012 window and excludes GU/PR/VI (no real state-level HPI series, only national-fallback) -- documented via freddie/macro.py's own fallback flags",
      "Realized LGD denominator is zero_balance_removal_upb (UPB at removal), not orig_upb or D90-event-month UPB; 4 loans with removal UPB < $1,000 excluded as near-zero-denominator artifacts; LGD is a first look only, no seasoning/vintage/regional model fitted",
      "State default-rate ranking and HPI-drawdown regression restricted to states with >=200 sampled loans in the 2006-2007 vintages, to avoid noisy small-territory rates",
      "2006-2007 vintage 'cumulative default rate' is treated as near-final given 15-19 years of observation, but is not formally censoring-adjusted"
    ]
  }
]
```

## 6. Verdict

**PASS.** 553/553 tests green (513 pre-existing + 40 new freddie tests, exact match, zero
regressions). Contamination check clean — only the approved freddie footprint plus a single
in-scope `.gitignore` line changed. Frozen five (`engine/{hazard,lgd,ead,staging,ecl}.py`)
NONE on both the fingerprint scanner and an independent git-blob sha256 cross-check.
`data/processed/panel.parquet` untouched (stale mtime, empty diff on its sole producer).
Phase A of Rung-3 (Freddie Mac SFLLD ingest + state macro + EDA) is clear to proceed.
