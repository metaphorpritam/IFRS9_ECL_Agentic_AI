"""
Chapter 9 (The App: A Guidebook) figure generation.

Every figure below is either (a) rendered from LIVE JSON captured this
session from the running local FastAPI service (uv run --no-sync uvicorn
app.api.main:app --port 7861), saved under
/tmp/.../scratchpad/live/*.json, and is a matplotlib MOCKUP of the panel's
visual pattern -- explicitly labeled as such, never claimed to be a browser
screenshot (no browser tooling available, per the campaign facts) -- or
(b) a structural flowchart (endpoint wiring, Docker build stages) built
from the actual code (app/api/main.py route sweep, Dockerfile stages),
not from data.

Run: uv run --no-sync python notes/assets/img/ch09/build_diagrams.py
"""
import json
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..",
                                 ".claude", "skills", "pageindex-plus", "assets"))
from matplotlib_setup import apply_textbook_style, COLORS  # noqa: E402

apply_textbook_style()

HERE = os.path.dirname(os.path.abspath(__file__))
LIVE = "/tmp/claude-1000/-mnt-d-Python-UV-IFRS9-ECL-Agentic-AI/92d283b4-d797-4f6b-8a1f-37991aee5d16/scratchpad/live"


def load(name):
    with open(os.path.join(LIVE, name)) as f:
        return json.load(f)


def save(fig, name):
    path = os.path.join(HERE, name)
    fig.savefig(path)
    plt.close(fig)
    print("wrote", path)


MOCK_NOTE = "matplotlib mockup rendered from live API data -- not a browser screenshot (no browser tooling available)"

# --------------------------------------------------------------------------
# Fig 1 -- Executive Overview tab layout mockup
# --------------------------------------------------------------------------

def fig_executive_layout():
    s = load("api_ecl_summary.json")
    fig = plt.figure(figsize=(9.2, 6.4))
    gs = fig.add_gridspec(4, 4, height_ratios=[0.55, 0.9, 0.55, 1.6], hspace=0.75, wspace=0.5)

    fig.suptitle("Executive Overview -- tab layout mockup  (" + MOCK_NOTE + ")", fontsize=10.5, y=0.985)

    # header band
    ax_hdr = fig.add_subplot(gs[0, :])
    ax_hdr.axis("off")
    ax_hdr.text(0.0, 0.5, "IFRS 9 ECL Copilot", fontsize=12, fontweight="bold", va="center")
    ax_hdr.text(0.30, 0.5, "MDD", fontsize=9, color=COLORS["accent"], va="center",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=COLORS["accent"]))
    ax_hdr.text(0.62, 0.5,
                f"{s['as_of']['period']} · {s['n_loans']:,} loans · ${s['balance']/1e6:,.1f}m book",
                fontsize=9, color=COLORS["gray"], va="center")
    ax_hdr.axhline(0.05, color="0.7", lw=0.8)

    # 4 KPI tiles
    tiles = [
        ("Scenario-weighted allowance", f"${s['weighted_allowance']/1e6:,.1f}m",
         f"{s['n_loans']:,} loans, ${s['balance']/1e6:,.1f}m balance"),
        ("Coverage", f"{s['coverage']*100:.2f}%", "allowance / balance"),
        ("Jensen ratio", f"{s['jensen_ratio']:.4f}x", "weighted ECL vs avg-path ECL"),
        ("Reporting date", s["as_of"]["period"], f"t={s['as_of']['t']} of 60"),
    ]
    for i, (label, val, hint) in enumerate(tiles):
        ax = fig.add_subplot(gs[1, i])
        ax.axis("off")
        box = FancyBboxPatch((0.03, 0.05), 0.94, 0.9, boxstyle="round,pad=0.02,rounding_size=0.03",
                              fc="#f7f5ee", ec="0.75", lw=0.8, transform=ax.transAxes)
        ax.add_patch(box)
        ax.text(0.10, 0.78, label, fontsize=7.2, color=COLORS["gray"], transform=ax.transAxes, wrap=True)
        ax.text(0.10, 0.42, val, fontsize=13, fontweight="bold", color=COLORS["accent"], transform=ax.transAxes)
        ax.text(0.10, 0.15, hint, fontsize=6.3, color=COLORS["gray"], transform=ax.transAxes)
        ax.text(0.90, 0.85, "✦", fontsize=8, color=COLORS["purple"], transform=ax.transAxes, ha="right")

    # Exhibit 1 -- stage mix bar
    ax_sm = fig.add_subplot(gs[2, :])
    stage_pct = [s["stage_mix"]["stage1"]["allowance_pct_of_total"],
                 s["stage_mix"]["stage2"]["allowance_pct_of_total"],
                 s["stage_mix"]["stage3"]["allowance_pct_of_total"]]
    stage_colors = [COLORS["good"], "#d39e00", COLORS["warn"]]
    stage_labels = ["Stage 1 (performing)", "Stage 2 (SICR)", "Stage 3 (impaired)"]
    left = 0
    ax_sm.text(-0.01, 1.55, "Exhibit 1 -- Stage mix of allowance", fontsize=8.5, fontweight="bold",
               transform=ax_sm.transAxes)
    for pct, c, lab in zip(stage_pct, stage_colors, stage_labels):
        ax_sm.barh(0, pct, left=left, color=c, height=0.5, edgecolor="white")
        if pct > 5:
            ax_sm.text(left + pct / 2, 0, f"{pct:.1f}%", ha="center", va="center", fontsize=7.5, color="white")
        left += pct
    ax_sm.set_xlim(0, 100)
    ax_sm.set_ylim(-1.3, 2.0)
    ax_sm.axis("off")
    for i, (lab, c, pct, n) in enumerate(zip(stage_labels, stage_colors, stage_pct,
                                              [s["stage_mix"]["stage1"]["n_loans"], s["stage_mix"]["stage2"]["n_loans"], s["stage_mix"]["stage3"]["n_loans"]])):
        ax_sm.text(i * 33, -1.0, f"■ {lab}: {pct:.1f}%, {n:,} loans", fontsize=6.6, color=c)

    # scenario table snippet
    ax_tab = fig.add_subplot(gs[3, :])
    ax_tab.axis("off")
    ax_tab.text(0.0, 1.02, "Exhibit 2 -- Scenario table (25/50/25 adopted)", fontsize=8.5, fontweight="bold",
                transform=ax_tab.transAxes)
    cols = ["Scenario", "Weight", "Allowance ($m)", "Coverage", "UER peak (pp)"]
    rows = [[sc["name"], f"{sc['weight']*100:.0f}%", f"${sc['allowance']/1e6:,.1f}m",
             f"{sc['coverage']*100:.2f}%", f"{sc['uer_peak_pp']:.1f}"] for sc in s["scenarios"]]
    tbl = ax_tab.table(cellText=rows, colLabels=cols, loc="upper center", cellLoc="center",
                        bbox=[0.0, 0.35, 1.0, 0.55])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.3)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("0.8")
        if r == 0:
            cell.set_facecolor("#e8eef7")
            cell.set_text_props(fontweight="bold")
    ax_tab.text(0.0, 0.20, "Below (not shown here -- own exhibits, Fig. 9.2/9.3): Exhibit 3 Allowance bridge "
                            "(WaterfallChart, t=59→t=60 default) and Exhibit 4 Credit cycle (PIT vs TTC).",
                fontsize=6.6, color=COLORS["gray"], transform=ax_tab.transAxes, style="italic")
    ax_tab.text(0.0, 0.02,
                "Every tile/panel heading also carries a ✦ AI-explain icon (not drawn on every tile above "
                "for clarity -- see §9.9).",
                fontsize=6.3, color=COLORS["gray"], transform=ax_tab.transAxes, style="italic")

    save(fig, "01_executive_tab_layout.png")


# --------------------------------------------------------------------------
# Fig 2 -- Waterfall chart (Allowance bridge), live t=59->60
# --------------------------------------------------------------------------

def fig_waterfall():
    d = load("api_ecl_waterfall_t0_59_t1_60.json")
    comps = d["components"]
    opening = comps[0]["amount"] / 1e6
    closing = comps[-1]["amount"] / 1e6
    steps = comps[1:-1]

    labels = ["Opening\nallowance"] + [c["component"].replace("_", "\n") for c in steps] + ["Closing\nallowance"]
    running = [opening]
    for c in steps:
        running.append(running[-1] + c["amount"] / 1e6)
    running.append(closing)

    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    x = range(len(labels))
    bottoms = [0.0] * len(labels)
    heights = [0.0] * len(labels)
    colors = [COLORS["accent"]]
    for c in steps:
        colors.append(COLORS["good"] if c["amount"] >= 0 else COLORS["warn"])
    colors.append(COLORS["accent"])

    prev = opening
    heights[0] = opening
    for i, c in enumerate(steps, start=1):
        val = c["amount"] / 1e6
        if val >= 0:
            bottoms[i] = prev
            heights[i] = val
        else:
            bottoms[i] = prev + val
            heights[i] = -val
        prev = prev + val
    heights[-1] = closing

    bars = ax.bar(x, heights, bottom=bottoms, color=colors, edgecolor="white", width=0.62)
    for i, (b, h, bt) in enumerate(zip(bars, heights, bottoms)):
        label_val = running[i] if i in (0, len(labels) - 1) else steps[i - 1]["amount"] / 1e6
        txt = f"${running[i]:,.1f}m" if i in (0, len(labels) - 1) else f"{'+' if label_val>=0 else ''}{label_val:,.1f}m"
        ax.text(b.get_x() + b.get_width() / 2, bt + h + 0.35, txt, ha="center", fontsize=8)

    # connector lines
    for i in range(len(labels) - 1):
        y = running[i] if i == 0 else running[i]
        ax.plot([i + 0.31, i + 1 - 0.31], [y, y], color="0.6", lw=0.8, ls="--")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=7.8)
    ax.set_ylabel("Allowance ($m)")
    ax.set_title(f"Exhibit 9.2 -- Allowance bridge, t=59 ({d['period_t0']}) → t=60 ({d['period_t1']})\n"
                 f"({MOCK_NOTE})", fontsize=9.3)
    legend_handles = [mpatches.Patch(color=COLORS["accent"], label="Running total"),
                      mpatches.Patch(color=COLORS["good"], label="Adds to allowance"),
                      mpatches.Patch(color=COLORS["warn"], label="Reduces allowance")]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=7.5, frameon=False)
    ax.margins(y=0.18)
    save(fig, "02_waterfall_chart.png")


# --------------------------------------------------------------------------
# Fig 3 -- Credit cycle chart (PIT vs TTC vs observed)
# --------------------------------------------------------------------------

def fig_credit_cycle():
    d = load("api_exhibits_credit_cycle.json")
    pts = d["points"]
    cal = [p["calendar"] for p in pts]
    obs = [p["observed_dr"] * 100 for p in pts]
    ttc = [p["ttc_pd"] * 100 for p in pts]
    pit = [p["pit_pd"] * 100 for p in pts]

    fig, ax = plt.subplots(figsize=(8.6, 3.6))
    idx = range(len(cal))
    ax.plot(idx, obs, color=COLORS["orange"], lw=1.1, label="Observed default rate", alpha=0.85)
    ax.plot(idx, ttc, color=COLORS["gray"], lw=1.6, ls="--", label="TTC PD")
    ax.plot(idx, pit, color=COLORS["accent"], lw=1.8, label="PIT PD")
    tick_idx = list(range(0, len(cal), 8))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([cal[i] for i in tick_idx], rotation=30, fontsize=7.5, ha="right")
    ax.set_ylabel("Quarterly PD (%)")
    ax.set_title(f"Exhibit 9.3 -- Credit cycle, PIT vs TTC (ρ = {d['rho']:.4f})\n({MOCK_NOTE})", fontsize=9.3)
    ax.legend(loc="upper right", fontsize=8, frameon=False)
    save(fig, "03_credit_cycle_chart.png")


# --------------------------------------------------------------------------
# Fig 4 -- The Model tab: hazard-ratio coefficient table mockup
# --------------------------------------------------------------------------

def fig_model_coefficients():
    d = load("api_model_coefficients.json")
    rows = d["models"]["default"]["coefficients"]
    fig, ax = plt.subplots(figsize=(9.0, 5.4))
    ax.axis("off")
    ax.set_title(f"Exhibit 9.4 -- The Model tab, hazard-ratio coefficients (default hazard, "
                 f"n={d['models']['default']['n_fit']:,})\n({MOCK_NOTE})", fontsize=9.3, pad=14)

    col_labels = ["▸", "Variable", "Hazard ratio", "Per-unit HR", "95% CI", "p"]
    cell_text = []
    cell_colors = []
    for r in rows:
        hr = r["hazard_ratio"]
        per_unit = r.get("hazard_ratio_per_unit")
        varname = r["variable"]
        if len(varname) > 32:
            varname = varname[:29] + "..."
        cell_text.append([
            "▸", varname, f"{hr:.4f}",
            f"{per_unit:.4f}" if per_unit is not None else "—",
            f"[{r['ci'][0]:.3f}, {r['ci'][1]:.3f}]", r["p_display"],
        ])
        cell_colors.append(["white", "white", "#eaf7f1" if hr > 1 else "#fdecea", "white", "white", "white"])

    tbl = ax.table(cellText=cell_text, colLabels=col_labels, cellLoc="left", loc="center",
                    cellColours=cell_colors, colWidths=[0.03, 0.34, 0.14, 0.13, 0.18, 0.14])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.6)
    tbl.scale(1, 1.35)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("0.85")
        if r == 0:
            cell.set_facecolor("#e8eef7")
            cell.set_text_props(fontweight="bold")
    ax.text(0.0, -0.06, "Green cell = hazard-increasing (HR>1); red = hazard-reducing (HR<1). Click ▸ "
                        "expands: unit meaning, transformation, economic channel, worked example (Requirement 12).",
            transform=ax.transAxes, fontsize=7.3, color=COLORS["gray"])
    save(fig, "04_model_coefficients_table.png")


# --------------------------------------------------------------------------
# Fig 5 -- Scenario Lab tab layout mockup
# --------------------------------------------------------------------------

def fig_scenario_lab_layout():
    shock = load("shock_uer2.json")
    fig = plt.figure(figsize=(9.2, 5.6))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.4], wspace=0.35)
    fig.suptitle(f"Scenario Lab -- tab layout mockup  ({MOCK_NOTE})", fontsize=10.3, y=0.99)

    ax_ctrl = fig.add_subplot(gs[0, 0])
    ax_ctrl.axis("off")
    controls = [
        ("Reweight scenarios", "reweight_scenarios", "3 sliders (up/base/down), normalised to sum=1"),
        ("Macro shock", "shock_macro", "var select (UER/HPI/GDP) + shape select + shock-size slider"),
        ("Rerun by segment", "rerun_ecl", "segment select: all/stage1/stage2/stage3/investor/high_ltv"),
        ("Decompose waterfall", "decompose_waterfall", "t0, t1 number inputs (1..60)"),
    ]
    y = 0.97
    for title, tool, desc in controls:
        box = FancyBboxPatch((0.0, y - 0.20), 1.0, 0.19, boxstyle="round,pad=0.015,rounding_size=0.02",
                              fc="#f7f5ee", ec="0.75", lw=0.8, transform=ax_ctrl.transAxes)
        ax_ctrl.add_patch(box)
        ax_ctrl.text(0.04, y - 0.045, title, fontsize=8.4, fontweight="bold", transform=ax_ctrl.transAxes)
        ax_ctrl.text(0.04, y - 0.10, tool + "(...)", fontsize=7.2, color=COLORS["accent"], family="monospace",
                     transform=ax_ctrl.transAxes)
        ax_ctrl.text(0.04, y - 0.16, desc, fontsize=6.6, color=COLORS["gray"], transform=ax_ctrl.transAxes, wrap=True)
        y -= 0.25
    ax_ctrl.text(0.0, 0.0, "✦ = every control panel also carries the AI-explain icon", fontsize=6.6,
                 color=COLORS["gray"], transform=ax_ctrl.transAxes)

    ax_res = fig.add_subplot(gs[0, 1])
    ax_res.axis("off")
    ax_res.text(0.0, 1.0, "Exhibit 9.5a -- Result & interpretation (after Run shock, UER +2.0pp)",
                fontsize=8.2, fontweight="bold", transform=ax_res.transAxes)
    box = FancyBboxPatch((0.0, 0.55), 1.0, 0.38, boxstyle="round,pad=0.015,rounding_size=0.02",
                          fc="#f7f5ee", ec="0.75", lw=0.8, transform=ax_res.transAxes)
    ax_res.add_patch(box)
    ax_res.text(0.03, 0.86, "shock_macro   Result card", fontsize=7.6, transform=ax_res.transAxes, color=COLORS["accent"])
    ax_res.text(0.03, 0.78, shock["headline"], fontsize=6.7, transform=ax_res.transAxes, wrap=True)
    ax_res.text(0.03, 0.68, f"${shock['shocked_allowance']/1e6:,.1f}m allowance   "
                            f"{shock['coverage']*100:.2f}% coverage   "
                            f"+{shock['delta_pct']:.1f}% vs baseline",
                fontsize=7.0, fontweight="bold", transform=ax_res.transAxes)
    ax_res.text(0.03, 0.60, "Auto-interpretation (POST /api/agent/interpret) — AI interpretation badge or "
                            "Engine summary fallback", fontsize=6.4, color=COLORS["gray"], transform=ax_res.transAxes, style="italic")

    # mini waterfall echo
    wf = shock["waterfall_vs_baseline"]
    running = [wf[0]["amount"] / 1e6]
    for c in wf[1:-1]:
        running.append(running[-1] + c["amount"] / 1e6)
    running.append(wf[-1]["amount"] / 1e6)
    ax_wf = fig.add_axes([0.56, 0.10, 0.40, 0.38])
    labels = [c["component"].replace("_", "\n") for c in wf]
    heights = [wf[0]["amount"] / 1e6] + [c["amount"] / 1e6 for c in wf[1:-1]] + [wf[-1]["amount"] / 1e6]
    bottoms = [0]
    prev = wf[0]["amount"] / 1e6
    for c in wf[1:-1]:
        v = c["amount"] / 1e6
        bottoms.append(prev if v >= 0 else prev + v)
        prev += v
    bottoms.append(0)
    heights_abs = [abs(h) if i not in (0, len(heights) - 1) else h for i, h in enumerate(heights)]
    colors = [COLORS["accent"]] + [COLORS["good"] if c["amount"] >= 0 else COLORS["warn"] for c in wf[1:-1]] + [COLORS["accent"]]
    ax_wf.bar(range(len(labels)), heights_abs, bottom=bottoms, color=colors, width=0.6, edgecolor="white")
    ax_wf.set_xticks(range(len(labels)))
    short_labels = ["opening", "stage\nmigr.", "remeas.", "derecog.", "new\nloans", "closing"]
    ax_wf.set_xticklabels(short_labels, fontsize=6.0)
    ax_wf.set_title("Exhibit 9.5b -- Allowance bridge (shock_macro mode)", fontsize=7.6)
    ax_wf.tick_params(axis="y", labelsize=6.5)

    save(fig, "05_scenario_lab_layout.png")


# --------------------------------------------------------------------------
# Fig 6 -- Policy tab: staging sensitivity + scenario-weight sensitivity
# --------------------------------------------------------------------------

def fig_policy_panels():
    staging = load("api_policy_staging_sensitivity.json")
    weights = load("api_policy_weights_table.json")

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9))
    fig.suptitle(f"Policy tab -- Exhibit 9.6a/9.6b  ({MOCK_NOTE})", fontsize=9.6, y=1.03)

    ax = axes[0]
    thresholds = staging["thresholds"]
    x = range(len(thresholds))
    t20 = [staging["rows"][0]["stage2_share_pct"][t] for t in thresholds]
    t40 = [staging["rows"][1]["stage2_share_pct"][t] for t in thresholds]
    w = 0.35
    ax.bar([i - w / 2 for i in x], t20, width=w, color=COLORS["good"], label="t=20 (2005Q1, calm)")
    ax.bar([i + w / 2 for i in x], t40, width=w, color=COLORS["warn"], label="t=40 (2010Q1, stress)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(thresholds)
    ax.set_ylabel("Stage-2 share of allowance (%)")
    ax.set_title("9.6a -- Stage-2 share vs SICR threshold", fontsize=8.6)
    ax.legend(fontsize=7, frameon=False)
    ax.axvline(1, color=COLORS["accent"], ls=":", lw=1)
    ax.text(1.05, 5, "2.0x adopted", fontsize=6.5, color=COLORS["accent"])

    ax2 = axes[1]
    ws = weights["weight_sets"]
    labels = [w["label"].split(" (")[0] for w in ws]
    vals = [w["weighted_allowance"] / 1e6 for w in ws]
    colors = [COLORS["accent"] if w["id"] == "adopted" else "0.65" for w in ws]
    bars = ax2.bar(labels, vals, color=colors, width=0.55)
    for b, v in zip(bars, vals):
        ax2.text(b.get_x() + b.get_width() / 2, v + 0.5, f"${v:,.1f}m", ha="center", fontsize=7.3)
    ax2.set_ylabel("Weighted allowance ($m)")
    ax2.set_title("9.6b -- Scenario-weight sensitivity", fontsize=8.6)
    ax2.tick_params(axis="x", labelsize=7, rotation=8)
    fig.tight_layout()
    save(fig, "06_policy_panels.png")


# --------------------------------------------------------------------------
# Fig 7 -- Freddie backtest honesty panel (the 9.42x centrepiece)
# --------------------------------------------------------------------------

def fig_freddie_backtest():
    d = load("api_freddie_backtest.json")
    rows = d["rows"]
    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    x = range(len(rows))
    frozen = [r["miss_ratio_frozen"] for r in rows]
    actual = [r["miss_ratio_actual"] for r in rows]
    w = 0.35
    b1 = ax.bar([i - w / 2 for i in x], frozen, width=w, color=COLORS["warn"], label="Miss ratio (frozen macro)")
    b2 = ax.bar([i + w / 2 for i in x], actual, width=w, color=COLORS["accent"], label="Miss ratio (hindsight macro)")
    for i, r in enumerate(rows):
        ax.text(i - w / 2, r["miss_ratio_frozen"] + 0.15, f"{r['miss_ratio_frozen']:.2f}x", ha="center", fontsize=7)
        ax.text(i + w / 2, r["miss_ratio_actual"] + 0.15, f"{r['miss_ratio_actual']:.2f}x", ha="center", fontsize=7)
    ax.axhline(1.0, color="0.5", lw=0.8, ls="--")
    ax.set_xticks(list(x))
    ax.set_xticklabels([r["asof"] for r in rows])
    ax.set_ylabel("Miss ratio (realized / predicted)")
    ax.set_title(f"Exhibit 9.7 -- Real Data tab, backtest honesty panel\n"
                 f"2007-12: {rows[0]['miss_ratio_frozen']:.2f}x underprediction of the GFC ({MOCK_NOTE})",
                 fontsize=9.0)
    ax.legend(fontsize=7.5, frameon=False)
    ax.annotate("centrepiece\nfinding", xy=(0, rows[0]["miss_ratio_frozen"]), xytext=(0.6, 7.5),
                fontsize=7.5, color=COLORS["warn"],
                arrowprops=dict(arrowstyle="->", color=COLORS["warn"], lw=1))
    save(fig, "07_freddie_backtest_honesty.png")


# --------------------------------------------------------------------------
# Fig 8 -- Copilot chat dock status states (live recorded exchanges)
# --------------------------------------------------------------------------

def fig_copilot_states():
    grounded = load("ask_downside.json")
    reasoned = load("ask_reasoned.json")
    refuse = load("ask_refuse.json")

    fig, axes = plt.subplots(3, 1, figsize=(8.8, 6.6))
    fig.suptitle(f"Copilot -- chat-dock status states, live recorded exchanges  ({MOCK_NOTE})", fontsize=9.6, y=0.995)

    def nodollar(s):
        # A live LLM answer may carry "$34.0m" (real currency -> keep, reworded
        # "USD" so mathtext parsing of a bare "$" is never triggered) or
        # "$-0.006$"/"$\times$" (inline-math delimiters -> strip, plain text).
        import re
        s = re.sub(r"\$(-?[\d.,]+(?:m|bn))", r"USD \1", s)  # currency amounts only
        s = s.replace("\\times", " x ")
        s = re.sub(r"\$([^$]*)\$", r"\1", s)  # remaining $...$ math spans -> plain
        s = s.replace("$", "")
        return s

    panels = [
        ("GROUNDED", COLORS["good"], "What is the reported allowance under the downside scenario?", nodollar(grounded["answer"]), grounded["route"]),
        ("REASONED", COLORS["purple"], "Why does the double-trigger LTV x UER coefficient come out negative?",
         nodollar(reasoned["answer"].replace("[REASONED — interpretation, not engine output] ", "")), reasoned["route"]),
        ("OUT OF SCOPE", COLORS["warn"], "What is the price of Bitcoin today?",
         nodollar(refuse["answer"][:220]) + "...", refuse["route"]),
    ]
    for ax, (status, color, q, a, route) in zip(axes, panels):
        ax.axis("off")
        ax.add_patch(mpatches.Circle((0.012, 0.80), 0.012, color=color, transform=ax.transAxes, clip_on=False))
        ax.text(0.03, 0.80, status, fontsize=9.5, fontweight="bold", color=color, va="center", transform=ax.transAxes)
        ax.text(0.32, 0.80, f"route: {route}", fontsize=7.3, color=COLORS["gray"], va="center", transform=ax.transAxes)
        box = FancyBboxPatch((0.0, 0.05), 1.0, 0.62, boxstyle="round,pad=0.01,rounding_size=0.02",
                              fc="#f7f5ee", ec="0.8", lw=0.7, transform=ax.transAxes)
        ax.add_patch(box)
        ax.text(0.03, 0.56, "User: " + nodollar(q), fontsize=7.4, style="italic", transform=ax.transAxes, wrap=True)
        wrapped = a if len(a) < 260 else a[:257] + "..."
        ax.text(0.03, 0.15, "Copilot: " + wrapped, fontsize=6.9, transform=ax.transAxes, wrap=True)
    save(fig, "08_copilot_chat_states.png")


# --------------------------------------------------------------------------
# Fig 9 -- Tab -> endpoint wiring flowchart
# --------------------------------------------------------------------------

def box(ax, xy, w, h, text, fc="#f7f5ee", ec="0.5", fs=7.2, weight="normal"):
    b = FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.01,rounding_size=0.01", fc=fc, ec=ec, lw=0.9)
    ax.add_patch(b)
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=fs, weight=weight, wrap=True)
    return (xy[0] + w / 2, xy[1] + h / 2)


def arrow(ax, p0, p1, color="0.4"):
    a = FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8, color=color, lw=0.8, shrinkA=6, shrinkB=6)
    ax.add_patch(a)


def fig_endpoint_wiring():
    fig, ax = plt.subplots(figsize=(9.6, 8.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 15.5)
    ax.axis("off")
    ax.set_title(f"Exhibit 9.9 -- Tab → endpoint wiring (6 tabs, 22 endpoints + 3 static mounts)\n"
                 "(structural diagram from app/ui/src/app.jsx TABS + the tabs' own api.js calls, "
                 "cross-checked against docs/api_contract.md's summary table)", fontsize=9.2)

    tabs = [
        ("Executive\nOverview", 13.7), ("The Model", 11.6), ("Scenario\nLab", 9.5),
        ("Policy", 7.4), ("Real Data", 5.3), ("Copilot", 3.2),
    ]
    tab_pos = {}
    for name, y in tabs:
        tab_pos[name] = box(ax, (0.1, y), 1.7, 1.1, name, fc="#e8eef7", weight="bold", fs=7.6)

    endpoints = [
        ("GET /api/ecl/summary", 14.7, "Executive\nOverview"),
        ("GET /api/ecl/waterfall", 14.2, "Executive\nOverview"),
        ("GET /api/exhibits/credit_cycle", 13.7, "Executive\nOverview"),
        ("GET /api/model/coefficients", 12.6, "The Model"),
        ("GET /api/model/variable_dictionary", 12.15, "The Model"),
        ("GET /api/model/macro_glossary", 11.7, "The Model"),
        ("GET /api/model/lgd", 11.25, "The Model"),
        ("GET /api/exhibits/list", 10.8, "The Model"),
        ("POST /api/tools/shock_macro", 10.2, "Scenario\nLab"),
        ("POST /api/tools/reweight_scenarios", 9.75, "Scenario\nLab"),
        ("POST /api/tools/rerun_ecl", 9.3, "Scenario\nLab"),
        ("POST /api/tools/decompose_waterfall", 8.85, "Scenario\nLab"),
        ("POST /api/agent/interpret", 8.4, "Scenario\nLab"),
        ("GET /api/policy/staging_sensitivity", 7.7, "Policy"),
        ("GET /api/policy/weights_table", 7.25, "Policy"),
        ("GET /api/freddie/summary", 6.0, "Real Data"),
        ("GET /api/freddie/hazard", 5.55, "Real Data"),
        ("GET /api/freddie/backtest", 5.1, "Real Data"),
        ("GET /api/freddie/exhibits", 4.65, "Real Data"),
        ("POST /api/agent/ask", 3.5, "Copilot"),
        ("GET /api/agent/stream", 3.0, "Copilot"),
    ]
    for label, y, tab in endpoints:
        p = box(ax, (2.4, y - 0.2), 4.3, 0.38, label, fc="white", fs=6.3)
        arrow(ax, (tab_pos[tab][0] + 0.85, tab_pos[tab][1]), (2.4, y))

    shared = [
        ("GET /api/health\n(app.jsx boot)", 14.9),
        ("MiniChatDock/ChatPanel/\nSelectionExplain → POST /api/agent/ask\n(all 5 non-Copilot tabs)", 2.2),
    ]
    for label, y in shared:
        box(ax, (7.2, y - 0.35), 2.5, 0.75, label, fc="#fdf1e3", fs=6.2)

    box(ax, (7.2, 12.9), 2.5, 1.0, "/static/exhibits/*\n/static/freddie/*\n/static/mdd/*\n(read-only mounts)",
        fc="#ecf7ee", fs=6.4)

    save(fig, "09_endpoint_wiring_flowchart.png")


# --------------------------------------------------------------------------
# Fig 10 -- Docker multi-stage build + static-mount linkage
# --------------------------------------------------------------------------

def fig_docker_linkage():
    fig, ax = plt.subplots(figsize=(9.4, 4.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Exhibit 9.10 -- Docker build stages → static assets this chapter's panels consume\n"
                 "(Dockerfile, both stages; app/api/main.py static mounts)", fontsize=9.4)

    s1 = box(ax, (0.3, 3.6), 2.6, 1.7, "Stage 1: node:22-alpine\nnpm ci && npm run build\n"
                                        "app/ui/src → app/ui/dist", fc="#e8eef7", fs=7.2, weight="bold")
    s2 = box(ax, (4.2, 3.6), 2.6, 1.7, "Stage 2: python:3.13-slim\nCOPY allowlist: engine/ agent/\napp/api/ "
                                        "analysis/ wiki/ knowledge/\ndata/ outputs/{models,hazard,lgd,\n"
                                        "staging,eda,vasicek,scenario_ecl,\nchallenger,freddie,mdd}",
             fc="#e8eef7", fs=6.6, weight="bold")
    arrow(ax, (s1[0] + 1.3, s1[1] - 0.85), (s2[0] - 1.3, s2[1] - 0.85))
    ax.text(2.9, 3.1, "COPY --from=ui\n/build/dist", fontsize=6.3, ha="center", color=COLORS["gray"])

    n1 = box(ax, (0.3, 0.4), 2.5, 1.4, "app/ui/dist\n→ mounted at /\n(SPA, last-registered route)", fc="#ecf7ee", fs=6.8)
    n2 = box(ax, (3.1, 0.4), 2.5, 1.4, "outputs/**\n→ /static/exhibits/*\n(whole-outputs mount)", fc="#ecf7ee", fs=6.8)
    n3 = box(ax, (5.9, 0.4), 2.5, 1.4, "outputs/freddie/**\n→ /static/freddie/*\n(guarded 2nd mount)", fc="#ecf7ee", fs=6.8)
    n4 = box(ax, (8.7, 0.4), 2.5, 1.4, "outputs/mdd/**\n→ /static/mdd/*\n(MDD.html header link)", fc="#ecf7ee", fs=6.8)
    for n in (n1, n2, n3, n4):
        arrow(ax, (n[0], 2.0), (n[0], 1.7))
    arrow(ax, (s2[0], s2[1] - 0.85), (n2[0], 1.9))
    ax.text(7.2, 5.0, "non-root appuser (uid 1000); EXPOSE 7860; CMD uvicorn app.api.main:app --workers 1\n"
                      "(full stage-by-stage Dockerfile read: Chapter 10)", fontsize=6.8, color=COLORS["gray"])
    save(fig, "10_docker_deployment_linkage.png")


# --------------------------------------------------------------------------
# Fig 11 -- Design-direction comparison (FINAL_SPEC.md scoring table)
# --------------------------------------------------------------------------

def fig_design_comparison():
    criteria = ["North-star\nfit", "Information\nhierarchy", "Data-ink\ndiscipline", "Dark+light\nparity",
                "Implement-\nability"]
    editorial = [8, 9, 8, 7, 5]
    fintech = [9, 8, 7, 9, 9]
    terminal = [7, 7, 8, 8, 9]

    fig, ax = plt.subplots(figsize=(8.8, 3.9))
    x = range(len(criteria))
    w = 0.26
    ax.bar([i - w for i in x], editorial, width=w, color=COLORS["purple"], label="editorial")
    ax.bar([i for i in x], fintech, width=w, color=COLORS["accent"], label="fintech (WINNER)")
    ax.bar([i + w for i in x], terminal, width=w, color=COLORS["gray"], label="terminal")
    ax.set_xticks(list(x))
    ax.set_xticklabels(criteria, fontsize=7.4)
    ax.set_ylabel("Score (1-10)")
    ax.set_ylim(0, 10.5)
    ax.set_title("Exhibit 9.11 -- Three design directions, judge scoring\n"
                 "(outputs/design/FINAL_SPEC.md §0; totals 37 / 42 / 39 -- fintech wins with 5 grafts adopted "
                 "from the other two)", fontsize=8.8)
    ax.legend(fontsize=7.5, frameon=False, loc="lower right")
    save(fig, "11_design_direction_comparison.png")


if __name__ == "__main__":
    fig_executive_layout()
    fig_waterfall()
    fig_credit_cycle()
    fig_model_coefficients()
    fig_scenario_lab_layout()
    fig_policy_panels()
    fig_freddie_backtest()
    fig_copilot_states()
    fig_endpoint_wiring()
    fig_docker_linkage()
    fig_design_comparison()
    print("all figures written")
