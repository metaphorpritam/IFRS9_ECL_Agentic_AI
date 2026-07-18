"""SFLLD champion hazard refit: monthly discrete-time cloglog D90 hazard (rung 3).

Isolation: freddie/ namespace only. Reads panel_monthly.parquet, loan_orig.parquet
and state_macro_panel.parquet (via freddie.macro.merge_macro); NEVER touches
engine/, agent/, app/, analysis/, challenger/, data/processed/panel.parquet, or
any existing test file. engine/hazard.py and outputs/variable_dictionary.md are
read-only references used ONLY to build the coefficient-sign comparison table
below -- nothing here imports engine.hazard or mutates it.

--------------------------------------------------------------------------
WHY A FRESH REFIT, NOT A REUSE OF engine/hazard.py
--------------------------------------------------------------------------
The DCR champion (engine/hazard.py) is fit on a loan-QUARTER panel with
national-only macro and a quarterly lag. This rung-3 SFLLD panel is a
loan-MONTH panel (panel_monthly.parquet) with STATE-level macro (freddie.macro)
and NO left truncation (sampled from origination -- an upgrade over the DCR
panel, which enters loans already seasoned). The unit of analysis, lag
granularity and macro geography all differ, so the model is refit from
scratch on this panel; engine/hazard.py is read read-only purely to produce
the "sign vs DCR champion" comparison column in the coefficients table.

--------------------------------------------------------------------------
UNIT / TARGET / ABSORBING-EVENT FRAMING (inherited from freddie/build_panel.py)
--------------------------------------------------------------------------
unit = loan-month (panel_monthly.parquet is already truncated at each loan's
first D90 month -- see freddie/build_panel.py's docstring: "a loan is at risk
of first default only up to its first default month"). y = d90_event. This
IS the discrete-time survival likelihood under non-informative right
censoring / no-lookahead construction, exactly as engine/hazard.py's module
docstring reasons for the DCR panel -- see engine/hazard.py CENSORING /
TRUNCATION section for the general argument; it applies unchanged here.
Only the DEFAULT (D90) cause-specific hazard is fit in this refit (no
competing-risk prepayment hazard -- SIMPLIFICATION, see hazard_report.md).

--------------------------------------------------------------------------
LINK / ESTIMATOR
--------------------------------------------------------------------------
Discrete-time cloglog hazard (mirrors DCR): lambda(t|x) via
statsmodels GLM Binomial(CLogLog link), IRLS, warm-started from the
same-formula LOGIT solution (rare-event convergence trick -- see
engine/hazard.py's "Warm start" note; the quarterly-hazard argument there
applies a fortiori to this MONTHLY panel, whose hazard is rarer still,
~0.11% train-window average).

--------------------------------------------------------------------------
COVARIATE FAMILIES (per-variable rationale table in hazard_report.md)
--------------------------------------------------------------------------
  cr(loan_age, df=SPLINE_DF)  baseline seasoning curve (natural cubic spline,
                              same df as DCR champion, for comparability)
  fico_s = credit_score/100   per-100-point FICO (DCR scaling convention)
  dti_s  = dti/10             per-10pp DTI (new vs DCR, which has no DTI field
                              at this rung's comparison point)
  ltv10  = updated_ltv/10, winsorised at LTV_CAP=300 (mirrors DCR's LTV_CAP
                              and winsorisation rationale verbatim)
  C(occupancy_status, Treatment(reference='P'))   owner-occ baseline
  C(loan_purpose, Treatment(reference='P'))       purchase baseline
  C(channel, Treatment(reference='R'))            retail baseline
  uer_lag1, delta_uer_lag1, hpi_growth_lag1       STATE-level, each lagged
                              ONE MONTH inside freddie.macro (see that
                              module's TIMING CONVENTION section) -- the
                              geographic-resolution upgrade over DCR's
                              national-only macro.

No double-trigger (LTV x UER) interaction term in this refit -- SIMPLIFICATION
(the spec's covariate-family list omits it; see hazard_report.md).

--------------------------------------------------------------------------
SAMPLING / WEIGHTING (pragmatic subsample of the 39.5M-row panel)
--------------------------------------------------------------------------
Fitting a cloglog GLM by IRLS on tens of millions of rows in this
environment's memory budget is impractical (transient IRLS working arrays
scale with rows x design-matrix columns). Every event row (d90_event == 1)
is ALWAYS kept; non-event ("control") at-risk rows are subsampled at
CONTROL_SAMPLE_RATE (documented below) and corrected via WESML
(Manski-Lerman 1977 weighted-exogenous-sampling MLE): controls carry
freq_weight = 1 / CONTROL_SAMPLE_RATE, events carry freq_weight = 1. This is
a choice-based / case-control sampling correction that is valid for ANY GLM
link (unlike the logit-only Prentice-Pregibon offset trick), because it
reweights the log-likelihood contribution of every row back to its
population frequency; it is fit as `freq_weights=` in statsmodels' GLM. The
fit is refit on a SECOND random seed (SEED_B) as a documented stability
check: coefficients must not qualitatively flip sign or swing wildly between
seeds for the fit to be trusted (see test_freddie_hazard.py and
stability_check.json in the outputs directory).

--------------------------------------------------------------------------
COVID / FORBEARANCE REGIME (the recorded Phase-A design question)
--------------------------------------------------------------------------
Phase-A's roll-rate EDA found current->90+/liquidation reads broken during
forbearance (2020-04..2021-09): the 60->90+ roll worse than GFC while
90+->liquidation collapsed >10x, because loans in payment-assistance programs
were shielded from the delinquency ladder that feeds d90_event. Because the
CHAMPION split below trains on performance months <= 2016-12 -- entirely
BEFORE the forbearance window -- the champion fit itself never sees COVID
rows and needs no regime handling; COVID lands squarely in its OOT (as
recorded). The three-way COVID comparison this module runs is therefore a
SEPARATE, clearly-labelled exercise on an EXTENDED estimation window
(performance month <= EXT_CUTOFF = 2021-09, i.e. champion-train + the
pre-COVID OOT months + the forbearance window itself), because that is the
only way any of the three treatments below can be actually estimated:
  * naive    -- fit straight through, no regime adjustment
  * additive -- + covid_regime dummy (1 for 2020-04..2021-09) in the RHS
  * exclude  -- covid_regime rows dropped from the fit likelihood entirely
All three are then SCORED (never re-fit) on the identical genuinely-unseen
OOT2 window (performance month > EXT_CUTOFF, i.e. 2021-10 onward) for AUC,
plus calibration-by-calendar-year across 2017-2025 (spanning both the
extended-fit years, shown as an in-fit diagnostic, and the true OOT2 years
2022+). See hazard_report.md section 3 for the full comparison and
recommendation.

--------------------------------------------------------------------------
TRAIN / OOT SPLIT (matches DCR convention: split by CALENDAR time)
--------------------------------------------------------------------------
TRAIN_CUTOFF = 2016-12: train = performance month <= 2016-12, OOT = 2017+.
This is the CHAMPION split used for the coefficients-vs-DCR table, train/OOT
AUC, calibration-by-year, seasoning curve and state-macro exhibits (spec
deliverables). The COVID three-way comparison uses the separate EXT_CUTOFF
window described above.

Run as a module to (re)build every deliverable (offline; needs the
already-cached panel/orig/macro parquets, no network):
    cd <repo root> && uv run --no-sync python -m freddie.fit_hazard
"""

from __future__ import annotations

import json
import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from sklearn.metrics import roc_auc_score

from freddie import macro as freddie_macro

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths -- rung-3 isolation
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = REPO_ROOT / "data" / "processed" / "freddie" / "panel_monthly.parquet"
ORIG_PATH = REPO_ROOT / "data" / "processed" / "freddie" / "loan_orig.parquet"
CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "hazard"
OUT_DIR = REPO_ROOT / "outputs" / "freddie" / "hazard"

#: checkpoint artifacts -- see CHECKPOINT DISCIPLINE in the module docstring.
#: main() checks each of these before redoing the corresponding (expensive)
#: step, so a session break can be resumed with a plain re-invocation of
#: `python -m freddie.fit_hazard` rather than a rewrite from scratch.
MODEL_FRAME_CACHE = CACHE_DIR / "model_frame.parquet"
CHAMPION_A_CACHE = CACHE_DIR / "champion_model.pkl"
CHAMPION_B_CACHE = CACHE_DIR / "champion_model_seed_b.pkl"
COVID_MODELS_CACHE = CACHE_DIR / "covid_models.pkl"

DCR_HAZARD_MODULE = REPO_ROOT / "engine" / "hazard.py"                    # read-only reference
DCR_VARIABLE_DICT = REPO_ROOT / "outputs" / "variable_dictionary.md"      # read-only reference

# --------------------------------------------------------------------------
# Spec constants (documented choices)
# --------------------------------------------------------------------------
SPLINE_DF = 5                     # same df as the DCR champion's seasoning spline
LTV_CAP = 300.0                    # winsorisation cap for updated_ltv (%), mirrors DCR
CONTROL_SAMPLE_RATE = 0.05         # WESML control retention rate (see module docstring)
SEED_A = 42                       # primary fit seed
SEED_B = 1234                     # stability-check second seed

TRAIN_CUTOFF = pd.Timestamp("2016-12-01")   # champion train: perf month <= this
COVID_START = pd.Timestamp("2020-04-01")
COVID_END = pd.Timestamp("2021-09-01")      # inclusive
EXT_CUTOFF = COVID_END                      # extended estimation window, COVID exercise only

AUC_FLOOR_TRAIN = 0.65

# --------------------------------------------------------------------------
# Model specification
# --------------------------------------------------------------------------
BASE_RHS = (
    f"cr(loan_age, df={SPLINE_DF})"
    " + fico_s + dti_s + ltv10"
    " + C(occupancy_status, Treatment(reference='P'))"
    " + C(loan_purpose, Treatment(reference='P'))"
    " + C(channel, Treatment(reference='R'))"
    " + uer_lag1 + delta_uer_lag1 + hpi_growth_lag1"
)
COVID_DUMMY_TERM = "covid_regime"
COVID_RHS = BASE_RHS + " + " + COVID_DUMMY_TERM

BASE_FORMULA = "d90_event ~ " + BASE_RHS
COVID_FORMULA = "d90_event ~ " + COVID_RHS

#: raw covariates every model frame must carry (post-derivation, pre-formula)
REQUIRED_COLS = [
    "loan_age", "fico_s", "dti_s", "ltv10",
    "occupancy_status", "loan_purpose", "channel",
    "uer_lag1", "delta_uer_lag1", "hpi_growth_lag1",
]

MODEL_FRAME_COLS = [
    "loan_sequence_number", "monthly_reporting_period", "property_state",
    "d90_event", "covid_regime",
] + REQUIRED_COLS


@dataclass
class HazardModel:
    """A fitted discrete-time D90 hazard (wraps the statsmodels GLM result)."""

    result: object
    formula: str
    name: str
    n_obs: int = 0
    n_events: int = 0
    control_rate: float = 0.0
    seed: int = 0
    fit_meta: dict = field(default_factory=dict)

    @property
    def params(self) -> pd.Series:
        return self.result.params

    def mcfadden_r2(self) -> float:
        return float(1.0 - self.result.llf / self.result.llnull)


# ==========================================================================
# 1. Model frame: merge loan_orig + state macro onto panel_monthly
# ==========================================================================
def _yyyymm(dt: pd.Series) -> pd.Series:
    """Datetime -> yyyymm int (freddie.macro.merge_macro's expected format)."""
    return (dt.dt.year * 100 + dt.dt.month).astype("int64")


def _fast_local(path: Path) -> Path:
    """Mirror a /mnt/d (9P-mounted) parquet onto VM-native ext4 before reading.

    The 9P mount is the frame-build bottleneck, and host-side VM restarts keep
    interrupting the build mid-read; ext4 reads cut the stage well under the
    observed VM lifetime. Re-copies only when the source is newer; the copy is
    atomic (tmp + replace) so an interrupted copy never leaves a bad cache.
    """
    import shutil

    cache = Path.home() / ".cache" / "freddie" / path.name
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists() or cache.stat().st_mtime < path.stat().st_mtime:
        tmp = cache.with_name(cache.name + ".tmp")
        shutil.copy2(path, tmp)
        tmp.replace(cache)
    return cache


def load_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.read_parquet(_fast_local(PANEL_PATH), columns=[
        "loan_sequence_number", "monthly_reporting_period", "loan_age",
        "current_actual_upb", "d90_event",
    ])
    orig = pd.read_parquet(_fast_local(ORIG_PATH), columns=[
        "loan_sequence_number", "credit_score", "dti", "occupancy_status",
        "loan_purpose", "channel", "property_state", "orig_ltv", "orig_upb",
        "first_payment_date",
    ])
    return panel, orig


def build_model_frame(
    panel: pd.DataFrame | None = None,
    orig: pd.DataFrame | None = None,
    macro_panel: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge loan-orig covariates + state macro onto the loan-month panel and
    derive the covariates BASE_FORMULA/COVID_FORMULA expect.

    NO LOOKAHEAD: uer_lag1 / delta_uer_lag1 / hpi_growth_lag1 come straight
    from freddie.macro.merge_macro, which lags each state's series by one
    calendar MONTH inside a continuous per-state index (see that module's
    TIMING CONVENTION section) -- nothing here re-derives or overrides the
    lag. updated_ltv indexes CURRENT-quarter collateral (accepted state-
    variable exception, mirrors DCR -- see engine/hazard.py's TIMING
    CONVENTION section for the argument).
    """
    if panel is None or orig is None:
        panel, orig = load_raw_frames()

    df = panel.merge(orig, on="loan_sequence_number", how="left", validate="many_to_one")
    df = df.rename(columns={"current_actual_upb": "current_upb"})

    # merge_macro expects yyyymm ints (its _yyyymm_to_month_start helper),
    # not the datetime64 columns panel_monthly/loan_orig actually carry --
    # convert on throwaway columns and restore the real datetime afterwards
    # so every downstream date comparison (train/OOT split, COVID window,
    # calendar-year groupby) uses a real Timestamp.
    perf_month = df["monthly_reporting_period"].copy()
    df["monthly_reporting_period"] = _yyyymm(df["monthly_reporting_period"])
    df["first_payment_date"] = _yyyymm(df["first_payment_date"])
    df = freddie_macro.merge_macro(df, macro=macro_panel)
    df["monthly_reporting_period"] = perf_month

    df["fico_s"] = df["credit_score"].astype("float64") / 100.0
    df["dti_s"] = df["dti"].astype("float64") / 10.0
    df["ltv10"] = df["updated_ltv"].clip(upper=LTV_CAP).astype("float64") / 10.0
    df["loan_age"] = df["loan_age"].astype("float64")
    df["occupancy_status"] = df["occupancy_status"].astype("string")
    df["loan_purpose"] = df["loan_purpose"].astype("string")
    df["channel"] = df["channel"].astype("string")
    df["covid_regime"] = (
        (df["monthly_reporting_period"] >= COVID_START)
        & (df["monthly_reporting_period"] <= COVID_END)
    ).astype("int8")

    return df[MODEL_FRAME_COLS].copy()


# ==========================================================================
# 2. Case-control (WESML) subsampling
# ==========================================================================
def sample_case_control(
    df: pd.DataFrame,
    event_col: str = "d90_event",
    rate: float = CONTROL_SAMPLE_RATE,
    seed: int = SEED_A,
) -> pd.DataFrame:
    """Keep every event row; subsample non-event rows at `rate`.

    Returns a copy with a `freq_weight` column: 1.0 for events, 1/rate for
    sampled controls -- the WESML correction (see module docstring) that
    makes the weighted-likelihood GLM fit on the subsample consistent for
    the full-population coefficients.
    """
    events = df[df[event_col] == 1]
    controls = df[df[event_col] == 0].sample(frac=rate, random_state=seed)
    out = pd.concat([events, controls], ignore_index=True)
    out["freq_weight"] = np.where(out[event_col] == 1, 1.0, 1.0 / rate)
    return out


# ==========================================================================
# 3. Fit (warm-started cloglog GLM, mirrors engine/hazard.py's IRLS trick)
# ==========================================================================
def fit_hazard(
    df: pd.DataFrame,
    formula: str = BASE_FORMULA,
    name: str = "champion",
    weight_col: str | None = "freq_weight",
) -> HazardModel:
    need = REQUIRED_COLS + ["d90_event"]
    if COVID_DUMMY_TERM in formula:
        need = need + [COVID_DUMMY_TERM]
    n_before = len(df)
    d = df.dropna(subset=need).copy()
    n_dropped = n_before - len(d)

    weights = d[weight_col] if weight_col and weight_col in d.columns else None

    warm = smf.glm(
        formula, data=d, family=sm.families.Binomial(), freq_weights=weights,
    ).fit()
    model = smf.glm(
        formula, data=d,
        family=sm.families.Binomial(link=sm.families.links.CLogLog()),
        freq_weights=weights,
    )
    res = model.fit(start_params=warm.params.to_numpy(), maxiter=200)
    if not res.converged:
        raise RuntimeError(f"{name} hazard GLM did not converge")

    return HazardModel(
        result=res, formula=formula, name=name,
        n_obs=len(d), n_events=int(d["d90_event"].sum()),
        control_rate=CONTROL_SAMPLE_RATE,
        fit_meta={"rows_dropped_nan": int(n_dropped), "warm_start": "logit",
                  "weighted": weights is not None},
    )


# ==========================================================================
# 4. Scoring (chunked by calendar year to bound memory on the full panel)
# ==========================================================================
def predict_hazard(model: HazardModel, df: pd.DataFrame) -> pd.Series:
    """Predicted hazard for `df` (raw covariate columns, NaNs dropped first).

    Reuses the patsy design_info memorised at fit time (spline knots,
    Treatment-coded categories) exactly as engine/hazard.py's predict path
    does -- statsmodels' formula-fitted GLMResults.predict(newdata) rebuilds
    the design matrix from the training formula, so extrapolation beyond the
    training age/LTV range is handled the same documented way (natural
    cubic spline -> linear beyond the boundary knots).
    """
    need = REQUIRED_COLS.copy()
    if COVID_DUMMY_TERM in model.formula:
        need = need + [COVID_DUMMY_TERM]
    sub = df.dropna(subset=need)
    return model.result.predict(sub).reindex(df.index)


def score_by_year(
    model: HazardModel,
    df: pd.DataFrame,
    year_col: str = "monthly_reporting_period",
) -> tuple[np.ndarray, pd.DataFrame]:
    """One pass over `df`, chunked by calendar year, returning:
      - a full-length float32 array of predicted hazard (NaN where covariates
        were missing and the row was dropped)
      - a per-calendar-year observed-vs-predicted calibration table
    Chunking by year bounds the transient patsy design-matrix memory to one
    year's rows (~1-3M) instead of materialising it for the whole panel.
    """
    preds = np.full(len(df), np.nan, dtype="float32")
    years = df[year_col].dt.year
    rows = []
    for yr, idx in df.groupby(years).groups.items():
        chunk = df.loc[idx]
        p = predict_hazard(model, chunk)
        preds[df.index.get_indexer(idx)] = p.to_numpy(dtype="float32")
        rows.append({
            "year": int(yr),
            "n": len(chunk),
            "n_events": int(chunk["d90_event"].sum()),
            "observed_hazard": float(chunk["d90_event"].mean()),
            "predicted_hazard": float(np.nanmean(p.to_numpy())),
        })
    calib = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    calib["ratio_obs_over_pred"] = calib["observed_hazard"] / calib["predicted_hazard"]
    return preds, calib


def compute_auc(df: pd.DataFrame, preds: np.ndarray, mask: np.ndarray) -> float:
    y = df["d90_event"].to_numpy()[mask]
    p = preds[mask]
    ok = ~np.isnan(p)
    return float(roc_auc_score(y[ok], p[ok]))


# ==========================================================================
# 5. Exhibits
# ==========================================================================
def _era_shading(ax):
    from analysis.mpl_style import COLORS
    ax.axvspan(pd.Timestamp("2007-01-01"), pd.Timestamp("2009-12-31"),
               color=COLORS["warn"], alpha=0.08, zorder=0)
    ax.axvspan(pd.Timestamp("2020-01-01"), pd.Timestamp("2021-12-31"),
               color=COLORS["purple"], alpha=0.08, zorder=0)


def plot_calibration_by_year(calib: pd.DataFrame, title: str, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = calib["year"]
    ax.plot(x, calib["observed_hazard"] * 100, marker="o", color=COLORS["accent"], label="Observed D90 hazard")
    ax.plot(x, calib["predicted_hazard"] * 100, marker="s", color=COLORS["warn"], label="Predicted D90 hazard", linestyle="--")
    ax.axvspan(2020, 2021.75, color=COLORS["purple"], alpha=0.08, zorder=0, label="Forbearance window (2020-04..2021-09)")
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Monthly D90 hazard (%)")
    ax.set_title(title)
    ax.legend(fontsize=7.5)
    fig.savefig(path)
    plt.close(fig)


def plot_covid_comparison(calibs: dict[str, pd.DataFrame], path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    colors = {"naive": COLORS["warn"], "additive": COLORS["accent"], "exclude": COLORS["good"]}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharex=True)
    for name, calib in calibs.items():
        axes[0].plot(calib["year"], calib["observed_hazard"] * 100, color=colors[name], alpha=0.4, linestyle=":")
        axes[0].plot(calib["year"], calib["predicted_hazard"] * 100, marker="o", color=colors[name], label=name)
        axes[1].plot(calib["year"], calib["ratio_obs_over_pred"], marker="o", color=colors[name], label=name)
    axes[1].axhline(1.0, color=COLORS["gray"], linestyle="--", linewidth=1)
    for ax in axes:
        ax.axvspan(2020, 2021.75, color=COLORS["purple"], alpha=0.08, zorder=0)
        ax.set_xlabel("Calendar year")
    axes[0].set_ylabel("Monthly D90 hazard (%) -- dotted = observed, marker = predicted")
    axes[1].set_ylabel("Observed / predicted hazard ratio")
    axes[0].set_title("COVID regime comparison: calibration by year")
    axes[1].set_title("Calibration ratio (1.0 = perfect)")
    axes[0].legend(fontsize=7.5)
    axes[1].legend(fontsize=7.5)
    fig.savefig(path)
    plt.close(fig)


def plot_seasoning_curve(model: HazardModel, ref_row: pd.Series, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    ages = np.arange(0, 181)
    grid = pd.DataFrame([ref_row.to_dict()] * len(ages))
    grid["loan_age"] = ages
    pred = predict_hazard(model, grid)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(ages, pred.to_numpy() * 100, color=COLORS["accent"])
    peak_age = int(ages[np.nanargmax(pred.to_numpy())])
    ax.axvline(peak_age, color=COLORS["warn"], linestyle="--", linewidth=1)
    ax.text(peak_age + 2, pred.max() * 100 * 0.9, f"peak {peak_age}mo", color=COLORS["warn"], fontsize=8)
    ax.set_xlabel("Loan age (months)")
    ax.set_ylabel("Predicted D90 hazard (%)")
    ax.set_title("Seasoning curve (natural cubic spline, other covariates at reference)")
    fig.savefig(path)
    plt.close(fig)


def plot_state_uer_effect(model: HazardModel, df: pd.DataFrame, path: Path) -> pd.DataFrame:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    sub = df.dropna(subset=REQUIRED_COLS).copy()
    sub["uer_q"] = pd.qcut(sub["uer_lag1"], 4, labels=["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"])
    pred = predict_hazard(model, sub)
    sub["pred"] = pred.to_numpy()
    g = sub.groupby("uer_q", observed=True).agg(
        observed=("d90_event", "mean"), predicted=("pred", "mean"), n=("d90_event", "size"),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = np.arange(len(g))
    width = 0.35
    ax.bar(x - width / 2, g["observed"] * 100, width, color=COLORS["accent"], label="Observed")
    ax.bar(x + width / 2, g["predicted"] * 100, width, color=COLORS["warn"], label="Predicted")
    ax.set_xticks(x)
    ax.set_xticklabels(g["uer_q"])
    ax.set_ylabel("Monthly D90 hazard (%)")
    ax.set_title("State-macro effect: hazard by state UER quartile (uer_lag1, OOT rows)")
    ax.legend(fontsize=8)
    fig.savefig(path)
    plt.close(fig)
    return g


# ==========================================================================
# 6. DCR sign comparison (read-only reference)
# ==========================================================================
_DCR_SIGN_MAP = {
    "fico_s": ("fico_s", "-"),
    "dti_s": (None, "n/a (DCR has no DTI field at this rung)"),
    "ltv10": ("ltv10", "+"),
    "uer_lag1": ("uer_lag1", "+ (net, level+momentum -- see DCR variable dictionary)"),
    "delta_uer_lag1": ("uer_chg4_lag1", "+"),
    "hpi_growth_lag1": ("hpi_growth_lag1", "-"),
    "cr(loan_age, df=5)": ("cr(loan_age, df=5)", "hump (DCR peak ~12 QUARTERS ~= 36 months)"),
}


def dcr_sign_table() -> pd.DataFrame:
    rows = []
    for var, (dcr_var, dcr_sign) in _DCR_SIGN_MAP.items():
        rows.append({"variable": var, "dcr_variable": dcr_var, "dcr_expected_sign": dcr_sign})
    return pd.DataFrame(rows)


# ==========================================================================
# 7. Coefficients table
# ==========================================================================
def coefficients_table(model: HazardModel) -> pd.DataFrame:
    res = model.result
    ci = res.conf_int()
    out = pd.DataFrame({
        "term": res.params.index,
        "coef": res.params.values,
        "std_err": res.bse.values,
        "z": res.tvalues.values,
        "p_value": res.pvalues.values,
        "ci_low": ci[0].values,
        "ci_high": ci[1].values,
        "hazard_ratio": np.exp(res.params.values),
    })
    return out


# ==========================================================================
# 8. Checkpointed loaders (CHECKPOINT DISCIPLINE -- resume after a session
#    break without redoing already-converged, already-persisted work)
# ==========================================================================
class _CheckpointUnpickler(pickle.Unpickler):
    """Map HazardModel references recorded under '__main__' back to this
    module's canonical class. The fits are pickled by `python -m
    freddie.fit_hazard`, where this module IS '__main__', so a plain
    pickle.load from any other entry point (tests, backtest, a notebook)
    raises AttributeError: Can't get attribute 'HazardModel' on __main__.
    """

    def find_class(self, module: str, name: str):
        if name == "HazardModel":
            return HazardModel
        return super().find_class(module, name)


def _load_pickle(path: Path):
    with open(path, "rb") as f:
        return _CheckpointUnpickler(f).load()


def get_model_frame(refresh: bool = False) -> pd.DataFrame:
    """Build (or load the cached) merged model frame.

    The panel+orig+state-macro merge over 39.5M rows is the single most
    expensive non-fit step in this pipeline; cache it to parquet the moment
    it is built so a later re-run of `main()` skips straight to fitting.
    """
    if MODEL_FRAME_CACHE.exists() and not refresh:
        logger.info("Loading cached model frame from %s", MODEL_FRAME_CACHE)
        return pd.read_parquet(MODEL_FRAME_CACHE)
    # Memory-lean per-vintage build: the original single-pass merge over all
    # 39.5M loan-months peaked >15GB resident and was OOM-killed at the WSL
    # VM's 15.5GB cap (dmesg-confirmed). Chunking by vintage keeps the merge
    # working set to one vintage (~2.5M rows) plus the accumulating float32
    # result (~2GB total); categorical conversion happens once, post-concat,
    # because per-chunk categories with differing levels would upcast to
    # object on concat and reinflate memory.
    logger.info("Building model frame per vintage (memory-lean, OOM fix)...")
    from freddie.ingest import VINTAGE_YEARS

    orig_full = pd.read_parquet(_fast_local(ORIG_PATH), columns=[
        "loan_sequence_number", "vintage", "credit_score", "dti",
        "occupancy_status", "loan_purpose", "channel", "property_state",
        "orig_ltv", "orig_upb", "first_payment_date",
    ])
    chunks: list[pd.DataFrame] = []
    for v in VINTAGE_YEARS:
        panel_v = pd.read_parquet(
            _fast_local(PANEL_PATH),
            columns=["loan_sequence_number", "monthly_reporting_period",
                     "loan_age", "current_actual_upb", "d90_event"],
            filters=[("vintage", "==", v)],
        )
        orig_v = orig_full[orig_full["vintage"] == v].drop(columns=["vintage"])
        chunk = build_model_frame(panel=panel_v, orig=orig_v)
        del panel_v, orig_v
        for c in chunk.columns:
            if chunk[c].dtype == "float64":
                chunk[c] = chunk[c].astype("float32")
        chunks.append(chunk)
        logger.info("  vintage %s: %d rows", v, len(chunk))
    df = pd.concat(chunks, ignore_index=True)
    del chunks
    for c in ("occupancy_status", "loan_purpose", "channel", "property_state"):
        if c in df.columns:
            df[c] = df[c].astype("category")
    logger.info("Model frame: %d rows, %d columns", *df.shape)
    df.to_parquet(MODEL_FRAME_CACHE, index=False)
    return df


def get_champion_fits(
    train_df: pd.DataFrame, refresh: bool = False,
) -> tuple[HazardModel, HazardModel, pd.DataFrame]:
    """Champion fit (seed A) + second-seed stability check (seed B).

    Both fitted models are pickled the moment they converge, and the
    stability table is written to `outputs/freddie/hazard/seed_stability.csv`
    immediately after -- BEFORE any exhibit code runs -- so a session break
    during exhibit-building never loses a converged fit.
    """
    stability_path = OUT_DIR / "seed_stability.csv"
    if (not refresh and CHAMPION_A_CACHE.exists() and CHAMPION_B_CACHE.exists()
            and stability_path.exists()):
        logger.info("Loading cached champion fits (seed A + seed B)...")
        champion = _load_pickle(CHAMPION_A_CACHE)
        champion_b = _load_pickle(CHAMPION_B_CACHE)
        stability = pd.read_csv(stability_path)
        return champion, champion_b, stability

    logger.info("Champion train rows: %d, events: %d", len(train_df), train_df["d90_event"].sum())

    sample_a = sample_case_control(train_df, rate=CONTROL_SAMPLE_RATE, seed=SEED_A)
    champion = fit_hazard(sample_a, formula=BASE_FORMULA, name="champion")
    logger.info("Champion fit: n=%d events=%d converged", champion.n_obs, champion.n_events)
    with open(CHAMPION_A_CACHE, "wb") as f:
        pickle.dump(champion, f)

    # second-seed stability check
    sample_b = sample_case_control(train_df, rate=CONTROL_SAMPLE_RATE, seed=SEED_B)
    champion_b = fit_hazard(sample_b, formula=BASE_FORMULA, name="champion_seed_b")
    with open(CHAMPION_B_CACHE, "wb") as f:
        pickle.dump(champion_b, f)

    stability = pd.DataFrame({
        "term": champion.params.index,
        "coef_seed_a": champion.params.values,
        "coef_seed_b": champion_b.params.reindex(champion.params.index).values,
    })
    stability["abs_diff"] = (stability["coef_seed_a"] - stability["coef_seed_b"]).abs()
    stability["rel_diff"] = stability["abs_diff"] / stability["coef_seed_a"].abs().clip(lower=1e-6)
    stability.to_csv(stability_path, index=False)
    return champion, champion_b, stability


def get_covid_fits(ext_df: pd.DataFrame, refresh: bool = False) -> dict[str, HazardModel]:
    """The naive / additive / exclude COVID-regime variants, pickle-cached."""
    if COVID_MODELS_CACHE.exists() and not refresh:
        logger.info("Loading cached COVID variants from %s", COVID_MODELS_CACHE)
        return _load_pickle(COVID_MODELS_CACHE)

    logger.info("COVID comparison: fitting naive / additive / exclude on extended window...")
    covid_variants: dict[str, HazardModel] = {}

    naive_sample = sample_case_control(ext_df, rate=CONTROL_SAMPLE_RATE, seed=SEED_A)
    covid_variants["naive"] = fit_hazard(naive_sample, formula=BASE_FORMULA, name="covid_naive")

    additive_sample = naive_sample  # same rows; formula adds the dummy
    covid_variants["additive"] = fit_hazard(additive_sample, formula=COVID_FORMULA, name="covid_additive")

    ext_no_covid = ext_df.loc[ext_df["covid_regime"] == 0]
    exclude_sample = sample_case_control(ext_no_covid, rate=CONTROL_SAMPLE_RATE, seed=SEED_A)
    covid_variants["exclude"] = fit_hazard(exclude_sample, formula=BASE_FORMULA, name="covid_exclude")

    with open(COVID_MODELS_CACHE, "wb") as f:
        pickle.dump(covid_variants, f)
    return covid_variants


# ==========================================================================
# 9. Orchestration
# ==========================================================================
def main(refresh: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    df = get_model_frame(refresh=refresh)

    train_mask_full = (df["monthly_reporting_period"] <= TRAIN_CUTOFF).to_numpy()
    oot_mask_full = ~train_mask_full

    # ---------------- Champion fit (train <= 2016-12) ----------------
    train_df = df.loc[train_mask_full]
    champion, champion_b, stability = get_champion_fits(train_df, refresh=refresh)

    # ---------------- Scoring: champion, full panel by year ----------------
    logger.info("Scoring champion over full panel (chunked by year)...")
    preds, calib_full = score_by_year(champion, df)
    train_auc = compute_auc(df, preds, train_mask_full)
    oot_auc = compute_auc(df, preds, oot_mask_full)
    logger.info("Champion AUC: train=%.4f oot=%.4f", train_auc, oot_auc)

    coef_tbl = coefficients_table(champion)
    coef_tbl.to_csv(OUT_DIR / "coefficients.csv", index=False)
    sign_tbl = dcr_sign_table()
    sign_tbl.to_csv(OUT_DIR / "dcr_sign_comparison.csv", index=False)

    metrics = {
        "train_auc": train_auc,
        "oot_auc": oot_auc,
        "train_n": int(train_mask_full.sum()),
        "train_events": int(df.loc[train_mask_full, "d90_event"].sum()),
        "oot_n": int(oot_mask_full.sum()),
        "oot_events": int(df.loc[oot_mask_full, "d90_event"].sum()),
        "champion_fit_n": champion.n_obs,
        "champion_fit_events": champion.n_events,
        "control_sample_rate": CONTROL_SAMPLE_RATE,
        "mcfadden_r2": champion.mcfadden_r2(),
        "rows_dropped_nan_fit": champion.fit_meta["rows_dropped_nan"],
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))

    plot_calibration_by_year(calib_full, "Champion hazard: calibration by calendar year (full panel)",
                              OUT_DIR / "calibration_by_year.png")
    calib_full.to_csv(OUT_DIR / "calibration_by_year.csv", index=False)

    # Reference row for seasoning curve: modal/median covariate values.
    ref_row = pd.Series({
        "loan_age": 0.0,
        "fico_s": float(train_df["fico_s"].median()),
        "dti_s": float(train_df["dti_s"].median()),
        "ltv10": float(train_df["ltv10"].median()),
        "occupancy_status": "P",
        "loan_purpose": "P",
        "channel": "R",
        "uer_lag1": float(train_df["uer_lag1"].median()),
        "delta_uer_lag1": float(train_df["delta_uer_lag1"].median()),
        "hpi_growth_lag1": float(train_df["hpi_growth_lag1"].median()),
    })
    plot_seasoning_curve(champion, ref_row, OUT_DIR / "seasoning_curve.png")

    # Empirical seasoning summary for the report's cohort-confounding caveat:
    # the raw train-window hazard-by-age profile (6mo bins) and the vintage
    # range that populates the high-age (>=96mo) region, where the spline's
    # late-age behaviour is identified exclusively by crisis cohorts.
    age_bin = (train_df["loan_age"] // 6) * 6
    emp_curve = train_df.groupby(age_bin, observed=True)["d90_event"].mean()
    hi_age = train_df.loc[train_df["loan_age"] >= 96]
    approx_vint = hi_age["monthly_reporting_period"].dt.year - (hi_age["loan_age"] // 12).astype(int)
    seasoning_notes = {
        "emp_peak_age_bin": int(emp_curve.idxmax()),
        "emp_peak_hazard": float(emp_curve.max()),
        "max_train_age": float(train_df["loan_age"].max()),
        "hi_age_vint_min": int(approx_vint.min()),
        "hi_age_vint_max": int(approx_vint.max()),
    }

    oot_df = df.loc[oot_mask_full]
    state_uer_tbl = plot_state_uer_effect(champion, oot_df, OUT_DIR / "state_uer_effect.png")
    state_uer_tbl.to_csv(OUT_DIR / "state_uer_effect.csv", index=False)

    # ---------------- COVID three-way comparison ----------------
    ext_df = df.loc[df["monthly_reporting_period"] <= EXT_CUTOFF]
    oot2_mask_full = (df["monthly_reporting_period"] > EXT_CUTOFF).to_numpy()

    covid_variants = get_covid_fits(ext_df, refresh=refresh)
    covid_calibs: dict[str, pd.DataFrame] = {}
    covid_aucs: dict[str, float] = {}

    covid_eval_df = df.loc[df["monthly_reporting_period"] >= pd.Timestamp("2017-01-01")]
    for name, mdl in covid_variants.items():
        p, calib = score_by_year(mdl, covid_eval_df)
        covid_calibs[name] = calib
        full_p = np.full(len(df), np.nan, dtype="float32")
        full_p[df.index.get_indexer(covid_eval_df.index)] = p
        covid_aucs[f"{name}_oot2_auc"] = compute_auc(df, full_p, oot2_mask_full)

    covid_coef_compare = pd.DataFrame({
        name: mdl.params for name, mdl in covid_variants.items()
    })
    covid_coef_compare.to_csv(OUT_DIR / "covid_coefficient_comparison.csv")

    plot_covid_comparison(covid_calibs, OUT_DIR / "covid_calibration_comparison.png")
    for name, calib in covid_calibs.items():
        calib.to_csv(OUT_DIR / f"covid_calibration_{name}.csv", index=False)

    (OUT_DIR / "covid_metrics.json").write_text(json.dumps(covid_aucs, indent=2))

    write_hazard_report(champion, metrics, coef_tbl, sign_tbl, stability,
                         covid_variants, covid_aucs, covid_coef_compare,
                         covid_calibs=covid_calibs, calib_full=calib_full,
                         seasoning_notes=seasoning_notes)
    logger.info("Done. Deliverables in %s", OUT_DIR)


#: fitted-sign priors from the per-variable rationale table below; the report
#: lists every term whose FITTED sign contradicts its prior instead of leaving
#: the reader to cross-check the two tables by hand.
_PRIOR_SIGNS = {
    "C(occupancy_status, Treatment(reference='P'))[T.I]": +1,
    "C(occupancy_status, Treatment(reference='P'))[T.S]": +1,
    "C(loan_purpose, Treatment(reference='P'))[T.C]": +1,
    "C(loan_purpose, Treatment(reference='P'))[T.N]": -1,
    "C(channel, Treatment(reference='R'))[T.B]": +1,
    "C(channel, Treatment(reference='R'))[T.C]": +1,
    "C(channel, Treatment(reference='R'))[T.T]": +1,
    "fico_s": -1, "dti_s": +1, "ltv10": +1,
    "uer_lag1": +1, "delta_uer_lag1": +1, "hpi_growth_lag1": -1,
}


def write_hazard_report(
    champion: HazardModel,
    metrics: dict,
    coef_tbl: pd.DataFrame,
    sign_tbl: pd.DataFrame,
    stability: pd.DataFrame,
    covid_variants: dict[str, HazardModel],
    covid_aucs: dict[str, float],
    covid_coef_compare: pd.DataFrame,
    covid_calibs: dict[str, pd.DataFrame] | None = None,
    calib_full: pd.DataFrame | None = None,
    seasoning_notes: dict | None = None,
) -> None:
    lines = []
    lines.append("# SFLLD Champion Hazard Refit -- Monthly Discrete-Time Cloglog D90 Hazard\n")
    lines.append(
        "Fresh refit on the SFLLD loan-month panel (`panel_monthly.parquet`), state-level "
        "macro (`freddie.macro`), no left truncation (sampled from origination -- an upgrade "
        "over the DCR panel). Only the DEFAULT (D90) cause-specific hazard is fit (no "
        "competing-risk prepayment hazard in this refit -- SIMPLIFICATION). See "
        "`freddie/fit_hazard.py` module docstring for the full methodology.\n"
    )

    lines.append("## 1. Sample & split\n")
    lines.append(
        f"- Champion train: performance month <= 2016-12 -- {metrics['train_n']:,} loan-months, "
        f"{metrics['train_events']:,} D90 events ({metrics['train_events']/metrics['train_n']:.4%} "
        "monthly hazard).\n"
        f"- OOT: performance month >= 2017-01 -- {metrics['oot_n']:,} loan-months, "
        f"{metrics['oot_events']:,} D90 events. COVID (2020-04..2021-09) lands entirely inside "
        "OOT, as recorded.\n"
        f"- Fit sample (WESML case-control): every train event row enters the sample "
        f"({metrics['train_events']:,}), plus a {metrics['control_sample_rate']:.0%} random "
        f"subsample of non-event train rows; {metrics['rows_dropped_nan_fit']:,} NaN-covariate "
        f"rows (events and controls alike) are then dropped, leaving {metrics['champion_fit_n']:,} "
        f"fit rows with {metrics['champion_fit_events']:,} events. Controls are reweighted by "
        "`freq_weight = 1/rate` (Manski-Lerman WESML), events by `freq_weight = 1` -- valid for "
        "any GLM link, not just logit (see module docstring).\n"
    )

    lines.append("## 2. Coefficients vs the DCR champion\n")
    lines.append(
        "Coefficients (`outputs/freddie/hazard/coefficients.csv`) and the sign comparison against "
        "`engine/hazard.py`'s DCR champion (read-only reference; `outputs/variable_dictionary.md` "
        "consulted for the DCR expected-direction column):\n\n"
    )
    def _sign(x):
        return "+" if x > 0 else "-"

    lines.append("| term | coef | hazard ratio | p-value | this-fit sign | DCR variable | DCR expected sign |\n")
    lines.append("|---|---:|---:|---:|:---:|---|---|\n")
    for _, r in coef_tbl.iterrows():
        matches = sign_tbl[sign_tbl["variable"].apply(lambda v: v in str(r["term"]))]
        if len(matches):
            # LONGEST matching key wins: 'delta_uer_lag1' must resolve to its
            # own row, not to its substring 'uer_lag1' (which the map lists
            # first and a first-match lookup would wrongly return).
            best = matches.loc[matches["variable"].str.len().idxmax()]
            dcr_var = best["dcr_variable"] if isinstance(best["dcr_variable"], str) else ""
            dcr_sign = best["dcr_expected_sign"]
        else:
            dcr_var = dcr_sign = ""
        lines.append(
            f"| {r['term']} | {r['coef']:.4f} | {r['hazard_ratio']:.3f} | {r['p_value']:.3g} | "
            f"{_sign(r['coef'])} | {dcr_var} | {dcr_sign} |\n"
        )

    lines.append("\n### Per-variable rationale (variable-dictionary style)\n")
    lines.append(
        "| variable | transform | timing | economic rationale | expected direction |\n"
        "|---|---|---|---|---|\n"
        "| `cr(loan_age, df=5)` | natural cubic spline of loan age | per-month | underwriting-quality "
        "burn-in -> peak default risk -> survivor selection (seasoning hump) | hump, peak then decay |\n"
        "| `fico_s` | `credit_score`/100 | static (origination) | ability/willingness to pay | - |\n"
        "| `dti_s` | `dti`/10 | static (origination) | debt-service cash-flow strain | + |\n"
        "| `ltv10` | `updated_ltv`/10, winsorised at 300 | current-month state (collateral "
        "indexation, documented DCR-style exception) | equity cushion / negative-equity trigger | + |\n"
        "| `occupancy_status` | Treatment(ref='P' owner-occ) | static | strategic-default propensity "
        "(investor/second-home = less skin in the game) | + for I/S |\n"
        "| `loan_purpose` | Treatment(ref='P' purchase) | static | cash-out extracts equity "
        "(higher risk); no-cash-out refi selects seasoned/improved borrowers (lower risk) | + for C, "
        "- for N |\n"
        "| `channel` | Treatment(ref='R' retail) | static | origination-control agency problem "
        "(broker/correspondent/TPO historically riskier than retail) | + for B/C/T |\n"
        "| `uer_lag1` | state unemployment rate, lag 1 month | lag 1mo | cash-flow shock channel | + |\n"
        "| `delta_uer_lag1` | 1-month change in state UER, lag 1 month | lag 1mo | labour-market "
        "momentum | + |\n"
        "| `hpi_growth_lag1` | state HPI log-growth, lag 1 month | lag 1mo | collateral/equity-"
        "building channel | - |\n"
    )

    coefs_by_term = coef_tbl.set_index("term")["coef"]
    mismatches = [
        (t, float(coefs_by_term[t]))
        for t, s in _PRIOR_SIGNS.items()
        if t in coefs_by_term.index and np.sign(coefs_by_term[t]) != s
    ]
    if mismatches:
        lines.append(
            "\n**Fitted signs vs the priors above -- misses, stated rather than "
            "left for the reader to find**: "
            + "; ".join(f"`{t}` fitted {c:+.3f} against a prior of "
                        f"{'+' if _PRIOR_SIGNS[t] > 0 else '-'}" for t, c in mismatches)
            + ". All are CONDITIONAL effects (given FICO/DTI/updated-LTV/macro), so a "
            "flipped categorical sign reads as composition within this sample, not a "
            "causal claim -- e.g. second-home borrowers who clear the same FICO/LTV bar "
            "as owner-occupants default less here, and correspondent loans in this "
            "Freddie sample are not the pre-crisis wholesale book the prior describes. "
            "The core risk drivers (FICO -, DTI +, updated LTV +, UER +, "
            "delta-UER +, HPI growth -) all match their priors.\n"
        )

    lines.append("\n## 3. COVID / forbearance regime handling\n")
    lines.append(
        "The champion fit above (train <= 2016-12) never sees COVID rows, so it needs no regime "
        "handling by construction -- COVID lands in its OOT. To actually test regime treatments we "
        f"extend the estimation window to performance month <= {EXT_CUTOFF.date()} (train + pre-COVID "
        "OOT + the forbearance window itself) and fit three variants, all scored (never re-fit) on "
        f"the identical, genuinely unseen OOT2 window (performance month > {EXT_CUTOFF.date()}):\n\n"
        "| variant | estimation window | OOT2 AUC |\n|---|---|---:|\n"
    )
    for name in ["naive", "additive", "exclude"]:
        lines.append(f"| {name} | <= {EXT_CUTOFF.date()} "
                     f"{'(covid rows excluded from likelihood)' if name == 'exclude' else ''} | "
                     f"{covid_aucs[f'{name}_oot2_auc']:.4f} |\n")

    # ---- what the FITTED numbers show (no expectations -- the actuals) ----
    cc = covid_coef_compare
    ch = champion.params

    def _cv(term: str, var: str) -> float:
        return float(cc.loc[term, var])

    dummy = _cv("covid_regime", "additive")

    def _r2020(name: str) -> float:
        if not covid_calibs:
            return float("nan")
        cal = covid_calibs[name]
        return float(cal.loc[cal["year"] == 2020, "ratio_obs_over_pred"].iloc[0])

    def _oot2_ratios(name: str) -> str:
        if not covid_calibs:
            return "n/a"
        cal = covid_calibs[name]
        r = cal.loc[cal["year"] >= 2022, "ratio_obs_over_pred"]
        return f"{r.min():.2f}-{r.max():.2f}"

    lines.append(
        "\nWhat the fitted numbers actually show "
        "(`outputs/freddie/hazard/covid_coefficient_comparison.csv`, per-variant calibration CSVs, "
        "`covid_calibration_comparison.png`):\n"
        f"- **naive**: the forbearance window destroys the structural macro block -- "
        f"`delta_uer_lag1` flips sign to {_cv('delta_uer_lag1', 'naive'):+.3f} (champion "
        f"{float(ch['delta_uer_lag1']):+.3f}) and `hpi_growth_lag1` collapses to "
        f"{_cv('hpi_growth_lag1', 'naive'):+.3f} (champion {float(ch['hpi_growth_lag1']):+.3f}). "
        f"Unconditionally it is the best-calibrated variant on the true OOT2 years "
        f"(obs/pred {_oot2_ratios('naive')} across 2022-2025) -- but with inverted macro "
        "sensitivities it cannot be used for scenario-conditional (IFRS-9) projection.\n"
        f"- **additive**: the regime dummy fits {dummy:+.3f} (hazard ratio {np.exp(dummy):.2f}) -- "
        "POSITIVE, i.e. it is absorbing the 2020 D90 spike the distorted macro terms fail to carry, "
        "not a clean 'forbearance suppression' lever. It has the best 2020 in-window calibration "
        f"(obs/pred {_r2020('additive'):.2f} vs naive {_r2020('naive'):.2f}), but the dummy does "
        f"NOT repair the structural block: `delta_uer_lag1` stays sign-flipped at "
        f"{_cv('delta_uer_lag1', 'additive'):+.3f} and `hpi_growth_lag1` overshoots to "
        f"{_cv('hpi_growth_lag1', 'additive'):+.3f} (exclude: {_cv('hpi_growth_lag1', 'exclude'):+.3f}). "
        "A calendar-level dummy cannot undo a joint covariate-outcome distortion (the UER spike and "
        "the forbearance-shielded delinquency ladder co-move inside the window).\n"
        f"- **exclude**: the only variant whose structural macro block survives -- "
        f"`delta_uer_lag1` {_cv('delta_uer_lag1', 'exclude'):+.3f}, `hpi_growth_lag1` "
        f"{_cv('hpi_growth_lag1', 'exclude'):+.3f}, `uer_lag1` {_cv('uer_lag1', 'exclude'):+.3f} "
        f"(champion: {float(ch['delta_uer_lag1']):+.3f} / {float(ch['hpi_growth_lag1']):+.3f} / "
        f"{float(ch['uer_lag1']):+.3f}). Scored THROUGH the window it saturates exactly like the "
        f"champion (2020 obs/pred {_r2020('exclude'):.2f}) because it never sees the regime.\n\n"
        "**Recommendation (follows the numbers above)**: prefer **exclude** for any structural or "
        "scenario-conditional use -- it is the only treatment that preserves economically-signed "
        "macro coefficients, and it is consistent with the champion itself (whose train window "
        "pre-dates COVID by construction). The OOT2 AUC spread (naive "
        f"{covid_aucs['naive_oot2_auc']:.4f} / additive {covid_aucs['additive_oot2_auc']:.4f} / "
        f"exclude {covid_aucs['exclude_oot2_auc']:.4f}) is too small to override that structural "
        "argument. The additive dummy is NOT recommended as previously argued: its own coefficient "
        "table shows the dummy fails to keep the structural terms near exclude's (the sign flip on "
        "`delta_uer_lag1` persists), so 'the dummy is doing its job' is contradicted by the fit. "
        "Handle any future forbearance-style regime as an explicit scoring overlay rather than an "
        "in-likelihood dummy. Residual caveat shared by ALL variants: 2022-2025 observed hazard runs "
        f"~{_oot2_ratios('exclude')} times predictions (exclude variant) -- a post-COVID level shift "
        "to hand to the backtest/ECL-overlay stage, not something the regime treatment fixes.\n"
    )

    lines.append("\n## 4. Discrimination & seasoning\n")
    lines.append(
        f"- Champion train AUC: **{metrics['train_auc']:.4f}** (floor 0.65). OOT AUC: "
        f"**{metrics['oot_auc']:.4f}**. McFadden pseudo-R2 (fit sample): {metrics['mcfadden_r2']:.4f}.\n"
        "- Seasoning curve: `seasoning_curve.png` (natural cubic spline, other covariates held at "
        "champion-train medians / modal categories).\n"
        "- State-macro effect: `state_uer_effect.png` + `.csv` -- predicted vs observed hazard by "
        "state `uer_lag1` quartile, scored on OOT rows.\n"
        "- Calibration by calendar year (champion, full panel): `calibration_by_year.png` + `.csv`.\n"
    )
    if seasoning_notes:
        sn = seasoning_notes
        lines.append(
            "- **Seasoning caveat (checked against the raw panel)**: the EMPIRICAL train-window "
            f"hazard-by-age profile is a single hump peaking in the {sn['emp_peak_age_bin']}-"
            f"{sn['emp_peak_age_bin'] + 6}mo bin ({sn['emp_peak_hazard']:.3%} monthly), consistent "
            "with the DCR champion's ~12-quarter peak. The fitted reference-row curve shows an "
            "ADDITIONAL, higher peak near 108mo that the raw profile does not: train rows with age "
            f">= 96mo come exclusively from the {sn['hi_age_vint_min']}-{sn['hi_age_vint_max']} "
            "crisis vintages (later vintages are too young by 2016-12), so the spline's late-age "
            "rise is unobserved cohort quality absorbed into the age baseline, not a seasoning "
            f"effect. Ages beyond {sn['max_train_age']:.0f}mo (max train age) in the exhibit are "
            "natural-spline linear extrapolation with no train support. Treat the baseline beyond "
            "~96mo with caution when projecting.\n"
        )
    if calib_full is not None and (calib_full["year"] == 2020).any():
        c20 = calib_full.loc[calib_full["year"] == 2020].iloc[0]
        lines.append(
            f"- **2020 calibration row** (observed {c20['observed_hazard']:.4%} vs predicted "
            f"{c20['predicted_hazard']:.4%} monthly): the champion scores straight through the "
            "forbearance window with pre-COVID coefficients; the April-2020 state UER jumps "
            f"(~+10pp month-on-month) enter `delta_uer_lag1` (coef {float(champion.params['delta_uer_lag1']):+.3f}, "
            "i.e. ~+7 on the linear predictor) and saturate the cloglog. Macro extrapolation, not a "
            "data or code error -- the regime treatments in Section 3 exist precisely for this.\n"
        )

    lines.append("\n## 5. Stability check (second seed) & WESML inference caveat\n")
    max_rel = stability["rel_diff"].max()
    max_rel_term = str(stability.loc[stability["rel_diff"].idxmax(), "term"])
    n_flips = int((np.sign(stability["coef_seed_a"]) != np.sign(stability["coef_seed_b"])).sum())
    stab = stability.set_index("term")
    bse = champion.result.bse
    du_sw = float(stab.loc["delta_uer_lag1", "abs_diff"])
    du_se = float(bse["delta_uer_lag1"])
    hpi_sw = float(stab.loc["hpi_growth_lag1", "abs_diff"])
    hpi_se = float(bse["hpi_growth_lag1"])
    lines.append(
        f"Refit on an independent control-sample seed ({SEED_B} vs {SEED_A}): sign flips = "
        f"{n_flips}; max relative coefficient difference = {max_rel:.3f}, on `{max_rel_term}` "
        "(a near-zero coefficient, where a relative measure overstates) "
        "(`outputs/freddie/hazard/seed_stability.csv`).\n\n"
        f"Macro-term absolute swings between seeds: `delta_uer_lag1` {du_sw:.3f} vs nominal SE "
        f"{du_se:.4f} (~{du_sw / du_se:.1f}x), `hpi_growth_lag1` {hpi_sw:.3f} vs nominal SE "
        f"{hpi_se:.4f} (~{hpi_sw / hpi_se:.1f}x). This is the expected WESML caveat, stated "
        "honestly: `freq_weights` scales the 5% control subsample back to population size, so the "
        "reported SEs/p-values approximate a FULL-population fit and exclude the Monte-Carlo noise "
        "of which controls were sampled (Manski-Lerman point estimates are consistent; their "
        "asymptotic variance needs a sandwich that this exhibit does not report). For macro terms, "
        "read `seed_stability.csv` -- not the nominal p-values -- as the operative uncertainty "
        "statement; all substantive conclusions here rest on signs and magnitudes that dwarf both "
        "noise measures.\n"
    )

    lines.append("\n## 6. Simplifications (declared)\n")
    lines.append(
        "- Only the DEFAULT (D90) cause-specific hazard is fit; no competing-risk prepayment hazard "
        "in this refit (unlike the DCR champion's dual-hazard framing).\n"
        "- No double-trigger (LTV x UER) interaction term (the spec's covariate-family list for this "
        "refit omits it).\n"
        "- Case-control (WESML) subsampling of control rows at "
        f"{CONTROL_SAMPLE_RATE:.0%} rather than a full-population fit (39.5M rows is impractical to "
        "fit directly in this environment's memory budget); every event row is always kept.\n"
        "- Reference-row seasoning curve uses champion-train MEDIAN covariates, not a fitted "
        "population-average marginal effect.\n"
        "- COVID three-way comparison uses an extended estimation window (through 2021-09) rather "
        "than the champion's train window, because COVID postdates champion-train entirely -- "
        "documented above.\n"
    )

    (OUT_DIR / "hazard_report.md").write_text("".join(lines))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="ignore cached model-frame/champion/COVID artifacts and rebuild everything from scratch",
    )
    args = parser.parse_args()
    main(refresh=args.refresh)
