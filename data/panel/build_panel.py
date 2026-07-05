"""Build the loan-quarter panel for the IFRS 9 ECL engine.

Input :  data/raw/dcr_full.csv   (Deep Credit Risk 50k-loan US mortgage panel,
         abstract quarterly clock time = 1..60, macros pre-merged)
Output:  data/processed/panel.parquet
         outputs/panel/waterfall.json / waterfall.md   (eligibility-waterfall exhibit)

Run as module (preferred) or script:
    cd <repo root> && uv run python -m data.panel.build_panel
    uv run python data/panel/build_panel.py

Methodology anchors: knowledge/sources/ifrs9_credit_risk_notes.md §5 (merge recipe,
data-prep essentials: left truncation & right censoring first-class) and §6.2
(discrete-time hazards on at-risk rows). MASTER_PLAN.md rung-1/2 scope pins:
pre-merged national macros only (no state-level merge), no delinquency ladder
(status_time is only 0/1/2, so roll-rate/cure EDA is out of scope at this rung —
documented simplification).

--------------------------------------------------------------------------------
ELIGIBILITY WATERFALL (every exclusion counted; see outputs/panel/waterfall.md)
--------------------------------------------------------------------------------
The raw file's "4 loans with rows after their default event" anomaly manifests,
on direct inspection, as duplicate/conflicting rows AT the terminal quarter:
  * ids 37067, 37130, 37792 — the terminal default row is duplicated verbatim
    (removed in step 1, exact-duplicate dedup);
  * id 3014 — an id COLLISION: two distinct loans (different orig_time,
    balance_orig_time, FICO) interleaved under one id, each with its own
    default row (removed in step 2 together with 11 further collision ids).
A generic "truncate at first terminal event" guard (step 4) then removes any
row that still sits after a loan's first terminal event — after steps 1-3 it
is expected to catch zero rows, and the exhibit records that fact.

Steps (order matters; counts are taken sequentially):
  1. exact duplicate rows (all 28 columns identical)  -> drop copies
  2. id-collision loans: >=1 same-(id,time) pair whose *covariates* conflict
     (two interleaved loans; rows cannot be attributed)  -> drop whole id
  3. same-quarter status conflicts: same-(id,time) pair identical on all
     covariates but conflicting outcome flags (one row status 0, one terminal)
     -> keep the terminal row (preserves the event), drop the shadow row
  4. post-terminal truncation guard: rows with time > loan's first terminal
     event time  -> drop (expected 0 after steps 1-3)
  5. loans with balance_orig_time <= 0 (origination balance missing-coded as
     zero): original property value = balance_orig / (LTV_orig/100) = 0, so
     updated LTV and the double-trigger interaction are incomputable for the
     WHOLE loan (static defect; these are exactly the rows where the vendor's
     own LTV_time is NaN)  -> drop whole loan
  6. non-terminal rows with balance_time <= 0 (live row, zero exposure:
     balance missing-coded as zero mid-history; the loan continues or is
     censored at the prior quarter)  -> drop row.  Terminal payoff rows with
     balance 0 are KEPT — the zero balance is the payoff itself and the row
     carries the competing-risk event.
  7. rows with interest_rate_time <= 0 (current note rate missing-coded as
     zero => prepayment incentive incomputable; all such rows are status 0)
     -> drop row

Counted but RETAINED (flagged, not dropped — reasons in waterfall.md):
  * state_orig_time missing — state is unused at this rung (national macros
    only; no state-level HPI/UER merge in scope);
  * Interest_Rate_orig_time == 0 — origination-rate snapshot missing-coded;
    the current note rate is populated and drives the incentive; flag column
    orig_rate_missing;
  * lag warm-up rows (time < 6) — some lag features undefined before the
    macro window starts; flag column lag_warmup;
  * within-loan time gaps — loans can skip quarters; macro lags are repaired
    from the panel-internal time->macro map (below), so no stale-lag bias.

--------------------------------------------------------------------------------
UPDATED LTV — derivation from first principles
--------------------------------------------------------------------------------
LTV_t = current exposure / current collateral value.
Collateral value moves with the house-price index:
    V_t = V_0 * (hpi_time / hpi_orig_time),  V_0 = balance_orig_time / (LTV_orig_time/100).
Hence
    updated_ltv = 100 * balance_time / V_t
                = LTV_orig_time * (balance_time / balance_orig_time)
                               * (hpi_orig_time / hpi_time).
Directionality sanity check: house prices UP (hpi_time > hpi_orig_time) =>
collateral worth MORE => LTV must FALL => the HPI factor enters as
hpi_orig_time / hpi_time (the collateral value itself scales by the inverse,
hpi_time / hpi_orig_time). The balance ratio adds amortisation; the naive
"indexed original LTV" (LTV_orig * hpi_orig/hpi_t) ignores paydown.
The vendor column LTV_time is the panel's own updated LTV and is used as a
cross-check: the build reports corr(updated_ltv, LTV_time) — it reproduces
LTV_time to ~1e-9, i.e. the vendor used exactly this formula.

--------------------------------------------------------------------------------
MACRO LAGS — built inside the panel, no lookahead
--------------------------------------------------------------------------------
Primary construction is groupby(id).shift (per the build plan). Two facts make
a completion step necessary and safe: (a) uer/gdp/hpi are NATIONAL series,
verified constant across loans within each quarter, so the panel itself
defines a unique time -> macro map; (b) the panel has ~1.6k within-loan time
gaps plus one first row per loan, where a raw shift would return a stale or
missing value. Therefore each lag is computed as macro(map, t - k): identical
to groupby(id).shift(k) wherever the shifted row is exactly k quarters back
(asserted numerically), and completing first rows / gap rows from the same
in-panel information set. Only past values (t-k, k>=1) are ever referenced =>
no lookahead. Lags:
    uer_lag1, uer_lag2        unemployment level, lagged 1 / 2 quarters
    uer_chg4_lag1             4-quarter change, lagged: uer(t-1) - uer(t-5)
    gdp_lag1                  GDP growth rate, lagged 1 quarter
    hpi_growth_lag1           one-quarter log-diff of HPI, lagged:
                              ln hpi(t-1) - ln hpi(t-2)
Macro-at-origination (hpi_orig_time etc.) is kept untouched for the SICR
"vs initial recognition" comparison (§5.3 merge recipe).

Double-trigger interaction: dt_ltv_uer = updated_ltv * uer_lag1
(negative-equity x labour-shock joint driver of mortgage default; both in %).

--------------------------------------------------------------------------------
TRAIN / OOT SPLIT
--------------------------------------------------------------------------------
split = 'train' where time <= 40, 'oot' where 41 <= time <= 60. Chronological,
row-level, no shuffling: every OOT row is strictly later in calendar time than
every training row, so the out-of-time set mimics deployment (models fitted on
the first ~2/3 of the observation window are scored on the last third, which
contains the stress episode). Loans alive at t=40 contribute rows to both
sides — standard for hazard-model OOT validation, where the loan-quarter row,
not the loan, is the unit of analysis; there is no target leakage because the
event indicator is row-specific and covariates at OOT rows use information
from t-1/t-2 only.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "dcr_full.csv"
PANEL_PARQUET = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT_DIR = PROJECT_ROOT / "outputs" / "panel"

TRAIN_MAX_TIME = 40          # split: train time <= 40, oot 41..60
WARMUP_MAX_TIME = 5          # uer_chg4_lag1 needs uer(t-5) => defined from t = 6
MACRO_COLS = ["uer_time", "gdp_time", "hpi_time"]

# Explicit dtypes for all 28 raw columns (columns that can carry NaN are float64;
# state is the pandas string dtype).
RAW_DTYPES: dict[str, str] = {
    "id": "int64",
    "time": "int64",
    "orig_time": "int64",
    "first_time": "int64",
    "mat_time": "int64",
    "res_time": "float64",
    "balance_time": "float64",
    "LTV_time": "float64",
    "interest_rate_time": "float64",
    "rate_time": "float64",
    "hpi_time": "float64",
    "gdp_time": "float64",
    "uer_time": "float64",
    "REtype_CO_orig_time": "int64",
    "REtype_PU_orig_time": "int64",
    "REtype_SF_orig_time": "int64",
    "investor_orig_time": "int64",
    "balance_orig_time": "float64",
    "FICO_orig_time": "int64",
    "LTV_orig_time": "float64",
    "Interest_Rate_orig_time": "float64",
    "state_orig_time": "str",
    "hpi_orig_time": "float64",
    "default_time": "int64",
    "payoff_time": "int64",
    "status_time": "int64",
    "lgd_time": "float64",
    "recovery_res": "float64",
}

# Outcome / resolution columns; everything else is a covariate for the purpose
# of deciding whether two same-(id,time) rows describe the same loan.
OUTCOME_COLS = ["status_time", "default_time", "payoff_time",
                "lgd_time", "recovery_res", "res_time"]

# Columns that must be NaN-free on modelling rows (lag_warmup == False).
MODEL_COLS = [
    "loan_age", "balance_time", "updated_ltv", "FICO_orig_time",
    "LTV_orig_time", "interest_rate_time", "prepay_incentive",
    "uer_lag1", "uer_lag2", "uer_chg4_lag1", "gdp_lag1", "hpi_growth_lag1",
    "dt_ltv_uer", "default_event", "payoff_event",
]


# ----------------------------------------------------------------------------
# waterfall bookkeeping
# ----------------------------------------------------------------------------

def _profile(df: pd.DataFrame) -> dict:
    return {
        "rows": int(len(df)),
        "loans": int(df["id"].nunique()),
        "defaults": int((df["status_time"] == 1).sum()),
        "payoffs": int((df["status_time"] == 2).sum()),
    }


class Waterfall:
    def __init__(self, df0: pd.DataFrame):
        self.raw = _profile(df0)
        self.steps: list[dict] = []

    def record(self, name: str, reason: str,
               before: pd.DataFrame, after: pd.DataFrame) -> None:
        b, a = _profile(before), _profile(after)
        self.steps.append({
            "step": len(self.steps) + 1,
            "name": name,
            "reason": reason,
            "rows_in": b["rows"],
            "rows_dropped": b["rows"] - a["rows"],
            "rows_out": a["rows"],
            "loans_in": b["loans"],
            "loans_dropped": b["loans"] - a["loans"],
            "loans_out": a["loans"],
            "defaults_dropped": b["defaults"] - a["defaults"],
            "payoffs_dropped": b["payoffs"] - a["payoffs"],
        })

    @property
    def total_rows_dropped(self) -> int:
        return sum(s["rows_dropped"] for s in self.steps)


# ----------------------------------------------------------------------------
# pipeline stages
# ----------------------------------------------------------------------------

def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_CSV, dtype=RAW_DTYPES)
    assert list(df.columns) == list(RAW_DTYPES), "unexpected raw column layout"
    return df.sort_values(["id", "time"], kind="stable").reset_index(drop=True)


def apply_waterfall(df: pd.DataFrame, wf: Waterfall) -> tuple[pd.DataFrame, dict]:
    notes: dict = {}

    # -- step 1: exact duplicate rows -------------------------------------
    before = df
    df = df.drop_duplicates(keep="first")
    wf.record(
        "exact_duplicate_rows",
        "Verbatim copies of an existing row (all 28 columns identical), incl. "
        "the doubled terminal default rows of ids 37067/37130/37792; dropped "
        "copies are duplicates of retained rows, so no information is lost.",
        before, df,
    )

    # -- classify residual same-(id,time) duplicates ----------------------
    dup_mask = df.duplicated(["id", "time"], keep=False)
    cov_cols = [c for c in df.columns if c not in OUTCOME_COLS + ["id", "time"]]
    dup_rows = df.loc[dup_mask]
    if len(dup_rows):
        gnu = dup_rows.groupby(["id", "time"])
        cov_conflict = gnu[cov_cols].nunique(dropna=False).gt(1).any(axis=1)
        term_count = gnu["status_time"].agg(lambda s: int((s != 0).sum()))
        # collision if covariates conflict OR two conflicting terminal rows
        bad_keys = cov_conflict | (term_count > 1)
        collision_ids = sorted({i for (i, _t) in bad_keys[bad_keys].index})
    else:
        collision_ids = []
    notes["collision_ids"] = collision_ids

    # -- step 2: id-collision loans ---------------------------------------
    before = df
    df = df[~df["id"].isin(collision_ids)]
    wf.record(
        "id_collision_loans",
        f"{len(collision_ids)} ids each contain two interleaved distinct loans "
        "(same-(id,time) rows with conflicting covariates, e.g. two different "
        "balance_orig/FICO tracks under id 3014, both defaulting); rows cannot "
        "be attributed to either loan, so the whole id is excluded.",
        before, df,
    )

    # -- step 3: same-quarter status conflicts ----------------------------
    # Remaining (id,time) dupes are identical on covariates but conflict on
    # outcome flags (one status-0 shadow row next to the terminal row).
    before = df
    prio = (df["status_time"] != 0).astype("int8")
    order = np.lexsort((prio.to_numpy(), df["time"].to_numpy(), df["id"].to_numpy()))
    df = df.iloc[order].drop_duplicates(["id", "time"], keep="last")
    df = df.sort_values(["id", "time"], kind="stable")
    wf.record(
        "same_quarter_status_conflict",
        "Same-(id,time) pairs identical on every covariate but with one "
        "status-0 row shadowing a terminal row (e.g. id 37528 at t=51): the "
        "terminal row is kept so the event is preserved; the shadow is dropped.",
        before, df,
    )

    # -- step 4: post-terminal truncation guard ---------------------------
    before = df
    ftt = (
        df.loc[df["status_time"].isin([1, 2])]
        .groupby("id")["time"].min()
        .rename("first_terminal_time")
    )
    ftt_aligned = df["id"].map(ftt)
    df = df[~(ftt_aligned.notna() & (df["time"] > ftt_aligned))]
    wf.record(
        "post_terminal_truncation",
        "Generic guard: any row after a loan's FIRST terminal event (default "
        "or payoff) is truncated — a loan leaves the at-risk set at its event. "
        "Expected 0 after steps 1-3 resolved the 4-loan anomaly; recorded to "
        "prove the check ran.",
        before, df,
    )

    # -- step 5: loans with balance_orig_time <= 0 ------------------------
    before = df
    bad_ids = df.loc[df["balance_orig_time"] <= 0, "id"].unique()
    df = df[~df["id"].isin(bad_ids)]
    wf.record(
        "nonpositive_origination_balance_loans",
        f"{len(bad_ids)} loans with balance_orig_time missing-coded as 0 (a "
        "static origination defect): original property value = balance_orig / "
        "(LTV_orig/100) = 0, so updated LTV and the double-trigger interaction "
        "are incomputable for every row of the loan; these are exactly the "
        "rows where the vendor's own LTV_time is NaN.",
        before, df,
    )

    # -- step 6: non-terminal rows with balance_time <= 0 ------------------
    before = df
    df = df[~((df["balance_time"] <= 0) & (df["status_time"] == 0))]
    wf.record(
        "zero_balance_live_rows",
        "Non-terminal (status 0) rows with balance_time <= 0: zero exposure "
        "on a live row is a missing-coded balance, not a real state — the "
        "history continues or the loan is censored at the prior quarter. "
        "Terminal payoff rows with balance 0 are KEPT (the zero balance IS "
        "the payoff; the row carries the competing-risk event).",
        before, df,
    )

    # -- step 7: rows with interest_rate_time <= 0 -------------------------
    before = df
    df = df[df["interest_rate_time"] > 0]
    wf.record(
        "nonpositive_current_note_rate_rows",
        "Rows with interest_rate_time missing-coded as 0: the prepayment "
        "incentive (note rate - market rate) is incomputable; all such rows "
        "are status 0, so no events are lost.",
        before, df,
    )

    return df.reset_index(drop=True), notes


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["loan_age"] = df["time"] - df["orig_time"]           # quarters on book
    df["time_to_mat"] = df["mat_time"] - df["time"]          # quarters to maturity
    df["default_event"] = (df["status_time"] == 1).astype("int8")
    df["payoff_event"] = (df["status_time"] == 2).astype("int8")
    df["terminal_event"] = (df["status_time"] != 0).astype("int8")
    df["is_last_obs"] = (
        df["time"].eq(df.groupby("id")["time"].transform("max")).astype("int8")
    )
    outcome = np.where(
        df["default_event"] == 1, "default",
        np.where(df["payoff_event"] == 1, "payoff", "censored"),
    )
    last_outcome = (
        pd.Series(outcome, index=df.index)
        .where(df["is_last_obs"] == 1)
        .groupby(df["id"]).transform("first")
    )
    df["loan_outcome"] = last_outcome                        # loan-level label

    # updated LTV (derivation in module docstring):
    # LTV_orig * (balance_t / balance_orig) * (hpi_orig / hpi_t)
    df["updated_ltv"] = (
        df["LTV_orig_time"]
        * (df["balance_time"] / df["balance_orig_time"])
        * (df["hpi_orig_time"] / df["hpi_time"])
    )

    df["prepay_incentive"] = df["interest_rate_time"] - df["rate_time"]
    df["orig_rate_missing"] = (df["Interest_Rate_orig_time"] <= 0).astype("int8")
    return df


def add_macro_lags(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Macro lags: groupby(id).shift primary, completed from the panel-internal
    time->macro map on first rows / gap rows (see module docstring)."""
    df = df.copy()

    # panel-internal national macro map (verified unique per quarter)
    per_t = df.groupby("time")[MACRO_COLS].nunique()
    assert (per_t.max() <= 1).all(), "macro series not constant within quarter"
    mm = df[["time"] + MACRO_COLS].drop_duplicates("time").set_index("time").sort_index()
    uer, gdp = mm["uer_time"], mm["gdp_time"]
    loghpi = np.log(mm["hpi_time"])

    def at(series: pd.Series, k: int) -> np.ndarray:
        return series.reindex(df["time"] - k).to_numpy()

    df["uer_lag1"] = at(uer, 1)
    df["uer_lag2"] = at(uer, 2)
    df["uer_chg4_lag1"] = at(uer, 1) - at(uer, 5)
    df["gdp_lag1"] = at(gdp, 1)
    df["hpi_growth_lag1"] = at(loghpi, 1) - at(loghpi, 2)

    # cross-check vs literal groupby(id).shift on consecutive rows
    g = df.groupby("id", sort=False)
    step1 = g["time"].diff(1).eq(1)
    step2 = g["time"].diff(2).eq(2)
    checks = {
        "uer_lag1": (g["uer_time"].shift(1), step1),
        "uer_lag2": (g["uer_time"].shift(2), step2),
        "gdp_lag1": (g["gdp_time"].shift(1), step1),
    }
    stats: dict = {}
    for col, (within, valid) in checks.items():
        comparable = valid & within.notna()
        mismatch = comparable & ((within - df[col]).abs() > 1e-9)
        assert not mismatch.any(), f"{col}: map lag != groupby(id).shift lag"
        stats[col] = {
            "rows_agree_groupby_shift": int(comparable.sum()),
            "rows_completed_from_time_map": int((~comparable & df[col].notna()).sum()),
            "rows_nan_warmup": int(df[col].isna().sum()),
        }

    df["lag_warmup"] = (df["time"] <= WARMUP_MAX_TIME).astype("int8")
    stats["gap_steps_within_loans"] = int((g["time"].diff(1).dropna() != 1).sum())
    stats["warmup_rows"] = int(df["lag_warmup"].sum())

    # double-trigger interaction (both factors in %)
    df["dt_ltv_uer"] = df["updated_ltv"] * df["uer_lag1"]
    return df, stats


def add_split(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["split"] = np.where(df["time"] <= TRAIN_MAX_TIME, "train", "oot")
    return df


# ----------------------------------------------------------------------------
# exhibits
# ----------------------------------------------------------------------------

def write_exhibits(wf: Waterfall, retained: dict, final: dict, lag_stats: dict,
                   notes: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": str(RAW_CSV.relative_to(PROJECT_ROOT)),
        "raw": wf.raw,
        "steps": wf.steps,
        "retained_but_flagged": retained,
        "lag_construction": lag_stats,
        "collision_ids": notes["collision_ids"],
        "final": final,
    }
    (OUT_DIR / "waterfall.json").write_text(json.dumps(payload, indent=2))

    lines = [
        "# Panel eligibility waterfall — dcr_full.csv -> panel.parquet",
        "",
        f"Generated {payload['generated_at_utc']} by `data/panel/build_panel.py`. "
        f"Raw: **{wf.raw['rows']:,} rows / {wf.raw['loans']:,} loans / "
        f"{wf.raw['defaults']:,} default rows / {wf.raw['payoffs']:,} payoff rows**.",
        "",
        "| # | Step | Rows in | Rows dropped | Defaults lost | Payoffs lost | Rows out | Loans out | Reason |",
        "|---|------|--------:|-------------:|--------------:|-------------:|---------:|----------:|--------|",
    ]
    for s in wf.steps:
        lines.append(
            f"| {s['step']} | {s['name']} | {s['rows_in']:,} | {s['rows_dropped']:,} "
            f"| {s['defaults_dropped']:,} | {s['payoffs_dropped']:,} "
            f"| {s['rows_out']:,} | {s['loans_out']:,} | {s['reason']} |"
        )
    lines += [
        "",
        f"**Final panel:** {final['rows']:,} rows / {final['loans']:,} loans / "
        f"{final['defaults']:,} defaults / {final['payoffs']:,} payoffs "
        f"({final['censored_loans']:,} loans right-censored; "
        f"train {final['train_rows']:,} rows, OOT {final['oot_rows']:,} rows).",
        "",
        "Note on step 1: the 3 'defaults lost' there are verbatim duplicate copies "
        "of retained default rows (ids 37067/37130/37792), not lost events. "
        "Steps 2 and 5 lose real events, counted above and reconciled in the "
        "self-checks. The raw file's documented '4 loans with rows after their "
        "default event' are exactly those three ids plus collision id 3014.",
        "",
        "## Counted but retained (flagged, not dropped)",
        "",
        "| Flag | Rows | Disposition |",
        "|------|-----:|-------------|",
    ]
    for k, v in retained.items():
        lines.append(f"| {k} | {v['rows']:,} | {v['disposition']} |")
    lines += [
        "",
        "## Lag construction audit",
        "",
        "Macro lags built inside the panel: `groupby(id).shift` on consecutive "
        "rows (agreement asserted to 1e-9), completed from the panel-internal "
        "time->macro map on loan first rows and within-loan gaps "
        f"({lag_stats['gap_steps_within_loans']:,} gap steps). No lookahead: "
        "only t-k (k>=1) values are referenced.",
        "",
        "| Lag column | Rows via groupby-shift | Completed from time map | NaN (warm-up) |",
        "|------------|----------------------:|------------------------:|--------------:|",
    ]
    for col in ["uer_lag1", "uer_lag2", "gdp_lag1"]:
        st = lag_stats[col]
        lines.append(
            f"| {col} | {st['rows_agree_groupby_shift']:,} "
            f"| {st['rows_completed_from_time_map']:,} | {st['rows_nan_warmup']:,} |"
        )
    lines += [
        "",
        f"Warm-up rows (time <= {WARMUP_MAX_TIME}, `lag_warmup=1`): "
        f"{lag_stats['warmup_rows']:,} — retained, excluded from the "
        "no-NaN guarantee on model columns.",
        "",
    ]
    (OUT_DIR / "waterfall.md").write_text("\n".join(lines))


# ----------------------------------------------------------------------------
# self-checks
# ----------------------------------------------------------------------------

def run_self_checks(df: pd.DataFrame, wf: Waterfall) -> list[str]:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        if not ok:
            failures.append(name)

    print("\nSELF-CHECKS")
    final = _profile(df)

    check("row_conservation",
          wf.raw["rows"] == final["rows"] + wf.total_rows_dropped,
          f"{wf.raw['rows']:,} raw = {final['rows']:,} kept + "
          f"{wf.total_rows_dropped:,} dropped across {len(wf.steps)} steps")

    dd = sum(s["defaults_dropped"] for s in wf.steps)
    pdrop = sum(s["payoffs_dropped"] for s in wf.steps)
    check("default_rows_reconciled",
          wf.raw["defaults"] == final["defaults"] + dd,
          f"{wf.raw['defaults']:,} raw default rows = {final['defaults']:,} kept "
          f"+ {dd} dropped (3 duplicate copies + real losses in steps 2/5)")
    check("payoff_rows_reconciled",
          wf.raw["payoffs"] == final["payoffs"] + pdrop,
          f"{wf.raw['payoffs']:,} raw payoff rows = {final['payoffs']:,} kept + {pdrop} dropped")

    check("key_unique", not df.duplicated(["id", "time"]).any(),
          "(id,time) is a unique key")

    at_most_one = bool((df.groupby("id")["terminal_event"].sum() <= 1).all())
    terminal_is_last = bool(
        (df.loc[df["terminal_event"] == 1, "is_last_obs"] == 1).all()
    )
    check("one_terminal_row_per_loan",
          at_most_one and terminal_is_last,
          "every loan has at most one terminal row, and it is the last row"
          if (at_most_one and terminal_is_last)
          else f"at_most_one={at_most_one}, terminal_is_last={terminal_is_last}")

    check("age_nonnegative_in_window",
          bool((df["loan_age"] >= 0).all()
               and df["time"].between(1, 60).all()),
          f"loan_age in [{df['loan_age'].min()}, {df['loan_age'].max()}], "
          f"time in [{df['time'].min()}, {df['time'].max()}]")

    model_rows = df["lag_warmup"] == 0
    nan_counts = df.loc[model_rows, MODEL_COLS].isna().sum()
    check("no_nan_in_model_cols_after_warmup",
          int(nan_counts.sum()) == 0,
          f"{int(model_rows.sum()):,} modelling rows, NaNs per column all zero"
          if int(nan_counts.sum()) == 0 else f"NaNs: {nan_counts[nan_counts > 0].to_dict()}")

    corr = df["updated_ltv"].corr(df["LTV_time"])
    maxdiff = (df["updated_ltv"] - df["LTV_time"]).abs().max()
    check("updated_ltv_matches_vendor_LTV_time",
          bool(corr > 0.999),
          f"corr = {corr:.12f}, max |diff| = {maxdiff:.2e} "
          "(vendor LTV_time is exactly the derived formula)")

    lgd_on_defaults = df.loc[df["default_event"] == 1, "lgd_time"].notna().all()
    lgd_elsewhere = df.loc[df["default_event"] == 0, "lgd_time"].isna().all()
    check("lgd_populated_exactly_on_defaults",
          bool(lgd_on_defaults and lgd_elsewhere),
          "lgd_time non-null on every default row and null elsewhere")

    tr, oo = df["split"] == "train", df["split"] == "oot"
    check("split_partition",
          bool((df.loc[tr, "time"].max() <= TRAIN_MAX_TIME)
               and (df.loc[oo, "time"].min() == TRAIN_MAX_TIME + 1)
               and (tr.sum() + oo.sum() == len(df))),
          f"train: {int(tr.sum()):,} rows (t<= {TRAIN_MAX_TIME}), "
          f"{int(df.loc[tr,'default_event'].sum()):,} defaults; "
          f"oot: {int(oo.sum()):,} rows (t {TRAIN_MAX_TIME+1}..60), "
          f"{int(df.loc[oo,'default_event'].sum()):,} defaults")

    first_obs = df.groupby("id").agg(t0=("time", "min"), ft=("first_time", "first"))
    mism = int((first_obs["t0"] != first_obs["ft"]).sum())
    check("left_truncation_consistent", mism == 0,
          f"first observed quarter == first_time for all but {mism} loans "
          "(left-truncated entrants enter the risk set at first_time)")

    return failures


# ----------------------------------------------------------------------------

def main() -> int:
    print(f"Loading {RAW_CSV} ...")
    raw = load_raw()
    wf = Waterfall(raw)
    print(f"  raw: {wf.raw['rows']:,} rows, {wf.raw['loans']:,} loans, "
          f"{wf.raw['defaults']:,} default rows, {wf.raw['payoffs']:,} payoff rows")

    df, notes = apply_waterfall(raw, wf)
    for s in wf.steps:
        print(f"  step {s['step']} {s['name']}: -{s['rows_dropped']:,} rows "
              f"(-{s['defaults_dropped']} defaults, -{s['payoffs_dropped']} payoffs) "
              f"-> {s['rows_out']:,}")

    # counted-but-retained diagnostics (on the eligible panel)
    retained = {
        "state_orig_time_missing": {
            "rows": int(df["state_orig_time"].isna().sum()),
            "disposition": "kept — state unused at this rung (national macros "
                           "only; no state-level merge in scope)",
        },
        "orig_rate_missing_coded_zero": {
            "rows": int((df["Interest_Rate_orig_time"] <= 0).sum()),
            "disposition": "kept + flag orig_rate_missing — origination-rate "
                           "snapshot missing-coded 0; current note rate is "
                           "populated and drives the prepayment incentive",
        },
    }

    df = add_derived(df)
    df, lag_stats = add_macro_lags(df)
    df = add_split(df)
    retained["lag_warmup_rows_time_le_5"] = {
        "rows": lag_stats["warmup_rows"],
        "disposition": "kept + flag lag_warmup — uer_chg4_lag1 needs uer(t-5), "
                       "undefined before t=6; excluded from no-NaN guarantee",
    }
    retained["within_loan_time_gaps"] = {
        "rows": lag_stats["gap_steps_within_loans"],
        "disposition": "kept — non-consecutive quarter steps inside loans; "
                       "macro lags repaired from the panel-internal time map "
                       "so lag distance is always exact",
    }

    final = _profile(df)
    final["censored_loans"] = int((df.groupby("id")["loan_outcome"].first()
                                   == "censored").sum())
    final["train_rows"] = int((df["split"] == "train").sum())
    final["oot_rows"] = int((df["split"] == "oot").sum())
    final["columns"] = len(df.columns)

    PANEL_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PANEL_PARQUET, index=False)
    write_exhibits(wf, retained, final, lag_stats, notes)
    print(f"\nWrote {PANEL_PARQUET.relative_to(PROJECT_ROOT)} "
          f"({final['rows']:,} rows x {final['columns']} cols), "
          f"outputs/panel/waterfall.json, outputs/panel/waterfall.md")

    failures = run_self_checks(df, wf)
    if failures:
        print(f"\n{len(failures)} SELF-CHECK FAILURE(S): {failures}")
        return 1
    print("\nAll self-checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
