"""ECL engine exhibits: allowance by stage, the movement waterfall, coverage.

Run:  cd <repo root> && uv run python analysis/run_ecl.py

Fits the rung-1 engines (cause-specific hazards on the training split --
identical call to analysis/fit_hazard.py -- and the two-stage LGD, which
filters to train-split resolved defaults internally), then runs the full
deterministic ECL assembly (engine/ecl.py) at the two exhibit snapshots:

    t = 20   calm quarter (pre-stress)
    t = 40   last training quarter, inside the stress episode

and writes to outputs/ecl/:

  allowance_by_stage.png   reported allowance ($m) by IFRS 9 stage, both
                           snapshots (12m ECL for Stage 1, lifetime for 2/3)
  ecl_waterfall.png        THE dashboard centrepiece: the allowance movement
                           t=20 -> t=40 -- opening, stage migration,
                           re-measurement, derecognitions, new loans, closing
                           (sequential attribution; ordering documented in
                           engine/ecl.py and annotated on the chart)
  coverage_by_stage.png    coverage ratios (allowance / EAD) by stage
  ecl_report.md            headline numbers, stage tables, movement table,
                           sanity gates, documented simplifications

Design choices (stated, not silent):
* ECL book = panel rows at t excluding payoff_event == 1 (derecognitions);
  default rows stay as Stage 3 -- same population as the staging exhibits.
* Models fitted once on the full training window; t=20 is an in-sample
  calm-quarter illustration, not a walk-forward simulation.
* Coverage = sum(reported allowance) / sum(balance) within each cell.

Sanity gates (FAIL LOUDLY -- SystemExit -- if violated):
  1. PD-grid consistency: the ECL engine's own cumulative PD
     (lifetime_pd_engine, the marginal-grid row sums) matches the staging
     fast path (lifetime_pd_now) to < 1e-10 on every loan, both snapshots;
  2. LGD age-clock grid matches engine.lgd.predict_components to < 1e-10
     on a fixed-seed loan sample (crosscheck_lgd_grid);
  3. reported allowance mapping exact (Stage 1 -> 12m, else lifetime) and
     Stage-3 ECL == lgd_current * balance exactly;
  4. 0 <= 12m ECL <= lifetime ECL on every loan;
  5. Stage-2 coverage > Stage-1 coverage at each snapshot (evaluated where
     the Stage-2 population has >= 30 loans);
  6. stress > calm: total coverage at t=40 exceeds t=20;
  7. waterfall identity: components sum to closing - opening within $0.01.
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
from engine.ecl import (  # noqa: E402
    WATERFALL_COMPONENTS,
    EclConfig,
    crosscheck_lgd_grid,
    ecl_for_snapshot,
    movement_decomposition,
)
from engine.hazard import fit_default_hazard, fit_prepay_hazard  # noqa: E402
from engine.lgd import fit_lgd_models  # noqa: E402

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "ecl"
SNAPSHOTS = (20, 40)
PD_GRID_TOL = 1e-10
LGD_GRID_TOL = 1e-10
MIN_STAGE2_LOANS = 30            # coverage gate needs a real population

#: fixed entity colours shared with the staging exhibits (calm navy, stress red)
SNAP_COLOR = {20: COLORS["accent"], 40: COLORS["warn"]}
SNAP_LABEL = {20: "t = 20 (calm)", 40: "t = 40 (stress)"}
STAGES = (1, 2, 3)


# ---------------------------------------------------------------------------
# aggregation helpers
# ---------------------------------------------------------------------------

def stage_aggregates(book: pd.DataFrame) -> pd.DataFrame:
    """Per-stage (and total) loans, EAD, reported allowance, coverage."""
    rows = []
    for s in list(STAGES) + ["total"]:
        d = book if s == "total" else book[book["stage"] == s]
        bal = float(d["balance"].sum())
        rep = float(d["ecl_reported"].sum())
        rows.append({
            "stage": s, "n_loans": len(d), "ead_m": bal / 1e6,
            "allowance_m": rep / 1e6,
            "coverage": rep / bal if bal > 0 else np.nan,
            "ecl_12m_m": float(d["ecl_12m"].sum()) / 1e6,
            "ecl_lifetime_m": float(d["ecl_lifetime"].sum()) / 1e6,
            "mean_lgd": float(d["lgd_current"].mean()) if len(d) else np.nan,
            "mean_pd_life": float(d["lifetime_pd_now"].mean())
            if len(d) else np.nan,
        })
    return pd.DataFrame(rows)


def coverage_of(agg: pd.DataFrame, stage) -> float:
    v = agg.loc[agg["stage"] == stage, "coverage"]
    return float(v.iloc[0]) if len(v) else float("nan")


# ---------------------------------------------------------------------------
# sanity gates
# ---------------------------------------------------------------------------

def sanity_checks(books: dict[int, pd.DataFrame],
                  aggs: dict[int, pd.DataFrame],
                  wf: pd.DataFrame, lgd_xcheck: float) -> list[dict]:
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    worst_pd = max(
        float(np.abs(b["lifetime_pd_engine"] - b["lifetime_pd_now"]).max())
        for b in books.values())
    add("ECL PD grid == staging lifetime PD (every loan)",
        worst_pd < PD_GRID_TOL,
        f"max abs diff = {worst_pd:.2e} (tol {PD_GRID_TOL:g})")

    add("LGD age-clock grid == predict_components (fixed-seed sample)",
        lgd_xcheck < LGD_GRID_TOL,
        f"max abs diff = {lgd_xcheck:.2e} (tol {LGD_GRID_TOL:g})")

    map_ok, s3_ok, order_ok = True, True, True
    for b in books.values():
        expect = np.where(b["stage"] == 1, b["ecl_12m"], b["ecl_lifetime"])
        map_ok &= bool(np.array_equal(expect, b["ecl_reported"].to_numpy()))
        d3 = b[b["stage"] == 3]
        s3_ok &= bool(np.allclose(d3["ecl_reported"],
                                  d3["lgd_current"] * d3["balance"],
                                  rtol=1e-12, atol=1e-9))
        order_ok &= bool((b["ecl_12m"] <= b["ecl_lifetime"]
                          + 1e-9 * np.maximum(b["ecl_lifetime"], 1)).all()
                         and (b["ecl_12m"] >= 0).all())
    add("reported mapping exact + Stage-3 == LGD x balance", map_ok and s3_ok,
        f"mapping {'OK' if map_ok else 'BROKEN'}, "
        f"stage-3 rule {'OK' if s3_ok else 'BROKEN'}")
    add("0 <= 12m ECL <= lifetime ECL on every loan", order_ok,
        "checked both snapshots")

    for t, agg in aggs.items():
        n2 = int(agg.loc[agg["stage"] == 2, "n_loans"].iloc[0])
        c1, c2 = coverage_of(agg, 1), coverage_of(agg, 2)
        if n2 >= MIN_STAGE2_LOANS:
            add(f"Stage-2 coverage > Stage-1 at t={t}", c2 > c1,
                f"stage 1 {c1:.3%} vs stage 2 {c2:.3%} ({n2:,} loans)")
        else:
            add(f"Stage-2 coverage > Stage-1 at t={t} (population gate)",
                True, f"only {n2} Stage-2 loans (< {MIN_STAGE2_LOANS}) -- "
                f"not evaluable; stage 1 {c1:.3%}"
                + (f" vs stage 2 {c2:.3%}" if n2 else ""))

    tot = {t: coverage_of(aggs[t], "total") for t in SNAPSHOTS}
    add("stress > calm: total coverage t=40 > t=20",
        tot[40] > tot[20], f"t=20 {tot[20]:.3%} -> t=40 {tot[40]:.3%}")

    amt = dict(zip(wf["component"], wf["amount"]))
    resid = abs(amt["closing"] - sum(
        amt[c] for c in WATERFALL_COMPONENTS if c != "closing"))
    add("waterfall components sum to closing", resid < 0.01,
        f"|closing - (opening + deltas)| = ${resid:.6f}")
    return checks


# ---------------------------------------------------------------------------
# exhibits
# ---------------------------------------------------------------------------

def plot_allowance_by_stage(aggs: dict[int, pd.DataFrame],
                            path: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    x = np.arange(len(STAGES), dtype=float)
    width = 0.36
    for j, t in enumerate(SNAPSHOTS):
        agg = aggs[t].set_index("stage")
        vals = [float(agg.loc[s, "allowance_m"]) for s in STAGES]
        bars = ax.bar(x + (j - 0.5) * (width + 0.04), vals, width,
                      color=SNAP_COLOR[t], label=SNAP_LABEL[t], zorder=3)
        for b, v in zip(bars, vals):
            ax.annotate(f"{v:,.1f}", (b.get_x() + b.get_width() / 2, v),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=8, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(["Stage 1\n(12-month ECL)",
                        "Stage 2\n(SICR, lifetime ECL)",
                        "Stage 3\n(default, lifetime ECL)"])
    ax.set_ylabel("reported allowance ($m)")
    ax.set_title("IFRS 9 reported allowance by stage: calm vs stress "
                 "snapshot (contractual EAD, competing-risk PD)")
    ax.legend(frameon=False)
    fig.savefig(path)
    plt.close(fig)


def plot_waterfall(wf: pd.DataFrame, path: Path) -> None:
    """The centrepiece: sequential allowance movement t=20 -> t=40."""
    apply_textbook_style()
    amt = {k: v / 1e6 for k, v in zip(wf["component"], wf["amount"])}
    nlo = dict(zip(wf["component"], wf["n_loans"]))
    labels = {
        "opening": f"Opening\n{wf.attrs['label_t0']}\n"
                   f"({nlo['opening']:,} loans)",
        "stage_migration": "Stage\nmigration",
        "remeasurement": "Re-measurement\n(macro & params,\nsame loans)",
        "derecognitions": "Derecognitions\n(payoffs, resolved\ndefaults)",
        "new_loans": "New loans\n(later\noriginations)",
        "closing": f"Closing\n{wf.attrs['label_t1']}\n"
                   f"({nlo['closing']:,} loans)",
    }
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    running = 0.0
    tops = []
    for i, name in enumerate(WATERFALL_COMPONENTS):
        v = amt[name]
        if name in ("opening", "closing"):
            ax.bar(i, v, width=0.62, color=COLORS["accent"], zorder=3)
            ax.annotate(f"{v:,.1f}", (i, v), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=9,
                        fontweight="bold", color="#333333")
            running = v if name == "opening" else running
            tops.append(v)
        else:
            color = COLORS["warn"] if v >= 0 else COLORS["good"]
            bottom = running if v >= 0 else running + v
            ax.bar(i, abs(v), bottom=bottom, width=0.62, color=color,
                   zorder=3)
            top = max(running, running + v)
            ax.annotate(f"{v:+,.1f}", (i, top), textcoords="offset points",
                        xytext=(0, 4), ha="center", fontsize=9,
                        color="#333333")
            running += v
            tops.append(top)
        if i < len(WATERFALL_COMPONENTS) - 1:      # connector to next bar
            ax.plot([i + 0.31, i + 1 - 0.31], [running, running],
                    color=COLORS["gray"], lw=1, ls="--", zorder=2)
    ax.set_xticks(range(len(WATERFALL_COMPONENTS)))
    ax.set_xticklabels([labels[c] for c in WATERFALL_COMPONENTS], fontsize=8)
    ax.set_ylim(0, max(tops) * 1.14)
    ax.set_ylabel("reported allowance ($m)")

    # Zoom inset: the surviving-book movement (opening -> subtotal before
    # new loans) is the P&L story but is visually crushed by the new-loans
    # bar on a 20-quarter jump of a growing book -- same data, zoomed scale.
    sub = (amt["opening"] + amt["stage_migration"] + amt["remeasurement"]
           + amt["derecognitions"])
    zoom_vals = [("open", amt["opening"], "level"),
                 ("stage\nmigr.", amt["stage_migration"], "delta"),
                 ("re-\nmeas.", amt["remeasurement"], "delta"),
                 ("derecog.", amt["derecognitions"], "delta"),
                 ("subtotal\n(no new\nloans)", sub, "level")]
    ax2 = fig.add_axes([0.145, 0.52, 0.34, 0.33])
    run2, peak = 0.0, 0.0
    for i, (lab, v, kind) in enumerate(zoom_vals):
        if kind == "level":
            ax2.bar(i, v, width=0.6, color=COLORS["accent"], zorder=3)
            ax2.annotate(f"{v:,.1f}", (i, v), textcoords="offset points",
                        xytext=(0, 2), ha="center", fontsize=6.5,
                        color="#333333")
            run2, top2 = (v if i == 0 else run2), v
        else:
            color = COLORS["warn"] if v >= 0 else COLORS["good"]
            ax2.bar(i, abs(v), bottom=(run2 if v >= 0 else run2 + v),
                    width=0.6, color=color, zorder=3)
            top2 = max(run2, run2 + v)
            ax2.annotate(f"{v:+,.1f}", (i, top2),
                         textcoords="offset points", xytext=(0, 2),
                         ha="center", fontsize=6.5, color="#333333")
            run2 += v
        peak = max(peak, top2)
        if i < len(zoom_vals) - 1:
            ax2.plot([i + 0.3, i + 1 - 0.3], [run2, run2],
                     color=COLORS["gray"], lw=0.8, ls="--", zorder=2)
    ax2.set_xticks(range(len(zoom_vals)))
    ax2.set_xticklabels([z[0] for z in zoom_vals], fontsize=6.5)
    ax2.set_ylim(0, peak * 1.22)
    ax2.tick_params(axis="y", labelsize=6.5)
    ax2.set_title("Zoom: surviving book, before new loans ($m)",
                  fontsize=7.5)
    ax2.grid(alpha=0.2, linestyle="--")
    ax.set_title("IFRS 9 allowance movement, t=20 (calm) to t=40 (stress) "
                 "-- sequential attribution waterfall")
    fig.text(0.995, 0.02,
             "Attribution order (order-dependent; engine/ecl.py): stage "
             "migration at t=20 marks, then re-measurement on surviving "
             "loans, then portfolio change.\nReported allowance = 12m ECL "
             "(Stage 1) / lifetime ECL (Stage 2 & 3). Charges in red, "
             "releases in green.",
             ha="right", va="bottom", fontsize=7, color="#555555")
    fig.subplots_adjust(bottom=0.28)
    fig.savefig(path)
    plt.close(fig)


def plot_coverage_by_stage(aggs: dict[int, pd.DataFrame],
                           path: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    x = np.arange(len(STAGES), dtype=float)
    width = 0.36
    ymax = 0.0
    for j, t in enumerate(SNAPSHOTS):
        agg = aggs[t].set_index("stage")
        vals, notes = [], []
        for s in STAGES:
            n = int(agg.loc[s, "n_loans"])
            c = float(agg.loc[s, "coverage"]) if n else np.nan
            vals.append(0.0 if not np.isfinite(c) else 100.0 * c)
            notes.append("n/a" if (n == 0 or not np.isfinite(c))
                         else f"{100.0 * c:.2f}%")
        bars = ax.bar(x + (j - 0.5) * (width + 0.04), vals, width,
                      color=SNAP_COLOR[t], label=SNAP_LABEL[t], zorder=3)
        ymax = max(ymax, max(vals))
        for b, note, v in zip(bars, notes, vals):
            ax.annotate(note, (b.get_x() + b.get_width() / 2, v),
                        textcoords="offset points", xytext=(0, 3),
                        ha="center", fontsize=8, color="#333333")
    ax.set_xticks(x)
    ax.set_xticklabels(["Stage 1", "Stage 2", "Stage 3"])
    ax.set_ylabel("coverage: allowance / EAD (%)")
    ax.set_ylim(0, ymax * 1.18)
    ax.set_title("Coverage ratios by stage -- the impairment gradient "
                 "(Stage 2 > Stage 1; stress > calm)")
    ax.legend(frameon=False, loc="upper left")
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def write_report(books: dict[int, pd.DataFrame],
                 aggs: dict[int, pd.DataFrame], wf: pd.DataFrame,
                 cfg: EclConfig, checks: list[dict],
                 timings: dict[str, float], path: Path) -> None:
    L: list[str] = []
    L.append("# ECL engine report -- allowance, coverage, movement\n")
    L.append("Generated by `analysis/run_ecl.py` (engine/ecl.py -- the "
             "deterministic ECL assembly).\n")

    L.append("## The formula\n")
    L.append("`ECL = sum_t S(t-1) * lambda_t * LGD_t * EAD_t * (1+EIR)^-t` "
             "(compute_ecl section-3 golden convention), per loan over the "
             "remaining contractual life in quarters. S(t) is the "
             "COMPETING-RISK survival (default + prepayment) from "
             "engine/hazard.py; **EAD_t is therefore the CONTRACTUAL "
             "amortisation balance (engine/ead.py), never prepay-scaled -- "
             "scaling EAD too would double-count prepayment.** EIR proxy: "
             "current note rate / 400 per quarter (same divisor as the EAD "
             "annuity). 12-month ECL = first "
             f"{cfg.quarters_12m} projected quarters; reported allowance = "
             "12m (Stage 1) / lifetime (Stage 2 & 3); Stage 3 = "
             "LGD(x_now) x current balance.\n")

    L.append("## Headline\n")
    tot = {t: aggs[t][aggs[t]["stage"] == "total"].iloc[0] for t in SNAPSHOTS}
    L.append("| snapshot | loans | EAD ($m) | reported allowance ($m) | "
             "coverage | sum 12m ECL ($m) | sum lifetime ECL ($m) |")
    L.append("|---|---|---|---|---|---|---|")
    for t in SNAPSHOTS:
        r = tot[t]
        L.append(f"| t={t} | {int(r['n_loans']):,} | {r['ead_m']:,.1f} | "
                 f"{r['allowance_m']:,.1f} | {r['coverage']:.3%} | "
                 f"{r['ecl_12m_m']:,.1f} | {r['ecl_lifetime_m']:,.1f} |")
    L.append("")
    L.append(f"Stress multiplies the book's coverage by "
             f"{tot[40]['coverage'] / tot[20]['coverage']:.1f}x "
             f"(t=20 {tot[20]['coverage']:.3%} -> t=40 "
             f"{tot[40]['coverage']:.3%}): the stage mix shifts toward "
             "lifetime ECL AND every leg re-marks (higher PDs, higher "
             "LGDs on collapsed collateral).\n")

    L.append("## Allowance by stage\n")
    for t in SNAPSHOTS:
        L.append(f"### t = {t}\n")
        L.append("| stage | loans | EAD ($m) | allowance ($m) | coverage | "
                 "mean LGD | mean lifetime PD |")
        L.append("|---|---|---|---|---|---|---|")
        for _, r in aggs[t].iterrows():
            cov = f"{r['coverage']:.3%}" if np.isfinite(r["coverage"]) \
                else "n/a"
            mlgd = f"{r['mean_lgd']:.3f}" if np.isfinite(r["mean_lgd"]) \
                else "n/a"
            mpd = f"{r['mean_pd_life']:.3f}" \
                if np.isfinite(r["mean_pd_life"]) else "n/a"
            L.append(f"| {r['stage']} | {int(r['n_loans']):,} | "
                     f"{r['ead_m']:,.1f} | {r['allowance_m']:,.2f} | {cov} | "
                     f"{mlgd} | {mpd} |")
        L.append("")

    L.append("## Movement decomposition (t=20 -> t=40)\n")
    L.append("Sequential attribution, ORDER-DEPENDENT (documented in "
             "engine/ecl.py): (1) stage migration on surviving loans at "
             "frozen t=20 marks; (2) re-measurement at the migrated stage "
             "('same loans, re-marked'); (3) derecognitions at opening "
             "marks; (4) new loans at closing marks. A different ordering "
             "would allocate the migration x re-measurement interaction "
             "differently.\n")
    L.append("| component | $m | loans |")
    L.append("|---|---|---|")
    for _, r in wf.iterrows():
        L.append(f"| {r['component']} | {r['amount'] / 1e6:+,.2f} | "
                 f"{int(r['n_loans']):,} |")
    amt = dict(zip(wf["component"], wf["amount"]))
    L.append("")
    L.append(f"Net portfolio change (derecognitions + new loans): "
             f"{(amt['derecognitions'] + amt['new_loans']) / 1e6:+,.2f} $m; "
             f"net P&L-style movement on surviving loans (migration + "
             f"re-measurement): "
             f"{(amt['stage_migration'] + amt['remeasurement']) / 1e6:+,.2f}"
             " $m.\n")

    L.append("## Sanity gates\n")
    L.append("| check | result | detail |")
    L.append("|---|---|---|")
    for c in checks:
        L.append(f"| {c['name']} | {'PASS' if c['ok'] else '**FAIL**'} | "
                 f"{c['detail']} |")
    L.append("")

    L.append("## Performance\n")
    for k, v in timings.items():
        L.append(f"* {k}: {v:.1f}s")
    L.append("")

    L.append("## Documented simplifications (engine/ecl.py docstring)\n")
    L.append("* EIR proxy = current note rate / 400 per quarter (fixed-rate "
             "book; IFRS 9's origination EIR coincides up to repricing). "
             "Unusable rate -> undiscounted (defensive only; never fires "
             "on the panel).")
    L.append("* Frozen covariates over the projection on the hazard AND LGD "
             "legs; only the loan-age clock advances (hazard age spline + "
             "LGD loan_age term, exact within the fitted GLMs). No macro "
             "path -- scenario conditioning is a later rung.")
    L.append("* EAD is the CONTRACTUAL level-payment path -- never "
             "prepay-scaled (the competing-risk survival already carries "
             "prepayment; double-counting rule).")
    L.append("* Stage-3 ECL = LGD x current balance, undiscounted (loss "
             "crystallised; workout discounting embedded in the vendor's "
             "lgd_time per engine/lgd.py).")
    L.append("* 12-month ECL = first 4 projected quarters.")
    L.append("* Movement attribution is sequential and order-dependent "
             "(ordering stated above).")
    L.append("* ECL book excludes payoff-quarter rows (derecognitions); "
             "models fitted once on the training window -- t=20 is an "
             "in-sample calm-quarter illustration.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = EclConfig()
    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]

    timings: dict[str, float] = {}
    t0 = _time.perf_counter()
    models = {"default": fit_default_hazard(train),
              "prepay": fit_prepay_hazard(train),
              "lgd": fit_lgd_models(panel)}   # train filter internal
    timings["model fits (2 hazards + 2-stage LGD)"] = \
        _time.perf_counter() - t0
    print(f"fitted hazards + LGD in "
          f"{timings['model fits (2 hazards + 2-stage LGD)']:.1f}s")

    books: dict[int, pd.DataFrame] = {}
    aggs: dict[int, pd.DataFrame] = {}
    for t in SNAPSHOTS:
        t1 = _time.perf_counter()
        books[t] = ecl_for_snapshot(panel, t, models, cfg)
        timings[f"ecl_for_snapshot t={t}"] = _time.perf_counter() - t1
        aggs[t] = stage_aggregates(books[t])
        r = aggs[t][aggs[t]["stage"] == "total"].iloc[0]
        print(f"t={t}: {int(r['n_loans']):,} loans, allowance "
              f"${r['allowance_m']:,.1f}m, coverage {r['coverage']:.3%} "
              f"({timings[f'ecl_for_snapshot t={t}']:.2f}s)")

    wf = movement_decomposition(books[20], books[40],
                                label_t0="t=20", label_t1="t=40")
    print("waterfall ($m): " + ", ".join(
        f"{c} {v / 1e6:+,.1f}" for c, v in zip(wf['component'],
                                               wf['amount'])))

    snap40 = panel[(panel["time"] == 40) & (panel["payoff_event"] == 0)]
    lgd_xcheck = crosscheck_lgd_grid(models["lgd"], snap40,
                                     n_sample=20, k_max=40, seed=0)
    print(f"LGD grid crosscheck max |fast - reference| = {lgd_xcheck:.2e}")

    checks = sanity_checks(books, aggs, wf, lgd_xcheck)
    plot_allowance_by_stage(aggs, OUT / "allowance_by_stage.png")
    plot_waterfall(wf, OUT / "ecl_waterfall.png")
    plot_coverage_by_stage(aggs, OUT / "coverage_by_stage.png")
    write_report(books, aggs, wf, cfg, checks, timings,
                 OUT / "ecl_report.md")
    for f in ("allowance_by_stage.png", "ecl_waterfall.png",
              "coverage_by_stage.png", "ecl_report.md"):
        print(f"wrote {OUT / f}")

    if not all(c["ok"] for c in checks):
        for c in checks:
            if not c["ok"]:
                print(f"FAILED: {c['name']} -- {c['detail']}")
        raise SystemExit("ECL sanity checks FAILED -- see report")
    print("all ECL sanity checks PASSED")


if __name__ == "__main__":
    main()
