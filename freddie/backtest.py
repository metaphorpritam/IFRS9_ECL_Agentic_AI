"""ALFRED-vintage HONEST backtest of the SFLLD champion hazard (rung 3).

Isolation: freddie/ namespace only. Reads panel_monthly.parquet, loan_orig.parquet,
the cached FINAL state_macro_panel.parquet (via freddie.macro), and pulls live
ALFRED (FRED real-time) macro vintages over the network on cache-miss. Reuses
freddie.fit_hazard's fitting machinery (BASE_FORMULA, fit_hazard, sample_case_control,
predict_hazard, HazardModel) verbatim -- NOT a re-derivation of the champion spec.
NEVER touches engine/, agent/, app/, analysis/, challenger/, or any existing test
file. outputs/freddie/lgd/cure_rate_by_era.csv is read READ-ONLY as a reference for
the COVID loss-non-materialization narrative in section 3 of the report below.

--------------------------------------------------------------------------
WHY THIS EXISTS -- THE MODEL-RISK QUESTION A CALENDAR-TIME OOT SPLIT CANNOT ANSWER
--------------------------------------------------------------------------
freddie/fit_hazard.py's champion/OOT split (train <= 2016-12, OOT >= 2017-01) is
a single fit, scored on later calendar time -- the standard machine-learning
generalisation test. It is NOT the IFRS-9 question. IFRS-9 asks: "if a bank had
been running THIS modelling approach live, refitting periodically as new data
arrived, using ONLY the macro data actually published by each date, how wrong
would its 12-month/lifetime ECL projections have been at each point in time?"
That requires re-fitting the SAME champion spec at several historical
"pseudo-reporting dates", using ONLY performance months <= that date and ONLY
macro vintages that existed as of that date (no lookahead into future macro
revisions OR future loan performance), then projecting forward and comparing
to what actually happened. This module is that exercise -- the capstone's
model-risk centerpiece, because it is the one exhibit that can show a model
being HONESTLY WRONG (the 2007-12 vintage model cannot see the GFC coming;
the point is to show BY HOW MUCH it misses, not to hide the miss).

--------------------------------------------------------------------------
RELATIONSHIP TO THE DCR VASICEK / SCENARIO-OVERLAY LAYER (connect the dots)
--------------------------------------------------------------------------
The DCR champion (engine/hazard.py + engine/scenario.py) is a POINT-IN-TIME
(PIT) hazard, IFRS-9-compliant only when paired with a forward-looking
overlay: base/adverse/severe macro paths (Vasicek-simulated or scenario-set)
multiplied through the PIT hazard to get a FORWARD-LOOKING ECL. The backtest
below is exactly that pairing, historicised: scenario (a) ("macro frozen at
last-known values") is the naive PIT extrapolation a bank would produce with
NO forward-looking overlay -- the failure mode IFRS-9 para 5.5.17 exists to
prevent. Scenario (b) ("actual realised macro", hindsight) is the ceiling a
PERFECT scenario overlay could have achieved -- it still is not perfect,
because it holds every OTHER covariate (LTV, in particular) frozen at its
last-known value; see SIMPLIFICATIONS. The gap between scenario (a) and
realised outcomes at 2007-12 IS the number a Vasicek/scenario overlay is
built to close; the gap that REMAINS between scenario (b) and realised
outcomes is the model-risk floor no overlay can close (parameter/spec risk).

--------------------------------------------------------------------------
ALFRED: WHAT IS ACTUALLY AVAILABLE (empirically verified against the live
FRED/ALFRED API, 2026-07 -- see get_alfred_coverage_note / alfred_coverage.json)
--------------------------------------------------------------------------
FRED's `realtime_start`/`realtime_end` params return a series AS THE DATA
WOULD HAVE READ on that date (the ALFRED real-time-vintage semantics), for
ANY series that has vintage history archived. Empirically:
  * State AND national unemployment rate series (`{POSTAL}UR`, `UNRATE`)
    DO carry real ALFRED vintage history -- values for the same historical
    month genuinely differ across vintages (seasonal-factor/benchmark
    revisions), and the LAST available observation in a T-dated vintage
    pull is naturally 1-3 months behind T (the true BLS publication lag --
    no manual lag assumption needed, the API enforces it by construction).
  * State AND national house-price index series (`{POSTAL}STHPI`,
    `USSTHPI`) have **NO ALFRED vintage archive at all** -- FRED returns
    HTTP 400 "the series does not exist in ALFRED" for ANY historical
    `realtime_start`. FHFA does not publish a revision history to FRED.
    For HPI, "as known at T" can therefore only be approximated by
    TRUNCATING the (single, current) series at an assumed publication lag
    -- see HPI_PUBLICATION_LAG_MONTHS below. This is a documented,
    unavoidable data-availability SIMPLIFICATION, not a coding shortcut.
Every UER pull is genuinely vintage-correct; every HPI pull is a
publication-lag-truncated proxy. `get_alfred_coverage_note()` records this
per-series distinction on disk exactly once (`alfred_coverage.json`) rather
than leaving the reader to infer it from behaviour.

--------------------------------------------------------------------------
PUBLICATION LAG
--------------------------------------------------------------------------
UER: EMPIRICAL -- whatever the T-dated ALFRED pull's last available monthly
observation actually is (no assumption imposed).
HPI: ASSUMED -- HPI_PUBLICATION_LAG_MONTHS = 5. FHFA's quarterly STHPI print
is dated at the quarter's FIRST month (see freddie/macro.py's "QUARTERLY ->
MONTHLY CHOICE") and is actually released roughly 2 months after the
quarter's END, i.e. 3 (quarter length) + 2 (release lag) = 5 months after
its own dated month. `_hpi_cutoff(T)` floors `T - 5 months` to the most
recent quarter-start <= that date.

--------------------------------------------------------------------------
PSEUDO-REPORTING DATES / SPLIT
--------------------------------------------------------------------------
REPORTING_DATES = 2007-12, 2009-12, 2015-12, 2019-12, 2021-12 (spec-given).
At each T: champion spec (freddie.fit_hazard.BASE_FORMULA) refit on
performance months <= T ONLY (mechanically verified -- see
test_freddie_backtest.py), vintages originated by T (falls out of the
performance-month filter automatically: a loan's first panel row is its
origination month), state macro AS KNOWN AT T (see above). Every
then-ACTIVE loan (a panel row at exactly month T with d90_event == 0) is
then projected forward PROJECTION_HORIZON_MONTHS = 36 months under two
macro scenarios, respecting each loan's own termination (see
`effective_horizon`): (a) FROZEN -- the last macro values actually known as
of T, held constant for the full horizon; (b) ACTUAL -- the realised
(final-revision) state macro path for months T+1..T+36 (hindsight
ceiling). Predicted cumulative D90 (both scenarios) is compared to REALISED
cumulative D90 by origination-vintage cohort. Realised D90 timing comes
from the MODELING panel's per-loan terminal month (`panel_terminal_months`):
because panel_monthly.parquet applies absorbing-D90 truncation (every row up
to AND INCLUDING the first D90 month), that terminal month IS the D90 event
month whenever `had_d90_event` is True. It must NOT be taken from
loan_orig's `last_reported_period`, which is the UN-truncated tape's
DISPOSITION month -- median ~33 months after first D90 for GFC-era
defaults, which would silently drop most defaults-in-window from the
realised side (adversarial-review finding, 2026-07-18).

--------------------------------------------------------------------------
SIMPLIFICATIONS (declared; also restated in the returned simplifications
array and backtest_report.md section 5)
--------------------------------------------------------------------------
  * HPI "as known at T" is a publication-lag TRUNCATION of the single
    current-vintage series, not a genuine historical revision (no ALFRED
    archive exists for STHPI at all -- see above).
  * updated_ltv (and therefore `ltv10`) is held FROZEN at its last-known-at-T
    value for the ENTIRE 36-month projection, in BOTH macro scenarios --
    this module does not re-derive an amortisation/prepayment path for
    `current_upb`, so only the macro-path assumption varies between
    scenarios (isolates the exhibit's actual point: macro-overlay choice).
  * `loan_age`, `fico_s`, `dti_s`, `occupancy_status`, `loan_purpose`,
    `channel` are the loan's true covariates at T (fico/dti/occ/purpose/
    channel are static by construction; loan_age increments deterministically
    each projected month).
  * Projection is EXPECTED-VALUE hazard roll-forward (cumulative product of
    monthly survival probabilities), not a stochastic/Monte-Carlo
    simulation -- appropriate for a point comparison against realised
    COHORT-level cumulative default rates.
  * State-level UER ALFRED coverage is verified empirically per pull; any
    state series lacking ALFRED history (see get_alfred_coverage_note)
    falls back to the NATIONAL UNRATE vintage for that reporting date.

Run as a module to (re)build every deliverable (network on ALFRED
cache-miss only; needs FRED_API_KEY in .env for a first run):
    cd <repo root> && uv run --no-sync python -m freddie.backtest
"""

from __future__ import annotations

import gc
import json
import logging
import pickle
import time
from pathlib import Path

import numpy as np
import pandas as pd

from freddie import fit_hazard as fh
from freddie import macro as freddie_macro
from freddie.ingest import VINTAGE_YEARS

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths -- rung-3 isolation
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = fh.PANEL_PATH
ORIG_PATH = fh.ORIG_PATH
LGD_CURE_REF = REPO_ROOT / "outputs" / "freddie" / "lgd" / "cure_rate_by_era.csv"  # read-only reference

ALFRED_CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "alfred"
BACKTEST_CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "backtest"
OUT_DIR = REPO_ROOT / "outputs" / "freddie" / "backtest"

FRED_OBS_URL = freddie_macro.FRED_OBS_URL

# --------------------------------------------------------------------------
# Spec constants
# --------------------------------------------------------------------------
REPORTING_DATES: list[pd.Timestamp] = [
    pd.Timestamp("2007-12-01"),
    pd.Timestamp("2009-12-01"),
    pd.Timestamp("2015-12-01"),
    pd.Timestamp("2019-12-01"),
    pd.Timestamp("2021-12-01"),
]
PROJECTION_HORIZON_MONTHS = 36
HPI_PUBLICATION_LAG_MONTHS = 5  # see module docstring "PUBLICATION LAG"

COVID_START = fh.COVID_START
COVID_END = fh.COVID_END

MODEL_FRAME_COLS = fh.MODEL_FRAME_COLS
REQUIRED_COLS = fh.REQUIRED_COLS
BASE_FORMULA = fh.BASE_FORMULA


# ==========================================================================
# 1. ALFRED (FRED real-time vintage) pulls, cached per (series, asof)
# ==========================================================================
def _alfred_cache_path(series_id: str, asof: pd.Timestamp, cache_dir: Path) -> Path:
    return cache_dir / f"{series_id}__{asof:%Y%m}.csv"


def _alfred_marker_path(series_id: str, asof: pd.Timestamp, cache_dir: Path) -> Path:
    return cache_dir / f"{series_id}__{asof:%Y%m}.unavailable.json"


def fetch_alfred_vintage(
    series_id: str,
    asof: pd.Timestamp,
    api_key: str | None = None,
    cache_dir: Path = ALFRED_CACHE_DIR,
    max_retries: int = 3,
) -> pd.DataFrame | None:
    """Return the (date, value) series AS KNOWN on `asof` (realtime_start ==
    realtime_end == asof), cached as CSV -- offline after the first pull,
    mirrors freddie.macro.fetch_fred_series's cache discipline exactly.

    Returns None (and caches a `.unavailable.json` marker, so we never
    re-hit the network for a known-unsupported series/vintage) if FRED
    reports the series has no ALFRED vintage archive -- the documented HPI
    case (see module docstring).
    """
    cache_path = _alfred_cache_path(series_id, asof, cache_dir)
    marker_path = _alfred_marker_path(series_id, asof, cache_dir)
    if marker_path.exists():
        return None
    if cache_path.exists():
        return pd.read_csv(cache_path, parse_dates=["date"])

    if not api_key:
        raise RuntimeError(
            f"No ALFRED cache for '{series_id}' as of {asof.date()} at {cache_path} "
            "and no FRED_API_KEY provided -- run `python -m freddie.backtest` once "
            "with network + the key set to populate the cache."
        )

    import requests

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "realtime_start": asof.strftime("%Y-%m-%d"),
        "realtime_end": asof.strftime("%Y-%m-%d"),
    }
    last_exc: Exception | None = None
    resp = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(FRED_OBS_URL, params=params, timeout=30)
            break
        except Exception as exc:  # noqa: BLE001 -- retry any transient network failure
            last_exc = exc
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    if resp is None:
        raise RuntimeError(f"ALFRED pull failed for {series_id}@{asof.date()} after {max_retries} attempts") from last_exc

    if resp.status_code == 400:
        payload = resp.json()
        if "does not exist in ALFRED" in payload.get("error_message", ""):
            cache_dir.mkdir(parents=True, exist_ok=True)
            marker_path.write_text(json.dumps(payload, indent=2))
            return None
        raise RuntimeError(f"ALFRED pull 400 for {series_id}@{asof.date()}: {payload}")
    resp.raise_for_status()
    payload = resp.json()

    obs = payload.get("observations", [])
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    logger.info("ALFRED pull: %s as of %s (%d obs) -> %s", series_id, asof.date(), len(df), cache_path)
    return df


def get_alfred_coverage_note(
    states: list[str], asof: pd.Timestamp, api_key: str | None = None,
) -> dict:
    """Per-series ALFRED-vintage-availability record for one reporting date
    (which state UER pulls succeeded vs fell back to national UNRATE; the
    blanket HPI unavailability fact -- see module docstring)."""
    rows = []
    for state in states:
        ur_id, ur_is_fb, hpi_id, hpi_is_fb = freddie_macro.resolve_series_ids(state)
        ur_df = fetch_alfred_vintage(ur_id, asof, api_key=api_key)
        used_national_fallback = ur_df is None or ur_df.empty
        rows.append({
            "state": state,
            "ur_series_requested": ur_id,
            "ur_alfred_available": not used_national_fallback,
            "ur_national_fallback_used": used_national_fallback or ur_is_fb,
            "hpi_alfred_available": False,  # empirically verified: never available (module docstring)
        })
    return {
        "asof": str(asof.date()),
        "n_states": len(states),
        "n_ur_national_fallback": sum(r["ur_national_fallback_used"] for r in rows),
        "hpi_note": (
            "FHFA STHPI (state AND national) carries NO ALFRED vintage archive -- "
            "every HPI 'as known at T' value is a publication-lag TRUNCATION of the "
            f"single current-vintage series (HPI_PUBLICATION_LAG_MONTHS={HPI_PUBLICATION_LAG_MONTHS}), "
            "not a genuine historical revision."
        ),
        "per_state": rows,
    }


# ==========================================================================
# 2. As-of-T state macro panel (UER: real ALFRED vintage; HPI: lag-truncated)
# ==========================================================================
def _hpi_cutoff(asof: pd.Timestamp) -> pd.Timestamp:
    """Last quarter-start month whose FHFA STHPI print would have been
    published by `asof` -- see module docstring "PUBLICATION LAG"."""
    candidate = asof - pd.DateOffset(months=HPI_PUBLICATION_LAG_MONTHS)
    q_month = ((candidate.month - 1) // 3) * 3 + 1
    return pd.Timestamp(year=candidate.year, month=q_month, day=1)


def build_asof_macro_panel(
    asof: pd.Timestamp,
    states: list[str] | None = None,
    final_macro: pd.DataFrame | None = None,
    api_key: str | None = None,
) -> pd.DataFrame:
    """State x month macro panel AS KNOWN AT `asof`: real ALFRED-vintage UER
    (per state, national-UNRATE fallback where a state has no ALFRED
    history) + publication-lag-truncated FINAL HPI (no ALFRED archive
    exists for HPI at all -- see module docstring). Same schema as
    freddie.macro's state_macro_panel (reuses `_add_derived_columns` for
    the rebase/delta/lag derivation, verbatim -- no re-derivation).
    """
    if states is None:
        states = freddie_macro.get_states_in_data()
    if final_macro is None:
        final_macro = freddie_macro.get_or_build_state_macro_panel()

    hpi_cutoff = _hpi_cutoff(asof)
    frames = []
    for state in states:
        ur_id, ur_is_fb, hpi_id, hpi_is_fb = freddie_macro.resolve_series_ids(state)

        ur_df = fetch_alfred_vintage(ur_id, asof, api_key=api_key)
        used_national_fallback = ur_df is None or ur_df.empty
        if used_national_fallback:
            ur_df = fetch_alfred_vintage(freddie_macro.NATIONAL_UR_SERIES, asof, api_key=api_key)

        state_final = final_macro.loc[final_macro["property_state"] == state, ["month", "hpi_raw"]].sort_values("month")
        full_idx = state_final["month"].to_numpy()

        if ur_df is not None and not ur_df.empty:
            ur_monthly = (
                ur_df.assign(month=ur_df["date"].dt.to_period("M").dt.to_timestamp())
                .set_index("month")["value"].rename("uer")
            )
            uer_vals = ur_monthly.reindex(full_idx).to_numpy()
        else:
            uer_vals = np.full(len(full_idx), np.nan)

        hpi_vals = np.where(full_idx <= hpi_cutoff.to_datetime64(), state_final["hpi_raw"].to_numpy(), np.nan)

        df = pd.DataFrame({"month": full_idx, "uer": uer_vals, "hpi_raw": hpi_vals})
        df["property_state"] = state
        df["uer_is_national_fallback"] = bool(used_national_fallback or ur_is_fb)
        df["hpi_is_national_fallback"] = bool(hpi_is_fb)
        frames.append(df)

    panel = pd.concat(frames, ignore_index=True)
    panel = freddie_macro._add_derived_columns(panel)
    return panel


def get_or_build_asof_macro_panel(asof: pd.Timestamp, refresh: bool = False, api_key: str | None = None) -> pd.DataFrame:
    cache_path = ALFRED_CACHE_DIR / f"asof_macro_{asof:%Y%m}.parquet"
    if cache_path.exists() and not refresh:
        return pd.read_parquet(cache_path)
    panel = build_asof_macro_panel(asof, api_key=api_key)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(cache_path, index=False)
    return panel


_MACRO_LEVEL_COLS = [
    "uer", "hpi_raw", "hpi_index", "delta_uer", "hpi_growth",
    "uer_lag1", "delta_uer_lag1", "hpi_growth_lag1",
]


def _ffill_snapshot(asof_macro: pd.DataFrame) -> pd.DataFrame:
    """Per-state forward-fill of every macro level/lag column.

    Necessary for the PROJECTION BASE (active_loans_at) only: publication
    lag means the row dated EXACTLY `asof` is usually itself still NaN in
    `asof_macro` (e.g. state UER's ~2-month lag means uer_lag1 for the
    reporting month itself is not yet knowable at T; HPI's 5-month lag is
    worse). Carrying forward the last published print to compute a loan's
    T-dated `updated_ltv`/macro covariates is standard real-world practice
    (an analyst computing "current LTV" mid-quarter uses the last published
    HPI index, not an unpublished future one) -- NOT a lookahead violation,
    because it only ever fills a NaN with an EARLIER already-known value.
    Only used to build the projection's STARTING covariate snapshot; the
    as-of-T FIT frame (`build_asof_model_frame`) is deliberately left
    un-ffilled, so its tail-of-window rows with genuinely-not-yet-published
    macro are dropped by `fh.fit_hazard`'s dropna, as they honestly should be.
    """
    df = asof_macro.sort_values(["property_state", "month"]).copy()
    df[_MACRO_LEVEL_COLS] = df.groupby("property_state")[_MACRO_LEVEL_COLS].ffill()
    return df


def last_known_macro(asof_macro: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Per-state LAST NON-NULL macro row at or before `asof` (forward-filled)
    -- the "macro frozen at last-known values" scenario's starting point.
    Indexed by property_state; columns uer_lag1/delta_uer_lag1/hpi_growth_lag1.
    """
    cols = ["uer_lag1", "delta_uer_lag1", "hpi_growth_lag1"]
    sub = asof_macro.loc[asof_macro["month"] <= asof, ["property_state", "month"] + cols].sort_values(
        ["property_state", "month"]
    )
    sub[cols] = sub.groupby("property_state")[cols].ffill()
    last = sub.groupby("property_state", as_index=True).last()[cols]
    return last


# ==========================================================================
# 3. As-of-T model frame (memory-lean per-vintage build, mirrors
#    fit_hazard.get_model_frame -- REUSES fh.build_model_frame verbatim,
#    only the macro panel and the performance-month/vintage bounds differ)
# ==========================================================================
def build_asof_model_frame(asof: pd.Timestamp, asof_macro: pd.DataFrame) -> pd.DataFrame:
    """Merged model frame for performance months <= `asof` ONLY, using
    macro AS KNOWN AT `asof`. Mechanically guarantees zero post-T rows
    (test_freddie_backtest.py::test_asof_fit_touches_zero_post_t_rows) by
    filtering panel_v BEFORE the merge, not after.
    """
    vintages = [v for v in VINTAGE_YEARS if v <= asof.year]
    orig_full = pd.read_parquet(fh._fast_local(ORIG_PATH), columns=[
        "loan_sequence_number", "vintage", "credit_score", "dti",
        "occupancy_status", "loan_purpose", "channel", "property_state",
        "orig_ltv", "orig_upb", "first_payment_date",
    ])
    chunks: list[pd.DataFrame] = []
    for v in vintages:
        panel_v = pd.read_parquet(
            fh._fast_local(PANEL_PATH),
            columns=["loan_sequence_number", "monthly_reporting_period",
                     "loan_age", "current_actual_upb", "d90_event"],
            filters=[("vintage", "==", v), ("monthly_reporting_period", "<=", asof)],
        )
        if panel_v.empty:
            continue
        orig_v = orig_full[orig_full["vintage"] == v].drop(columns=["vintage"])
        chunk = fh.build_model_frame(panel=panel_v, orig=orig_v, macro_panel=asof_macro)
        del panel_v, orig_v
        for c in chunk.columns:
            if chunk[c].dtype == "float64":
                chunk[c] = chunk[c].astype("float32")
        chunks.append(chunk)
    df = pd.concat(chunks, ignore_index=True)
    del chunks
    for c in ("occupancy_status", "loan_purpose", "channel", "property_state"):
        if c in df.columns:
            df[c] = df[c].astype("category")
    return df


def get_asof_model_frame(asof: pd.Timestamp, asof_macro: pd.DataFrame, refresh: bool = False) -> pd.DataFrame:
    cache_path = BACKTEST_CACHE_DIR / f"model_frame_{asof:%Y%m}.parquet"
    if cache_path.exists() and not refresh:
        logger.info("Loading cached as-of model frame from %s", cache_path)
        return pd.read_parquet(cache_path)
    logger.info("Building as-of model frame for T=%s (vintages<=%d)...", asof.date(), asof.year)
    df = build_asof_model_frame(asof, asof_macro)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    logger.info("  as-of model frame T=%s: %d rows", asof.date(), len(df))
    return df


class _CheckpointUnpickler(pickle.Unpickler):
    """See freddie.fit_hazard's identical unpickler -- maps HazardModel
    references back to the canonical class regardless of which module was
    __main__ when the checkpoint was written."""

    def find_class(self, module: str, name: str):
        if name == "HazardModel":
            return fh.HazardModel
        return super().find_class(module, name)


def get_asof_champion_fit(asof: pd.Timestamp, train_df: pd.DataFrame, refresh: bool = False) -> fh.HazardModel:
    """Champion spec refit on `train_df` (already filtered to perf month <=
    T). Checkpointed the moment it converges -- see module CHECKPOINT
    DISCIPLINE: every reporting-date fit gets its own pickle file."""
    cache_path = BACKTEST_CACHE_DIR / f"champion_asof_{asof:%Y%m}.pkl"
    if cache_path.exists() and not refresh:
        logger.info("Loading cached as-of champion fit for T=%s", asof.date())
        with open(cache_path, "rb") as f:
            return _CheckpointUnpickler(f).load()

    logger.info("Fitting as-of champion for T=%s: %d train rows, %d events",
                asof.date(), len(train_df), int(train_df["d90_event"].sum()))
    sample = fh.sample_case_control(train_df, rate=fh.CONTROL_SAMPLE_RATE, seed=fh.SEED_A)
    model = fh.fit_hazard(sample, formula=BASE_FORMULA, name=f"asof_{asof:%Y%m}")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(model, f)
    logger.info("Champion T=%s converged: fit_n=%d fit_events=%d", asof.date(), model.n_obs, model.n_events)
    return model


# ==========================================================================
# 4. Projection: then-active loans at T, forward 36 months, two macro
#    scenarios, respecting loan termination
# ==========================================================================
def effective_horizon(
    last_reported_period: pd.Series,
    asof: pd.Timestamp,
    horizon: int = PROJECTION_HORIZON_MONTHS,
) -> np.ndarray:
    """Months of forward risk exposure for each loan: min(`horizon`, months
    from `asof` to that loan's own last observed panel month), clipped at
    >= 0. This is the SAME quantity used to (a) truncate the projection
    loop for a loan that terminates before the full horizon and (b) bound
    the REALISED-outcome lookup window -- so "projection horizon respects
    loan termination" is enforced identically on both sides of the
    predicted-vs-realised comparison.
    """
    months = (
        (last_reported_period.dt.year - asof.year) * 12
        + (last_reported_period.dt.month - asof.month)
    )
    return np.clip(months.to_numpy(), 0, horizon)


def panel_terminal_months(asof: pd.Timestamp) -> pd.Series:
    """Per-loan LAST month in the MODELING panel (panel_monthly.parquet),
    restricted to rows >= `asof` (sufficient for any loan active at T, whose
    panel necessarily has a row at exactly T). Because the panel applies
    absorbing-D90 truncation (build_panel._build_monthly_panel: every row up
    to AND INCLUDING the first D90 month, nothing after), this terminal month
    IS the first-D90 event month for a defaulted loan, and the last observed
    (prepay/maturity/censoring) month for any other loan.

    This is deliberately NOT loan_orig's `last_reported_period`: that field
    is built from the UN-truncated servicing tape's terminal row
    (build_panel._terminal_rows_full_history), i.e. the DISPOSITION month --
    for GFC-era defaults a median of ~33 months (p90 ~10 years) AFTER the
    first D90 month. Timing the realised D90 outcome by disposition month
    silently drops every loan that went D90 within the projection window but
    was liquidated after it (75% of the 2007-12 book's defaults-in-window).
    """
    vintages = [v for v in VINTAGE_YEARS if v <= asof.year]
    parts: list[pd.Series] = []
    for v in vintages:
        p = pd.read_parquet(
            fh._fast_local(PANEL_PATH),
            columns=["loan_sequence_number", "monthly_reporting_period"],
            filters=[("vintage", "==", v), ("monthly_reporting_period", ">=", asof)],
        )
        if p.empty:
            continue
        parts.append(p.groupby("loan_sequence_number", observed=True)["monthly_reporting_period"].max())
        del p
    return pd.concat(parts)


def active_loans_at(asof: pd.Timestamp, asof_macro: pd.DataFrame, orig: pd.DataFrame | None = None) -> pd.DataFrame:
    """Then-ACTIVE loans at T: a panel row at exactly month T with
    d90_event == 0 (i.e. not yet defaulted), merged with orig covariates
    (AS-OF-T macro) + the realised-outcome fields needed for the honesty
    comparison (`had_d90_event`, `vintage`, and the MODELING panel's
    per-loan terminal month -- see `panel_terminal_months` for why the
    D90-event timing must come from the panel, NOT loan_orig's
    disposition-month `last_reported_period`).
    """
    vintages = [v for v in VINTAGE_YEARS if v <= asof.year]
    panel_t = pd.read_parquet(
        fh._fast_local(PANEL_PATH),
        columns=["loan_sequence_number", "monthly_reporting_period", "loan_age",
                 "current_actual_upb", "d90_event"],
        filters=[("vintage", "in", vintages), ("monthly_reporting_period", "==", asof), ("d90_event", "==", 0)],
    )
    if orig is None:
        orig = pd.read_parquet(fh._fast_local(ORIG_PATH), columns=[
            "loan_sequence_number", "vintage", "credit_score", "dti", "occupancy_status",
            "loan_purpose", "channel", "property_state", "orig_ltv", "orig_upb",
            "first_payment_date", "had_d90_event",
        ])
    snapshot_macro = _ffill_snapshot(asof_macro)
    frame = fh.build_model_frame(
        panel=panel_t,
        orig=orig.drop(columns=["had_d90_event", "vintage"]),
        macro_panel=snapshot_macro,
    )
    frame = frame.merge(
        orig[["loan_sequence_number", "vintage", "had_d90_event"]],
        on="loan_sequence_number", how="left", validate="one_to_one",
    )
    # Scoreable-population restriction: a loan with a missing STATIC covariate
    # (fico/dti/etc.) cannot be scored by the champion spec at any step --
    # predict_hazard drops it and project_forward's fillna(0) would otherwise
    # book it as ZERO predicted risk while its realised outcome still counted
    # (an asymmetry that deflates every predicted mean, ~2.5% of the 2007-12
    # book). Exclude such loans from BOTH sides of the comparison instead.
    static_cols = ["loan_age", "fico_s", "dti_s", "ltv10",
                   "occupancy_status", "loan_purpose", "channel"]
    scoreable = frame[static_cols].notna().all(axis=1)
    n_unscoreable = int((~scoreable).sum())
    if n_unscoreable:
        logger.info("active_loans_at T=%s: dropping %d/%d loans with NaN static covariates "
                    "from both sides of the comparison", asof.date(), n_unscoreable, len(frame))
        frame = frame.loc[scoreable].reset_index(drop=True)
    term = panel_terminal_months(asof)
    frame["panel_terminal_month"] = frame["loan_sequence_number"].map(term)
    frame["horizon_steps"] = effective_horizon(frame["panel_terminal_month"], asof)
    months_to_event = (
        (frame["panel_terminal_month"].dt.year - asof.year) * 12
        + (frame["panel_terminal_month"].dt.month - asof.month)
    )
    frame["realized_d90"] = frame["had_d90_event"] & (months_to_event > 0) & (months_to_event <= PROJECTION_HORIZON_MONTHS)
    return frame


def project_forward(
    model: fh.HazardModel,
    base_frame: pd.DataFrame,
    macro_scenario_fn,
    horizon: int = PROJECTION_HORIZON_MONTHS,
) -> pd.Series:
    """Expected-value cumulative D90 probability per loan, `horizon` months
    forward from T, respecting `base_frame["horizon_steps"]` (loan
    termination -- see `effective_horizon`). `macro_scenario_fn(step,
    property_state)` returns a DataFrame of uer_lag1/delta_uer_lag1/
    hpi_growth_lag1 aligned to `property_state`, for the given step
    (1..horizon) ahead of T.
    """
    idx = base_frame.index
    survival = pd.Series(1.0, index=idx)
    cum_default = pd.Series(0.0, index=idx)
    horizon_steps = base_frame["horizon_steps"]
    base_age = base_frame["loan_age"].astype("float64")

    static_cols = ["fico_s", "dti_s", "ltv10", "occupancy_status", "loan_purpose", "channel", "property_state"]
    static = base_frame[static_cols]

    for step in range(1, horizon + 1):
        mask = (horizon_steps >= step) & (survival > 0)
        if not mask.any():
            continue
        cov = static.loc[mask].copy()
        cov["loan_age"] = base_age.loc[mask] + step
        macro_vals = macro_scenario_fn(step, cov["property_state"])
        cov[["uer_lag1", "delta_uer_lag1", "hpi_growth_lag1"]] = macro_vals.to_numpy()
        h = fh.predict_hazard(model, cov).fillna(0.0)
        s = survival.loc[mask]
        cum_default.loc[mask] += s * h
        survival.loc[mask] = s * (1.0 - h)

    return cum_default


def make_frozen_macro_fn(asof_macro: pd.DataFrame, asof: pd.Timestamp):
    """Scenario (a): macro FROZEN at the last values actually known at T
    (from the ALFRED-as-of-T panel), held constant for every future step."""
    last = last_known_macro(asof_macro, asof)

    def _fn(step: int, states: pd.Series) -> pd.DataFrame:
        return last.reindex(states.to_numpy())

    return _fn


def make_actual_macro_fn(final_macro: pd.DataFrame, asof: pd.Timestamp):
    """Scenario (b): macro path REALISED (final-revision), looked up at
    T+step for each loan's state -- the hindsight ceiling."""
    cols = ["uer_lag1", "delta_uer_lag1", "hpi_growth_lag1"]
    lookup = final_macro.set_index(["property_state", "month"])[cols]

    def _fn(step: int, states: pd.Series) -> pd.DataFrame:
        month = asof + pd.DateOffset(months=step)
        keys = list(zip(states.to_numpy(), [month] * len(states)))
        return lookup.reindex(keys)

    return _fn


# ==========================================================================
# 5. Honesty exhibit: predicted vs realised by cohort
# ==========================================================================
def cohort_summary(base_frame: pd.DataFrame, pred_frozen: pd.Series, pred_actual: pd.Series) -> pd.DataFrame:
    df = base_frame[["vintage"]].copy()
    df["realized"] = base_frame["realized_d90"].astype(float)
    df["predicted_frozen"] = pred_frozen
    df["predicted_actual"] = pred_actual

    g = df.groupby("vintage").agg(
        n_loans=("realized", "size"),
        realized_cum_d90=("realized", "mean"),
        predicted_cum_d90_frozen=("predicted_frozen", "mean"),
        predicted_cum_d90_actual=("predicted_actual", "mean"),
    ).reset_index()

    overall = pd.DataFrame([{
        "vintage": "ALL",
        "n_loans": len(df),
        "realized_cum_d90": df["realized"].mean(),
        "predicted_cum_d90_frozen": df["predicted_frozen"].mean(),
        "predicted_cum_d90_actual": df["predicted_actual"].mean(),
    }])
    out = pd.concat([g, overall], ignore_index=True)
    out["miss_ratio_frozen"] = out["realized_cum_d90"] / out["predicted_cum_d90_frozen"].clip(lower=1e-9)
    out["miss_ratio_actual"] = out["realized_cum_d90"] / out["predicted_cum_d90_actual"].clip(lower=1e-9)
    return out


def plot_cohort_summary(summary: pd.DataFrame, asof: pd.Timestamp, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    rows = summary[summary["vintage"] != "ALL"].sort_values("vintage")
    x = np.arange(len(rows))
    width = 0.27

    fig, ax = plt.subplots(figsize=(max(7, len(rows) * 1.1), 4.5))
    ax.bar(x - width, rows["realized_cum_d90"] * 100, width, color=COLORS["accent"], label="Realized")
    ax.bar(x, rows["predicted_cum_d90_frozen"] * 100, width, color=COLORS["warn"], label="Predicted (macro frozen)")
    ax.bar(x + width, rows["predicted_cum_d90_actual"] * 100, width, color=COLORS["good"], label="Predicted (actual macro, hindsight)")
    ax.set_xticks(x)
    ax.set_xticklabels(rows["vintage"].astype(int))
    ax.set_xlabel("Origination vintage (cohort)")
    ax.set_ylabel(f"Cumulative D90 within {PROJECTION_HORIZON_MONTHS}mo (%)")
    ax.set_title(f"Honesty exhibit -- reporting date T={asof:%Y-%m}: predicted vs realized by cohort")
    ax.legend(fontsize=8)
    fig.savefig(path)
    plt.close(fig)


# ==========================================================================
# 6. Per-reporting-date orchestration
# ==========================================================================
def run_reporting_date(asof: pd.Timestamp, refresh: bool = False, api_key: str | None = None) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKTEST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ALFRED_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    asof_macro = get_or_build_asof_macro_panel(asof, refresh=refresh, api_key=api_key)
    final_macro = freddie_macro.get_or_build_state_macro_panel()

    train_df = get_asof_model_frame(asof, asof_macro, refresh=refresh)
    assert (train_df["monthly_reporting_period"] <= asof).all(), "as-of fit frame leaked post-T rows"
    model = get_asof_champion_fit(asof, train_df, refresh=refresh)
    train_n, train_events = len(train_df), int(train_df["d90_event"].sum())
    del train_df
    gc.collect()

    base = active_loans_at(asof, asof_macro)
    frozen_fn = make_frozen_macro_fn(asof_macro, asof)
    actual_fn = make_actual_macro_fn(final_macro, asof)
    pred_frozen = project_forward(model, base, frozen_fn)
    pred_actual = project_forward(model, base, actual_fn)

    summary = cohort_summary(base, pred_frozen, pred_actual)
    summary.to_csv(OUT_DIR / f"predicted_vs_realized_{asof:%Y%m}.csv", index=False)
    plot_cohort_summary(summary, asof, OUT_DIR / f"predicted_vs_realized_{asof:%Y%m}.png")

    overall = summary.loc[summary["vintage"] == "ALL"].iloc[0]
    metrics = {
        "asof": str(asof.date()),
        "train_n": train_n,
        "train_events": train_events,
        "fit_n": model.n_obs,
        "fit_events": model.n_events,
        "n_active_loans": len(base),
        "realized_cum_d90": float(overall["realized_cum_d90"]),
        "predicted_cum_d90_frozen": float(overall["predicted_cum_d90_frozen"]),
        "predicted_cum_d90_actual": float(overall["predicted_cum_d90_actual"]),
        "miss_ratio_frozen": float(overall["miss_ratio_frozen"]),
        "miss_ratio_actual": float(overall["miss_ratio_actual"]),
    }
    (OUT_DIR / f"metrics_{asof:%Y%m}.json").write_text(json.dumps(metrics, indent=2))

    del base, pred_frozen, pred_actual, asof_macro
    gc.collect()
    return metrics


# ==========================================================================
# 7. Report
# ==========================================================================
def write_backtest_report(all_metrics: list[dict], coverage_2007: dict) -> None:
    lines = []
    lines.append("# ALFRED-Vintage HONEST Backtest -- SFLLD Champion Hazard, Refit-in-Time\n")
    lines.append(
        "This is the model-risk exhibit: the champion hazard spec "
        "(`freddie/fit_hazard.py::BASE_FORMULA`, reused verbatim) refit at each "
        "historical pseudo-reporting date on ONLY the data and macro vintages that "
        "actually existed then, then projected forward 36 months and compared to what "
        "actually happened. See `freddie/backtest.py` module docstring for the full "
        "ALFRED-availability findings and every declared simplification.\n"
    )

    lines.append("## 1. IFRS-9 narrative: PIT hazard vs forward-looking overlay\n")
    lines.append(
        "The DCR champion (`engine/hazard.py`) is a point-in-time (PIT) hazard; IFRS-9 "
        "compliance requires pairing it with a forward-looking scenario overlay "
        "(`engine/scenario.py`'s Vasicek/scenario macro paths) rather than scoring it "
        "with macro frozen at today's value. This backtest historicises exactly that "
        "distinction: scenario **(a) frozen** below is the naive PIT extrapolation IFRS-9 "
        "para 5.5.17 exists to prevent; scenario **(b) actual** (hindsight) is the ceiling "
        "a PERFECT overlay could have achieved. The gap between (a) and realised outcomes "
        "is what a scenario overlay is built to close; the gap that REMAINS between (b) and "
        "realised outcomes is the model-risk floor no overlay closes (spec/parameter risk, "
        "and here also the frozen-LTV simplification -- see module docstring).\n"
    )

    lines.append("## 2. Predicted vs realized by reporting date\n")
    lines.append(
        "| T (reporting date) | fit n / events | active loans | realized D90 (36mo) | "
        "predicted (frozen) | miss ratio (frozen) | predicted (actual, hindsight) | miss ratio (actual) |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
    )
    for m in all_metrics:
        lines.append(
            f"| {m['asof']} | {m['fit_n']:,} / {m['fit_events']:,} | {m['n_active_loans']:,} | "
            f"{m['realized_cum_d90']:.3%} | {m['predicted_cum_d90_frozen']:.3%} | "
            f"{m['miss_ratio_frozen']:.2f}x | {m['predicted_cum_d90_actual']:.3%} | "
            f"{m['miss_ratio_actual']:.2f}x |\n"
        )

    m2007 = next((m for m in all_metrics if m["asof"] == "2007-12-01"), None)
    if m2007 is not None:
        underpredicts = m2007["miss_ratio_frozen"] > 1.0
        lines.append(
            f"\n**2007-12 check (spec requirement)**: miss ratio (frozen) = "
            f"{m2007['miss_ratio_frozen']:.2f}x (realized {m2007['realized_cum_d90']:.3%} vs "
            f"predicted {m2007['predicted_cum_d90_frozen']:.3%}) -- "
            + ("**UNDERPREDICTS the GFC, as expected**: a model fit on pre-2008 data with "
               "macro frozen at 2007-12 levels cannot see the crisis coming; this is the "
               "exhibit's central honesty result, not a defect.\n"
               if underpredicts else
               "**DOES NOT underpredict** -- this is the flagged anomaly the spec calls out "
               "as a leakage suspect. Investigate before trusting this backtest (see "
               "Section 4 caveats): candidate causes are the projection's frozen-LTV "
               "simplification masking negative-equity risk, or the ALFRED HPI publication-lag "
               "proxy admitting late-2007 information the truncation was meant to withhold.\n"),
        )

    lines.append("\n## 3. The 2019-12-vs-COVID panel: dlq-spike miss + loss non-materialization\n")
    m2019 = next((m for m in all_metrics if m["asof"] == "2019-12-01"), None)
    if m2019 is not None:
        lines.append(
            f"The 2019-12 model (fit on pre-COVID data, macro frozen at 2019-12 levels or "
            f"even the hindsight-actual path) projects forward straight through the "
            f"2020-04..2021-09 forbearance window it never saw (see "
            "`freddie/fit_hazard.py` COVID section -- the champion hazard has the same blind "
            f"spot). Miss ratio (frozen): {m2019['miss_ratio_frozen']:.2f}x; (actual macro, "
            f"hindsight): {m2019['miss_ratio_actual']:.2f}x -- both computed on realised D90 "
            "*counts*, which is the roll-rate half of the story. The OTHER half -- realised "
            "*losses* -- did NOT spike commensurately: `outputs/freddie/lgd/cure_rate_by_era.csv` "
            "(read-only reference; this module writes nothing there) shows the 'modern "
            "2018-2025' era's OOT cure rate at 97.9%, because forbearance/deferral resolved "
            "the overwhelming majority of the 2020 D90 spike as CURES, not liquidations -- see "
            "`freddie/lgd.py`'s COVID caveat. So a bank reading ONLY the D90-hazard miss ratio "
            "above would overstate the COVID ECL shock; the forbearance wedge is precisely "
            "the gap between the delinquency-count miss shown here and the loss miss the LGD "
            "module documents separately. This is the connective finding IFRS-9 modellers "
            "need both halves (PD hazard AND LGD/cure) to see.\n"
        )
        if m2019["predicted_cum_d90_actual"] > 0.20:
            lines.append(
                f"\n**Why the hindsight-macro prediction ({m2019['predicted_cum_d90_actual']:.1%}) "
                "is absurdly large -- and why that IS the exhibit**: the champion spec is "
                "linear in `delta_uer_lag1`, fitted on a history where month-on-month UER "
                "moves are a few tenths of a point (2019-12 refit coefficient ~+0.85 per pp). "
                "Fed the ACTUAL April-2020 print (+10.6pp in one month, UER 14.7%), the "
                "cloglog linear predictor implies a hazard multiplier in the tens of "
                "thousands, saturating the monthly hazard toward 1 for much of the book in a "
                "single projected month. This is not a computation error -- it is faithful "
                "linear extrapolation ~20 standard deviations outside the training support, "
                "i.e. the purest form of the parameter/spec model risk this backtest exists "
                "to expose: even a PERFECT macro overlay cannot rescue a hazard whose "
                "functional form was never identified in the regime the scenario visits.\n"
            )

    lines.append("\n## 4. ALFRED coverage (empirical)\n")
    lines.append(
        f"As-of 2007-12-01 (illustrative pull): {coverage_2007['n_ur_national_fallback']} of "
        f"{coverage_2007['n_states']} states' UER series fell back to the national UNRATE "
        f"ALFRED vintage. {coverage_2007['hpi_note']} Full per-state detail: "
        "`outputs/freddie/backtest/alfred_coverage_200712.json`.\n"
    )

    lines.append("\n## 5. Simplifications (declared)\n")
    lines.append(
        "- HPI 'as known at T' is a publication-lag TRUNCATION of the single current-vintage "
        "series (`HPI_PUBLICATION_LAG_MONTHS=5`), not a genuine ALFRED historical revision -- "
        "FHFA STHPI has NO vintage archive on FRED at all (empirically verified, both state "
        "and national).\n"
        "- `updated_ltv` (and `ltv10`) is held FROZEN at its last-known-at-T value for the "
        "entire 36-month projection in BOTH macro scenarios -- no amortisation/prepayment path "
        "is re-derived, so the two scenarios differ ONLY in the macro-path assumption (the "
        "exhibit's actual point).\n"
        "- Projection is expected-value hazard roll-forward (cumulative survival product), not "
        "a stochastic simulation.\n"
        "- The FROZEN scenario freezes the model's macro COVARIATES -- including the "
        "first-difference terms `delta_uer_lag1` and `hpi_growth_lag1` -- at their last-known "
        "values, so it perpetuates the last-known macro MOMENTUM (e.g. still-rising "
        "unemployment at 2009-12) for all 36 months, not just frozen LEVELS (which would imply "
        "zero delta/growth after the first step). This makes 'frozen' more adverse than a "
        "level-freeze when entered from a deteriorating quarter and more benign when entered "
        "from an improving one.\n"
        "- State UER series lacking ALFRED history (rare; see Section 4) fall back to the "
        "national UNRATE vintage for that reporting date.\n"
        "- Case-control (WESML) subsampling at `freddie.fit_hazard.CONTROL_SAMPLE_RATE` "
        "reused unchanged for every as-of-T refit, same rationale as the champion fit.\n"
        "- Loans with a missing STATIC covariate are excluded from BOTH sides of the "
        "predicted-vs-realized comparison -- the champion spec cannot score them, and booking "
        "them as zero predicted risk while counting their realized defaults would deflate "
        "every predicted mean. This is ~2.5% of the 2007-12 book but ~14% of the 2015-12 "
        "book, dominated by missing-DTI (HARP/Relief-Refi-era 2009/2010/2014/2015 vintages, "
        "where DTI is genuinely not collected) -- and that excluded subpopulation runs "
        "RISKIER than the scoreable book (2015-12: realized 36mo D90 2.23% excluded vs 1.40% "
        "scoreable), so the exhibit's cohort understates the whole-book realized rate. A spec "
        "that needs DTI simply cannot testify about loans that have none; declared, not hidden.\n"
        "- The as-of-T FIT frame is deliberately NOT forward-filled for unpublished macro: "
        "tail-of-window months whose macro was not yet published at T drop out of the refit "
        "(at 2007-12 this removes ~46% of the window's events -- the model is fit on the "
        "world through mid-2007, which is exactly what makes the GFC miss honest). The "
        "PROJECTION starting snapshot, by contrast, forward-fills the last published print "
        "(standard current-LTV practice; fills NaN with EARLIER known values only).\n"
    )

    (OUT_DIR / "backtest_report.md").write_text("".join(lines))


# ==========================================================================
# 8. Orchestration
# ==========================================================================
def main(refresh: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    import os

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("FRED_API_KEY")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    states = freddie_macro.get_states_in_data()
    coverage_2007 = get_alfred_coverage_note(states, REPORTING_DATES[0], api_key=api_key)
    (OUT_DIR / f"alfred_coverage_{REPORTING_DATES[0]:%Y%m}.json").write_text(json.dumps(coverage_2007, indent=2))

    all_metrics = []
    for asof in REPORTING_DATES:
        logger.info("=" * 60)
        logger.info("Reporting date T=%s", asof.date())
        m = run_reporting_date(asof, refresh=refresh, api_key=api_key)
        all_metrics.append(m)
        logger.info("T=%s: %s", asof.date(), m)
        gc.collect()

    (OUT_DIR / "all_metrics.json").write_text(json.dumps(all_metrics, indent=2))
    write_backtest_report(all_metrics, coverage_2007)
    logger.info("Done. Deliverables in %s", OUT_DIR)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="ignore cached as-of macro/model-frame/fit artifacts and rebuild everything",
    )
    args = parser.parse_args()
    main(refresh=args.refresh)
