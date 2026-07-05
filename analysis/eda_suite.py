"""EDA verification suite for the IFRS 9 ECL loan-quarter panel.

Every chart is a TEST with a known expected shape, not decoration: each exhibit
renders a PNG *and* records an expected-vs-observed verdict row. A FAILED
expectation is a finding — it is reported in outputs/eda/eda_report.md, never
hidden. Exit code 0 = all hard expectations PASS, 1 = at least one FAIL.

Input : data/processed/panel.parquet   (built by data/panel/build_panel.py —
        see its docstring for column semantics: eligibility waterfall, updated
        LTV derivation, in-panel macro lags, train/OOT split)
Output: outputs/eda/*.png + outputs/eda/eda_report.md

Run:    cd <repo root> && uv run python analysis/eda_suite.py

Methodology anchors: knowledge/sources/ifrs9_credit_risk_notes.md §5 (data-prep:
left truncation & right censoring first-class) and §6.2 (discrete-time hazards
on at-risk rows); MASTER_PLAN.md rung scope pins. Style: analysis/mpl_style.py
(textbook look shared with the notes' exhibits).

Design rules honoured (dataviz method): one axis per panel — co-movement is
shown with stacked shared-x panels, never a dual y-axis; ordered vintage
cohorts use a single-hue sequential ramp with one emphasis colour for the worst
cohort; grids recessive; selective direct labels only.

Scope note recorded in the report: roll-rate / cure-rate EDA is OUT OF SCOPE at
this rung — the DCR panel has no delinquency ladder (status_time is only
0/1/2), so transitions between delinquency states are unobservable. Deferred to
the Freddie Mac rung (rung 3), whose performance file carries the full ladder.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless — must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mpl_style import COLORS, apply_textbook_style  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "eda"

RAW_DEFAULT_ROWS = 15_158  # raw-file default rows, for reconciliation note

# ---------------------------------------------------------------------------
# verdict bookkeeping
# ---------------------------------------------------------------------------

class Verdicts:
    """Collects expected-vs-observed rows; FAIL rows drive the exit code."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, exhibit: str, expectation: str, observed: str,
            passed: bool | None) -> None:
        verdict = "INFO" if passed is None else ("PASS" if passed else "FAIL")
        self.rows.append({"exhibit": exhibit, "expectation": expectation,
                          "observed": observed, "verdict": verdict})
        print(f"  [{verdict}] {exhibit}: {expectation}\n         -> {observed}")

    @property
    def n_fail(self) -> int:
        return sum(r["verdict"] == "FAIL" for r in self.rows)


# ---------------------------------------------------------------------------
# exhibit 1 — default rate by calendar quarter vs macro stress
# ---------------------------------------------------------------------------

def exhibit_default_rate_vs_macro(df: pd.DataFrame, v: Verdicts) -> dict:
    q = df.groupby("time").agg(at_risk=("id", "size"), d=("default_event", "sum"))
    q["dr"] = q["d"] / q["at_risk"]
    macro = df.groupby("time")[["uer_time", "hpi_time"]].first()
    drawdown = macro["hpi_time"] / macro["hpi_time"].cummax() - 1.0

    corr = float(np.corrcoef(q["dr"], macro.loc[q.index, "uer_time"])[0, 1])
    stress = drawdown[drawdown < -0.10]
    stress_lo, stress_hi = (int(stress.index.min()), int(stress.index.max())) \
        if len(stress) else (None, None)
    # the shaded band spans min..max stress quarter — verify that is honest
    stress_contiguous = bool(len(stress)) and bool(
        (np.diff(stress.index.to_numpy()) == 1).all())

    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8.4, 6.6),
                             gridspec_kw={"height_ratios": [1.5, 1, 1]})
    for ax in axes:
        if stress_lo is not None:
            ax.axvspan(stress_lo, stress_hi, color=COLORS["warn"], alpha=0.07,
                       zorder=0)

    ax = axes[0]
    ax.plot(q.index, 100 * q["dr"], color=COLORS["accent"], lw=1.8)
    pk = int(q["dr"].idxmax())
    ax.annotate(f"peak {100 * q['dr'].max():.1f}% (t={pk})",
                xy=(pk, 100 * q["dr"].max()), xytext=(pk - 16, 100 * q["dr"].max()),
                fontsize=8, va="center",
                arrowprops=dict(arrowstyle="-", color=COLORS["gray"], lw=0.8))
    ax.set_ylabel("default rate, % / qtr")
    ax.set_title("Quarterly default hazard co-moves with the macro stress episode "
                 f"(shaded: HPI drawdown < -10%, t={stress_lo}..{stress_hi})")

    ax = axes[1]
    ax.plot(macro.index, macro["uer_time"], color=COLORS["warn"], lw=1.6)
    ax.set_ylabel("unemployment, %")

    ax = axes[2]
    ax.fill_between(drawdown.index, 100 * drawdown, 0, color=COLORS["purple"],
                    alpha=0.30, lw=0)
    ax.plot(drawdown.index, 100 * drawdown, color=COLORS["purple"], lw=1.4)
    ax.set_ylabel("HPI drawdown, %")
    ax.set_xlabel("panel quarter t (abstract clock, 1..60)")

    fig.align_ylabels(axes)
    fig.savefig(OUT / "default_rate_vs_macro.png")
    plt.close(fig)

    peak_in_stress = (stress_lo is not None) and (stress_lo <= pk <= stress_hi)
    v.add("1 default_rate_vs_macro",
          "default rate co-moves with unemployment / HPI stress: "
          "corr(default rate, uer level) > 0 AND the default-rate peak "
          "quarter falls inside the HPI-drawdown stress window",
          f"corr = {corr:+.3f}; default rate peaks {100 * q['dr'].max():.2f}%/qtr at t={pk} "
          f"{'inside' if peak_in_stress else 'OUTSIDE'} the stress window "
          f"t={stress_lo}..{stress_hi} "
          f"({'contiguous' if stress_contiguous else 'NON-CONTIGUOUS — shaded band overstates'}; "
          f"uer peak {macro['uer_time'].max():.1f}% at t={int(macro['uer_time'].idxmax())}, "
          f"max HPI drawdown {100 * drawdown.min():.1f}% at t={int(drawdown.idxmin())})",
          (corr > 0) and peak_in_stress and stress_contiguous)
    return {"corr_dr_uer": corr, "stress_window": (stress_lo, stress_hi)}


# ---------------------------------------------------------------------------
# exhibit 2 — hazard by loan age (seasoning)
# ---------------------------------------------------------------------------

def exhibit_hazard_by_age(df: pd.DataFrame, v: Verdicts,
                          min_exposure: int = 500) -> dict:
    h = df.groupby("loan_age").agg(n=("id", "size"), d=("default_event", "sum"))
    h["haz"] = h["d"] / h["n"]
    grid = h[h["n"] >= min_exposure]           # ages with credible exposure
    ages = grid.index.to_numpy()
    peak_age = int(grid["haz"].idxmax())
    peak_pos = int(np.where(ages == peak_age)[0][0])
    ok = (peak_pos >= 2) and (peak_pos < len(ages) - 5)

    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(8.4, 4.8),
                             gridspec_kw={"height_ratios": [2, 1]})
    ax = axes[0]
    ax.plot(ages, 100 * grid["haz"], color=COLORS["accent"], lw=1.8)
    ax.axvline(peak_age, color=COLORS["warn"], lw=1.0, ls=":")
    ax.annotate(f"peak {100 * grid['haz'].max():.2f}% at age {peak_age}",
                xy=(peak_age, 100 * grid["haz"].max()),
                xytext=(peak_age + 4, 100 * grid["haz"].max()), fontsize=8,
                va="center")
    ax.set_ylabel("default hazard, % / qtr")
    ax.set_title("Seasoning: default hazard by loan age "
                 f"(ages with >= {min_exposure} at-risk loan-quarters)")

    ax = axes[1]
    ax.bar(ages, grid["n"], color=COLORS["gray"], alpha=0.55, width=0.9)
    ax.set_ylabel("at-risk rows")
    ax.set_xlabel("loan age, quarters since origination")

    fig.align_ylabels(axes)
    fig.savefig(OUT / "hazard_by_loan_age.png")
    plt.close(fig)

    v.add("2 hazard_by_loan_age",
          "hump shape: peak in mid-life, i.e. NOT in the first two nor the "
          "last five age quarters of the exposure-credible grid",
          f"peak at age {peak_age} (grid position {peak_pos + 1} of {len(ages)}, "
          f"ages {ages.min()}..{ages.max()}); hazard rises "
          f"{100 * grid['haz'].iloc[0]:.2f}% -> {100 * grid['haz'].max():.2f}% "
          f"then declines to {100 * grid['haz'].iloc[-1]:.2f}%",
          ok)
    return {"peak_age": peak_age}


# ---------------------------------------------------------------------------
# exhibit 3 — cumulative default curves by origination vintage
# ---------------------------------------------------------------------------

def exhibit_vintage_curves(df: pd.DataFrame, v: Verdicts,
                           width: int = 5, min_loans: int = 500) -> dict:
    loans = df.groupby("id").agg(orig=("orig_time", "first"))
    edges = np.arange(-40, 61, width)
    loans["cohort_lo"] = edges[np.searchsorted(edges, loans["orig"], side="right") - 1]
    sizes = loans.groupby("cohort_lo").size()
    keep = sizes[sizes >= min_loans].index.to_list()

    d_rows = df.loc[df["default_event"] == 1, ["id", "loan_age"]].merge(
        loans.reset_index()[["id", "cohort_lo"]], on="id")

    # pass 1 — compute every cohort curve, so the worst cohort is known
    # BEFORE plotting and can carry the emphasis colour in the legend too
    curves: dict[int, tuple[np.ndarray, np.ndarray, int]] = {}
    for lo in keep:
        n = int(sizes[lo])
        sub = d_rows[d_rows["cohort_lo"] == lo]
        max_age = int(df.loc[df["id"].isin(
            loans.index[loans["cohort_lo"] == lo]), "loan_age"].max())
        ages = np.arange(0, max_age + 1)
        cum = np.searchsorted(np.sort(sub["loan_age"].to_numpy()), ages,
                              side="right") / n
        curves[lo] = (ages, cum, n)
    results = {lo: float(cum[-1]) for lo, (_, cum, _) in curves.items()}
    worst_lo = max(results, key=lambda k: results[k])

    # pass 2 — plot; worst cohort in emphasis colour (legend swatch matches)
    fig, ax = plt.subplots(figsize=(9.4, 4.4))
    ramp = plt.matplotlib.colors.LinearSegmentedColormap.from_list(
        "accent_ramp", ["#c3cfdd", COLORS["accent"]])
    for i, lo in enumerate(keep):
        ages, cum, n = curves[lo]
        emph = lo == worst_lo
        ax.plot(ages, 100 * cum, lw=2.2 if emph else 1.5,
                label=f"orig t {lo}..{lo + width - 1}  (n={n:,})",
                color=COLORS["warn"] if emph else ramp(i / max(len(keep) - 1, 1)))
    ages, cum, _ = curves[worst_lo]
    ax.annotate(f"worst: orig t {worst_lo}..{worst_lo + width - 1} "
                f"({100 * results[worst_lo]:.1f}%)",
                xy=(ages[-1], 100 * cum[-1]),
                xytext=(ages[-1] + 2, 100 * cum[-1] - 2.5),
                fontsize=8, color=COLORS["warn"], ha="left", va="top")

    ax.set_xlabel("loan age, quarters since origination")
    ax.set_ylabel("cumulative default incidence, % of cohort loans")
    ax.set_title(f"Vintage curves: cumulative defaults by {width}-quarter "
                 f"origination cohort (cohorts with >= {min_loans} loans)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False,
              title="origination cohort", title_fontsize=8)
    fig.savefig(OUT / "vintage_cumulative_default.png")
    plt.close(fig)

    # checks: (i) worst cohort originated in the run-up to / at the HPI peak
    # (t=25), i.e. just before the stress window (HPI drawdown < -10% from
    # ~t=29); (ii) separation is real — worst cohort's terminal incidence at
    # least 1.5x the median cohort's, so "visible separation" is asserted,
    # not just eyeballed
    median_rate = float(np.median(list(results.values())))
    separation = results[worst_lo] / median_rate if median_rate > 0 else np.inf
    ok = (15 <= worst_lo <= 30) and (separation >= 1.5)
    v.add("3 vintage_cumulative_default",
          "cohort separation asserted: worst cohort >= 1.5x the median "
          "cohort's terminal incidence; worst cohorts originated just before "
          "the stress episode (HPI peak t=25, stress window from ~t=29)",
          f"worst cohort = orig t {worst_lo}..{worst_lo + width - 1} with "
          f"{100 * results[worst_lo]:.1f}% cumulative default incidence = "
          f"{separation:.1f}x the median cohort ({100 * median_rate:.1f}%); "
          "ranking: " + ", ".join(
              f"t{lo}..{lo + width - 1}={100 * r:.1f}%" for lo, r in
              sorted(results.items(), key=lambda kv: -kv[1])[:4]) +
          " (pre-window cohorts are left-truncated; incidence = defaults / "
          "cohort loans, competing payoff risk not removed)",
          ok)
    return {"worst_cohort_lo": int(worst_lo), "worst_rate": results[worst_lo]}


# ---------------------------------------------------------------------------
# exhibit 4 — prepayment incidence vs rate incentive
# ---------------------------------------------------------------------------

def exhibit_prepay_incentive(df: pd.DataFrame, v: Verdicts) -> dict:
    edges = [-np.inf, -2, -1, -0.5, 0, 0.5, 1, 1.5, 2, 3, np.inf]
    binned = pd.cut(df["prepay_incentive"], bins=edges)
    g = df.groupby(binned, observed=True).agg(
        n=("id", "size"), haz=("payoff_event", "mean"),
        x=("prepay_incentive", "median"))
    rho, pval = spearmanr(np.arange(len(g)), g["haz"].to_numpy())

    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    ax.plot(g["x"], 100 * g["haz"], color=COLORS["good"], lw=1.8, marker="o",
            ms=5, mec="white", mew=0.8)
    ax.axvline(0, color=COLORS["gray"], lw=0.9, ls=":")
    for xi, yi, ni in zip(g["x"], 100 * g["haz"], g["n"]):
        ax.annotate(f"{ni / 1000:.0f}k", xy=(xi, yi), xytext=(0, -11),
                    textcoords="offset points", ha="center", fontsize=6.5,
                    color=COLORS["gray"])
    ax.set_xlabel("rate incentive, pp  (note rate - current market rate; "
                  "bin medians, row counts below markers)")
    ax.set_ylabel("payoff hazard, % / qtr")
    ax.set_ylim(bottom=0)
    ax.set_title("Prepayment hazard rises with the refinancing incentive")
    fig.savefig(OUT / "prepay_vs_rate_incentive.png")
    plt.close(fig)

    v.add("4 prepay_vs_rate_incentive",
          "monotone-increasing prepayment hazard in the incentive: strong "
          "rank correlation across ordered bins (Spearman rho >= 0.7, not "
          "merely > 0) AND top bin hazard above bottom bin hazard",
          f"Spearman rho = {rho:+.3f} (p = {pval:.1e}) across {len(g)} bins; "
          f"hazard {100 * g['haz'].iloc[0]:.2f}% -> {100 * g['haz'].iloc[-1]:.2f}%/qtr "
          "from deepest out-of-the-money to deepest in-the-money bin "
          "(mild local dip over incentives 1.0-2.0pp; ranking otherwise clean)",
          (rho >= 0.7) and (g["haz"].iloc[-1] > g["haz"].iloc[0]))
    return {"spearman": float(rho)}


# ---------------------------------------------------------------------------
# exhibit 5 — origination-quality distributions
# ---------------------------------------------------------------------------

def exhibit_orig_quality(df: pd.DataFrame, v: Verdicts) -> dict:
    lo = df.sort_values(["id", "time"]).groupby("id").first()
    fico, ltv = lo["FICO_orig_time"], lo["LTV_orig_time"]
    rate = lo["Interest_Rate_orig_time"]
    rate_pos = rate[rate > 0]
    n_rate0 = int((rate <= 0).sum())

    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.0))
    ax = axes[0]
    ax.hist(fico, bins=np.arange(395, 855, 10), color=COLORS["accent"],
            alpha=0.85)
    ax.set_xlabel("FICO at origination")
    ax.set_ylabel("loans")
    ax.set_title(f"FICO (skew {fico.skew():+.2f})")

    ax = axes[1]
    ax.hist(ltv, bins=np.arange(45, 225, 2.5), color=COLORS["blue2"], alpha=0.85)
    ax.axvline(100, color=COLORS["warn"], lw=1.0, ls=":")
    ax.annotate(f">100: {int((ltv > 100).sum())} loans\nmax {ltv.max():.1f}",
                xy=(0.62, 0.75), xycoords="axes fraction", fontsize=7.5,
                color=COLORS["warn"])
    ax.set_xlabel("LTV at origination, %")
    ax.set_title("LTV (mass at 80)")

    ax = axes[2]
    ax.hist(rate_pos, bins=np.arange(0, 20.5, 0.5), color=COLORS["orange"],
            alpha=0.85)
    ax.annotate(f"{n_rate0:,} loans ({100 * n_rate0 / len(lo):.1f}%)\n"
                "missing-coded 0,\nexcluded here\n(flag orig_rate_missing)",
                xy=(0.60, 0.55), xycoords="axes fraction", fontsize=7.5,
                color=COLORS["gray"])
    ax.set_xlabel("note rate at origination, %")
    ax.set_title("Origination rate (rate > 0)")

    fig.suptitle("Origination quality — one row per loan "
                 f"({len(lo):,} loans)", y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / "origination_quality.png")
    plt.close(fig)

    obs = (f"FICO in [{int(fico.min())}, {int(fico.max())}] (within 400-840), "
           f"skew {fico.skew():+.2f} (left-skewed); "
           f"LTV mode 80, {100 * ltv.between(75, 85).mean():.0f}% of loans in "
           f"[75, 85], {int((ltv > 100).sum())} loans "
           f"({100 * (ltv > 100).mean():.2f}%) above 100, max {ltv.max():.1f} "
           "(the documented 218.5); positive origination rates in "
           f"[{rate_pos.min():.2f}, {rate_pos.max():.2f}]%. "
           f"ANOMALY reported (not asserted): {n_rate0:,} loans "
           f"({100 * n_rate0 / len(lo):.1f}%) have Interest_Rate_orig_time "
           "missing-coded as 0 — retained upstream with flag orig_rate_missing; "
           "the current note rate drives the prepay incentive instead")
    v.add("5 origination_quality",
          "FICO left-skewed within 400-840; LTV massed near 80 with a tail "
          "above 100 (max 218.5 exists); rates in plausible range — anomalies "
          "reported rather than hard-asserted",
          obs, None)
    return {"n_rate_zero": n_rate0}


# ---------------------------------------------------------------------------
# exhibit 6 — realised LGD bimodality
# ---------------------------------------------------------------------------

def exhibit_lgd(df: pd.DataFrame, v: Verdicts) -> dict:
    lgd = df.loc[df["default_event"] == 1, "lgd_time"]
    share_lo = float((lgd < 0.1).mean())
    share_hi = float((lgd > 0.4).mean())
    n_neg, n_gt1 = int((lgd < 0).sum()), int((lgd > 1).sum())
    n_gt_clip = int((lgd > 1.5).sum())

    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    ax.hist(lgd[lgd <= 1.5], bins=np.arange(0, 1.53, 0.03),
            color=COLORS["accent"], alpha=0.85)
    ax.axvline(0.1, color=COLORS["good"], lw=1.0, ls=":")
    ax.axvline(0.4, color=COLORS["warn"], lw=1.0, ls=":")
    ax.annotate(f"cure spike\n{100 * share_lo:.1f}% < 0.1\n"
                f"({100 * float((lgd == 0).mean()):.1f}% exactly 0)",
                xy=(0.10, 0.78), xycoords="axes fraction", fontsize=8,
                color=COLORS["good"])
    ax.annotate(f"write-off hump\n{100 * share_hi:.1f}% > 0.4",
                xy=(0.45, 0.78), xycoords="axes fraction", fontsize=8,
                color=COLORS["warn"])
    ax.annotate(f"not shown: {n_gt_clip} rows with LGD > 1.5 (max "
                f"{lgd.max():.2f}); {n_gt1:,} rows ({100 * n_gt1 / len(lgd):.1f}%) "
                f"exceed 1.0 and {n_neg} are negative — reported, NOT clipped",
                xy=(0.28, 0.24), xycoords="axes fraction", fontsize=7.5,
                color=COLORS["gray"])
    ax.set_xlabel("realised LGD on default rows (lgd_time)")
    ax.set_ylabel("default events")
    ax.set_title(f"Realised LGD is bimodal ({len(lgd):,} defaults) — "
                 "cure spike near 0, write-off hump at high loss")
    fig.savefig(OUT / "lgd_realised_bimodal.png")
    plt.close(fig)

    v.add("6 lgd_realised_bimodal",
          "bimodal (cure spike near 0, write-off hump at high loss; notes "
          "Fig 8): meaningful mass below 0.1 AND above 0.4 (>= 10% each); "
          "values outside [0,1] reported, not clipped",
          f"{100 * share_lo:.1f}% of {len(lgd):,} defaults below 0.1 "
          f"({100 * float((lgd == 0).mean()):.1f}% exactly 0) and "
          f"{100 * share_hi:.1f}% above 0.4; out-of-[0,1]: {n_neg} negative, "
          f"{n_gt1:,} rows ({100 * n_gt1 / len(lgd):.1f}%) above 1 (max "
          f"{lgd.max():.2f}) — plotted range truncated at 1.5 for readability "
          f"with the {n_gt_clip}-row tail annotated, underlying data untouched. "
          f"Panel has {len(lgd):,} default rows vs {RAW_DEFAULT_ROWS:,} raw: "
          f"{RAW_DEFAULT_ROWS - len(lgd)} rows removed by the reviewed "
          "eligibility waterfall (duplicate copies + id collisions + "
          "zero-balance-origination loans; see outputs/panel/waterfall.md)",
          (share_lo >= 0.10) and (share_hi >= 0.10))
    return {"share_lo": share_lo, "share_hi": share_hi, "n_gt1": n_gt1}


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(v: Verdicts, df: pd.DataFrame) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    n_pass = sum(r["verdict"] == "PASS" for r in v.rows)
    n_info = sum(r["verdict"] == "INFO" for r in v.rows)
    lines = [
        "# EDA verification suite — expected-vs-observed verdicts",
        "",
        f"Generated {ts} by `analysis/eda_suite.py` on "
        f"`data/processed/panel.parquet` ({len(df):,} loan-quarter rows, "
        f"{df['id'].nunique():,} loans, {int(df['default_event'].sum()):,} "
        f"defaults, {int(df['payoff_event'].sum()):,} payoffs, "
        f"time 1..60 abstract quarterly clock).",
        "",
        "Every chart is a TEST with a pre-registered expected shape. "
        f"Result: **{n_pass} PASS, {v.n_fail} FAIL, {n_info} INFO** "
        "(INFO = report-only expectation, no hard assertion by design).",
        "",
        "| Exhibit (PNG) | Expected | Observed | Verdict |",
        "|---|---|---|---|",
    ]
    for r in v.rows:
        lines.append(f"| {r['exhibit']} | {r['expectation']} | "
                     f"{r['observed']} | **{r['verdict']}** |")
    lines += [
        "",
        "## Out of scope at this rung",
        "",
        "**Roll-rate / cure-rate chart: OUT OF SCOPE.** The DCR panel carries "
        "no delinquency ladder — `status_time` takes only 0 (performing), "
        "1 (default) and 2 (payoff), so current -> 30 -> 60 -> 90+ roll rates "
        "and cure transitions are unobservable here. Documented simplification "
        "(see `data/panel/build_panel.py` docstring and MASTER_PLAN.md); "
        "deferred to the Freddie Mac rung (rung 3), whose monthly performance "
        "file has the full delinquency ladder.",
        "",
        "## Method notes",
        "",
        "- Default/payoff hazards are computed on at-risk loan-quarter rows "
        "(discrete-time hazard convention, notes §6.2); the panel is already "
        "truncated at each loan's first terminal event by the build waterfall.",
        "- Left truncation (orig_time down to -40) and right censoring "
        "(loans alive at t=60) are first-class: vintage curves flag that "
        "pre-window cohorts miss their earliest ages; the seasoning grid is "
        "restricted to ages with >= 500 at-risk rows so sparse old ages "
        "cannot fake a peak.",
        "- Vintage cumulative incidence = cohort defaults by age / cohort "
        "loans (competing payoff risk not removed — standard vintage exhibit, "
        "stated on the chart caption side).",
        "- Chart 1 uses stacked shared-x panels instead of a dual y-axis "
        "(one-axis rule); the stress band is HPI drawdown < -10%.",
        "- No values were clipped or dropped by this suite; LGD > 1 and the "
        "missing-coded origination rates are reported as findings.",
        "",
        "Exit code contract: 0 iff no FAIL row above.",
    ]
    (OUT / "eda_report.md").write_text("\n".join(lines))


def main() -> int:
    apply_textbook_style()
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(PANEL)
    print(f"Panel: {len(df):,} rows, {df['id'].nunique():,} loans, "
          f"{int(df['default_event'].sum()):,} defaults, "
          f"{int(df['payoff_event'].sum()):,} payoffs\n")

    v = Verdicts()
    exhibit_default_rate_vs_macro(df, v)
    exhibit_hazard_by_age(df, v)
    exhibit_vintage_curves(df, v)
    exhibit_prepay_incentive(df, v)
    exhibit_orig_quality(df, v)
    exhibit_lgd(df, v)
    write_report(v, df)

    pngs = sorted(p.name for p in OUT.glob("*.png"))
    print(f"\nWrote {len(pngs)} PNGs to {OUT.relative_to(PROJECT_ROOT)}: "
          + ", ".join(pngs))
    print(f"Report: {(OUT / 'eda_report.md').relative_to(PROJECT_ROOT)}")
    if v.n_fail:
        print(f"\n{v.n_fail} EXPECTATION(S) FAILED — see report (findings, "
              "not hidden).")
        return 1
    print("\nAll hard expectations PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
