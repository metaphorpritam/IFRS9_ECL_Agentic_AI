"""Scenario-set exhibits (plan section 2.6; notes section 9).

Renders to outputs/scenarios/:
  fan_uer.png          3-scenario unemployment fan, 40q extended horizon
  fan_hpi_growth.png   3-scenario quarterly HPI-growth fan, same horizon
  scenarios_report.md  mapping table, weights rationale, upside convention

Run:  cd <repo root> && uv run --no-sync python -m analysis.scenario_exhibits

Chart conventions (house style + dataviz pass): one measure per chart (no
dual axes); fixed entity colors — base=accent navy, down=warn red, up=good
green (semantic: stress red, boom green); identity never color-alone (legend
+ neutral-ink direct labels; palette CVD separation validated, worst adjacent
pair deltaE 21.4); real calendar quarters on the x-axis from the t=60 ~ 2015Q1
jump-off; R&S window and reversion ramp shaded.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.mpl_style import COLORS, apply_textbook_style
from engine.scenarios import ScenarioSet, build_scenario_set

OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "scenarios"

SCEN_STYLE = {  # fixed entity -> (color, label) — never cycled
    "base": (COLORS["accent"], "Base (DFAST baseline deltas, w=0.50)"),
    "down": (COLORS["warn"], "Down (DFAST severely adverse deltas, w=0.25)"),
    "up": (COLORS["good"], "Up (damped mirror -0.35, w=0.25)"),
}
INK = "#333333"  # neutral text ink for direct labels (not series-colored)


def _fan(ax, sset: ScenarioSet, concept: str, scale: float = 1.0) -> None:
    """Draw the 3-scenario fan for one concept with h=0 jump-off anchoring."""
    h = np.arange(0, sset.horizon + 1)  # 0 = jump-off
    for name in ("down", "base", "up"):
        color, label = SCEN_STYLE[name]
        y = np.concatenate([[sset.jumpoff[concept]],
                            sset.paths[name][concept].to_numpy()]) * scale
        ax.plot(h, y, color=color, lw=1.8, label=label, zorder=3)
    ax.plot(0, sset.jumpoff[concept] * scale, "o", color=INK, ms=5, zorder=4)

    # R&S window and reversion ramp shading
    ax.axvspan(0, sset.rs_window, color="#1f3a5f", alpha=0.06, zorder=1)
    ax.axvspan(sset.rs_window, sset.rs_window + sset.reversion,
               color="#7f8c8d", alpha=0.08, zorder=1)
    ax.axhline(sset.longrun[concept] * scale, color=COLORS["gray"],
               ls="--", lw=1.0, zorder=2)

    # calendar ticks every 4 quarters from the jump-off
    ticks = np.arange(0, sset.horizon + 1, 4)
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(sset.jumpoff_period + int(t)) for t in ticks],
                       rotation=45, ha="right")
    ax.set_xlim(0, sset.horizon)


def _zone_notes(ax, sset: ScenarioSet, y: float, va: str = "top") -> None:
    common = dict(ha="center", va=va, fontsize=7.5, color=INK)
    ax.text(sset.rs_window / 2, y, "R&S window\n(DFAST 13q shape)", **common)
    ax.text(sset.rs_window + sset.reversion / 2, y, "reversion\n(8q linear)",
            **common)
    ax.text((sset.rs_window + sset.reversion + sset.horizon) / 2, y,
            "hold at panel long-run mean", **common)


def fan_uer(sset: ScenarioSet, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    _fan(ax, sset, "uer")
    peak_h = int(sset.paths["down"]["uer"].idxmax())
    peak = sset.paths["down"]["uer"].max()
    ax.annotate(
        f"severe peak {peak:.1f}pp\n(+{peak - sset.jumpoff['uer']:.1f}pp "
        f"vs jump-off, {sset.jumpoff_period + peak_h})",
        xy=(peak_h, peak), xytext=(peak_h + 5, peak - 0.7),
        fontsize=7.5, color=INK,
        arrowprops=dict(arrowstyle="-", color=INK, lw=0.7))
    ax.text(0.4, sset.jumpoff["uer"] - 0.55,
            f"jump-off t=60 ({sset.jumpoff_period}): "
            f"{sset.jumpoff['uer']:.1f}pp", fontsize=7.5, color=INK)
    ax.text(sset.horizon - 0.7, sset.longrun["uer"] + 0.12,
            f"panel long-run mean {sset.longrun['uer']:.2f}pp",
            fontsize=7.5, color=INK, ha="right")
    # neutral-ink direct labels inside the R&S window (identity not color-alone)
    for name, hh, dy in (("down", 9, 0.42), ("base", 9, 0.30), ("up", 9, 0.35)):
        ax.text(hh, sset.paths[name]["uer"].loc[hh] + dy, name,
                fontsize=8, color=INK, ha="center")
    _zone_notes(ax, sset, 3.5)
    ax.set_ylim(2.8, 12.4)
    ax.set_ylabel("Unemployment rate (pp)")
    ax.set_title("Scenario fan — unemployment rate, 40-quarter extended horizon\n"
                 "(DFAST 2026 deltas rebased onto the panel t=60 macro state)")
    ax.legend(loc="upper right", frameon=False)
    fig.savefig(path)
    plt.close(fig)


def fan_hpi_growth(sset: ScenarioSet, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    _fan(ax, sset, "hpi_growth", scale=100.0)  # display in %/q
    ax.axhline(0.0, color=INK, lw=0.8, zorder=2)
    trough_h = int(sset.paths["down"]["hpi_growth"].idxmin())
    trough = sset.paths["down"]["hpi_growth"].min() * 100
    ax.annotate(
        f"severe trough {trough:.1f}%/q ({sset.jumpoff_period + trough_h})\n"
        "(DFAST severe: ~-30% peak-to-trough HPI level)",
        xy=(trough_h, trough), xytext=(trough_h + 4.5, trough - 0.4),
        fontsize=7.5, color=INK,
        arrowprops=dict(arrowstyle="-", color=INK, lw=0.7))
    ax.text(sset.horizon - 0.7, sset.longrun["hpi_growth"] * 100 + 0.15,
            f"panel long-run mean {sset.longrun['hpi_growth'] * 100:.2f}%/q",
            fontsize=7.5, color=INK, ha="right")
    for name, hh, dy in (("down", 5, -0.55), ("base", 10, 0.3), ("up", 2, 0.35)):
        ax.text(hh, sset.paths[name]["hpi_growth"].loc[hh] * 100 + dy, name,
                fontsize=8, color=INK, ha="center")
    _zone_notes(ax, sset, 4.65)
    ax.set_ylim(-6.9, 4.9)
    ax.set_ylabel("HPI growth (% per quarter, log-diff)")
    ax.set_title("Scenario fan — quarterly house-price growth, 40-quarter horizon\n"
                 "(log-diff of DFAST HPI level, rebased onto the panel t=60 state)")
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(path)
    plt.close(fig)


def write_report(sset: ScenarioSet, path: Path) -> None:
    j, lr = sset.jumpoff, sset.longrun
    md = f"""# Scenario set — DFAST 2026 ingestion and the base/down/up paths

Reporting date: panel t=60 ~ {sset.jumpoff_period} (calendar anchoring verified
vs FRED UNRATE, corr 0.9963). Horizon: {sset.horizon} quarters
({sset.jumpoff_period + 1} .. {sset.jumpoff_period + sset.horizon}).
R&S window: {sset.rs_window} quarters (the DFAST 2026 path length);
reversion: {sset.reversion} quarters, linear, to the panel long-run means; hold thereafter.

## DFAST column -> panel concept -> transformation

| DFAST column | Panel concept | Transformation |
|---|---|---|
| Unemployment rate | `uer` (pp) | level, as-is |
| House Price Index (Level) | `hpi_growth` (decimal/q) | quarterly log-diff; 2026Q1 differenced against the last historic actual (2025Q4 level 323.4) |
| Real GDP growth (SAAR %) | `gdp_growth` (%/q) | `100*((1+g/100)^(1/4)-1)` — SAAR de-annualised to a plain quarterly rate |
| Mortgage rate | `mortgage_rate` (pp) | level, as-is |

Panel-side concept construction: `uer_time` / `hpi_time` / `gdp_time` are
national series (constant within quarter); `rate_time` varies mildly across
loans, so its quarterly MEDIAN is the market-rate level (the
`engine.staging.build_macro_map` convention). The panel's `gdp_time` is
YEAR-OVER-YEAR growth (2009 trough -4.15, matching YoY, not the -8.5 SAAR
trough) and is converted with the same fourth-root formula — the intra-year
quarterly profile is unidentified from YoY alone (documented simplification).

## Rebasing convention (shape transplant)

The panel ends ~2015Q1; the DFAST 2026 paths run 2026Q1-2029Q1. DFAST's value
is the supervisor-designed COHERENT multivariate shape, so each variable's
change-from-jump-off (jump-off = 2025Q4 actuals) is added to the panel's t=60
level:  `scenario_h(c) = panel_t60(c) + (dfast_h(c) - dfast_2025Q4(c))`,
uniformly across level and growth concepts. This preserves DFAST co-movement
exactly (severe UER peak-minus-jump-off stays +5.5pp) while anchoring at the
reporting-date macro state. It is a shape transplant, not a 2015-vintage forecast.

| Concept | Jump-off (t=60) | Long-run panel mean (reversion target) |
|---|---|---|
| uer (pp) | {j['uer']:.2f} | {lr['uer']:.2f} |
| hpi_growth (%/q) | {j['hpi_growth'] * 100:.2f} | {lr['hpi_growth'] * 100:.2f} |
| gdp_growth (%/q) | {j['gdp_growth']:.2f} | {lr['gdp_growth']:.2f} |
| mortgage_rate (pp) | {j['mortgage_rate']:.2f} | {lr['mortgage_rate']:.2f} |

## Scenarios and weights

| Scenario | Construction | Weight |
|---|---|---|
| base | DFAST Supervisory Baseline deltas, rebased | {sset.weights['base']:.2f} |
| down | DFAST Severely Adverse deltas, rebased | {sset.weights['down']:.2f} |
| up | judgmental damped mirror of the severely-adverse deltas, factor -0.35; UER floored at 3.5pp | {sset.weights['up']:.2f} |

**Why 50/25/25 is judgmental and why that is fine (plan section 2.6):**
scenario probabilities are not statistically identified — there is no dataset
of "how likely was the severe scenario". Banks set them by governance
committee and document the rationale; auditors test the documentation, not
the number. The deliverable is this rationale plus weight-sensitivity
exhibits downstream, not the number itself. **Named enhancement:** anchor the
weights (and the upside path itself) to Philadelphia-Fed SPF forecaster-
distribution percentiles — e.g. take the upside from the 25th percentile of
the SPF unemployment distribution instead of the -0.35 mirror.

**Upside convention:** DFAST publishes no upside. The damped mirror
(-0.35 x severe deltas) inherits DFAST's multivariate coherence; damping
encodes the empirical asymmetry of the cycle (booms are shallower than
busts). Result: a mild boom — UER drifts to ~{sset.paths['up']['uer'].min():.2f}pp
(floor 3.5pp, not binding), HPI appreciates ~{sset.paths['up']['hpi_growth'].max() * 100:.1f}%/q at peak.

**Beyond the R&S window (notes section 9.4):** macro paths are reasonable and
supportable only over the 13q DFAST window; each path then reverts linearly
over 8 quarters to the panel's own long-run means and holds — the standard
"PIT over the R&S window, revert to TTC" construction. All three scenarios
share the same long-run tail, so scenario differentiation lives entirely in
the 13q path + 8q ramp. Jensen caution (notes section 9.2): downstream ECL is
the weighted average of per-scenario ECLs, never the ECL of the weighted path.

## Exhibits

* `fan_uer.png` — unemployment fan; severe peak {sset.paths['down']['uer'].max():.1f}pp (+{sset.paths['down']['uer'].max() - j['uer']:.1f}pp vs jump-off).
* `fan_hpi_growth.png` — quarterly HPI-growth fan; severe trough {sset.paths['down']['hpi_growth'].min() * 100:.1f}%/q.
"""
    path.write_text(md, encoding="utf-8")


def main() -> None:
    apply_textbook_style()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sset = build_scenario_set()
    fan_uer(sset, OUT_DIR / "fan_uer.png")
    fan_hpi_growth(sset, OUT_DIR / "fan_hpi_growth.png")
    write_report(sset, OUT_DIR / "scenarios_report.md")
    print(f"wrote {OUT_DIR}/fan_uer.png, fan_hpi_growth.png, scenarios_report.md")


if __name__ == "__main__":
    main()
