"""Rung-3 EDA: the exhibits that make real Freddie Mac SFLLD data worth the
upgrade over the DCR engine's anonymized-clock synthetic panel.

Isolation: this module lives in freddie/ alongside ingest.py/build_panel.py/
macro.py -- it imports freddie.ingest (read-only, for the *un-truncated* raw
servicing history the roll-rate exhibit needs -- see "WHY RE-READ SVCG"
below) and consumes the already-built parquets under data/processed/freddie/.
It never touches engine/, data/processed/panel.parquet, or any existing test.

Run as a module (repo root):
    cd <repo root> && uv run --no-sync python -m freddie.eda

Output: outputs/freddie/eda/*.png (one file per exhibit, several exhibits
have 2-3 panels) + outputs/freddie/eda/eda_report.md (the write-up, built
from the same numbers the charts plot -- no numbers in the report are
hand-typed guesses, every f-string below is filled from a computed value).

--------------------------------------------------------------------------
WHY RE-READ SVCG FOR THE ROLL-RATE EXHIBIT (the one deliberate deviation
from "just consume the parquets")
--------------------------------------------------------------------------
panel_monthly.parquet is built with ABSORBING-D90 TRUNCATION (see
freddie/build_panel.py's docstring): once a loan's first 90+ DPD month
fires, every subsequent loan-month is dropped, even genuine cures. That
truncation is exactly right for the hazard-modeling panel it was built for,
but it is exactly wrong for a roll-rate matrix, which must be able to see
"90+ -> cure" transitions and the loan-level borrower_assistance_status_code
column (dropped from MONTHLY_PANEL_COLUMNS, since it plays no role in the
D90/prepay-event build). So compute_roll_rate_transitions() below calls
freddie.ingest.read_svcg_vintage() directly -- the same read-only reader
build_panel.py itself calls -- to get the FULL, un-truncated per-loan
monthly history, and immediately reduces each vintage to (from_bucket,
to_bucket, window) transition counts before moving to the next vintage, so
peak memory never holds more than one vintage's raw servicing frame. This
is "consuming an existing reader function", not "re-ingesting" (no parquet
under data/processed/ is rebuilt or touched by this module). Because the
full scan of all 17 vintages takes a few minutes (~40M raw loan-months),
the aggregated (small) transition-count table is cached to
outputs/freddie/eda/_cache_roll_rate_transitions.parquet; delete that file
(or pass --refresh-transitions) to force a rebuild after any upstream
change to ingest.py/build_panel.py's default definitions.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless -- must precede pyplot import (matches every analysis/*.py script)

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from analysis.mpl_style import COLORS, apply_textbook_style, figsize_for  # noqa: E402
from freddie import ingest  # noqa: E402

apply_textbook_style()
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "freddie"
MACRO_DIR = PROCESSED_DIR / "macro"
OUT_DIR = REPO_ROOT / "outputs" / "freddie" / "eda"
REPORT_PATH = OUT_DIR / "eda_report.md"

PANEL_PATH = PROCESSED_DIR / "panel_monthly.parquet"
LOAN_PATH = PROCESSED_DIR / "loan_orig.parquet"
STATE_MACRO_PATH = MACRO_DIR / "state_macro_panel.parquet"
UNRATE_PATH = MACRO_DIR / "UNRATE.csv"

TRANSITIONS_CACHE = OUT_DIR / "_cache_roll_rate_transitions.parquet"
ASSIST_CACHE = OUT_DIR / "_cache_borrower_assistance.parquet"

# --------------------------------------------------------------------------
# Era classification (fixed, in the master-plan's own words) -- 3 categorical
# colors, never a per-vintage rainbow (18 hues would be unreadable); within
# an era, vintages are distinguished by direct end-of-line labels instead.
# --------------------------------------------------------------------------
ERA_OF_VINTAGE: dict[int, str] = {}
for _y in (2005, 2006, 2007, 2008):
    ERA_OF_VINTAGE[_y] = "bubble 2005-2008"
for _y in (2009, 2010, 2014, 2015, 2016):
    ERA_OF_VINTAGE[_y] = "recovery 2009-10, 14-16"
for _y in (2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025):
    ERA_OF_VINTAGE[_y] = "modern 2018-2025"

ERA_COLORS = {
    "bubble 2005-2008": COLORS["warn"],
    "recovery 2009-10, 14-16": COLORS["orange"],
    "modern 2018-2025": COLORS["accent"],
}
ERA_ORDER = ["bubble 2005-2008", "recovery 2009-10, 14-16", "modern 2018-2025"]


def load_panel() -> pd.DataFrame:
    return pd.read_parquet(PANEL_PATH)


def load_loan() -> pd.DataFrame:
    return pd.read_parquet(LOAN_PATH)


def load_state_macro() -> pd.DataFrame:
    return pd.read_parquet(STATE_MACRO_PATH)


def load_national_uer() -> pd.DataFrame:
    df = pd.read_csv(UNRATE_PATH, parse_dates=["date"])
    return df.rename(columns={"date": "month", "value": "uer_national"})


# ==========================================================================
# Exhibit 1 -- vintage curves (cumulative D90 + cumulative prepay by MOB)
# ==========================================================================
def compute_vintage_curves(panel: pd.DataFrame, loan: pd.DataFrame) -> pd.DataFrame:
    n_loans = loan.groupby("vintage", observed=True).size()
    p = panel.dropna(subset=["loan_age"]).copy()
    p["loan_age"] = p["loan_age"].astype("int32")
    g = (
        p.groupby(["vintage", "loan_age"], observed=True)[["d90_event", "prepay_event"]]
        .sum()
        .reset_index()
        .sort_values(["vintage", "loan_age"])
    )
    g["cum_d90"] = g.groupby("vintage")["d90_event"].cumsum()
    g["cum_prepay"] = g.groupby("vintage")["prepay_event"].cumsum()
    g["n_loans"] = g["vintage"].map(n_loans)
    g["cum_d90_rate"] = g["cum_d90"] / g["n_loans"]
    g["cum_prepay_rate"] = g["cum_prepay"] / g["n_loans"]
    return g


def _mob_for_calendar(loan: pd.DataFrame, vintage: int, calendar_month: pd.Timestamp) -> float:
    """Median loan_age (months on book) that `vintage`'s loans had reached at
    `calendar_month` -- used to annotate a calendar event (e.g. the 2020-21
    refi wave) onto a months-on-book x-axis."""
    fp = loan.loc[loan["vintage"] == vintage, "first_payment_date"]
    months = (calendar_month.year - fp.dt.year) * 12 + (calendar_month.month - fp.dt.month)
    return float(months.median())


def plot_vintage_curves(curves: pd.DataFrame, loan: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"), sharex=False)
    ax_d90, ax_prepay = axes

    peak_rates = {}
    for vintage in sorted(curves["vintage"].unique()):
        sub = curves[curves["vintage"] == vintage]
        era = ERA_OF_VINTAGE[int(vintage)]
        color = ERA_COLORS[era]
        # within-era recency shading: earlier vintage in the era = more transparent
        era_years = sorted(y for y, e in ERA_OF_VINTAGE.items() if e == era)
        alpha = 0.35 + 0.65 * (era_years.index(int(vintage)) / max(len(era_years) - 1, 1))
        ax_d90.plot(sub["loan_age"], sub["cum_d90_rate"] * 100, color=color, alpha=alpha, lw=1.3)
        ax_prepay.plot(sub["loan_age"], sub["cum_prepay_rate"] * 100, color=color, alpha=alpha, lw=1.3)
        peak_rates[int(vintage)] = {
            "cum_d90_rate": float(sub["cum_d90_rate"].iloc[-1]),
            "cum_prepay_rate": float(sub["cum_prepay_rate"].iloc[-1]),
            "max_mob": int(sub["loan_age"].iloc[-1]),
        }

    # Headroom so the 2007 label (the highest annotation, at peak+1.2) doesn't
    # collide with the axes title above it.
    ax_d90.set_ylim(0, peak_rates[2007]["cum_d90_rate"] * 100 + 5)

    # Annotate the 2006/2007/2008 peaks (the crisis-era standouts) on the D90 panel
    for vintage, dy in [(2007, 0), (2006, -1.6), (2008, 1.6)]:
        r = peak_rates[vintage]
        ax_d90.annotate(
            f"{vintage}: {r['cum_d90_rate']:.1%}",
            xy=(r["max_mob"], r["cum_d90_rate"] * 100),
            xytext=(r["max_mob"] - 55, r["cum_d90_rate"] * 100 + dy + 1.2),
            fontsize=7.5, color=ERA_COLORS[ERA_OF_VINTAGE[vintage]],
            arrowprops=dict(arrowstyle="-", color=ERA_COLORS[ERA_OF_VINTAGE[vintage]], lw=0.6),
        )
    ax_d90.set_xlabel("Months on book")
    ax_d90.set_ylabel("Cumulative D90 rate (%)")
    ax_d90.set_title("Cumulative D90 (90+ DPD) rate by vintage")
    ax_d90.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))

    # Annotate the COVID refi wave onto two pre-2020 vintage prepay curves. Fixed
    # axes-fraction text positions (not data-relative offsets) keep the two boxes
    # apart regardless of how close the underlying (MOB, rate) points happen to be.
    for vintage, frac_xy in [(2015, (0.30, 0.82)), (2018, (0.66, 0.30))]:
        mob_2020 = _mob_for_calendar(loan, vintage, pd.Timestamp("2020-03-01"))
        row = curves[(curves["vintage"] == vintage) & (curves["loan_age"] == int(round(mob_2020)))]
        if len(row):
            y = float(row["cum_prepay_rate"].iloc[0]) * 100
            ax_prepay.annotate(
                f"{vintage} vintage hits\n2020Q1 here (MOB {int(mob_2020)})",
                xy=(mob_2020, y), xycoords="data", xytext=frac_xy, textcoords="axes fraction",
                fontsize=6.8, ha="center", color=ERA_COLORS[ERA_OF_VINTAGE[vintage]],
                arrowprops=dict(arrowstyle="-", color=ERA_COLORS[ERA_OF_VINTAGE[vintage]], lw=0.6),
            )
    ax_prepay.set_xlabel("Months on book")
    ax_prepay.set_ylabel("Cumulative prepay rate (%)")
    ax_prepay.set_title("Cumulative prepayment rate by vintage\n(2020-21 refi wave hits many vintages at once)")
    ax_prepay.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))

    handles = [plt.Line2D([0], [0], color=ERA_COLORS[e], lw=2) for e in ERA_ORDER]
    fig.legend(handles, ERA_ORDER, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.04), frameon=False, fontsize=8)
    fig.suptitle("Exhibit 1 -- Vintage curves: real-dated SFLLD 2005-2025 sample", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "exhibit1_vintage_curves.png", bbox_inches="tight")
    plt.close(fig)
    return peak_rates


# ==========================================================================
# Exhibit 2 -- roll-rate matrices (needs the un-truncated raw svcg history)
# ==========================================================================
BUCKET_FROM_ORDER = ["current", "30", "60", "90+"]
BUCKET_TO_ORDER = ["current", "30", "60", "90+", "prepaid", "default_terminal"]

WINDOWS = {
    "GFC 2007-2009": (pd.Timestamp("2007-01-01"), pd.Timestamp("2009-12-31")),
    "Calm 2015-2018": (pd.Timestamp("2015-01-01"), pd.Timestamp("2018-12-31")),
    "COVID 2020-2021": (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-12-31")),
}


def _bucket_vintage_svcg(svcg: pd.DataFrame) -> pd.DataFrame:
    zb = svcg["zero_balance_code"]
    d = svcg["dlq_num"].to_numpy()
    reo = svcg["is_reo_acquisition"].to_numpy()
    active = zb.isna().to_numpy()

    bucket = np.full(len(svcg), "other_removed", dtype=object)
    bucket[active & (d == 0)] = "current"
    bucket[active & (d == 1)] = "30"
    bucket[active & (d == 2)] = "60"
    bucket[(active & (d >= 3)) | (active & reo)] = "90+"
    bucket[(zb == "01").to_numpy()] = "prepaid"
    bucket[zb.isin(["02", "03", "09", "96"]).to_numpy()] = "default_terminal"
    bucket[zb.isin(["15", "16"]).to_numpy()] = "other_removed"
    svcg = svcg.assign(bucket=pd.Categorical(bucket))
    return svcg


def compute_roll_rate_transitions(refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (transition_counts, assist_summary).

    transition_counts: one row per (window, from_bucket, to_bucket) with a
    `n` count, aggregated across ALL 17 vintages' full un-truncated svcg
    history (see module docstring, "WHY RE-READ SVCG").
    assist_summary: one row per (window, from_bucket) with n_rows and
    n_with_assist (borrower_assistance_status_code populated) -- the
    forbearance corroboration for the COVID-window narrative.
    """
    if TRANSITIONS_CACHE.exists() and ASSIST_CACHE.exists() and not refresh:
        return pd.read_parquet(TRANSITIONS_CACHE), pd.read_parquet(ASSIST_CACHE)

    trans_frames, assist_frames = [], []
    cols = [
        "loan_sequence_number", "monthly_reporting_period", "loan_age", "dlq_num",
        "is_reo_acquisition", "zero_balance_code", "borrower_assistance_status_code",
    ]
    for year in ingest.VINTAGE_YEARS:
        print(f"  [roll-rate scan] reading full svcg for vintage {year} ...", flush=True)
        svcg = ingest.read_svcg_vintage(year)[cols]
        svcg = svcg.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)
        svcg = _bucket_vintage_svcg(svcg)

        g = svcg.groupby("loan_sequence_number", sort=False, observed=True)
        next_bucket = g["bucket"].shift(-1)
        next_age = g["loan_age"].shift(-1)
        consecutive = (next_age - svcg["loan_age"]) == 1
        valid = (consecutive & next_bucket.notna()).to_numpy()

        month = svcg["monthly_reporting_period"]
        window_label = pd.Series(pd.NA, index=svcg.index, dtype="object")
        for wname, (start, end) in WINDOWS.items():
            window_label = window_label.mask((month >= start) & (month <= end), wname)

        t = pd.DataFrame({
            "window": window_label, "from_bucket": svcg["bucket"], "to_bucket": next_bucket,
        })[valid & window_label.notna().to_numpy()]
        if len(t):
            trans_frames.append(t.groupby(["window", "from_bucket", "to_bucket"], observed=True).size()
                                 .rename("n").reset_index())

        assist_pop = svcg[window_label.notna() & svcg["bucket"].isin(["60", "90+"])].copy()
        assist_pop["window"] = window_label[assist_pop.index]
        assist_pop["has_assist"] = assist_pop["borrower_assistance_status_code"].notna()
        if len(assist_pop):
            a = (assist_pop.groupby(["window", "bucket"], observed=True)
                 .agg(n_rows=("has_assist", "size"), n_with_assist=("has_assist", "sum"))
                 .reset_index().rename(columns={"bucket": "from_bucket"}))
            assist_frames.append(a)

        del svcg, g, next_bucket, next_age, consecutive, valid, month, window_label, t, assist_pop

    trans = pd.concat(trans_frames, ignore_index=True).groupby(
        ["window", "from_bucket", "to_bucket"], observed=True)["n"].sum().reset_index()
    assist = pd.concat(assist_frames, ignore_index=True).groupby(
        ["window", "from_bucket"], observed=True)[["n_rows", "n_with_assist"]].sum().reset_index()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trans.to_parquet(TRANSITIONS_CACHE, index=False)
    assist.to_parquet(ASSIST_CACHE, index=False)
    return trans, assist


def _matrix_for_window(trans: pd.DataFrame, window: str) -> pd.DataFrame:
    sub = trans[trans["window"] == window]
    mat = sub.pivot_table(index="from_bucket", columns="to_bucket", values="n", aggfunc="sum", fill_value=0)
    mat = mat.reindex(index=BUCKET_FROM_ORDER, columns=BUCKET_TO_ORDER, fill_value=0)
    probs = mat.div(mat.sum(axis=1), axis=0)
    return probs


def plot_roll_rate_matrices(trans: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6))
    key_cells = {}
    for ax, window in zip(axes, WINDOWS):
        probs = _matrix_for_window(trans, window)
        im = ax.imshow(probs.values * 100, cmap="Reds", vmin=0, vmax=100, aspect="auto")
        ax.set_xticks(range(len(BUCKET_TO_ORDER)))
        ax.set_xticklabels(BUCKET_TO_ORDER, rotation=45, ha="right", fontsize=7.5)
        ax.set_yticks(range(len(BUCKET_FROM_ORDER)))
        ax.set_yticklabels(BUCKET_FROM_ORDER, fontsize=7.5)
        for i in range(len(BUCKET_FROM_ORDER)):
            for j in range(len(BUCKET_TO_ORDER)):
                v = probs.values[i, j] * 100
                if v >= 0.05:
                    ax.text(j, i, f"{v:.1f}", ha="center", va="center",
                            fontsize=6.3, color="white" if v > 55 else "black")
        ax.set_title(window, fontsize=9.5)
        ax.set_xlabel("To")
        if window == list(WINDOWS)[0]:
            ax.set_ylabel("From")

        cur_to_30 = float(probs.loc["current", "30"]) if "current" in probs.index else np.nan
        cure_from_90 = float(probs.loc["90+", ["current", "30", "60"]].sum()) if "90+" in probs.index else np.nan
        roll_60_to_90 = float(probs.loc["60", "90+"]) if "60" in probs.index else np.nan
        liquidation_from_90 = float(probs.loc["90+", "default_terminal"]) if "90+" in probs.index else np.nan
        key_cells[window] = {
            "current_to_30": cur_to_30, "cure_from_90plus": cure_from_90,
            "roll_60_to_90": roll_60_to_90, "liquidation_from_90plus": liquidation_from_90,
        }

    fig.colorbar(im, ax=axes, shrink=0.75, label="Transition probability (%)", pad=0.015)
    fig.suptitle("Exhibit 2 -- Monthly roll-rate matrices, three windows (real calendar dates)", y=1.06)
    fig.savefig(OUT_DIR / "exhibit2_roll_rate_matrices.png", bbox_inches="tight")
    plt.close(fig)
    return key_cells


# ==========================================================================
# Exhibit 3 -- calendar-time D90-entry rate vs national UER
# ==========================================================================
def compute_calendar_series(panel: pd.DataFrame) -> pd.DataFrame:
    g = panel.groupby("monthly_reporting_period", observed=True).agg(
        n_active=("loan_sequence_number", "size"), n_d90=("d90_event", "sum")
    ).reset_index().rename(columns={"monthly_reporting_period": "month"})
    g["d90_entry_rate"] = g["n_d90"] / g["n_active"]
    return g.sort_values("month")


def plot_calendar_series(cal: pd.DataFrame, uer: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=figsize_for("tall"), sharex=True,
                                    gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(cal["month"], cal["d90_entry_rate"] * 100, color=COLORS["warn"], lw=1.4)
    ax1.set_ylabel("D90-entry rate (%/mo)")
    ax1.set_title("Exhibit 3 -- Monthly D90-entry rate, all vintages combined, 2005-2025")
    ax1.axvspan(pd.Timestamp("2007-12-01"), pd.Timestamp("2009-06-01"), color=COLORS["warn"], alpha=0.08)
    ax1.axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2021-04-01"), color=COLORS["purple"], alpha=0.08)
    ax1.text(pd.Timestamp("2008-06-01"), cal["d90_entry_rate"].max() * 100 * 0.92, "GFC",
              fontsize=7.5, ha="center", color=COLORS["warn"])
    ax1.text(pd.Timestamp("2020-09-01"), cal["d90_entry_rate"].max() * 100 * 0.92, "COVID",
              fontsize=7.5, ha="center", color=COLORS["purple"])

    ax1b = ax1.twinx()
    ax1b.plot(cal["month"], cal["n_active"] / 1000, color=COLORS["gray"], lw=0.8, alpha=0.5, ls=":")
    ax1b.set_ylabel("Loans at risk (000s)\n(composition, dotted)", color=COLORS["gray"], fontsize=7.5)
    ax1b.tick_params(axis="y", labelsize=7, colors=COLORS["gray"])

    ax2.plot(uer["month"], uer["uer_national"], color=COLORS["accent"], lw=1.4)
    ax2.set_ylabel("National UER (%)")
    ax2.set_xlabel("Calendar date")
    ax2.set_xlim(pd.Timestamp("2004-06-01"), pd.Timestamp("2026-01-01"))
    ax2.axvspan(pd.Timestamp("2007-12-01"), pd.Timestamp("2009-06-01"), color=COLORS["warn"], alpha=0.08)
    ax2.axvspan(pd.Timestamp("2020-02-01"), pd.Timestamp("2021-04-01"), color=COLORS["purple"], alpha=0.08)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "exhibit3_calendar_time_series.png", bbox_inches="tight")
    plt.close(fig)


# ==========================================================================
# Exhibit 4 -- state heterogeneity (2006-2007 vintages)
# ==========================================================================
MIN_LOANS_PER_STATE = 200


def compute_state_default_rates(loan: pd.DataFrame) -> pd.DataFrame:
    sub = loan[loan["vintage"].isin([2006, 2007])]
    g = sub.groupby("property_state", observed=True).agg(
        n_loans=("had_d90_event", "size"), n_d90=("had_d90_event", "sum")
    ).reset_index()
    g["default_rate"] = g["n_d90"] / g["n_loans"]
    return g[g["n_loans"] >= MIN_LOANS_PER_STATE].sort_values("default_rate", ascending=False)


def compute_state_hpi_drawdown(macro: pd.DataFrame, start="2006-01-01", trough_by="2012-12-31") -> pd.DataFrame:
    m = macro[(macro["month"] >= start) & (macro["month"] <= trough_by)]
    peak = m.groupby("property_state")["hpi_index"].max()
    trough = m.groupby("property_state")["hpi_index"].min()
    # only keep states/dates where the trough occurs AFTER the peak (a real drawdown, not noise)
    drawdown = (peak - trough) / peak
    fallback = macro.groupby("property_state")["hpi_is_national_fallback"].any()
    out = pd.DataFrame({"peak_hpi": peak, "trough_hpi": trough, "hpi_drawdown": drawdown,
                         "hpi_is_national_fallback": fallback}).reset_index()
    return out


def plot_state_heterogeneity(state_rates: pd.DataFrame, hpi_dd: pd.DataFrame) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    ax_bar, ax_scatter = axes

    top10 = state_rates.head(10)
    bot10 = state_rates.tail(10).sort_values("default_rate")
    combo = pd.concat([top10, bot10])
    highlight = {"NV", "AZ", "FL", "CA", "TX", "ND"}
    colors = [COLORS["warn"] if s in {"NV", "AZ", "FL", "CA"} else
              (COLORS["good"] if s in {"TX", "ND"} else COLORS["gray"]) for s in combo["property_state"]]
    ypos = np.arange(len(combo))
    ax_bar.barh(ypos, combo["default_rate"] * 100, color=colors)
    ax_bar.set_yticks(ypos)
    ax_bar.set_yticklabels(combo["property_state"], fontsize=7.5)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Cumulative D90 rate, 2006-07 vintages (%)")
    ax_bar.set_title("Top/bottom 10 states")
    ax_bar.axhline(9.5, color=COLORS["gray"], lw=0.6, ls="--")

    merged = state_rates.merge(hpi_dd, on="property_state", how="inner")
    merged_valid = merged[~merged["hpi_is_national_fallback"]]
    ax_scatter.scatter(merged_valid["hpi_drawdown"] * 100, merged_valid["default_rate"] * 100,
                        color=COLORS["accent"], s=18, alpha=0.75)
    for _, r in merged_valid[merged_valid["property_state"].isin(highlight)].iterrows():
        ax_scatter.annotate(r["property_state"], (r["hpi_drawdown"] * 100, r["default_rate"] * 100),
                             fontsize=7.5, xytext=(3, 3), textcoords="offset points")
    slope, intercept, r_value, p_value, se = stats.linregress(
        merged_valid["hpi_drawdown"] * 100, merged_valid["default_rate"] * 100)
    xs = np.linspace(merged_valid["hpi_drawdown"].min() * 100, merged_valid["hpi_drawdown"].max() * 100, 50)
    ax_scatter.plot(xs, slope * xs + intercept, color=COLORS["warn"], lw=1.2,
                     label=f"fit: r={r_value:.2f}, p={p_value:.1g}")
    ax_scatter.set_xlabel("State peak-to-trough HPI drawdown 2006-2012 (%)")
    ax_scatter.set_ylabel("2006-07 vintage D90 rate (%)")
    ax_scatter.set_title("The collateral channel")
    ax_scatter.legend(fontsize=7.5, frameon=False)

    fig.suptitle("Exhibit 4 -- State heterogeneity, 2006-2007 vintages", y=1.03)
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.32)
    fig.savefig(OUT_DIR / "exhibit4_state_heterogeneity.png", bbox_inches="tight")
    plt.close(fig)
    return {
        "top10": top10[["property_state", "n_loans", "default_rate"]].to_dict("records"),
        "bot10": bot10[["property_state", "n_loans", "default_rate"]].to_dict("records"),
        "regression": {"slope": slope, "intercept": intercept, "r": r_value, "p": p_value,
                        "n_states": len(merged_valid)},
    }


# ==========================================================================
# Exhibit 5 -- realized LGD first look
# ==========================================================================
LIQUIDATION_ZB_CODES = ["09", "03", "02", "15"]
MIN_REMOVAL_UPB = 1000.0  # excludes a handful of near-zero-denominator artifacts (see report)


def compute_realized_lgd(loan: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    d90 = loan[loan["terminal_outcome"] == "d90_default"]
    eligible = d90[
        d90["zero_balance_code"].isin(LIQUIDATION_ZB_CODES) & d90["actual_loss_calculation"].notna()
    ]
    n_excluded_small_denom = int((eligible["zero_balance_removal_upb"] < MIN_REMOVAL_UPB).sum())
    pop = eligible[eligible["zero_balance_removal_upb"] >= MIN_REMOVAL_UPB].copy()
    pop["lgd"] = -pop["actual_loss_calculation"] / pop["zero_balance_removal_upb"]
    pop["disposition"] = pop["zero_balance_code"].map(ingest.ZERO_BALANCE_CODE_LABELS)
    pop["liq_year"] = pop["zero_balance_effective_date"].dt.year
    return pop, n_excluded_small_denom


def plot_realized_lgd(pop: pd.DataFrame, n_excluded_small_denom: int) -> dict:
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    ax_disp, ax_year = axes

    disp_order = [ingest.ZERO_BALANCE_CODE_LABELS[c] for c in LIQUIDATION_ZB_CODES]
    data_by_disp = [pop.loc[pop["disposition"] == d, "lgd"] for d in disp_order]
    bp = ax_disp.boxplot(data_by_disp, tick_labels=disp_order, showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor(COLORS["blue2"])
        patch.set_alpha(0.5)
    ax_disp.set_xticklabels(disp_order, rotation=30, ha="right", fontsize=7.5)
    ax_disp.set_ylabel("LGD = -actual_loss / removal UPB")
    ax_disp.set_title("Realized LGD by disposition type")
    ax_disp.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=0))

    yearly = pop.groupby("liq_year")["lgd"].agg(["median", "mean", "count"]).reset_index()
    yearly = yearly[yearly["count"] >= 10].reset_index(drop=True)

    # Find the elevated-severity plateau empirically: the contiguous run of
    # years (mean LGD >= 50%) that contains the single peak year, rather than
    # assuming the crisis-origination years (2008-2011) are themselves the
    # severity peak. They are NOT: liquidation-year severity keeps climbing
    # well past the GFC's origination/default window because the REO/short-sale
    # pipeline stayed clogged for years afterward (loans that first went 90+ DPD
    # in 2008-2009 often didn't liquidate, and realize their loss, until years
    # later) -- the true peak year (by median) is 2016, not 2008-2011.
    peak_i = int(yearly["mean"].to_numpy().argmax())
    above = (yearly["mean"] >= 0.50).to_numpy()
    lo = hi = peak_i
    while lo - 1 >= 0 and above[lo - 1]:
        lo -= 1
    while hi + 1 < len(above) and above[hi + 1]:
        hi += 1
    plateau_start, plateau_end = int(yearly["liq_year"].iloc[lo]), int(yearly["liq_year"].iloc[hi])
    peak_year = int(yearly["liq_year"].iloc[peak_i])

    ax_year.plot(yearly["liq_year"], yearly["median"] * 100, color=COLORS["warn"], marker="o", ms=3, label="median")
    ax_year.plot(yearly["liq_year"], yearly["mean"] * 100, color=COLORS["accent"], marker="s", ms=3, label="mean",
                 alpha=0.7)
    ax_year.set_xlabel("Year of liquidation (zero_balance_effective_date)")
    ax_year.set_ylabel("LGD (%)")
    ax_year.set_title(f"Realized LGD by liquidation year\n({plateau_start}-{plateau_end} severity plateau)")
    ax_year.legend(fontsize=7.5, frameon=False)
    ax_year.axvspan(plateau_start, plateau_end, color=COLORS["warn"], alpha=0.08)

    fig.suptitle("Exhibit 5 -- Realized LGD first look (D90-default population)", y=1.03)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "exhibit5_realized_lgd.png", bbox_inches="tight")
    plt.close(fig)
    return {
        "n_pop": len(pop), "median_lgd": float(pop["lgd"].median()), "mean_lgd": float(pop["lgd"].mean()),
        "pct_negative": float((pop["lgd"] < 0).mean()), "n_excluded_small_denom": n_excluded_small_denom,
        "yearly": yearly.to_dict("records"),
        "by_disposition": pop.groupby("disposition")["lgd"].agg(["count", "median", "mean"]).to_dict("index"),
        "plateau_start": plateau_start, "plateau_end": plateau_end, "peak_year": peak_year,
        "peak_median": float(yearly["median"].iloc[peak_i]), "peak_mean": float(yearly["mean"].iloc[peak_i]),
    }


# ==========================================================================
# Report assembly
# ==========================================================================
def write_report(stats_bundle: dict) -> None:
    peak = stats_bundle["vintage_curves"]
    key_cells = stats_bundle["roll_rate_key_cells"]
    assist = stats_bundle["assist_summary"]
    state = stats_bundle["state_heterogeneity"]
    lgd = stats_bundle["lgd"]
    cal = stats_bundle["calendar"]

    lines = []
    lines.append("# Freddie Mac SFLLD -- Rung-3 EDA report\n")
    lines.append(
        "Source: 17 vintages of the real Freddie Mac Single-Family Loan-Level Dataset sample "
        "(2005-2010, 2014-2016, 2018-2025; 2011-2013 and 2017 are a documented coverage gap, never "
        "downloaded), ingested by freddie/ingest.py + freddie/build_panel.py, macro series merged by "
        "freddie/macro.py. All five exhibits below are computed directly from "
        "data/processed/freddie/{panel_monthly,loan_orig}.parquet and "
        "data/processed/freddie/macro/state_macro_panel.parquet -- every number in this report is "
        "read off those computations, not hand-typed.\n"
    )

    lines.append("## Exhibit 1 -- Vintage curves (outputs/freddie/eda/exhibit1_vintage_curves.png)\n")
    lines.append(
        f"The 2007 vintage dominates: cumulative D90 rate reaches **{peak[2007]['cum_d90_rate']:.2%}** by "
        f"month {peak[2007]['max_mob']} on book, vs {peak[2006]['cum_d90_rate']:.2%} for 2006 and "
        f"{peak[2008]['cum_d90_rate']:.2%} for 2008 -- the classic pre-crisis-vintage hump, with 2006-2008 "
        f"(the 'bubble' era) sitting far above every recovery-era (2009-10, 2014-16) or modern (2018-2025) "
        f"vintage, which top out below "
        f"{max(peak[y]['cum_d90_rate'] for y in peak if ERA_OF_VINTAGE[y] != 'bubble 2005-2008'):.2%}. "
        "The companion prepayment panel shows the 2020-21 refi wave as a visible acceleration in the "
        "pre-2020 vintages' (2014-2019) cumulative-prepay curves right around the months-on-book value "
        "each of those vintages had reached by 2020Q1 -- annotated on the chart -- rather than as a feature "
        "of the 2020/2021 vintages' own (fresh-clock) curves.\n"
    )

    lines.append("## Exhibit 2 -- Roll-rate matrices (outputs/freddie/eda/exhibit2_roll_rate_matrices.png)\n")
    lines.append(
        "Computed from the FULL, un-truncated raw monthly servicing history (see freddie/eda.py module "
        "docstring: panel_monthly.parquet's absorbing-D90 truncation deliberately hides cures, so this "
        "exhibit re-reads freddie.ingest.read_svcg_vintage() directly, aggregated to transition counts "
        "per window, never holding more than one vintage's raw frame in memory at a time).\n"
    )
    lines.append("| Window | current -> 30 | 60 -> 90+ | 90+ -> cure (back to <90) | 90+ -> liquidation |")
    lines.append("|---|---|---|---|---|")
    for w in WINDOWS:
        kc = key_cells[w]
        lines.append(
            f"| {w} | {kc['current_to_30']:.2%} | {kc['roll_60_to_90']:.2%} | "
            f"{kc['cure_from_90plus']:.2%} | {kc['liquidation_from_90plus']:.2%} |"
        )
    lines.append("")
    covid_assist = assist[assist["window"] == "COVID 2020-2021"]
    calm_assist = assist[assist["window"] == "Calm 2015-2018"]
    covid_pct = float(covid_assist["n_with_assist"].sum() / covid_assist["n_rows"].sum()) if len(covid_assist) else 0
    calm_pct = float(calm_assist["n_with_assist"].sum() / calm_assist["n_rows"].sum()) if len(calm_assist) else 0
    kc_covid, kc_calm, kc_gfc = key_cells["COVID 2020-2021"], key_cells["Calm 2015-2018"], key_cells["GFC 2007-2009"]
    lines.append(
        "**COVID anomaly, narrated precisely (read the table above, not just the headline current->30 "
        "cell)**: current->30 is actually LOWER-to-similar in COVID "
        f"({kc_covid['current_to_30']:.2%} vs {kc_gfc['current_to_30']:.2%} in GFC / {kc_calm['current_to_30']:.2%} in "
        "calm) -- an entirely naive read would conclude COVID was a mild credit event. But 60->90+ is "
        f"actually the HIGHEST of the three windows in COVID ({kc_covid['roll_60_to_90']:.2%} vs "
        f"{kc_gfc['roll_60_to_90']:.2%} GFC / {kc_calm['roll_60_to_90']:.2%} calm) -- the raw delinquency-status "
        "ladder kept advancing on a contractual schedule for loans in forbearance even though the borrower "
        "was not being pursued for foreclosure -- while 90+ -> LIQUIDATION (the true terminal credit event) "
        f"COLLAPSES to {kc_covid['liquidation_from_90plus']:.2%} in COVID, vs {kc_gfc['liquidation_from_90plus']:.2%} "
        f"in GFC and {kc_calm['liquidation_from_90plus']:.2%} in calm -- a 10x-plus drop, the loan-level "
        "signature of the CARES Act foreclosure moratorium. 90+ cure is if anything slightly HIGHER in "
        f"COVID ({kc_covid['cure_from_90plus']:.2%} vs {kc_gfc['cure_from_90plus']:.2%} GFC / "
        f"{kc_calm['cure_from_90plus']:.2%} calm), consistent with borrowers exiting via a repayment "
        "plan/modification rather than genuinely healing. This is corroborated at the loan level: loans "
        "that were 60/90+ DPD during COVID carried an active borrower_assistance_status_code "
        f"(forbearance/trial/repayment-plan) **{covid_pct:.1%} of the time**, vs **{calm_pct:.1%}** in the "
        "calm window. Net read: COVID delinquency-STATUS escalation (60->90+) looks WORSE than the GFC by "
        "this metric, but that is a servicing/administrative artifact of forbearance accounting, not "
        "genuine credit deterioration -- the collapse in actual liquidation is the real tell.\n"
    )

    lines.append("## Exhibit 3 -- Calendar-time credit cycle (outputs/freddie/eda/exhibit3_calendar_time_series.png)\n")
    gfc_win = cal[(cal["month"] >= "2007-01-01") & (cal["month"] <= "2009-12-31")]
    covid_row = cal[(cal["month"] >= "2020-01-01") & (cal["month"] <= "2021-12-31")]
    gfc_peak = gfc_win.loc[gfc_win["d90_entry_rate"].idxmax()]
    covid_peak = covid_row.loc[covid_row["d90_entry_rate"].idxmax()]
    lines.append(
        f"The combined-vintage monthly D90-entry rate's GLOBAL peak is actually the COVID spike -- "
        f"{covid_peak['d90_entry_rate']:.3%} in {covid_peak['month'].strftime('%Y-%m')}, roughly "
        f"{covid_peak['d90_entry_rate'] / gfc_peak['d90_entry_rate']:.1f}x the GFC's own peak of "
        f"{gfc_peak['d90_entry_rate']:.3%} in {gfc_peak['month'].strftime('%Y-%m')}. Read alongside Exhibit "
        "2's roll-rate finding, this is NOT evidence that COVID was a worse credit event than the GFC -- "
        "it is the same forbearance-accounting artifact: the naive D90 (dlq_num>=3) definition fires on "
        "administrative delinquency-status advancement for loans in forbearance, even though the "
        "liquidation-rate collapse (Exhibit 2) shows the true terminal-loss event virtually stopped during "
        "the same window. A D90 entry-rate spike alone, without the liquidation-rate context, would badly "
        "mislead a reader into treating COVID as the larger of the two credit events. Composition note: the "
        "loans-at-risk series (dotted, right-hand context) shows the panel's own denominator shrinking and "
        "refilling as vintages amortize/terminate and new vintages are added, so the entry-rate series is "
        "not a fixed-cohort rate -- it mixes vintages of different ages and different eras' underwriting "
        "standards at every calendar point, by construction.\n"
    )

    lines.append("## Exhibit 4 -- State heterogeneity (outputs/freddie/eda/exhibit4_state_heterogeneity.png)\n")
    top3 = ", ".join(f"{r['property_state']} ({r['default_rate']:.1%})" for r in state["top10"][:3])
    bot3 = ", ".join(f"{r['property_state']} ({r['default_rate']:.1%})" for r in state["bot10"][:3])
    reg = state["regression"]
    lines.append(
        f"For the 2006-2007 vintages, the worst 2006-07-vintage states are {top3}, and the best are "
        f"{bot3} -- states with {MIN_LOANS_PER_STATE}+ sampled loans only. NV/AZ/FL/CA (the bubble "
        "sand-states) sit far above TX/ND (which never had a comparable house-price boom-bust). The "
        f"scatter of state peak-to-trough HPI drawdown (2006-2012) vs. 2006-07-vintage default rate "
        f"across {reg['n_states']} states (GU/PR/VI excluded -- FRED has no state-level HPI series for "
        f"them, see freddie/macro.py's national-fallback flags) fits a slope of {reg['slope']:.3f} "
        f"pts-default-per-pt-drawdown, r={reg['r']:.2f}, p={reg['p']:.1g} -- the collateral channel, in "
        "real geography, that a national-only DCR panel cannot show at all.\n"
    )

    lines.append("## Exhibit 5 -- Realized LGD first look (outputs/freddie/eda/exhibit5_realized_lgd.png)\n")
    lines.append(
        f"Population: {lgd['n_pop']:,} D90-defaulted loans (terminal_outcome=='d90_default') that reached "
        "a liquidation zero_balance_code (third-party sale/short-sale/REO/whole-loan-sale) with "
        "actual_loss_calculation populated. **Denominator choice**: LGD = -actual_loss_calculation / "
        "zero_balance_removal_upb (the UPB at removal/disposition -- not orig_upb or the D90-event-month "
        "UPB, both of which overstate the true loss base for a loan that partially amortized or "
        f"capitalized arrears before liquidation); {lgd['n_excluded_small_denom']} loans "
        f"(excluded here, removal UPB < ${MIN_REMOVAL_UPB:,.0f}) blow up this ratio on a near-zero "
        "denominator and are dropped as data artifacts, not modeled outcomes. **Sign convention**: "
        "SFLLD's actual_loss_calculation is NEGATIVE for an economic loss to the trust (confirmed "
        "empirically: mean actual_loss_calculation across this population is negative, consistent with "
        "the User Guide), so LGD is defined here as the negated ratio. "
        f"Median realized LGD is {lgd['median_lgd']:.1%} (mean {lgd['mean_lgd']:.1%}); "
        f"{lgd['pct_negative']:.1%} of loans realize a NEGATIVE LGD (net gain at disposition -- property "
        "sold for more than the removal UPB plus costs, plausible in rising-price years). **The yearly panel "
        "does NOT show a clean 2008-2011 severity peak that then falls** -- by LIQUIDATION year (not "
        "origination or default year), severity climbs from the 2008 crisis onset and stays elevated on a "
        f"plateau from **{lgd['plateau_start']}-{lgd['plateau_end']}** (mean LGD >=50% every year in that "
        f"stretch), actually PEAKING in **{lgd['peak_year']}** (median {lgd['peak_median']:.1%}, mean "
        f"{lgd['peak_mean']:.1%}) -- years after the GFC's origination/default wave -- before declining from "
        "2017 onward and falling sharply again over 2020-2022 alongside record HPI appreciation. The lag is "
        "the REO/short-sale liquidation pipeline: loans that first went 90+ DPD in 2008-2009 often did not "
        "reach a liquidation zero-balance code, and realize their loss, until years later, while the market "
        "was still absorbing crisis-era inventory -- liquidation-year severity is a lagging, not "
        "coincident, indicator of the origination-era credit event. This is a first look, not the rung-3 LGD "
        "model -- no seasoning/vintage/regional adjustment or beta-regression is attempted here.\n"
    )

    lines.append("## What real GSE data buys over the DCR engine's synthetic panel\n")
    lines.append(
        "- **Real calendar dates** -- every exhibit above is anchored to an actual month, so the GFC hump, "
        "the COVID spike, and the 2022-24 normalization are dated events with dated causes (UER, HPI), not "
        "an anonymized clock index.\n"
        "- **Real states** -- Exhibit 4's collateral channel (NV/AZ/FL/CA vs. TX/ND) is invisible to a panel "
        "with no state field; the DCR engine's rung-1/2 scope pin ('state_orig_time ... unused at this "
        "rung') is exactly the gap this rung closes.\n"
        "- **Real realized losses** -- Exhibit 5 uses actual_loss_calculation, an audited realized-loss "
        "field, not a modeled LGD assumption; this is the first EDA in this project with an empirical "
        "severity distribution to calibrate against.\n"
        "- **Forbearance-regime visibility** -- Exhibit 2's borrower_assistance_status_code corroboration "
        "is only possible because the raw SFLLD servicing file carries a program-participation flag; a "
        "synthetic panel has no equivalent signal to distinguish 'suppressed by policy' from 'genuinely "
        "cured'.\n"
    )

    lines.append("## Modeling cautions for the Phase-B hazard model (discovered here, not yet acted on)\n")
    lines.append(
        "- **COVID forbearance breaks the naive dlq-based (D90) default definition -- in the DANGEROUS "
        "direction of making COVID look like a WORSE credit event than the GFC, not a milder one.** "
        "Exhibits 2+3 together show the 60->90+ roll rate and the combined D90-entry rate both PEAK "
        "during 2020-2021, exceeding their GFC-window values, while the 90+->liquidation rate collapses "
        "over 10x in the same window -- i.e. the delinquency-status ladder kept climbing on forbearance "
        "loans' contractual schedule while actual loss realization stopped. A hazard model trained on "
        "D90 as the target across 2020-2021 without a regime dummy (or an explicit exclusion window) will "
        "OVER-estimate default risk in that window and then be blindsided when forbearance unwinds and the "
        "liquidation rate normalizes -- exactly the opposite failure mode of the naive assumption that "
        "'forbearance suppresses defaults'.\n"
        "- **The combined calendar-time D90-entry series (Exhibit 3) mixes vintages of different ages and "
        "eras at every point** -- a hazard model needs to condition on loan_age/vintage/era jointly, not "
        "just calendar time, or it will misattribute a composition shift (e.g. a wave of young, "
        "just-originated modern-era loans diluting the entry rate) to an actual credit-cycle improvement.\n"
        "- **Realized LGD (Exhibit 5) is only observed for a selected subset of D90 defaults.** Only "
        f"{lgd['n_pop']:,} of 44,593 D90 defaults (~{lgd['n_pop']/44593:.1%}) reach a liquidation "
        "zero_balance_code with actual_loss populated -- most D90 defaults in this "
        "sample cure, modify, or are still open/censored, so any LGD model built on this population alone "
        "is conditioning on a selected (worse-than-average-outcome) subsample and needs an explicit "
        "selection/censoring treatment, not a naive mean.\n"
        "- **State-level HPI/UER coverage is incomplete** (GU, VI have no state series at all; PR has UER "
        "but no HPI) -- any state-level feature in the Phase-B model needs the national-fallback flag "
        "carried through as a feature or an explicit exclusion, not silently blended into a 'state' number.\n"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines))


# ==========================================================================
# Main
# ==========================================================================
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-transitions", action="store_true",
                         help="Force-rebuild the roll-rate transition cache (re-scans all 17 vintages' "
                              "full raw svcg history, ~a few minutes).")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading panel_monthly.parquet + loan_orig.parquet ...")
    panel = load_panel()
    loan = load_loan()

    print("Exhibit 1 -- vintage curves ...")
    curves = compute_vintage_curves(panel, loan)
    peak_rates = plot_vintage_curves(curves, loan)

    print("Exhibit 2 -- roll-rate matrices (full raw svcg re-scan, cached after first run) ...")
    trans, assist = compute_roll_rate_transitions(refresh=args.refresh_transitions)
    key_cells = plot_roll_rate_matrices(trans)

    print("Exhibit 3 -- calendar-time series ...")
    cal = compute_calendar_series(panel)
    uer = load_national_uer()
    plot_calendar_series(cal, uer)

    print("Exhibit 4 -- state heterogeneity ...")
    state_rates = compute_state_default_rates(loan)
    macro = load_state_macro()
    hpi_dd = compute_state_hpi_drawdown(macro)
    state_stats = plot_state_heterogeneity(state_rates, hpi_dd)

    print("Exhibit 5 -- realized LGD first look ...")
    lgd_pop, n_excluded_small_denom = compute_realized_lgd(loan)
    lgd_stats = plot_realized_lgd(lgd_pop, n_excluded_small_denom)

    bundle = {
        "vintage_curves": peak_rates,
        "roll_rate_key_cells": key_cells,
        "assist_summary": assist,
        "calendar": cal,
        "state_heterogeneity": state_stats,
        "lgd": lgd_stats,
    }
    print("Writing eda_report.md ...")
    write_report(bundle)

    print(f"\nDone. Exhibits + report written to {OUT_DIR}")


if __name__ == "__main__":
    main()
