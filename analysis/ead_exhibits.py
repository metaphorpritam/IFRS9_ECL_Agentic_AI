"""EAD exhibits: contractual amortisation profiles + full-book sanity report.

Run:  cd <repo root> && uv run python analysis/ead_exhibits.py

Takes the live book at the last TRAINING quarter (t = 40, the same snapshot
convention as analysis/fit_hazard.py -- the OOT window stays untouched even
as an exhibit source), builds every loan's CONTRACTUAL level-payment EAD
path with engine/ead.py, and writes to outputs/ead/:

  ead_profiles.png   declining contractual EAD paths for three representative
                     loans (short / median / long remaining term, picked
                     deterministically at the 2nd / 50th / 98th remaining-
                     term percentiles, ties broken by id), annotated with the
                     no-prepayment-double-counting rule
  ead_report.md      conventions, snapshot composition, the three profiled
                     loans, and the full-book sanity checks

Sanity checks (FAIL LOUDLY -- SystemExit -- if violated on ANY loan):
  1. EAD_1 equals the snapshot balance;
  2. every path is monotone non-increasing (no negative amortisation);
  3. terminal balance is exactly 0 one quarter past each loan's maturity;
  4. max EAD never exceeds the snapshot balance grown by one quarter's
     interest (in fact never exceeds the balance itself, since EAD_t is the
     start-of-period balance -- both bounds are reported).
"""

from __future__ import annotations

import sys
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
from engine.ead import RATE_DIVISOR, ccf_ead, ead_matrix  # noqa: E402

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "ead"
SNAP_TIME = 40                       # last training quarter (fit_hazard.py)
QUANTILES = (0.02, 0.50, 0.98)       # representative remaining-term picks
                                     # (2nd/50th/98th pct: the central 10-90
                                     # band is too tight at t=40 to tell the
                                     # three paths apart visually)
LABELS = ("short remaining term", "median remaining term",
          "long remaining term")
# fixed categorical order, all from the project palette (mpl_style.COLORS);
# CVD-validated (dataviz six checks) with line style + direct labels as
# secondary encoding
SERIES = [(COLORS["blue2"], "-"), (COLORS["orange"], "--"),
          (COLORS["good"], "-.")]


def load_snapshot() -> pd.DataFrame:
    cols = ["id", "time", "mat_time", "balance_time", "interest_rate_time",
            "terminal_event", "loan_age"]
    panel = pd.read_parquet(PANEL, columns=cols)
    snap = panel[(panel["time"] == SNAP_TIME)
                 & (panel["terminal_event"] == 0)
                 & (panel["balance_time"] > 0)].copy()
    snap["remaining_q"] = (snap["mat_time"] - snap["time"]).clip(lower=1)
    return snap.sort_values("id").reset_index(drop=True)


def pick_representatives(snap: pd.DataFrame) -> pd.DataFrame:
    """Deterministic picks at the remaining-term quantiles (ties -> lowest id)."""
    ordered = snap.sort_values(["remaining_q", "id"]).reset_index(drop=True)
    pos = [int(round(q * (len(ordered) - 1))) for q in QUANTILES]
    reps = ordered.iloc[pos].copy()
    reps["label"] = LABELS
    return reps


def sanity_checks(snap: pd.DataFrame, ead: pd.DataFrame) -> list[dict]:
    vals = ead.to_numpy()
    bal = snap.set_index("id").loc[ead.index, "balance_time"].to_numpy()
    r_q = snap.set_index("id").loc[ead.index,
                                   "interest_rate_time"].to_numpy() / RATE_DIVISOR
    rem = snap.set_index("id").loc[ead.index, "remaining_q"].to_numpy(int)
    tol = 1e-6 * np.maximum(bal, 1.0)
    # 3. balance one quarter PAST maturity (horizon covers rem+1 for all)
    past_maturity = vals[np.arange(len(vals)), rem]  # column rem = period rem+1
    checks = [
        dict(name="EAD_1 equals snapshot balance",
             metric=float(np.abs(vals[:, 0] - bal).max()),
             threshold="max abs diff == 0",
             passed=bool(np.abs(vals[:, 0] - bal).max() == 0.0)),
        dict(name="monotone non-increasing path",
             metric=float(np.diff(vals, axis=1).max()),
             threshold="max one-step increase <= float noise",
             passed=bool(np.all(np.diff(vals, axis=1) <= tol[:, None]))),
        dict(name="terminal balance 0 past maturity",
             metric=float(np.abs(past_maturity).max()),
             threshold="max |EAD_{rem+1}| == 0",
             passed=bool(np.all(past_maturity == 0.0))),
        dict(name="EAD_t <= balance * (1 + one quarter's interest)",
             metric=float((vals.max(axis=1) / bal).max()),
             threshold="max path/balance ratio <= 1 + r_q",
             passed=bool(np.all(vals.max(axis=1) <= bal * (1.0 + r_q) + tol))),
        dict(name="(stricter) EAD_t <= snapshot balance",
             metric=float((vals.max(axis=1) - bal).max()),
             threshold="max excess over balance <= 0",
             passed=bool(np.all(vals.max(axis=1) <= bal + tol))),
    ]
    return checks


def plot_profiles(reps: pd.DataFrame, ead: pd.DataFrame, path: Path) -> None:
    apply_textbook_style()
    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    # trim the x-range to the plotted loans (the full-book sanity horizon is
    # much longer than the three representatives need)
    x_max = int(reps["remaining_q"].max()) + 6
    quarters = np.arange(1, x_max + 1)
    for (_, r), (color, ls) in zip(reps.iterrows(), SERIES):
        y = ead.loc[r["id"]].to_numpy()[:x_max] / 1_000.0
        rem = int(r["remaining_q"])
        name = (f"{r['label']} — id {int(r['id'])}: matures t+{rem} "
                f"@ {r['interest_rate_time']:.2f}%")
        ax.plot(quarters, y, color=color, ls=ls, lw=2.0, label=name)
        # direct marker where the path amortises to exactly zero
        ax.plot(min(rem + 1, x_max), 0.0, marker="o", ms=5, color=color,
                clip_on=False, zorder=5)
    ax.set_xlabel("projected quarter t (t = 1 is the first quarter after "
                  f"the snapshot at time {SNAP_TIME})")
    ax.set_ylabel("contractual EAD_t ($ thousand)")
    ax.set_title("Contractual level-payment EAD profiles — "
                 "three representative loans, live book at t = 40")
    ax.set_xlim(0, x_max)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", frameon=False)
    fig.text(0.995, -0.04,
             "Contractual amortisation only — deliberately NOT prepay-scaled: "
             "the ECL survival S(t-1) is the competing-risk survival and "
             "already removes prepaid exposure;\nscaling EAD by prepayment "
             "too would double-count. Dots mark the quarter after maturity, "
             "where the contractual balance is exactly zero.",
             ha="right", va="top", fontsize=7.5, style="italic",
             color="#444444")
    fig.savefig(path)
    plt.close(fig)


def write_report(snap: pd.DataFrame, reps: pd.DataFrame,
                 checks: list[dict], horizon: int, path: Path) -> None:
    rev = ccf_ead(5.0, 20.0, 0.6)
    lines = [
        "# EAD exhibits — contractual exposure profiles (engine/ead.py)",
        "",
        f"Snapshot: live book at t = {SNAP_TIME} (last training quarter; "
        "terminal rows and zero balances excluded) — "
        f"**{len(snap):,} loans**, total balance "
        f"${snap['balance_time'].sum() / 1e9:.2f}bn, "
        f"median note rate {snap['interest_rate_time'].median():.2f}%, "
        f"median remaining term {snap['remaining_q'].median():.0f} quarters. "
        f"Projection horizon {horizon} quarters (covers every loan's "
        "maturity plus one quarter).",
        "",
        "## Conventions (engine/ead.py docstring is binding)",
        "",
        "* **EAD_t = contractual balance entering period t** (after t-1 "
        "scheduled payments), matching the compute_ecl §3 golden fixture; "
        "EAD_1 = snapshot balance.",
        "* Level-payment (annuity) amortisation, quarterly compounding of "
        "the nominal annual note rate in percent: r_q = rate/400.",
        "* Rate <= 0 / missing -> straight-line fallback (defensive only: "
        "every panel row has interest_rate_time > 0).",
        "* Remaining term = mat_time - time, floored at 1 quarter.",
        "* **CRITICAL — no prepayment double counting**: the path is "
        "CONTRACTUAL, never prepay-scaled. The ECL survival "
        "S(t) = prod(1 - lambda_default - lambda_prepay) from "
        "engine/hazard.py already carries prepayment; scaling EAD as well "
        "would double-count and understate lifetime ECL.",
        "* Revolver capability (no revolvers in the DCR book): "
        "EAD = drawn + CCF x max(limit - drawn, 0); reproduces the §12 "
        f"fixture 5 + 0.6 x 15 = **{rev:.1f}m** "
        "(asserted in tests/test_ead.py).",
        "",
        "## Representative loans (deterministic 2nd/50th/98th "
        "remaining-term percentiles)",
        "",
        "| profile | id | balance $ | note rate % | remaining quarters | "
        "loan age (q) |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in reps.iterrows():
        lines.append(
            f"| {r['label']} | {int(r['id'])} | {r['balance_time']:,.0f} | "
            f"{r['interest_rate_time']:.2f} | {r['remaining_q']:.0f} | "
            f"{r['loan_age']:.0f} |")
    lines += [
        "",
        "![contractual EAD profiles](ead_profiles.png)",
        "",
        "## Full-book sanity checks (all loans in the snapshot)",
        "",
        "| check | metric | criterion | result |",
        "|---|---|---|---|",
    ]
    for c in checks:
        lines.append(f"| {c['name']} | {c['metric']:.3e} | {c['threshold']} "
                     f"| {'PASS' if c['passed'] else '**FAIL**'} |")
    lines += [
        "",
        "## Documented simplifications",
        "",
        "* Original contractual maturity only — no modification / "
        "payment-holiday reprofiling data exists in the panel.",
        "* Every term loan treated as level-pay to zero; no balloon or "
        "interest-only structures (no amortisation-type field in the DCR "
        "data — disciplined default for US fixed-rate mortgages).",
        "* Fixed note rate over the projection (interest_rate_time frozen "
        "at the snapshot; ARM resets out of scope at this rung).",
        "* Loans at/past maturity (remaining term floored at 1) are due in "
        "full within one quarter.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    snap = load_snapshot()
    horizon = int(snap["remaining_q"].max()) + 1
    ead = ead_matrix(snap, horizon=horizon)
    checks = sanity_checks(snap, ead)
    reps = pick_representatives(snap)
    plot_profiles(reps, ead, OUT / "ead_profiles.png")
    write_report(snap, reps, checks, horizon, OUT / "ead_report.md")
    for c in checks:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"[{status}] {c['name']}  (metric {c['metric']:.3e})")
    print(f"snapshot loans: {len(snap):,}; horizon: {horizon} quarters")
    print(f"wrote {OUT / 'ead_profiles.png'}")
    print(f"wrote {OUT / 'ead_report.md'}")
    if not all(c["passed"] for c in checks):
        raise SystemExit("EAD sanity checks FAILED — see report")


if __name__ == "__main__":
    main()
