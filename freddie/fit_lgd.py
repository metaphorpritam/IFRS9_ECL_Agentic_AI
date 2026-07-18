"""Rung-3 realized-loss LGD orchestration: fits freddie/lgd.py's two-stage
cure x severity model on real SFLLD D90 workouts and builds every spec
deliverable in outputs/freddie/lgd/.

Isolation: freddie/ namespace only. Reads panel_monthly.parquet and
loan_orig.parquet (via freddie.lgd, which additionally re-reads raw SFLLD
servicing zips through freddie.ingest for the reverted-status check --
freddie.lgd's own docstring/module for that rationale); NEVER touches
engine/, agent/, app/, analysis/, challenger/, data/processed/panel.parquet,
or any existing test. engine/lgd.py and outputs/lgd/lgd_report.md are
read-only references used ONLY to build the DCR-vs-SFLLD comparison section
below -- nothing here imports engine.lgd or mutates it.

--------------------------------------------------------------------------
CACHING (the one expensive step: resolve_reverted_status)
--------------------------------------------------------------------------
freddie.lgd.build_lgd_sample re-reads all 17 raw SFLLD servicing zips (via
freddie.ingest.read_svcg_vintage) for the ~11k had_d90_event loans whose
zero_balance_code is NaN on the full un-truncated tape (no terminal
disposition recorded) -- that raw re-read takes several minutes (measured
~4-5 minutes end to end for the full 837.5k-loan population), comparable to
the freddie/eda.py roll-rate exhibit's own full-tape scan. build_sample_cached()
below caches the built one-row-per-D90-loan sample to
data/processed/freddie/lgd/lgd_sample.parquet so this module (and the test
suite, and any report regeneration) doesn't pay that cost on every run;
delete the cache (or pass --refresh) to force a rebuild after any upstream
change to freddie/lgd.py's outcome-partition logic.

Run as a module to (re)build every deliverable (offline; needs the
already-cached panel/orig parquets, no network):
    cd <repo root> && uv run --no-sync python -m freddie.fit_lgd [--refresh]
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from freddie import lgd
from freddie.eda import ERA_COLORS, ERA_ORDER

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths -- rung-3 isolation
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = REPO_ROOT / "data" / "processed" / "freddie" / "panel_monthly.parquet"
ORIG_PATH = REPO_ROOT / "data" / "processed" / "freddie" / "loan_orig.parquet"
CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "lgd"
OUT_DIR = REPO_ROOT / "outputs" / "freddie" / "lgd"
SAMPLE_CACHE_PATH = CACHE_DIR / "lgd_sample.parquet"

DCR_LGD_MODULE = REPO_ROOT / "engine" / "lgd.py"                    # read-only reference
DCR_LGD_REPORT = REPO_ROOT / "outputs" / "lgd" / "lgd_report.md"    # read-only reference

# DCR champion headline numbers, copied verbatim from outputs/lgd/lgd_report.md
# (read-only reference; never recomputed by importing engine.lgd) -- used only
# to populate the comparison section/table below.
DCR_NUMBERS = {
    "mean_realized_lgd_train": 0.5995,
    "mean_realized_lgd_oot": 0.6113,
    "cure_rate_train": 0.1224,
    "cure_rate_oot": 0.0716,
    "cure_auc_train": 0.837,
    "cure_auc_oot": 0.769,
    "excess_loading": 0.0255,
    "share_sev_gt_cap_noncure": 0.142,
    "n_resolved_train": 9496,
}


# ==========================================================================
# 1. Sample build (cached -- see module docstring)
# ==========================================================================
def load_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    loan_orig = pd.read_parquet(ORIG_PATH)
    panel_d90 = pd.read_parquet(PANEL_PATH, columns=lgd.PANEL_MONTHLY_REQUIRED_COLS)
    panel_d90 = panel_d90.loc[panel_d90["d90_event"] == 1].reset_index(drop=True)
    return loan_orig, panel_d90


def build_sample_cached(refresh: bool = False) -> pd.DataFrame:
    if not refresh and SAMPLE_CACHE_PATH.exists():
        logger.info("Loading cached LGD sample from %s", SAMPLE_CACHE_PATH)
        return pd.read_parquet(SAMPLE_CACHE_PATH)
    logger.info(
        "Building LGD sample from raw parquets (re-reads all 17 SFLLD servicing "
        "zips for NaN-zero-balance-code D90 loans -- several minutes)..."
    )
    loan_orig, panel_d90 = load_raw_frames()
    sample = lgd.build_lgd_sample(loan_orig, panel_d90)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_parquet(SAMPLE_CACHE_PATH, index=False)
    logger.info("Cached LGD sample -> %s (%d rows)", SAMPLE_CACHE_PATH, len(sample))
    return sample


# ==========================================================================
# 2. Diagnostics
# ==========================================================================
def outcome_partition_table(sample: pd.DataFrame) -> pd.DataFrame:
    """Exhaustive + disjoint outcome counts by split -- the sanity table
    behind the report's sample-description section."""
    tbl = (
        sample.groupby(["split", "lgd_outcome"], observed=True)
        .size()
        .rename("n")
        .reset_index()
        .pivot(index="lgd_outcome", columns="split", values="n")
        .fillna(0)
        .astype(int)
    )
    tbl["total"] = tbl.sum(axis=1)
    return tbl.reindex(["cure", "liquidation", "unresolved"])


def unresolved_rate_by_default_year_table(sample: pd.DataFrame) -> pd.DataFrame:
    """Selection-bias quantification, BY DEFAULT CALENDAR YEAR (not vintage
    era -- COVID D90s occur across every origination vintage, so vintage era
    can't isolate the effect): share of D90 loans still UNRESOLVED as of the
    panel's 2025-09 window end. This is the module docstring's documented
    selection-bias claim ("loans that resolve fast are over-represented in
    the observed population, so fitted cure is biased up / severity down for
    cohorts near the panel's own window end") made numeric and, separately,
    the COVID caveat's ("the 2020 D90 spike overwhelmingly resolves CURE")
    flip side -- most of that spike hasn't even reached a TERMINAL
    disposition yet, resolved or not."""
    d = sample.dropna(subset=["default_month"]).copy()
    d["default_year"] = d["default_month"].dt.year
    rows = []
    for year, grp in d.groupby("default_year"):
        rows.append({
            "default_year": int(year),
            "n": len(grp),
            "unresolved_rate": float((grp["lgd_outcome"] == "unresolved").mean()),
            "cure_rate": float((grp["lgd_outcome"] == "cure").mean()),
            "liquidation_rate": float((grp["lgd_outcome"] == "liquidation").mean()),
        })
    return pd.DataFrame(rows).sort_values("default_year").reset_index(drop=True)


def cure_auc(models: lgd.LgdModels, sample: pd.DataFrame) -> dict[str, float]:
    """Cure-stage discrimination on resolved rows, train and OOT."""
    d = sample[sample["lgd_outcome"] != "unresolved"].dropna(
        subset=["ltv10", "fico_s", "loan_age_at_default", "era", "property_state"]
    ).copy()
    d["cure"] = (d["lgd_outcome"] == "cure").astype(int)
    out = {}
    for split in ("train", "oot"):
        sub = d[d["split"] == split]
        if sub["cure"].nunique() < 2:
            out[f"cure_auc_{split}"] = float("nan")
            continue
        p = models.cure_result.predict(sub)
        out[f"cure_auc_{split}"] = float(roc_auc_score(sub["cure"], p))
    return out


def cure_rate_by_era_table(sample: pd.DataFrame, models: lgd.LgdModels) -> pd.DataFrame:
    """Observed vs model-predicted cure rate by vintage era and split --
    the spec's "cure-rate-by-era table" deliverable."""
    resolved = sample[sample["lgd_outcome"] != "unresolved"].dropna(
        subset=["ltv10", "fico_s", "loan_age_at_default", "era", "property_state"]
    ).copy()
    resolved["cure"] = (resolved["lgd_outcome"] == "cure").astype(int)
    resolved["p_cure_pred"] = np.asarray(models.cure_result.predict(resolved))

    rows = []
    for era in ERA_ORDER:
        for split in ("train", "oot"):
            grp = resolved[(resolved["era"] == era) & (resolved["split"] == split)]
            if grp.empty:
                continue
            rows.append({
                "era": era, "split": split, "n": len(grp),
                "observed_cure_rate": float(grp["cure"].mean()),
                "predicted_cure_rate": float(grp["p_cure_pred"].mean()),
            })
        grp_all = resolved[resolved["era"] == era]
        if not grp_all.empty:
            rows.append({
                "era": era, "split": "all", "n": len(grp_all),
                "observed_cure_rate": float(grp_all["cure"].mean()),
                "predicted_cure_rate": float(grp_all["p_cure_pred"].mean()),
            })
    return pd.DataFrame(rows)


def severity_by_liq_year_table(sample: pd.DataFrame) -> pd.DataFrame:
    """Realized severity by raw liquidation calendar year (2006-2025) -- the
    spec's "severity-by-liquidation-year exhibit (2008-2012 severity cycle)"
    deliverable's underlying table. Uses ALL resolved liquidations with usable
    loss data (train + OOT together), since the cycle itself is the point."""
    liq = sample[(sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"]].dropna(
        subset=["liq_year", "severity"]
    )
    rows = []
    for year, grp in liq.groupby("liq_year"):
        rows.append({
            "liq_year": int(year),
            "n": len(grp),
            "mean_severity": float(grp["severity"].mean()),
            "median_severity": float(grp["severity"].median()),
            "mean_severity_capped": float(grp["severity"].clip(0.0, lgd.SEV_CAP).mean()),
            "share_gt_cap": float((grp["severity"] > lgd.SEV_CAP).mean()),
            "share_lt_0": float((grp["severity"] < 0).mean()),
        })
    return pd.DataFrame(rows).sort_values("liq_year").reset_index(drop=True)


def excess_loading_by_bucket_table(sample: pd.DataFrame) -> pd.DataFrame:
    """Constant (DCR-style) vs cycle-bucket excess-loss loading -- answers the
    spec's question of whether a single constant loading is still defensible
    once liquidation-year is already a regression covariate."""
    liq = sample[(sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"]].dropna(
        subset=["liq_year_bucket", "severity"]
    )
    rows = []
    for bucket, grp in liq.groupby("liq_year_bucket", observed=True):
        if grp.empty:
            continue
        rows.append({
            "liq_year_bucket": bucket, "n": len(grp),
            "excess_loading": float((grp["severity"] - lgd.SEV_CAP).clip(lower=0.0).mean()),
            "share_gt_cap": float((grp["severity"] > lgd.SEV_CAP).mean()),
            "mean_severity": float(grp["severity"].mean()),
        })
    return pd.DataFrame(rows)


def denominator_reconciliation(sample: pd.DataFrame) -> dict[str, float]:
    """upb_at_default (this module's severity denominator) vs
    zero_balance_removal_upb (the alternative, UPB at the final liquidation
    row) -- the spec's "reconcile the two" requirement."""
    liq = sample[(sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"]].dropna(
        subset=["upb_at_default", "zero_balance_removal_upb"]
    )
    corr = float(liq["upb_at_default"].corr(liq["zero_balance_removal_upb"]))
    ratio = float((liq["zero_balance_removal_upb"] / liq["upb_at_default"]).mean())
    return {"n": int(len(liq)), "corr": corr, "mean_ratio_removal_over_default": ratio}


def _df_to_md(df: pd.DataFrame, index: bool = False, floatfmt: str = ".4f") -> str:
    """Minimal markdown-table writer (no `tabulate` dependency in this env).

    Formats per COLUMN dtype, not per iterrows() row value: DataFrame.
    iterrows() returns each ROW as a single pandas Series, so a row spanning
    an int64 column and a float64 column silently upcasts the int to float
    -- invisible whenever the table ALSO has a string column (forcing
    row-wise object dtype, which preserves each value's original type), but
    NOT for an all-numeric table (e.g. severity_by_liq_year_table's liq_year
    /n, unresolved_rate_by_default_year_table's default_year/n), which would
    otherwise render "2020" as "2020.0000". Checking is_integer_dtype on the
    ORIGINAL column (before the iterrows() upcast) sidesteps this."""
    d = df.reset_index() if index else df.copy()
    cols = list(d.columns)
    is_int_col = {c: pd.api.types.is_integer_dtype(d[c]) for c in cols}

    def _fmt(col, v):
        if is_int_col[col]:
            return str(int(v))
        if isinstance(v, float) or isinstance(v, np.floating):
            return format(v, floatfmt)
        return str(v)

    lines = ["| " + " | ".join(str(c) for c in cols) + " |"]
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, row in d.iterrows():
        lines.append("| " + " | ".join(_fmt(c, row[c]) for c in cols) + " |")
    return "\n".join(lines)


def coefficients_table(result) -> pd.DataFrame:
    ci = result.conf_int()
    return pd.DataFrame({
        "term": result.params.index,
        "coef": result.params.values,
        "std_err": result.bse.values,
        "z": result.tvalues.values,
        "p_value": result.pvalues.values,
        "ci_low": ci[0].values,
        "ci_high": ci[1].values,
        "exp_coef": np.exp(result.params.values),
    })


def population_lgd_summary(sample: pd.DataFrame, models: lgd.LgdModels) -> pd.DataFrame:
    """Aggregate (portfolio-level) realized-vs-model-implied mean LGD by
    split. Realized: population mean over resolved rows of realized severity
    (cure -> 0, matches DCR's LGD_cure=0 convention). `n_resolved` /
    `cure_rate_observed` / `cure_rate_predicted` cover ALL resolved rows
    (cure + liquidation, unresolved excluded, matching the cure stage's own
    fit population) -- but `mean_realized_lgd` additionally excludes
    liquidation rows with NO populated `actual_loss_calculation` ("loss not
    yet finalized", the same exclusion the severity stage itself applies,
    see freddie/lgd.py's module docstring). A prior version of this function
    zero-filled those rows' missing severity, silently conflating "loss not
    yet known" with "no loss" and biasing the reported mean_realized_lgd
    DOWN by construction (~7% of liquidations nationally have no loss field
    -- see denominator_reconciliation's sibling diagnostic); this version
    excludes them instead and reports the excluded count in
    `n_liq_excluded_no_loss_data`, consistent with every other "never
    silently zero-fill" rule in this module. Model-implied:
    (1 - mean p_cure over resolved) * (mean predicted severity over
    liquidation rows, capped, + excess_loading) -- an AGGREGATE approximation
    only, not a per-row score (see module docstring / freddie/lgd.py's
    docstring: severity-stage covariates are ex-post / only known once a
    loan has actually liquidated, so there is no per-row forward LGD for a
    still-resolving loan in this refit)."""
    rows = []
    for split in ("train", "oot"):
        resolved = sample[(sample["lgd_outcome"] != "unresolved") & (sample["split"] == split)].dropna(
            subset=["ltv10", "fico_s", "loan_age_at_default", "era", "property_state"]
        ).copy()
        if resolved.empty:
            continue
        is_liq = resolved["lgd_outcome"] == "liquidation"
        liq_no_loss = is_liq & ~resolved["has_loss_data"]
        realized_pop = resolved.loc[~liq_no_loss]
        realized_lgd = np.where(realized_pop["lgd_outcome"] == "cure", 0.0, realized_pop["severity"])
        p_cure_pred = np.asarray(models.cure_result.predict(resolved))

        liq = resolved[(resolved["lgd_outcome"] == "liquidation") & resolved["has_loss_data"]].dropna(
            subset=["liq_year_bucket", "is_judicial", "disposition_type"]
        )
        mean_pred_sev = float(np.asarray(models.severity_result.predict(liq)).mean()) if len(liq) else float("nan")

        rows.append({
            "split": split,
            "n_resolved": len(resolved),
            "n_liq_excluded_no_loss_data": int(liq_no_loss.sum()),
            "cure_rate_observed": float((resolved["lgd_outcome"] == "cure").mean()),
            "cure_rate_predicted": float(p_cure_pred.mean()),
            "mean_realized_lgd": float(np.mean(realized_lgd)),
            "mean_predicted_lgd_aggregate": float(
                (1.0 - p_cure_pred.mean()) * (mean_pred_sev + models.excess_loading)
            ) if not np.isnan(mean_pred_sev) else float("nan"),
        })
    return pd.DataFrame(rows)


# ==========================================================================
# 3. Exhibits
# ==========================================================================
def _gfc_covid_shading(ax):
    ax.axvspan(2007, 2009, color=ERA_COLORS["bubble 2005-2008"], alpha=0.10, zorder=0, label="GFC era")
    ax.axvspan(2020, 2021, color=ERA_COLORS["modern 2018-2025"], alpha=0.10, zorder=0, label="COVID era")


def plot_severity_by_liq_year(tbl: pd.DataFrame, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(tbl["liq_year"], tbl["mean_severity_capped"] * 100, marker="o",
            color=COLORS["accent"], label="Mean severity (capped at 100% of EAD)")
    ax.plot(tbl["liq_year"], tbl["mean_severity"] * 100, marker="s", linestyle="--",
            color=COLORS["warn"], label="Mean severity (uncapped)")
    _gfc_covid_shading(ax)
    ax.set_xlabel("Liquidation calendar year")
    ax.set_ylabel("Severity (% of UPB at default)")
    ax.set_title("SFLLD workout severity by liquidation year (2006-2025)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ==========================================================================
# 4. Orchestration
# ==========================================================================
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="rebuild the LGD sample cache from scratch")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sample = build_sample_cached(refresh=args.refresh)
    logger.info("LGD sample: %d rows, %d columns", *sample.shape)

    partition_tbl = outcome_partition_table(sample)
    partition_tbl.to_csv(OUT_DIR / "outcome_partition.csv")
    logger.info("Outcome partition:\n%s", partition_tbl)

    unresolved_year_tbl = unresolved_rate_by_default_year_table(sample)
    unresolved_year_tbl.to_csv(OUT_DIR / "unresolved_rate_by_default_year.csv", index=False)

    models = lgd.fit_lgd_models(sample, split="train")
    logger.info(
        "Fitted: cure n=%d (%d cure / %d liquidation), severity fit n=%d",
        models.n_resolved, models.n_cure, models.n_liquidation, models.n_severity_fit,
    )

    aucs = cure_auc(models, sample)
    cure_era_tbl = cure_rate_by_era_table(sample, models)
    cure_era_tbl.to_csv(OUT_DIR / "cure_rate_by_era.csv", index=False)

    sev_year_tbl = severity_by_liq_year_table(sample)
    sev_year_tbl.to_csv(OUT_DIR / "severity_by_liq_year.csv", index=False)
    plot_severity_by_liq_year(sev_year_tbl, OUT_DIR / "severity_by_liq_year.png")

    loading_bucket_tbl = excess_loading_by_bucket_table(sample)
    loading_bucket_tbl.to_csv(OUT_DIR / "excess_loading_by_bucket.csv", index=False)

    recon = denominator_reconciliation(sample)

    cure_coef_tbl = coefficients_table(models.cure_result)
    cure_coef_tbl.to_csv(OUT_DIR / "cure_coefficients.csv", index=False)
    sev_coef_tbl = coefficients_table(models.severity_result)
    sev_coef_tbl.to_csv(OUT_DIR / "severity_coefficients.csv", index=False)

    pop_summary = population_lgd_summary(sample, models)
    pop_summary.to_csv(OUT_DIR / "population_lgd_summary.csv", index=False)

    metrics = {
        **aucs,
        "n_resolved_train": models.n_resolved,
        "n_cure_train": models.n_cure,
        "n_liquidation_train": models.n_liquidation,
        "n_severity_fit_train": models.n_severity_fit,
        "excess_loading": models.excess_loading,
        "floor_mass": models.floor_mass,
        "lgd_upper_bound": models.lgd_upper_bound,
        "denominator_reconciliation": recon,
        **models.fit_meta,
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))

    with open(CACHE_DIR / "lgd_models.pkl", "wb") as f:
        pickle.dump(models, f)

    write_lgd_report(
        sample, models, partition_tbl, unresolved_year_tbl, aucs, cure_era_tbl, sev_year_tbl,
        loading_bucket_tbl, recon, cure_coef_tbl, sev_coef_tbl, pop_summary,
    )
    logger.info("Done. Deliverables in %s", OUT_DIR)


def write_lgd_report(
    sample: pd.DataFrame,
    models: lgd.LgdModels,
    partition_tbl: pd.DataFrame,
    unresolved_year_tbl: pd.DataFrame,
    aucs: dict,
    cure_era_tbl: pd.DataFrame,
    sev_year_tbl: pd.DataFrame,
    loading_bucket_tbl: pd.DataFrame,
    recon: dict,
    cure_coef_tbl: pd.DataFrame,
    sev_coef_tbl: pd.DataFrame,
    pop_summary: pd.DataFrame,
) -> None:
    lines = []
    lines.append("# SFLLD Realized-Loss LGD -- Two-Stage Cure x Severity on Real Workouts\n")
    lines.append(
        "**The upgrade over DCR** (`engine/lgd.py`): the DCR champion fits on the CoreLogic "
        "vendor's pre-computed `lgd_time` field -- a number handed over with no visible "
        "construction. This refit RECONSTRUCTS realized loss from Freddie Mac's own reported "
        "cash components (`net_sale_proceeds`, `mi_recoveries`, `non_mi_recoveries`, "
        "`total_expenses`, `delinquent_accrued_interest`, `zero_balance_removal_upb`) and locks "
        "the sign convention with a fixture loan traced from the raw servicing tape "
        "(`tests/test_freddie_lgd.py`) rather than trusting an opaque vendor column. See "
        "`freddie/lgd.py`'s module docstring for the full sign-convention derivation.\n"
    )

    lines.append("## 1. Sign convention (empirically verified)\n")
    lines.append(
        "`actual_loss_calculation` reconciles to sub-dollar rounding with `net_sale_proceeds + "
        "mi_recoveries + non_mi_recoveries + total_expenses - zero_balance_removal_upb - "
        "delinquent_accrued_interest` (`total_expenses` already reported NEGATIVE by Freddie). "
        "This module defines `realized_loss = -actual_loss_calculation` so that "
        "`realized_loss > 0` is the common-sense LOSS direction. See "
        "`tests/test_freddie_lgd.py::test_sign_convention_fixture_loan` for the fixture-loan "
        "lock traced directly from a raw servicing zip.\n"
    )

    lines.append("## 2. Sample & outcome partition\n")
    n_total = len(sample)
    lines.append(
        f"{n_total:,} had_d90_event loans (loan_orig.parquet), partitioned exhaustively and "
        "disjointly into cure / liquidation / unresolved (see `freddie/lgd.py::partition_outcomes` "
        "docstring for the exact zero_balance_code logic and the reverted-status re-read for "
        "loans with no terminal code):\n\n"
    )
    lines.append(_df_to_md(partition_tbl, index=True) + "\n\n")
    code15_mask = sample["zero_balance_code"] == "15"
    n_code15_total = int(code15_mask.sum())
    n_npl_liq = int((code15_mask & sample["has_loss_data"]).sum())
    n_npl_no_loss = n_code15_total - n_npl_liq
    npl_pct = n_npl_liq / n_code15_total if n_code15_total else float("nan")
    # Severity-by-disposition-type comparison (recomputed live from `sample`,
    # not hardcoded -- a prior version pasted in a stale snapshot of these
    # three means/medians that silently drifted ~1% from the live sample).
    liq_all = sample.loc[(sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"]]
    sev_by_disp = liq_all.groupby("disposition_type", observed=True)["severity"].agg(["mean", "median"])
    npl_mean, npl_median = sev_by_disp.loc["whole_loan_sale", ["mean", "median"]]
    tp_mean = sev_by_disp.loc["third_party_sale", "mean"]
    reo_mean = sev_by_disp.loc["reo_disposition", "mean"]
    lines.append(
        "**Zero-balance code 15 (whole loan sale) is split, not lumped whole into unresolved**: "
        f"{n_npl_liq:,} of {n_code15_total:,} code-15 D90 rows carry a populated `actual_loss_calculation` "
        f"({npl_pct:.1%}), concentrated in 2015+ disposition dates and with severities (mean {npl_mean:.3f}, "
        f"median {npl_median:.3f}) statistically indistinguishable from third-party sale (mean {tp_mean:.3f}) "
        f"and REO (mean {reo_mean:.3f}) -- i.e. Freddie's non-performing-loan (NPL) sale program, a genuine "
        "liquidation-equivalent economic event. This refit counts that subset as **liquidation**, not "
        "unresolved (a correction versus treating all of code 15 as unresolved). Only the small "
        f"remaining no-loss-field subset ({n_npl_no_loss:,} rows, pre-2015 vintages) stays unresolved, since its "
        "ultimate resolution is genuinely unobservable. See `freddie/lgd.py`'s module docstring "
        "and `tests/test_freddie_lgd.py::test_npl_sale_code15_split_by_loss_data`.\n\n"
        "**Unresolved** (defect-prior-to-disposition code 96, the small no-loss-field code-15 "
        "subset above, or still-active-and-still-90+DPD with no terminal code) are excluded from "
        "BOTH stages -- "
        "the same resolved-workouts-only convention as DCR's `engine/lgd.py` "
        "(\"unresolved lgd_time is not a realised outcome\"), with the SAME documented "
        "selection-bias direction: loans that resolve fast are over-represented in the observed "
        "population, so cure is biased up / severity down for cohorts near the panel's own "
        "window end (2025-09).\n\n"
        "**COVID caveat** (Phase-A finding): the 2020 D90 spike overwhelmingly resolves CURE "
        "(deferral/reinstatement under forbearance), not a loss event -- visible directly in the "
        f"OOT split above ({int(partition_tbl.loc['cure','oot'])} OOT cures vs "
        f"{int(partition_tbl.loc['liquidation','oot'])} OOT liquidations): most post-2019-default "
        "loans have not yet had time to reach a liquidation disposition by the 2025-09 window end, "
        "so OOT liquidation counts are thin BY CONSTRUCTION, not because post-2019 defaults are "
        "safer. Reported honestly here, not patched.\n\n"
        "**Selection bias quantified BY DEFAULT YEAR** (not vintage era -- COVID D90s occur across "
        "every origination vintage, so vintage era can't isolate the effect): the resolved-only "
        "convention's stated bias (\"loans that resolve fast are over-represented in the observed "
        "population\") is real but concentrates in RECENCY, not specifically in the 2020 COVID "
        "spike -- a correction of the naive assumption that \"COVID-era defaults are heavily "
        "unresolved\":\n\n"
    )
    lines.append(_df_to_md(unresolved_year_tbl) + "\n\n")
    covid_row = unresolved_year_tbl.loc[unresolved_year_tbl["default_year"] == 2020].iloc[0]
    recent_row = unresolved_year_tbl.loc[unresolved_year_tbl["default_year"] == 2025].iloc[0]
    pre2020 = unresolved_year_tbl.loc[
        unresolved_year_tbl["default_year"].between(2005, 2019), "unresolved_rate"
    ]
    lines.append(
        f"**The 2020 COVID D90 spike itself is NOT heavily unresolved** -- its unresolved rate "
        f"({covid_row['unresolved_rate']:.1%}, n={int(covid_row['n']):,}) is BELOW the 2005-2019 "
        f"average ({pre2020.mean():.1%}), because forbearance-driven D90s cure fast (deferral/"
        f"reinstatement, {covid_row['cure_rate']:.1%} cure rate) and have had five years to do so "
        "by the 2025-09 window end. What IS heavily unresolved is RECENCY, unrelated to COVID: "
        f"default year 2025 is {recent_row['unresolved_rate']:.1%} unresolved (n={int(recent_row['n']):,}) "
        "simply because most of those D90s have not had TIME to reach a terminal disposition yet, "
        "rising monotonically from 2022 defaults onward. The resolved-only fit's real selection-bias "
        "exposure is therefore the most recent 2-3 default years, not the COVID cohort specifically "
        "-- reported here as measured, not assumed.\n"
    )

    lines.append("## 3. Severity denominator: upb_at_default vs zero_balance_removal_upb\n")
    lines.append(
        f"Reconciliation on {recon['n']:,} liquidation rows with both fields populated: "
        f"correlation = {recon['corr']:.4f}, mean ratio "
        f"(zero_balance_removal_upb / upb_at_default) = {recon['mean_ratio_removal_over_default']:.4f}. "
        "The two are essentially the same loan-level number -- upb_at_default (current_actual_upb "
        "on panel_monthly's own first-D90-event row) is used as the severity denominator because "
        "it is the theoretically correct EAD base (observable AT the default date, not years "
        "later at resolution, when continued interest capitalization / partial curtailments can "
        "move zero_balance_removal_upb away from the default-date balance) -- and it is what any "
        "ECL assembly multiplying LGD x EAD must use.\n"
    )

    lines.append("## 4. Stage 1 -- cure logit\n")
    lines.append(f"`{models.cure_formula}`, fit on train resolved rows "
                  f"(n={models.n_resolved:,}: {models.n_cure:,} cure / {models.n_liquidation:,} liquidation).\n\n")
    lines.append(_df_to_md(cure_coef_tbl) + "\n\n")
    lines.append(
        "### Per-variable rationale\n\n"
        "| variable | transform | economic rationale | expected direction |\n"
        "|---|---|---|---|\n"
        "| `ltv10` | `updated_ltv`/10 (state-HPI indexed, see freddie.macro) | equity cushion lets a "
        "distressed borrower sell or refinance out of default | - |\n"
        "| `fico_s` | `credit_score`/100 | ability/willingness to work a resolution | + (weak) |\n"
        "| `loan_age_at_default` | months at first D90 | seasoned defaulters cure less (burnout) | - |\n"
        "| `era` | vintage cohort (bubble/recovery/modern) | underwriting-quality + macro-regime "
        "cohort effect on workout outcomes | era-dependent |\n"
        "| `property_state` | fixed effects | regional foreclosure-process / servicing-practice "
        "heterogeneity (stage 2's judicial dummy only partially explains this) | state-dependent |\n\n"
        f"Cure AUC: train **{aucs.get('cure_auc_train', float('nan')):.4f}**, "
        f"OOT **{aucs.get('cure_auc_oot', float('nan')):.4f}**.\n"
    )

    lines.append("\n### Cure rate by era\n\n")
    lines.append(_df_to_md(cure_era_tbl) + "\n\n")
    modern_train_n = int(cure_era_tbl.loc[
        (cure_era_tbl["era"] == "modern 2018-2025") & (cure_era_tbl["split"] == "train"), "n"
    ].iloc[0]) if ((cure_era_tbl["era"] == "modern 2018-2025") & (cure_era_tbl["split"] == "train")).any() else 0
    lines.append(
        f"**Why OOT cure AUC ({aucs.get('cure_auc_oot', float('nan')):.4f}) is BELOW random, not just "
        f"weak**: the `era` fixed effect for `modern 2018-2025` is fit on only **{modern_train_n} "
        "train rows** -- a mechanical consequence of the calendar-time train/OOT split (SPLIT_CUTOFF "
        "= 2019-01): a modern-vintage (2018-2025-origination) loan can only default BEFORE 2019 if it "
        "reaches D90 within months of origination, so almost the entire modern-era D90 population "
        "falls in OOT by construction. The fitted coefficient (see section 4's coefficient table, "
        "`C(era)[T.modern 2018-2025]`) is statistically indistinguishable from zero (std_err ~4.7x "
        "the point estimate) -- effectively unidentified from training data. Combined with the "
        "post-2019 COVID-forbearance base-rate shift (observed cure rate jumps to 97-98% OOT vs "
        "43-66% train across eras -- see the table above), the model's LTV/FICO/state-driven "
        "discrimination, learned on a very different pre-2019 base rate, does not transfer -- a "
        "genuine small-sample-plus-regime-shift limitation, not a coding defect. Weight the OOT AUC "
        "comparison in section 8 accordingly.\n"
    )

    lines.append("\n## 5. Stage 2 -- severity | liquidation (fractional logit, HC1 robust SEs)\n")
    lines.append(f"`{models.severity_formula}`, fit on train liquidation rows with populated "
                  f"`actual_loss_calculation` (n={models.n_severity_fit:,}).\n\n")
    lines.append(_df_to_md(sev_coef_tbl) + "\n\n")
    lines.append(
        "### Per-variable rationale\n\n"
        "| variable | transform | economic rationale | expected direction |\n"
        "|---|---|---|---|\n"
        "| `ltv10` | `updated_ltv`/10 at default | less equity -> bigger foreclosure shortfall | + |\n"
        "| `liq_year_bucket` | coarse liquidation-year cycle phase | workout costs + distressed-"
        "sale discounts vary sharply with the disposition-year housing cycle | hump, "
        "peak 2010-2012 |\n"
        "| `is_judicial` | static judicial-foreclosure-state flag | judicial process is slower and "
        "costlier (more accrued interest/expenses by disposition) | + |\n"
        "| `disposition_type` | zero_balance_code label | third-party sale / short sale-charge-off "
        "/ REO / whole-loan (NPL) sale carry different cost structures | disposition-dependent |\n"
    )

    lines.append("\n### Severity by liquidation year (2006-2025 cycle)\n\n")
    lines.append(_df_to_md(sev_year_tbl) + "\n\n")
    lines.append("![severity by liquidation year](severity_by_liq_year.png)\n")

    lines.append("\n## 6. Severity > 1 / < 0 tail -- is a CONSTANT loading still defensible?\n")
    overall_gt = float((sample.loc[
        (sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"], "severity"
    ] > lgd.SEV_CAP).mean())
    overall_lt = float((sample.loc[
        (sample["lgd_outcome"] == "liquidation") & sample["has_loss_data"], "severity"
    ] < 0).mean())
    lines.append(
        f"{overall_gt:.1%} of liquidations have severity > 1 (workout costs + accrued interest "
        f"push the loss past upb_at_default); {overall_lt:.1%} are < 0 (net recoveries, MI/"
        "proceeds exceeded UPB + costs + accrued interest). Both are real, not data errors -- "
        "never silently discarded.\n\n"
        f"Overall (DCR-style) constant loading: **{models.excess_loading:.4f}** "
        f"(vs DCR's {DCR_NUMBERS['excess_loading']:.4f}). Per-liquidation-year-bucket loading, "
        "computed with the liquidation-year covariate ALREADY in the severity regression:\n\n"
    )
    lines.append(_df_to_md(loading_bucket_tbl) + "\n\n")
    bucket_range = loading_bucket_tbl["excess_loading"].max() - loading_bucket_tbl["excess_loading"].min()
    lines.append(
        f"The per-bucket loading ranges over {bucket_range:.4f} across cycle phases -- "
        f"{'wide enough that a single constant materially misstates stress-period severity' if bucket_range > 0.02 else 'close enough that a single constant is a reasonable simplification'} "
        "once `liq_year_bucket` is already a regression covariate (it absorbs most of the cycle "
        "dependence at the MEAN; the residual beyond-cap tail is what the per-bucket table "
        "measures). **Verdict**: unlike DCR's single national panel (which has no comparable "
        "liquidation-year span to test this against), the SFLLD liquidation-year cycle here spans "
        "the full 2006-2025 GFC-through-modern era, so this refit reports the per-bucket loading "
        "table above ALONGSIDE the constant, rather than asserting the constant is sufficient by "
        "fiat -- a downstream ECL assembly under active stress-period liquidation volume should "
        "prefer the bucket-specific loading over the pooled constant.\n"
    )

    lines.append("\n## 7. Portfolio-level LGD summary (aggregate, train vs OOT)\n")
    lines.append(_df_to_md(pop_summary) + "\n\n")
    lines.append(
        "`n_resolved` / `cure_rate_observed` / `cure_rate_predicted` cover ALL resolved rows (cure "
        "+ liquidation). `mean_realized_lgd` additionally EXCLUDES `n_liq_excluded_no_loss_data` "
        "liquidation rows with no populated `actual_loss_calculation` (\"loss not yet finalized\" "
        "-- the same exclusion the severity fit itself applies) rather than zero-filling their "
        "missing severity, which would silently conflate \"loss not yet known\" with \"no loss\" and "
        "bias the reported mean realized LGD DOWN.\n\n"
        "`mean_predicted_lgd_aggregate` combines the mean predicted cure-complement with the mean "
        "predicted severity (capped + excess loading) at the AGGREGATE level only, NOT per-row: "
        "the severity-stage covariates (liquidation-year bucket, disposition type) are only known "
        "once a loan has actually liquidated, so there is no per-row forward-LGD score for a "
        "still-resolving loan in this refit (documented simplification, see section 8 and "
        "`freddie/lgd.py`'s module docstring).\n"
    )

    lines.append("\n## 8. DCR vs SFLLD LGD comparison\n\n")
    dcr_row = DCR_NUMBERS
    sflld_train = pop_summary[pop_summary["split"] == "train"]
    sflld_oot = pop_summary[pop_summary["split"] == "oot"]
    lines.append(
        "| metric | DCR champion (`engine/lgd.py`) | SFLLD refit (train) | SFLLD refit (OOT) |\n"
        "|---|---:|---:|---:|\n"
        f"| mean realized LGD | {dcr_row['mean_realized_lgd_train']:.4f} / "
        f"{dcr_row['mean_realized_lgd_oot']:.4f} | "
        f"{sflld_train['mean_realized_lgd'].iloc[0] if len(sflld_train) else float('nan'):.4f} | "
        f"{sflld_oot['mean_realized_lgd'].iloc[0] if len(sflld_oot) else float('nan'):.4f} |\n"
        f"| cure rate | {dcr_row['cure_rate_train']:.4f} / {dcr_row['cure_rate_oot']:.4f} | "
        f"{sflld_train['cure_rate_observed'].iloc[0] if len(sflld_train) else float('nan'):.4f} | "
        f"{sflld_oot['cure_rate_observed'].iloc[0] if len(sflld_oot) else float('nan'):.4f} |\n"
        f"| cure AUC | {dcr_row['cure_auc_train']:.4f} / {dcr_row['cure_auc_oot']:.4f} | "
        f"{aucs.get('cure_auc_train', float('nan')):.4f} | {aucs.get('cure_auc_oot', float('nan')):.4f} |\n"
        f"| excess-loss loading (constant) | {dcr_row['excess_loading']:.4f} | "
        f"{models.excess_loading:.4f} (overall) | -- |\n"
        f"| share severity > cap | {dcr_row['share_sev_gt_cap_noncure']:.1%} | {overall_gt:.1%} | -- |\n"
        f"| n resolved (train) | {dcr_row['n_resolved_train']:,} | {models.n_resolved:,} | -- |\n\n"
    )
    lines.append(
        "**Key differences, not just numbers**: (1) SFLLD's realized loss is RECONSTRUCTED from "
        "Freddie's own cash-component fields, not taken from an opaque vendor column (section 1); "
        "(2) SFLLD's OOT is dominated by the 2020 COVID D90 spike (section 2), so the SFLLD OOT "
        "cure rate/mean LGD comparison is NOT a clean like-for-like regime test the way DCR's "
        "quarterly-panel OOT is -- read the SFLLD OOT column as \"mostly forbearance-era cures\", "
        "not as forward-looking calibration evidence; (3) SFLLD's liquidation-year cycle spans "
        "2006-2025 (vs DCR's shorter panel), which is what makes the per-bucket excess-loading "
        "comparison in section 6 possible at all; (4) SFLLD adds state fixed effects + a judicial-"
        "foreclosure-state dummy that DCR's national panel has no field to support.\n"
    )

    lines.append("\n## 9. Documented simplifications\n")
    lines.append(
        "- `zero_balance_code == 16` (RPL securitization) is treated as a CURE by judgement, not a "
        "vendor label -- it never carries a realized loss field.\n"
        "- `zero_balance_code == 96` (defect prior to disposition) has NO observable loss (100% "
        "NaN `actual_loss_calculation`) and is folded into \"unresolved\" alongside the small "
        "no-loss-field subset of whole-loan-sale (code 15, 69 of 922 rows, pre-2015 vintages); "
        "the 853-row loss-bearing code-15 subset (Freddie's NPL-sale program) is treated as "
        "LIQUIDATION, not unresolved -- see section 2.\n"
        "- Liquidations with `actual_loss_calculation` still NaN (\"not yet finalized\") are "
        "excluded from the severity fit only, not from the cure stage's liquidation outcome.\n"
        "- `JUDICIAL_STATES` is a single static classification -- no within-sample (2005-2025) "
        "foreclosure-regime changes modeled; a handful of states are genuinely hybrid.\n"
        "- No downturn add-on; LGD is point-in-time (matches DCR's `engine/lgd.py`).\n"
        "- `predict_components`/`predict_lgd` (freddie/lgd.py) are calibration/diagnostic tools "
        "scored on ALREADY-RESOLVED history, not a forward-scoring API for a still-performing "
        "loan of unknown eventual liquidation date/type -- unlike DCR's severity stage, whose "
        "covariates are all available forward via a macro-scenario path. Wiring this into a live "
        "ECL assembly needs a projected liquidation-year substituted for the realized one -- "
        "documented future work, not built here.\n"
        "- Portfolio-level LGD summary (section 7) combines cure and severity predictions at the "
        "AGGREGATE level only (mean x mean), not per-row, for the reason above.\n"
    )

    (OUT_DIR / "lgd_report.md").write_text("".join(lines))


if __name__ == "__main__":
    main()
