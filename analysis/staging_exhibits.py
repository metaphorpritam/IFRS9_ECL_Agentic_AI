"""SICR staging exhibits: stage distributions, threshold sensitivity, report.

Run:  cd <repo root> && uv run python analysis/staging_exhibits.py

Fits the rung-1 cause-specific hazards on the TRAINING split (identical call
to analysis/fit_hazard.py), then stages the live book with engine/staging.py
at two snapshots:

    t = 20   calm quarter (pre-stress: unemployment ~5, HPI rising)
    t = 40   last training quarter, inside the stress episode

and writes to outputs/staging/:

  stage_distribution.png   stage shares of the staged book at both snapshots
                           (payoff-quarter rows excluded -- derecognitions)
  stage2_sensitivity.png   Stage-2 share vs the SICR ratio threshold
                           (1.5x / 2x / 3x / 4x) at both snapshots -- the
                           plan's headline governance exhibit: how hard the
                           doubling convention works in calm vs stress
  staging_report.md        config, stage tables, trigger mix, sensitivity
                           table, approximation-flag shares, the 49k-loan
                           scale benchmark, and the sanity-gate results

Design choices (stated, not silent):
* Snapshot population = all panel rows at time t EXCEPT payoff_event == 1
  rows: a payoff quarter is a derecognition, not a stageable exposure.
  Default rows stay in the book (Stage 3 -- that IS the quarter's default
  incidence).
* Models are fitted once on the full training window (t <= 40). Staging the
  t = 20 book with them is therefore an in-sample illustration of a calm
  quarter, not a walk-forward simulation -- fine for a staging exhibit, said
  out loud here.
* The sensitivity sweep varies ONLY ratio_threshold, holding the 0.5pp
  annualised add-on fixed, and applies the pure quantitative trigger (no
  probation lookback) to isolate the governance dial; probation adds a
  handful of held-over rows at the default config (reported).

Sanity gates (FAIL LOUDLY -- SystemExit -- if violated):
  1. exactness: fast-path lifetime PDs match pd_term_structure to < 1e-10
     on a fixed-seed loan sample (both legs);
  2. Stage-3 share == default incidence at each snapshot (count-exact);
  3. Stage-2 share rises sharply into the stress: t=40 share >= t=20 + 20pp;
  4. no Stage-1 loan carries lifetime_pd_now / lifetime_pd_orig > 10;
  5. Stage-2 share is monotone non-increasing in the ratio threshold.
"""

from __future__ import annotations

import sys
import time as _time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from mpl_style import COLORS, apply_textbook_style, figsize_for  # noqa: E402
from engine.hazard import fit_default_hazard, fit_prepay_hazard  # noqa: E402
from engine.staging import (  # noqa: E402
    StagingConfig,
    _cum_default_pd,
    assign_stages,
    build_macro_map,
    crosscheck_term_structure,
    lifetime_pd_table,
    origination_covariates,
    quantitative_sicr,
)

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "staging"
SNAPSHOTS = (20, 40)                 # calm vs stress reporting quarters
RATIOS = (1.5, 2.0, 3.0, 4.0)        # governance sweep of the ratio trigger
CROSSCHECK_TOL = 1e-10

#: fixed entity colours across BOTH exhibits (calm = navy, stress = red)
SNAP_COLOR = {20: COLORS["accent"], 40: COLORS["warn"]}
SNAP_LABEL = {20: "t = 20 (calm)", 40: "t = 40 (stress)"}


# ---------------------------------------------------------------------------
# staging runs
# ---------------------------------------------------------------------------

def stage_book(panel: pd.DataFrame, models: dict, cfg: StagingConfig,
               t: int) -> pd.DataFrame:
    """assign_stages at t (history rows only), payoff derecognitions dropped."""
    hist = panel[panel["time"] <= t]
    res = assign_stages(hist, models, cfg, snapshot_time=t)
    return res[res["payoff_event"] == 0].reset_index(drop=True)


def stage_shares(book: pd.DataFrame) -> dict[int, float]:
    n = len(book)
    return {s: float((book["stage"] == s).sum()) / n for s in (1, 2, 3)}


def sensitivity_table(panel: pd.DataFrame, models: dict,
                      macro_map: pd.DataFrame,
                      cfg: StagingConfig) -> pd.DataFrame:
    """Stage-2 share of the staged book vs ratio threshold, both snapshots.

    Reuses ONE lifetime-PD table per snapshot (the engine separates PD
    computation from the trigger, so a threshold sweep is arithmetic)."""
    rows = []
    for t in SNAPSHOTS:
        tbl = lifetime_pd_table(panel[panel["time"] <= t], models, t,
                                macro_map, cfg)
        book = tbl[tbl["payoff_event"] == 0]
        live = book[book["default_event"] == 0]
        for r in RATIOS:
            trig = quantitative_sicr(
                live, StagingConfig(ratio_threshold=r,
                                    abs_addon=cfg.abs_addon))
            rows.append({"time": t, "ratio_threshold": r,
                         "stage2_share": float(trig.sum()) / len(book)})
    return pd.DataFrame(rows)


def scale_benchmark(panel: pd.DataFrame, models: dict,
                    macro_map: pd.DataFrame) -> dict:
    """Both lifetime-PD legs for ~49k loans (each loan's last clean row)."""
    lag_cols = ["uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1", "gdp_lag1"]
    bench = (panel[panel["lag_warmup"] == 0].dropna(subset=lag_cols)
             .sort_values(["id", "time"]).groupby("id").tail(1))
    R = np.maximum((bench["mat_time"] - bench["time"]).to_numpy(), 1)
    orig = origination_covariates(bench, macro_map)
    t0 = _time.perf_counter()
    _cum_default_pd(models, bench, R)
    _cum_default_pd(models, orig, R)
    dt = _time.perf_counter() - t0
    return {"n_loans": int(len(bench)), "seconds": dt,
            "loans_per_s": len(bench) / dt, "max_R": int(R.max())}


# ---------------------------------------------------------------------------
# sanity gates
# ---------------------------------------------------------------------------

def sanity_checks(books: dict[int, pd.DataFrame], sens: pd.DataFrame,
                  xcheck_err: float) -> list[dict]:
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("fast path exact vs pd_term_structure",
        xcheck_err < CROSSCHECK_TOL,
        f"max abs(fast - reference) = {xcheck_err:.2e} "
        f"(tol {CROSSCHECK_TOL:g})")

    for t, book in books.items():
        n3 = int((book["stage"] == 3).sum())
        nd = int((book["default_event"] == 1).sum())
        add(f"Stage-3 == default incidence at t={t}", n3 == nd,
            f"stage-3 rows {n3}, default rows {nd}")

    s2 = {t: stage_shares(b)[2] for t, b in books.items()}
    add("Stage-2 share rises sharply into stress",
        s2[40] >= s2[20] + 0.20,
        f"t=20 share {s2[20]:.2%} -> t=40 share {s2[40]:.2%}")

    worst = 0.0
    ok10 = True
    for book in books.values():
        s1 = book[book["stage"] == 1]
        worst = max(worst, float(s1["pd_ratio"].max()))
        ok10 &= bool((s1["pd_ratio"] <= 10.0).all())
    add("no Stage-1 loan with pd_now/pd_orig > 10", ok10,
        f"max Stage-1 ratio across snapshots = {worst:.2f}")

    mono = True
    for t in SNAPSHOTS:
        v = sens.loc[sens["time"] == t, "stage2_share"].to_numpy()
        mono &= bool(np.all(np.diff(v) <= 1e-12))
    add("Stage-2 share monotone non-increasing in threshold", mono,
        "sweep " + " / ".join(f"{r}x" for r in RATIOS))
    return checks


# ---------------------------------------------------------------------------
# exhibits
# ---------------------------------------------------------------------------

def plot_stage_distribution(books: dict[int, pd.DataFrame],
                            path: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    stages = [1, 2, 3]
    x = np.arange(len(stages), dtype=float)
    width = 0.36
    for j, t in enumerate(SNAPSHOTS):
        sh = stage_shares(books[t])
        vals = [100.0 * sh[s] for s in stages]
        bars = ax.bar(x + (j - 0.5) * (width + 0.04), vals, width,
                      color=SNAP_COLOR[t], label=SNAP_LABEL[t], zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:.1f}%", (b.get_x() + b.get_width() / 2, v),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=8, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(["Stage 1\n(12-month ECL)",
                        "Stage 2\n(SICR, lifetime ECL)",
                        "Stage 3\n(default)"])
    ax.set_ylabel("share of staged book (%)")
    ax.set_ylim(0, 108)
    ax.set_title("IFRS 9 stage distribution: calm vs stress snapshot "
                 "(relative SICR test, 2x + 0.5pp p.a. add-on)")
    ax.legend(frameon=False)
    fig.savefig(path)
    plt.close(fig)


def plot_sensitivity(sens: pd.DataFrame, books: dict[int, pd.DataFrame],
                     cfg: StagingConfig, path: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    for t in SNAPSHOTS:
        d = sens[sens["time"] == t].sort_values("ratio_threshold")
        y = 100.0 * d["stage2_share"].to_numpy()
        xs = d["ratio_threshold"].to_numpy()
        label = SNAP_LABEL[t]
        if np.allclose(y, 0.0):      # flat-zero line: say it once, in the
            label += " -- 0.0% at every threshold"   # legend, not per point
        ax.plot(xs, y, marker="o", ms=5, color=SNAP_COLOR[t], label=label,
                zorder=3)
        if not np.allclose(y, 0.0):  # selective direct labels (stress line)
            for i, (xr, yv) in enumerate(zip(xs, y)):
                last = i == len(xs) - 1
                ax.annotate(f"{yv:.1f}%", (xr, yv),
                            textcoords="offset points",
                            xytext=(-8, 6) if last else (7, 6),
                            ha="right" if last else "left",
                            fontsize=8, color="#333333")
    ax.set_ylim(-4, 95)
    ax.axvline(cfg.ratio_threshold, color=COLORS["gray"], ls="--", lw=1,
               zorder=2)
    ax.annotate("adopted threshold: 2x\n(doubling convention)",
                (cfg.ratio_threshold, 14), textcoords="offset points",
                xytext=(8, 0), fontsize=8, color=COLORS["gray"])
    ax.set_xticks(list(RATIOS))
    ax.set_xlabel("SICR ratio threshold (lifetime PD now vs at origination)")
    ax.set_ylabel("Stage-2 share of staged book (%)")
    ax.set_title("Stage-2 population vs SICR threshold -- the governance "
                 "dial (add-on fixed at 0.5pp p.a.)")
    ax.legend(frameon=False, loc="center right")
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(books: dict[int, pd.DataFrame], sens: pd.DataFrame,
                 cfg: StagingConfig, bench: dict, xcheck_err: float,
                 fit_seconds: float, stage_seconds: dict[int, float],
                 checks: list[dict], path: Path) -> None:
    L: list[str] = []
    L.append("# SICR staging report -- relative lifetime-PD test\n")
    L.append("Generated by `analysis/staging_exhibits.py` "
             "(engine/staging.py; notes section 2.2).\n")

    L.append("## Rule under test\n")
    L.append(f"* Stage 2 iff lifetime_pd_now > {cfg.ratio_threshold}x "
             "lifetime_pd_orig (relative, same remaining-life window) AND "
             f"annualised add-on > {100*cfg.abs_addon:.1f}pp p.a. "
             "(ann = 1 - (1 - PD_life)^(4/R)).")
    L.append(f"* Probation: {cfg.cure_quarters} consecutive trigger-free "
             "quarters before Stage 2 -> 1 (window-equivalent form).")
    L.append("* **30-DPD backstop: STRUCTURALLY INERT on this dataset.** "
             "The DCR panel has no delinquency ladder (status is only "
             "performing / default / payoff), so the implemented hook "
             f"(`dpd_col='{cfg.dpd_col}'`) can never fire; Stage-2 below is "
             "quantitative-trigger-only and would be strictly larger with a "
             "live 30-DPD backstop.\n")

    L.append("## Stage distribution (payoff derecognitions excluded)\n")
    L.append("| snapshot | staged rows | Stage 1 | Stage 2 | Stage 3 | "
             "default incidence | staging runtime |")
    L.append("|---|---|---|---|---|---|---|")
    for t, book in books.items():
        sh = stage_shares(book)
        inc = float((book["default_event"] == 1).mean())
        L.append(f"| t={t} | {len(book):,} | {sh[1]:.2%} | {sh[2]:.2%} | "
                 f"{sh[3]:.2%} | {inc:.2%} | {stage_seconds[t]:.2f}s |")
    L.append("")

    L.append("### Trigger mix\n")
    L.append("| snapshot | " + " | ".join(
        ["default", "sicr_quantitative", "sicr_probation", "backstop_30dpd",
         "none"]) + " |")
    L.append("|---|---|---|---|---|---|")
    for t, book in books.items():
        vc = book["trigger_reason"].value_counts()
        L.append(f"| t={t} | " + " | ".join(
            str(int(vc.get(k, 0))) for k in
            ["default", "sicr_quantitative", "sicr_probation",
             "backstop_30dpd", "none"]) + " |")
    L.append("")

    L.append("## Governance sensitivity: Stage-2 share vs ratio threshold\n")
    L.append("Add-on held at "
             f"{100*cfg.abs_addon:.1f}pp p.a.; pure quantitative trigger "
             "(no probation lookback) on the non-default staged book.\n")
    hdr = "| snapshot | " + " | ".join(f"{r}x" for r in RATIOS) + " |"
    L.append(hdr)
    L.append("|---" * (len(RATIOS) + 1) + "|")
    for t in SNAPSHOTS:
        d = sens[sens["time"] == t].sort_values("ratio_threshold")
        L.append(f"| t={t} | " + " | ".join(
            f"{v:.2%}" for v in d["stage2_share"]) + " |")
    L.append("")
    L.append("Reading: in the calm quarter the relative test stages "
             "(almost) nobody at any threshold -- deterioration since "
             "origination simply has not happened -- while in the stress "
             "quarter the doubling convention (2x) moves roughly three "
             "quarters of the live book to lifetime ECL, and the choice "
             "between 2x and 4x swings the Stage-2 population by tens of "
             "percentage points of the book. The threshold is the single "
             "loudest governance dial in the impairment estimate (notes "
             "section 2.2 pitfall).\n")

    L.append("## Origination-benchmark quality flags\n")
    L.append("| snapshot | orig_macro_approx (pre-window clamp) | "
             "orig_rate_proxy (missing orig rate) |")
    L.append("|---|---|---|")
    for t, book in books.items():
        L.append(f"| t={t} | {float(book['orig_macro_approx'].mean()):.2%} | "
                 f"{float(book['orig_rate_proxy'].mean()):.2%} |")
    L.append("")

    L.append("## Performance\n")
    L.append(f"* hazard fits (both causes, training split): "
             f"{fit_seconds:.1f}s")
    L.append("* staging runtimes above include the t-1 lifetime-PD table "
             "for the probation lookback.")
    L.append(f"* scale benchmark: BOTH lifetime-PD legs for "
             f"{bench['n_loans']:,} loans (each loan's last clean row, "
             f"remaining life up to {bench['max_R']} quarters) in "
             f"{bench['seconds']:.2f}s ({bench['loans_per_s']:,.0f} "
             "loans/s) -- the exact age-offset factorisation documented in "
             "engine/staging.py (PERFORMANCE STRATEGY), not an "
             "approximation: cross-check below.")
    L.append(f"* exactness cross-check vs loan-by-loan pd_term_structure: "
             f"max abs diff = {xcheck_err:.2e}.\n")

    L.append("## Sanity gates\n")
    L.append("| check | result | detail |")
    L.append("|---|---|---|")
    for c in checks:
        L.append(f"| {c['name']} | {'PASS' if c['ok'] else '**FAIL**'} | "
                 f"{c['detail']} |")
    L.append("")

    L.append("## Documented simplifications\n")
    L.append("* Frozen-covariate lifetime PDs on BOTH legs "
             "(pd_term_structure rung-1 convention): no macro path, no LTV "
             "amortisation; scenario conditioning arrives with the "
             "satellite-model rung.")
    L.append("* 30-DPD backstop inert (no delinquency ladder in DCR) -- "
             "loud note above.")
    L.append("* Origination macro for pre-window vintages clamps to the "
             "earliest observed quarter (flagged per loan, "
             "`orig_macro_approx`); origination market rate is the "
             "per-quarter MEDIAN of loan-matched rate_time; zero-coded "
             "origination note rates fall back to the current note rate "
             "(`orig_rate_proxy`).")
    L.append("* No low-credit-risk exemption, no qualitative/watchlist "
             "triggers (fields do not exist in the dataset).")
    L.append("* Loans at/past scheduled maturity get a floored one-quarter "
             "window; payoff-quarter rows are excluded from the staged book "
             "as derecognitions.")
    L.append("* Models fitted on the full training window; the t=20 "
             "snapshot is an in-sample illustration, not a walk-forward "
             "simulation.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = StagingConfig()
    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]

    t0 = _time.perf_counter()
    models = {"default": fit_default_hazard(train),
              "prepay": fit_prepay_hazard(train)}
    fit_seconds = _time.perf_counter() - t0
    print(f"fitted both hazards in {fit_seconds:.1f}s")

    macro_map = build_macro_map(panel)

    books: dict[int, pd.DataFrame] = {}
    stage_seconds: dict[int, float] = {}
    for t in SNAPSHOTS:
        t0 = _time.perf_counter()
        books[t] = stage_book(panel, models, cfg, t)
        stage_seconds[t] = _time.perf_counter() - t0
        sh = stage_shares(books[t])
        print(f"t={t}: {len(books[t]):,} staged rows in "
              f"{stage_seconds[t]:.2f}s -- " +
              ", ".join(f"S{s} {sh[s]:.2%}" for s in (1, 2, 3)))

    sens = sensitivity_table(panel, models, macro_map, cfg)
    bench = scale_benchmark(panel, models, macro_map)
    print(f"benchmark: {bench['n_loans']:,} loans in "
          f"{bench['seconds']:.2f}s ({bench['loans_per_s']:,.0f} loans/s)")
    xcheck_err = crosscheck_term_structure(
        panel[panel["time"] <= 40], models, 40, n_sample=10, seed=0)
    print(f"crosscheck max |fast - reference| = {xcheck_err:.2e}")

    checks = sanity_checks(books, sens, xcheck_err)
    plot_stage_distribution(books, OUT / "stage_distribution.png")
    plot_sensitivity(sens, books, cfg, OUT / "stage2_sensitivity.png")
    write_report(books, sens, cfg, bench, xcheck_err, fit_seconds,
                 stage_seconds, checks, OUT / "staging_report.md")
    for f in ("stage_distribution.png", "stage2_sensitivity.png",
              "staging_report.md"):
        print(f"wrote {OUT / f}")

    if not all(c["ok"] for c in checks):
        for c in checks:
            if not c["ok"]:
                print(f"FAILED: {c['name']} -- {c['detail']}")
        raise SystemExit("staging sanity checks FAILED -- see report")
    print("all staging sanity checks PASSED")


if __name__ == "__main__":
    main()
