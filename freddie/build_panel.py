"""Build the combined SFLLD monthly loan panel + loan-level origination table.

Input :  data/SFLLD/sample_{YYYY}.zip, YYYY in freddie.ingest.VINTAGE_YEARS
         (via freddie.ingest.read_orig_vintage / read_svcg_vintage).
Output:  data/processed/freddie/panel_monthly.parquet  (loan-month rows)
         data/processed/freddie/loan_orig.parquet       (one row per loan)
         outputs/freddie/ingest/dq_report.md            (data-quality report)

Run as a module:
    cd <repo root> && uv run --no-sync python -m freddie.build_panel

--------------------------------------------------------------------------------
DEFAULT DEFINITION (the rung-3 "90 DPD re-flag" from MASTER_PLAN.md)
--------------------------------------------------------------------------------
Primary default event = D90: the FIRST loan-month where current_delinquency
_status corresponds to 90+ days delinquent, i.e. dlq_num >= 3 OR the loan has
gone straight to an REO Acquisition status ("RA", current_delinquency_status
field's own escape hatch for "days-delinquent no longer means anything, the
property has been acquired").  This is modeled as an ABSORBING event: once a
loan's cumulative first-D90 indicator fires, every subsequent loan-month for
that loan is dropped from the modeling panel (panel_monthly.parquet) -- even
if the servicer later reports the loan curing back below 90 DPD. This choice
mirrors the DCR engine's discrete-time hazard framing (engine/hazard.py, not
imported here -- rung 3 is a fresh build) where a loan is "at risk of first
default" only up to its first default month.

WHY D90 AND NOT D180 OR LIQUIDATION:
  * D90 (this rung) is the standard IFRS 9 / Basel "definition of default"
    trigger point and is available uniformly across every vintage from the
    first loan-month a loan goes 90+ days past due -- no need to wait for a
    servicer to decide on (or ever reach) a terminal disposition.
  * D180 would push the event further out and undercount early-stage risk;
    Freddie's own delinquency ladder makes D90 no harder to compute than D180
    (both are just a threshold on dlq_num).
  * Liquidation (zero_balance_code in {02,03,09,96}) is a strictly LATER,
    lower-frequency, servicer-dependent event -- many loans that go 90+ DPD
    cure, modify, or otherwise never reach a zero-balance code at all within
    the performance window, which would understate credit risk if used as the
    modeling target. Liquidation / zero-balance codes are instead kept as
    columns on the loan-level table (loan_orig.parquet) for competing-risk /
    LGD work, and prepayment (zero_balance_code == '01') is modeled as its own
    mutually-exclusive competing event, NOT as "default".

Consequences of the absorbing-D90 choice, made explicit:
  * d90_event and prepay_event are mutually exclusive AS MODELED: a loan can
    only prepay (zero_balance_code == 01) on its recorded terminal row if it
    never first went 90+ DPD in the (truncated) modeling panel; both are also
    mutually exclusive with the OTHER zero-balance codes for the same reason.
    A loan that goes 90+ DPD and is later foreclosed/short-saled/etc. is
    modeled purely as a D90 default -- the later liquidation is not a separate
    modeling-panel event, though it is fully preserved on loan_orig.parquet
    (terminal_outcome, realized-loss fields) since that table is built from
    the FULL, un-truncated servicing history, not the absorbing-censored panel.
  * Tie-break for the rare case where a loan's first D90 month lands on
    EXACTLY the same reporting row as its terminal zero_balance_code (see
    _build_monthly_panel): the zero-balance disposition code wins and
    d90_event is suppressed that row, so d90_event and prepay_event (or any
    other zero-balance-derived flag) never both fire on the same row.
  * "Cures" (dlq_num back down after >=3) are real in the raw data (see
    tests/test_freddie_ingest.py::test_absorbing_d90_censors_post_event_rows,
    loan F07Q10000581 in the 2007 vintage) and are deliberately NOT visible in
    panel_monthly.parquet after the event month -- documented simplification.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from freddie import ingest

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "freddie"
OUTPUTS_DIR = REPO_ROOT / "outputs" / "freddie" / "ingest"

PANEL_MONTHLY_PATH = PROCESSED_DIR / "panel_monthly.parquet"
LOAN_ORIG_PATH = PROCESSED_DIR / "loan_orig.parquet"
DQ_REPORT_PATH = OUTPUTS_DIR / "dq_report.md"

MONTHLY_PANEL_COLUMNS = [
    "loan_sequence_number", "vintage", "monthly_reporting_period", "loan_age",
    "remaining_months_legal_maturity", "current_actual_upb",
    "current_delinquency_status", "dlq_num", "is_reo_acquisition",
    "modification_flag", "zero_balance_code", "zero_balance_effective_date",
    "d90_event", "prepay_event", "is_terminal_row",
]

LOSS_FIELDS = [
    "actual_loss_calculation", "net_sale_proceeds", "total_expenses",
    "mi_recoveries", "non_mi_recoveries", "zero_balance_removal_upb",
    "delinquent_accrued_interest",
]


def _build_monthly_panel(svcg: pd.DataFrame) -> pd.DataFrame:
    """Absorbing-D90 truncation: keep every loan-month up to and including the
    first D90 month (dlq_num>=3 or REO acquisition); drop everything after."""
    df = svcg.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)
    severe = (df["dlq_num"].fillna(0) >= 3) | df["is_reo_acquisition"]
    # cumsum of severe INCLUDING the current row stays flat at 1 forever after
    # the first hit (a boolean cumsum only grows on a TRUE row) -- so
    # `cumsum <= 1` alone would keep every row after the event too. What we
    # actually want is "no severe row occurred strictly BEFORE this one",
    # which is the inclusive cumsum minus the row's own contribution.
    severe_cumsum_inclusive = severe.groupby(df["loan_sequence_number"], sort=False, observed=True).cumsum()
    prior_severe_count = severe_cumsum_inclusive - severe.astype("int64")
    keep = prior_severe_count == 0
    df = df.loc[keep].copy()
    severe = severe.loc[keep]

    # Tie-break (empirically real, ~0.1-0.2% of loans per vintage -- e.g.
    # F07Q10009844, F07Q40358784 in the 2007 vintage): a loan's very first
    # severe (90+ DPD / REO) month can coincide EXACTLY with the same row's
    # zero_balance_code being set (most often '01', Prepaid or Matured --
    # a DDLPI/MBA-method delinquency-status artifact at final payoff/maturity,
    # not a genuine ongoing default). When a terminal zero_balance_code is
    # populated on the same row that would otherwise trigger D90, the
    # disposition code wins and d90_event is suppressed on that row -- this is
    # what keeps d90_event and prepay_event/other terminal flags mutually
    # exclusive AS MODELED (tests/test_freddie_ingest.py::
    # test_prepay_and_default_mutually_exclusive_as_modeled).
    has_zb_same_row = df["zero_balance_code"].notna()
    df["d90_event"] = (severe & ~has_zb_same_row).astype("uint8")
    row_rank = df.groupby("loan_sequence_number", sort=False, observed=True).cumcount(ascending=False)
    df["is_terminal_row"] = row_rank == 0
    df["prepay_event"] = (df["is_terminal_row"] & (df["zero_balance_code"] == "01")).astype("uint8")
    return df[MONTHLY_PANEL_COLUMNS]


def _terminal_rows_full_history(svcg: pd.DataFrame) -> pd.DataFrame:
    """One row per loan taken from the FULL (un-truncated) servicing history --
    used for realized-loss fields and terminal_outcome on the loan-level table,
    since loss components only populate at the true disposition row, which can
    fall after the absorbing-D90 truncation point used for the modeling panel."""
    idx = svcg.groupby("loan_sequence_number", sort=False, observed=True)["monthly_reporting_period"].idxmax()
    term = svcg.loc[idx].set_index("loan_sequence_number")
    return term


def _terminal_outcome(term: pd.DataFrame, d90_loans: set[str]) -> pd.Series:
    zb = term["zero_balance_code"]
    outcome = pd.Series("censored", index=term.index, dtype="object")
    has_zb = zb.notna()
    # Safety net: a populated zero_balance_code the label table doesn't know
    # about (e.g. a future SFLLD refresh reintroducing "06" -- see the NOTE
    # in ingest.py's zero-balance-code docstring) must NOT silently fall
    # through to "censored" (that would misrepresent a real terminal
    # disposition as still-active). Flag it distinctly so it's visible in
    # the dq_report/terminal_outcome value_counts instead of hiding in
    # "censored". validate_svcg()'s bad_zb_codes check also catches this at
    # the per-vintage level.
    outcome.loc[has_zb] = "other_unmapped_zero_balance_code"
    for code, label in ingest.ZERO_BALANCE_CODE_LABELS.items():
        outcome.loc[has_zb & (zb == code)] = label
    is_d90 = term.index.to_series().isin(d90_loans)
    # D90 default takes precedence in the label even if a later zero-balance
    # code was also recorded (see docstring: D90 is the modeled event; the
    # zero-balance code, if any, is preserved separately on this same row).
    outcome.loc[is_d90.to_numpy()] = "d90_default"
    return outcome.astype("category")


def build_vintage(year: int) -> tuple[pd.DataFrame, pd.DataFrame, ingest.OrigValidation, ingest.SvcgValidation, dict]:
    orig = ingest.read_orig_vintage(year)
    svcg = ingest.read_svcg_vintage(year)

    orig_dq = ingest.validate_orig(orig, year)
    svcg_dq = ingest.validate_svcg(svcg, orig, year)

    monthly = _build_monthly_panel(svcg)
    d90_loans = set(monthly.loc[monthly["d90_event"] == 1, "loan_sequence_number"])

    term = _terminal_rows_full_history(svcg)
    outcome = _terminal_outcome(term, d90_loans)

    loan_level = orig.set_index("loan_sequence_number").copy()
    loan_level["terminal_outcome"] = outcome.reindex(loan_level.index)
    loan_level["last_reported_period"] = term["monthly_reporting_period"].reindex(loan_level.index)
    loan_level["months_observed"] = svcg.groupby("loan_sequence_number", observed=True).size().reindex(loan_level.index)
    loan_level["had_d90_event"] = loan_level.index.to_series().isin(d90_loans)
    for f in LOSS_FIELDS:
        loan_level[f] = term[f].reindex(loan_level.index)
    loan_level["zero_balance_code"] = term["zero_balance_code"].reindex(loan_level.index)
    loan_level["zero_balance_effective_date"] = term["zero_balance_effective_date"].reindex(loan_level.index)
    loan_level = loan_level.reset_index()

    sentinel_counts = {
        "orig": orig.attrs.get("sentinel_counts", {}),
        "svcg": svcg.attrs.get("sentinel_counts", {}),
    }
    return monthly, loan_level, orig_dq, svcg_dq, sentinel_counts


def _dq_report_md(rows: list[dict], sentinel_by_year: dict, orig_msgs: list[str], svcg_msgs: list[str],
                   perf_end_by_year: dict) -> str:
    lines = ["# Freddie Mac SFLLD -- data-quality report", ""]
    lines.append(
        "Coverage note: vintages "
        + ", ".join(str(y) for y in ingest.MISSING_VINTAGES)
        + " were never downloaded for this project (not an ingestion failure -- "
        "documented gap; see freddie/ingest.py MISSING_VINTAGES)."
    )
    lines.append("")
    lines.append("## Per-vintage row counts and event rates")
    lines.append("")
    lines.append("| vintage | n_loans | n_loan_months (modeled) | d90 rate | prepay rate | other-terminal rate | censored rate | perf. window end |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| {r['year']} | {r['n_loans']} | {r['n_loan_months']} | {r['d90_rate']:.4f} | "
            f"{r['prepay_rate']:.4f} | {r['other_terminal_rate']:.4f} | {r['censored_rate']:.4f} | "
            f"{perf_end_by_year[r['year']]} |"
        )
    total_loans = sum(r["n_loans"] for r in rows)
    total_months = sum(r["n_loan_months"] for r in rows)
    total_d90 = sum(r["n_d90"] for r in rows)
    total_prepay = sum(r["n_prepay"] for r in rows)
    lines.append("")
    lines.append(
        f"**Totals**: {total_loans:,} loans, {total_months:,} modeled loan-months, "
        f"overall D90 rate {total_d90/total_loans:.4f}, overall prepay rate {total_prepay/total_loans:.4f}."
    )
    lines.append("")
    lines.append("## Sentinel / missing-value profile (raw sentinel-code occurrences, pre-NaN-mapping)")
    lines.append("")
    lines.append("Documented sentinel codes (see freddie/ingest.py docstring for the full list; "
                  "credit_score=9999, dti=999, orig_ltv=999, cltv=999, mi_pct=999, num_units=99, "
                  "num_borrowers=99, property_type=99, eltv=999, net_sale_proceeds='U', plus the "
                  "categorical '9'/'7' Not-Available codes) are mapped to NaN on read. Counts below "
                  "are per vintage, BEFORE mapping.")
    lines.append("")
    all_cols = sorted({c for by in sentinel_by_year.values() for c in {**by["orig"], **by["svcg"]}})
    header = "| vintage | " + " | ".join(all_cols) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(all_cols) + 1))
    for year, by in sentinel_by_year.items():
        merged = {**by["orig"], **by["svcg"]}
        lines.append(f"| {year} | " + " | ".join(str(merged.get(c, 0)) for c in all_cols) + " |")
    lines.append("")
    lines.append("## Validation messages")
    lines.append("")
    if not orig_msgs and not svcg_msgs:
        lines.append("None -- every vintage passed field-count, join-orphan, delinquency-ladder and "
                      "zero-balance-code checks.")
    else:
        for m in orig_msgs + svcg_msgs:
            lines.append(f"- {m}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    monthly_frames, loan_frames = [], []
    report_rows, sentinel_by_year, perf_end_by_year = [], {}, {}
    orig_msgs, svcg_msgs = [], []

    for year in ingest.VINTAGE_YEARS:
        monthly, loan_level, orig_dq, svcg_dq, sentinel_counts = build_vintage(year)
        monthly_frames.append(monthly)
        loan_frames.append(loan_level)
        sentinel_by_year[year] = sentinel_counts
        orig_msgs.extend(orig_dq.messages)
        svcg_msgs.extend(svcg_dq.messages)
        perf_end_by_year[year] = monthly["monthly_reporting_period"].max().strftime("%Y-%m")

        n_loans = len(loan_level)
        outcome_counts = loan_level["terminal_outcome"].value_counts()
        n_d90 = int(outcome_counts.get("d90_default", 0))
        n_prepay = int(outcome_counts.get("prepaid_or_matured", 0))
        n_other_terminal = int(n_loans - n_d90 - n_prepay - outcome_counts.get("censored", 0))
        n_censored = int(outcome_counts.get("censored", 0))
        report_rows.append({
            "year": year, "n_loans": n_loans, "n_loan_months": len(monthly),
            "n_d90": n_d90, "n_prepay": n_prepay,
            "d90_rate": n_d90 / n_loans, "prepay_rate": n_prepay / n_loans,
            "other_terminal_rate": n_other_terminal / n_loans, "censored_rate": n_censored / n_loans,
        })
        print(f"{year}: {n_loans} loans, {len(monthly)} modeled loan-months, "
              f"d90={n_d90} ({n_d90/n_loans:.2%}), prepay={n_prepay} ({n_prepay/n_loans:.2%})")

    panel_monthly = pd.concat(monthly_frames, ignore_index=True)
    loan_orig = pd.concat(loan_frames, ignore_index=True)

    panel_monthly.to_parquet(PANEL_MONTHLY_PATH, index=False)
    loan_orig.to_parquet(LOAN_ORIG_PATH, index=False)

    report = _dq_report_md(report_rows, sentinel_by_year, orig_msgs, svcg_msgs, perf_end_by_year)
    DQ_REPORT_PATH.write_text(report)

    print(f"\nWrote {PANEL_MONTHLY_PATH} ({len(panel_monthly):,} rows)")
    print(f"Wrote {LOAN_ORIG_PATH} ({len(loan_orig):,} rows)")
    print(f"Wrote {DQ_REPORT_PATH}")


if __name__ == "__main__":
    main()
