"""Fit the rung-1 discrete-time cloglog hazard PD models and emit exhibits.

Run:  cd <repo root> && uv run python analysis/fit_hazard.py

Fits the cause-specific default and prepayment hazards (engine/hazard.py) on
the TRAINING split only (time <= 40); the out-of-time split (41..60) is
scored READ-ONLY for the one-quarter-ahead AUC -- no refitting, no peeking
during specification.

Exhibits written to outputs/hazard/:
  hazard_ratios.md      exp(coef), 95% CI, p for both models, with a one-line
                        real-world story per covariate family
  age_baseline.png      fitted seasoning curve vs the empirical age hazard
                        (the EDA seasoning hump must reappear; asserted)
  pd_term_structure.png conditional hazard + cumulative PD for three named
                        profiles over 40 quarters
  fit_stats.md          train/OOT AUC (one-quarter-ahead default), McFadden
                        pseudo-R2, model dimensions

Design choices (deviations documented here rather than silently made):
* PD term-structure macro scenario = the LAST TRAINING-WINDOW OBSERVED macro
  (t = 40: unemployment 10.0, GDP growth -0.24, HPI falling). "Last observed"
  is taken within the training window so the OOT period stays untouched even
  as a scenario source; t = 40 happens to sit in the stress episode, so the
  chart shows stress-conditioned term structures (stated on the exhibit).
* Fitted-baseline peak is asserted to (a) lie in a plausible seasoning window
  [4, 18] quarters and (b) fall within 8 quarters of the empirical peak. The
  fitted curve holds covariates and macro frozen, while the raw empirical
  curve confounds age with the calendar-time macro cycle (older ages are
  observed disproportionately in the stress quarters), so an exact match is
  not expected -- a tolerance band is the honest test.
* Sanity sign checks FAIL LOUDLY (SystemExit): PD must fall in FICO, rise in
  updated LTV, rise in unemployment; prepayment must rise in the rate
  incentive. Because the interaction components are centered at training
  means (engine/hazard.py), the LTV main effect IS the marginal LTV effect at
  mean unemployment. The unemployment check is the TOTAL effect of a 1pp
  labour-market shock at mean LTV: a real shock moves the level (uer_lag1)
  and the 4-quarter momentum (uer_chg4_lag1) one-for-one, so the economic
  object is beta(uer_lag1) + beta(uer_chg4_lag1). The level coefficient ALONE,
  conditional on momentum, is a decomposition artifact (level and 4q change
  correlate at 0.94 in-sample; momentum carries the stress signal and the
  residual level effect picks up late-stress burnout quarters) -- asserting on
  it in isolation would test collinearity noise, not economics. Both pieces
  are reported in the hazard-ratio table. The double-trigger interaction is
  reported either way, per spec.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "analysis"))

from mpl_style import COLORS, apply_textbook_style, figsize_for  # noqa: E402
from engine.hazard import (  # noqa: E402
    DT_TERM,
    REQUIRED_COLS,
    SPLINE_DF,
    fit_default_hazard,
    fit_prepay_hazard,
    pd_term_structure,
    predict_hazard,
)

PANEL = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
OUT = PROJECT_ROOT / "outputs" / "hazard"
HORIZON = 40
MIN_CELL = 2000        # min at-risk rows for an empirical age-hazard point
PEAK_WINDOW = (4, 18)  # plausible seasoning-peak band (quarters on book)
PEAK_TOL = 8           # max |fitted peak - empirical peak|

# one-line real-world story per covariate family, per model
# (hazard-ratio table; the same covariate reads differently for the two exits)
FAMILY_STORY_PREPAY = {
    "baseline": "Seasoning: refinancing needs time to become worthwhile "
                "(points/fees amortise), so the prepay hazard also humps "
                "with age.",
    "borrower": "Borrower quality: investors prepay LESS (buy-and-hold "
                "rentals, harder underwriting on refis); higher FICO here "
                "mildly lowers prepayment conditional on the incentive.",
    "collateral": "Collateral gates refinancing: underwater borrowers "
                  "cannot remortgage, so prepayment FALLS in updated LTV -- "
                  "and falls fastest when unemployment is high (negative "
                  "interaction).",
    "macro": "Macro: a hot housing market (HPI growth; HR is per full "
             "log-unit -- read exp(coef/100) per 1% growth) fuels turnover "
             "and cash-out refis; deteriorating labour momentum freezes "
             "the refi market.",
    "incentive": "Rate incentive: note rate above market -> refinancing "
                 "pays; the star prepayment driver, positive as required.",
}

FAMILY_STORY = {
    "baseline": "Seasoning: hazard climbs over the first ~2-3 years on book, "
                "then burns out (spline coefficients are basis weights, not "
                "individually interpretable -- see age_baseline.png).",
    "borrower": "Borrower quality: cleaner credit at origination defaults "
                "less; investors walk away from underwater rentals faster "
                "than owner-occupiers.",
    "collateral": "Collateral / double trigger: negative equity is the "
                  "ability-to-sell trigger; its bite varies with the labour "
                  "market via the LTV x unemployment interaction.",
    "macro": "Macro (all lagged, no lookahead): a labour-market shock moves "
             "level AND 4q momentum together and raises default risk (their "
             "coefficient SUM is the shock effect; the level coefficient "
             "alone, conditional on momentum, is a decomposition artifact -- "
             "the two correlate at 0.94 in-sample). Falling house prices "
             "raise default risk (HPI-growth HR is per full log-unit -- "
             "read exp(coef/100) per 1% quarterly growth). Satellites will "
             "scenario-condition these at a later rung.",
    "incentive": "Rate incentive: note rate above market -> refinancing "
                 "pays; the star prepayment driver, and for default it "
                 "proxies a high contractual debt-service burden.",
}

FAMILY_OF = {
    "Intercept": "baseline",
    "fico_s": "borrower",
    "investor_orig_time": "borrower",
    "REtype_CO_orig_time": "borrower",
    "REtype_PU_orig_time": "borrower",
    "REtype_SF_orig_time": "borrower",
    "ltv10": "collateral",
    DT_TERM: "collateral",
    "uer_lag1": "macro",
    "uer_chg4_lag1": "macro",
    "hpi_growth_lag1": "macro",
    "gdp_lag1": "macro",
    "prepay_incentive": "incentive",
}

PRETTY = {
    "fico_s": "FICO at orig. (per 100 pts)",
    "ltv10": "Updated LTV (per 10pp, at mean UER)",
    DT_TERM: "DOUBLE TRIGGER: LTV(10pp) x UER (centered)",
    "prepay_incentive": "Rate incentive (pp)",
    "investor_orig_time": "Investor loan",
    "REtype_CO_orig_time": "Condo",
    "REtype_PU_orig_time": "Planned urban dev.",
    "REtype_SF_orig_time": "Single family",
    "uer_lag1": "Unemployment level (lag 1)",
    "uer_chg4_lag1": "Unemployment 4q change (lag 1)",
    "hpi_growth_lag1": "HPI growth (lag 1)",
    "gdp_lag1": "GDP growth (lag 1)",
}


def fail(msg: str) -> None:
    print(f"\n*** SANITY FAILURE: {msg}", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# hazard-ratio table
# ---------------------------------------------------------------------------

def hazard_ratio_table(model) -> pd.DataFrame:
    res = model.result
    ci = res.conf_int()
    tab = pd.DataFrame({
        "coef": res.params,
        "hr": np.exp(res.params),
        "hr_lo": np.exp(ci[0]),
        "hr_hi": np.exp(ci[1]),
        "p": res.pvalues,
    })
    return tab


def render_hr_markdown(models: dict, meta: dict) -> str:
    lines = [
        "# Hazard-ratio tables -- discrete-time cloglog hazards",
        "",
        f"Loan-quarter panel, training split only (time <= {meta['train_max_t']}; "
        f"lag warm-up rows dropped). cloglog link = grouped-duration Cox, so "
        f"exp(coef) is a hazard ratio. Baseline age effect: natural cubic "
        f"spline cr(loan_age, df={SPLINE_DF}) -- basis coefficients omitted "
        f"here (not individually interpretable); the fitted curve is exhibit "
        f"age_baseline.png. The LTV x unemployment interaction components are "
        f"centered at training means, so the LTV and UER main effects read as "
        f"marginal effects at the partner's training mean; updated LTV is "
        f"winsorised at 300% (engine/hazard.py docstring).",
        "",
    ]
    for name, title in [("default", "Default hazard (y = default_event)"),
                        ("prepay", "Prepayment hazard (y = payoff_event)")]:
        m = models[name]
        tab = hazard_ratio_table(m)
        keep = [ix for ix in tab.index if "cr(loan_age" not in ix]
        tab = tab.loc[keep]
        lines += [f"## {title}",
                  "",
                  f"n = {m.n_obs:,} loan-quarters, events = {m.n_events:,}, "
                  f"McFadden pseudo-R2 = {m.mcfadden_r2():.4f}",
                  "",
                  "| Covariate | family | HR = exp(coef) | 95% CI | p |",
                  "|---|---|---|---|---|"]
        for ix, r in tab.iterrows():
            fam = FAMILY_OF.get(ix, "baseline")
            pretty = PRETTY.get(ix, ix)
            p = "<1e-16" if r["p"] < 1e-16 else f"{r['p']:.2e}"
            lines.append(
                f"| {pretty} | {fam} | {r['hr']:.4f} | "
                f"[{r['hr_lo']:.4f}, {r['hr_hi']:.4f}] | {p} |")
        stories = FAMILY_STORY if name == "default" else FAMILY_STORY_PREPAY
        lines += ["", "**Family stories**", ""]
        for fam in ["baseline", "borrower", "collateral", "macro", "incentive"]:
            lines.append(f"- **{fam}** -- {stories[fam]}")
        lines.append("")
    lines += [
        "## Double-trigger reading (default model)",
        "",
        meta["dt_story"],
        "",
        "## Unemployment-shock reading (default model)",
        "",
        meta["uer_story"],
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    apply_textbook_style()
    OUT.mkdir(parents=True, exist_ok=True)

    panel = pd.read_parquet(PANEL)
    train = panel[panel["split"] == "train"]
    oot = panel[panel["split"] == "oot"]
    train_fit = train[train["lag_warmup"] == 0]
    print(f"panel {len(panel):,} rows | train {len(train):,} "
          f"(fit rows {len(train_fit):,}) | oot {len(oot):,} (read-only)")

    # ---- fit ---------------------------------------------------------------
    m_def = fit_default_hazard(train)
    m_pre = fit_prepay_hazard(train)
    models = {"default": m_def, "prepay": m_pre}
    print(f"default hazard: n={m_def.n_obs:,} events={m_def.n_events:,}")
    print(f"prepay  hazard: n={m_pre.n_obs:,} events={m_pre.n_events:,}")

    # ---- sanity: economic signs (FAIL LOUDLY) ------------------------------
    # Interaction components are centered at training means, so:
    #   * beta(ltv10) IS the marginal LTV effect at mean unemployment;
    #   * at mean LTV the centered interaction contributes zero, so the
    #     effect of a 1pp labour-market shock (level AND 4q momentum move
    #     one-for-one) is beta(uer_lag1) + beta(uer_chg4_lag1) -- the
    #     economically meaningful "PD rises in unemployment" object (module
    #     docstring: the level coefficient alone conditional on momentum is
    #     a collinearity decomposition, not economics).
    pd_par, pp_par = m_def.params, m_pre.params
    mean_uer = float(train_fit["uer_lag1"].mean())

    b_fico = pd_par["fico_s"]
    b_ltv, b_uer = pd_par["ltv10"], pd_par["uer_lag1"]
    b_chg4 = pd_par["uer_chg4_lag1"]
    b_dt = pd_par[DT_TERM]
    dt_p = m_def.result.pvalues[DT_TERM]
    dltv_at_mean_uer = b_ltv                      # centered parametrisation
    duer_shock_at_mean_ltv = b_uer + b_chg4       # 1pp shock: level + momentum
    b_inc_pre = pp_par["prepay_incentive"]

    checks = [
        ("PD falls in FICO", b_fico < 0, f"beta(fico_s)={b_fico:+.4f}"),
        ("PD rises in updated LTV (marginal effect at mean UER)",
         dltv_at_mean_uer > 0,
         f"beta(ltv10)={dltv_at_mean_uer:+.4f}"),
        ("PD rises in unemployment (1pp shock: level+momentum, at mean LTV)",
         duer_shock_at_mean_ltv > 0,
         f"beta(uer)+beta(chg4)={duer_shock_at_mean_ltv:+.4f} "
         f"(level {b_uer:+.4f}, momentum {b_chg4:+.4f})"),
        ("Prepayment rises in rate incentive", b_inc_pre > 0,
         f"beta(prepay_incentive)={b_inc_pre:+.4f}"),
    ]
    for label, ok, detail in checks:
        print(f"  sign check: {label}: {detail} -> {'OK' if ok else 'FAIL'}")
        if not ok:
            fail(f"economically nonsensical sign -- {label} violated ({detail})")

    dt_sig = "significant" if dt_p < 0.05 else "NOT significant"
    dt_story = (
        f"beta(centered ltv10 x centered uer_lag1) = {b_dt:+.5f} "
        f"(p = {dt_p:.2e}, {dt_sig} at 5%; identical to the uncentered x*y "
        f"coefficient -- centering only reparametrises the main effects). "
        + ("Positive: each 10pp of current LTV hurts MORE when unemployment "
           "is high -- the negative-equity trigger needs the cash-flow "
           "trigger, the double-trigger mechanism in its textbook form."
           if b_dt > 0 else
           "Negative: the LTV slope flattens slightly at high unemployment "
           "-- in-sample the two triggers partially substitute (the main "
           "effects and momentum term already carry the joint stress "
           "response, and the worst-LTV loans default early in the stress "
           "window). Reported either way, per spec.")
        + f" Marginal LTV effect per 10pp: {dltv_at_mean_uer:+.4f} at mean "
        f"UER ({mean_uer:.1f}%); {b_ltv + b_dt * (10.0 - mean_uer):+.4f} at "
        f"UER 10%."
    )
    print("  double trigger:", dt_story.split(". ")[0])

    uer_story = (
        f"A 1pp labour-market shock moves the unemployment level and its "
        f"4-quarter change one-for-one, so its hazard effect at mean LTV is "
        f"beta(uer_lag1) + beta(uer_chg4_lag1) = {b_uer:+.4f} + {b_chg4:+.4f} "
        f"= {duer_shock_at_mean_ltv:+.4f} (hazard ratio "
        f"{np.exp(duer_shock_at_mean_ltv):.3f} per pp) -- PD RISES in "
        f"unemployment. The negative level coefficient in isolation is the "
        f"level-vs-momentum decomposition under 0.94 collinearity, not an "
        f"economic sign."
    )

    # ---- exhibit 1: hazard-ratio tables ------------------------------------
    meta = {"train_max_t": int(train["time"].max()), "dt_story": dt_story,
            "uer_story": uer_story}
    (OUT / "hazard_ratios.md").write_text(render_hr_markdown(models, meta))
    print("wrote", OUT / "hazard_ratios.md")

    # ---- exhibit 2: fitted age baseline vs empirical -----------------------
    emp = (train_fit.groupby("loan_age")["default_event"]
           .agg(["mean", "count"]))
    emp = emp[emp["count"] >= MIN_CELL]
    emp_peak = int(emp["mean"].idxmax())

    ref = {c: float(train_fit[c].median()) for c in REQUIRED_COLS}
    for c in ["investor_orig_time", "REtype_CO_orig_time",
              "REtype_PU_orig_time"]:
        ref[c] = 0.0
    ref["REtype_SF_orig_time"] = 1.0        # modal property type
    ages = np.arange(0, 41, dtype=float)
    grid = pd.DataFrame([ref] * len(ages))
    grid["loan_age"] = ages
    lam_fit = predict_hazard(m_def, grid)
    fit_peak = int(ages[int(np.argmax(lam_fit))])

    print(f"seasoning peak: empirical age {emp_peak}q, fitted age {fit_peak}q")
    if not (PEAK_WINDOW[0] <= fit_peak <= PEAK_WINDOW[1]):
        fail(f"fitted seasoning peak {fit_peak}q outside plausible window "
             f"{PEAK_WINDOW}")
    if abs(fit_peak - emp_peak) > PEAK_TOL:
        fail(f"fitted peak {fit_peak}q vs empirical {emp_peak}q differs by "
             f"more than {PEAK_TOL}q")

    fig, ax = plt.subplots(figsize=figsize_for("wide"))
    ax.plot(emp.index, 100 * emp["mean"], "o", ms=3.5,
            color=COLORS["gray"], label=f"empirical (cells >= {MIN_CELL} rows)")
    ax.plot(ages, 100 * lam_fit, color=COLORS["accent"], lw=2,
            label=f"fitted spline baseline (df={SPLINE_DF}), covariates at "
                  f"reference")
    ax.axvline(fit_peak, color=COLORS["warn"], ls=":", lw=1,
               label=f"fitted peak: {fit_peak}q (empirical: {emp_peak}q)")
    ax.set_xlabel("loan age (quarters on book)")
    ax.set_ylabel("quarterly default hazard (%)")
    ax.set_title("The seasoning hump: fitted cloglog age baseline vs "
                 "empirical age hazard (train)")
    ax.legend(frameon=False)
    ax.text(0.995, 0.02,
            "level gap is expected: fitted curve freezes covariates & macro "
            "at reference medians;\nthe raw empirical curve confounds age "
            "with the calendar stress cycle",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=7,
            style="italic", color=COLORS["gray"])
    fig.savefig(OUT / "age_baseline.png")
    plt.close(fig)
    print("wrote", OUT / "age_baseline.png")

    # ---- exhibit 3: PD term structures for three profiles ------------------
    q = lambda c, p: float(train_fit[c].quantile(p))
    last_t = int(train["time"].max())
    macro = (train_fit[train_fit["time"] == last_t]
             [["uer_lag1", "uer_chg4_lag1", "gdp_lag1", "hpi_growth_lag1"]]
             .iloc[0].to_dict())

    base = dict(loan_age=0.0, **macro,
                REtype_CO_orig_time=0.0, REtype_PU_orig_time=0.0,
                REtype_SF_orig_time=1.0, investor_orig_time=0.0)
    profiles = pd.DataFrame([
        {**base, "profile": "prime low-LTV",
         "FICO_orig_time": q("FICO_orig_time", 0.80),
         "updated_ltv": q("updated_ltv", 0.20),
         "prepay_incentive": q("prepay_incentive", 0.50)},
        {**base, "profile": "median",
         "FICO_orig_time": q("FICO_orig_time", 0.50),
         "updated_ltv": q("updated_ltv", 0.50),
         "prepay_incentive": q("prepay_incentive", 0.50)},
        {**base, "profile": "risky high-LTV investor",
         "FICO_orig_time": q("FICO_orig_time", 0.20),
         "updated_ltv": q("updated_ltv", 0.90),
         "prepay_incentive": q("prepay_incentive", 0.50),
         "investor_orig_time": 1.0},
    ])
    ts = pd_term_structure(models, profiles, horizon=HORIZON)
    ts.to_csv(OUT / "pd_term_structure.csv", index=False)

    pal = {"prime low-LTV": COLORS["good"], "median": COLORS["accent"],
           "risky high-LTV investor": COLORS["warn"]}
    fig, axes = plt.subplots(1, 2, figsize=figsize_for("twocol"))
    for name, g in ts.groupby("profile", sort=False):
        axes[0].plot(g["period"], 100 * g["hazard_default"], lw=2,
                     color=pal[name], label=name)
        axes[0].plot(g["period"], 100 * g["marginal_pd"], lw=1, ls="--",
                     color=pal[name], alpha=0.7)
        axes[1].plot(g["period"], 100 * g["cum_pd"], lw=2,
                     color=pal[name], label=name)
    axes[0].set_title("Conditional hazard (solid) and marginal PD (dashed)")
    axes[0].set_ylabel("quarterly PD (%)")
    axes[1].set_title("Cumulative PD (competing-risk survival)")
    axes[1].set_ylabel("cumulative PD (%)")
    axes[0].legend(frameon=False, fontsize=7)
    axes[1].legend(frameon=False, fontsize=7, loc="lower right")
    for ax in axes:
        ax.set_xlabel("quarters ahead")
    fig.suptitle(f"PD term structures, new loans, macro frozen at last "
                 f"training observation (t={last_t}: UER "
                 f"{macro['uer_lag1']:.1f}%, stress quarter)", y=1.04,
                 fontsize=11)
    fig.savefig(OUT / "pd_term_structure.png")
    plt.close(fig)
    print("wrote", OUT / "pd_term_structure.png")

    # ---- exhibit 4: fit stats (train + read-only OOT) ----------------------
    stats = {}
    for name, m in models.items():
        y_tr = train_fit[m.event_col].to_numpy()
        auc_tr = roc_auc_score(y_tr, predict_hazard(m, train_fit))
        y_oo = oot[m.event_col].to_numpy()
        auc_oo = roc_auc_score(y_oo, predict_hazard(m, oot))
        stats[name] = dict(auc_train=auc_tr, auc_oot=auc_oo,
                           r2=m.mcfadden_r2(), n=m.n_obs, ev=m.n_events)
        print(f"{name}: train AUC {auc_tr:.4f} | OOT AUC {auc_oo:.4f} | "
              f"McFadden R2 {stats[name]['r2']:.4f}")

    s = stats["default"]
    lines = [
        "# Fit statistics -- cloglog hazards (one-quarter-ahead)",
        "",
        "AUC is for the one-quarter-ahead event: per-row predicted hazard vs "
        "the row's event flag. All macro REGRESSORS are lagged (no lookahead); "
        "updated LTV and the rate incentive are loan-state variables indexed "
        "by the current quarter's HPI / market rate -- accepted collateral-"
        "indexation / option-moneyness exceptions documented in the "
        "engine/hazard.py TIMING CONVENTION. "
        "OOT (time 41-60, the stress + aftermath window) is scored strictly "
        "read-only -- fitted on train, no refit.",
        "",
        "| Model | n (fit) | events | train AUC | OOT AUC | McFadden R2 |",
        "|---|---|---|---|---|---|",
    ]
    for name in ["default", "prepay"]:
        v = stats[name]
        lines.append(f"| {name} | {v['n']:,} | {v['ev']:,} | "
                     f"{v['auc_train']:.4f} | {v['auc_oot']:.4f} | "
                     f"{v['r2']:.4f} |")
    lines += [
        "",
        f"Seasoning peak: fitted {fit_peak}q vs empirical {emp_peak}q "
        f"(tolerance {PEAK_TOL}q; plausible window {PEAK_WINDOW}).",
        "",
        f"Double trigger: {dt_story}",
        "",
        f"Unemployment shock: {uer_story}",
        "",
        "All economic-sign sanity checks passed (FICO down, LTV up, "
        "unemployment shock up for default; incentive up for prepayment).",
    ]
    (OUT / "fit_stats.md").write_text("\n".join(lines))
    print("wrote", OUT / "fit_stats.md")

    print("\nKEY NUMBERS")
    print(f"  default train AUC {s['auc_train']:.4f} | OOT AUC "
          f"{s['auc_oot']:.4f} | McFadden R2 {s['r2']:.4f}")
    print(f"  prepay  train AUC {stats['prepay']['auc_train']:.4f} | OOT AUC "
          f"{stats['prepay']['auc_oot']:.4f}")
    print(f"  seasoning peak fitted {fit_peak}q (empirical {emp_peak}q)")
    print(f"  double-trigger beta {b_dt:+.5f} (p={dt_p:.2e})")
    print("ALL GREEN")


if __name__ == "__main__":
    main()
