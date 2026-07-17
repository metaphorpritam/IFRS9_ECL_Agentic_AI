"""State-level macro series for the SFLLD panel (rung 3).

This is the geographic-resolution upgrade recorded as a documented DCR
limitation: rungs 1-2 merge only NATIONAL macros because the DCR panel
carries no state field (see data/panel/build_panel.py's docstring and
MASTER_PLAN.md's rung-1/2 scope pin, "state_orig_time ... unused at this
rung"). Freddie's SFLLD orig table DOES carry property_state, so rung 3
merges state-level unemployment and house-price series instead.

Pulls, per US state postal code present in the SFLLD orig tables (50 states
+ DC + PR + GU + VI -- verified empirically, see get_states_in_data):
  * civilian unemployment rate, monthly, SA   -- FRED '{POSTAL}UR'
  * FHFA all-transactions HPI, quarterly, NSA -- FRED '{POSTAL}STHPI'
plus the national anchors UNRATE (monthly) / USSTHPI (quarterly) used both
as a fallback for territories with no state-level series and as the
exhibit overlay / validation baseline.

--------------------------------------------------------------------------
COVERAGE NOTE (empirically verified against the live FRED API; see
tests/test_freddie_macro.py::test_coverage_note_matches_verified_fallbacks)
--------------------------------------------------------------------------
FRED's regional series do not cover every SFLLD territory:
  * GU, VI have NEITHER a '{POSTAL}UR' NOR a '{POSTAL}STHPI' series
    -> both uer and hpi fall back to the national anchor.
  * PR HAS a 'PRUR' unemployment series but NO 'PRSTHPI' house-price series
    -> uer is PR-specific, hpi falls back to the national anchor.
Every row carries the boolean flags uer_is_national_fallback /
hpi_is_national_fallback so the approximation is visible downstream rather
than silently blended into a "state" number.

--------------------------------------------------------------------------
QUARTERLY -> MONTHLY CHOICE (documented; matches MASTER_PLAN.md open-item
table: "HPI quarterly->monthly (rung 3 only): Forward-fill, documented --
standard, avoids inventing intra-quarter information")
--------------------------------------------------------------------------
FRED reports STHPI at quarter-START dates (Jan/Apr/Jul/Oct 1). We reindex
each state's HPI series onto a continuous monthly index and forward-fill:
the value published for a quarter is held constant across that quarter's
three months. The alternative (linear interpolation between quarter-start
prints) would let month 2 of a quarter "see" month 3's realized print
before it is published -- exactly the intra-quarter information the build
plan default rules out. A visible side effect, called out here rather than
smoothed away: hpi_growth (the monthly log-diff of the stepped series) is
~0 for two of every three months and carries the whole quarter's growth in
the first month of each new quarter. The exhibit uses a trailing 12-month
sum of hpi_growth (i.e. YoY log growth) specifically to avoid this
step-artifact reading as noise.

--------------------------------------------------------------------------
TIMING CONVENTION (mirrors the DCR panel's macro-lag convention, see
data/panel/build_panel.py: "Only past values (t-k, k>=1) are ever
referenced => no lookahead")
--------------------------------------------------------------------------
uer_lag1 / delta_uer_lag1 / hpi_growth_lag1 are each state's own series
shifted 1 MONTH (this panel's native frequency, vs. the DCR panel's 1
quarter) within a continuous per-state monthly index built by reindexing
onto pd.period_range -- so a lag is always exactly one calendar month back,
never a stale value bridging a data gap.

--------------------------------------------------------------------------
UPDATED LTV (state-HPI adaptation of the DCR-verified formula; see
data/panel/build_panel.py's "UPDATED LTV" section, which the vendor's own
LTV_time column reproduces to ~1e-9)
--------------------------------------------------------------------------
    updated_ltv = orig_ltv * (current_upb / orig_upb) * (hpi_orig / hpi_now)
hpi_now is the state HPI index for the performance row's own
monthly_reporting_period; hpi_orig is the state HPI index for the loan's
ORIGINATION month, approximated here by first_payment_date (the field the
SFLLD orig table actually carries) rather than the true note/closing date,
which the public layout does not expose -- first_payment_date is normally
one calendar month after closing, so this is a small, one-month,
DOCUMENTED approximation, not an estimate of unknown data.

Run as a script to (re)build the raw-CSV cache + derived state-month panel
+ exhibits (first run needs network + FRED_API_KEY; every subsequent run,
including the test suite, is offline against the cache):
    cd <repo root> && uv run python -m freddie.macro
"""

from __future__ import annotations

import json
import logging
import os
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths -- rung-3 isolation: nothing here reads/writes engine/ or
# data/processed/panel.parquet (the frozen DCR panel).
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
SFLLD_DIR = REPO_ROOT / "data" / "SFLLD"
MACRO_CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "macro"
EXHIBIT_DIR = REPO_ROOT / "outputs" / "freddie" / "macro"

STATE_PANEL_PATH = MACRO_CACHE_DIR / "state_macro_panel.parquet"
STATES_IN_DATA_PATH = MACRO_CACHE_DIR / "states_in_data.json"
COVERAGE_NOTE_PATH = MACRO_CACHE_DIR / "coverage_note.json"

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"

NATIONAL_UR_SERIES = "UNRATE"
NATIONAL_HPI_SERIES = "USSTHPI"

# Empirically verified (2026-07 pull against the live FRED API): these
# states/territories have no state-level series of the given kind.
UR_NATIONAL_FALLBACK_STATES = frozenset({"GU", "VI"})
HPI_NATIONAL_FALLBACK_STATES = frozenset({"GU", "PR", "VI"})

# Chosen to show visible state heterogeneity in the exhibits (NV crash vs
# ND shale boom, plus the three largest mortgage markets).
HIGHLIGHT_STATES = ["CA", "TX", "FL", "NV", "ND"]

REBASE_MONTH = pd.Timestamp("2000-01-01")

REQUIRED_LTV_COLS = {"orig_ltv", "orig_upb", "current_upb", "first_payment_date"}

# Origination field layout, SFLLD standard 32-field orig record (0-indexed).
ORIG_PROPERTY_STATE_IDX = 16


# ==========================================================================
# 1. States present in the data
# ==========================================================================
def get_states_in_data(sfll_dir: Path = SFLLD_DIR, cache_path: Path = STATES_IN_DATA_PATH) -> list[str]:
    """Scan every SFLLD orig zip (streaming, never extracted to disk) for the
    set of property_state postal codes actually present, caching the result.
    """
    if cache_path.exists():
        return json.loads(cache_path.read_text())["states"]

    states: set[str] = set()
    zips = sorted(sfll_dir.glob("sample_*.zip"))
    if not zips:
        raise FileNotFoundError(f"No SFLLD zips found under {sfll_dir}")
    for zp in zips:
        with zipfile.ZipFile(zp) as z:
            orig_name = next(n for n in z.namelist() if "orig" in n)
            with z.open(orig_name) as f:
                for line in f:
                    parts = line.decode().split("|")
                    states.add(parts[ORIG_PROPERTY_STATE_IDX])

    result = sorted(states)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"states": result, "n_vintages_scanned": len(zips)}, indent=2))
    return result


# ==========================================================================
# 2. FRED pull with on-disk cache (offline after first pull)
# ==========================================================================
def fetch_fred_series(
    series_id: str,
    api_key: str | None = None,
    cache_dir: Path = MACRO_CACHE_DIR,
    force: bool = False,
    max_retries: int = 3,
) -> pd.DataFrame:
    """Return a (date, value) DataFrame for a FRED series, cached as CSV.

    Cache hit -> no network call at all (this is what makes the test suite
    network-free after the first `python -m freddie.macro` run). Cache miss
    requires api_key.
    """
    cache_path = cache_dir / f"{series_id}.csv"
    if cache_path.exists() and not force:
        df = pd.read_csv(cache_path, parse_dates=["date"])
        return df

    if not api_key:
        raise RuntimeError(
            f"No cache for FRED series '{series_id}' at {cache_path} and no "
            "FRED_API_KEY provided -- run `python -m freddie.macro` once "
            "with network + the key set to populate the cache."
        )

    import requests

    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(FRED_OBS_URL, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            break
        except Exception as exc:  # noqa: BLE001 -- retry any transient failure
            last_exc = exc
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    else:
        raise RuntimeError(f"FRED pull failed for {series_id} after {max_retries} attempts") from last_exc

    obs = payload.get("observations", [])
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")  # FRED encodes missing obs as '.'

    cache_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False)
    logger.info("fetched %s (%d obs) -> %s", series_id, len(df), cache_path)
    return df


def resolve_series_ids(state: str) -> tuple[str, bool, str, bool]:
    """Return (ur_series_id, ur_is_fallback, hpi_series_id, hpi_is_fallback)."""
    ur_is_fb = state in UR_NATIONAL_FALLBACK_STATES
    hpi_is_fb = state in HPI_NATIONAL_FALLBACK_STATES
    ur_id = NATIONAL_UR_SERIES if ur_is_fb else f"{state}UR"
    hpi_id = NATIONAL_HPI_SERIES if hpi_is_fb else f"{state}STHPI"
    return ur_id, ur_is_fb, hpi_id, hpi_is_fb


def build_coverage_note(states: list[str]) -> dict:
    """Per-state record of which series are state-specific vs. national fallback."""
    rows = []
    for s in sorted(states):
        ur_id, ur_fb, hpi_id, hpi_fb = resolve_series_ids(s)
        rows.append(
            {
                "state": s,
                "ur_series_used": ur_id,
                "uer_is_national_fallback": ur_fb,
                "hpi_series_used": hpi_id,
                "hpi_is_national_fallback": hpi_fb,
            }
        )
    return {
        "n_states": len(states),
        "ur_fallback_states": sorted(UR_NATIONAL_FALLBACK_STATES & set(states)),
        "hpi_fallback_states": sorted(HPI_NATIONAL_FALLBACK_STATES & set(states)),
        "per_state": rows,
    }


# ==========================================================================
# 3. Derived state x month panel
# ==========================================================================
def _add_derived_columns(panel: pd.DataFrame) -> pd.DataFrame:
    """Add level/growth/lag columns per state, sorted chronologically within state."""
    panel = panel.sort_values(["property_state", "month"]).reset_index(drop=True)

    out_frames = []
    for state, g in panel.groupby("property_state", sort=False):
        g = g.sort_values("month").reset_index(drop=True)

        # Rebase HPI to 2000=100. If a state's series doesn't reach back to
        # Jan-2000 (documented edge case), use its first available month as
        # the base instead and flag it.
        base_row = g.loc[g["month"] == REBASE_MONTH]
        used_first_available = base_row.empty or pd.isna(base_row["hpi_raw"].iloc[0])
        if used_first_available:
            base_value = g["hpi_raw"].dropna().iloc[0]
        else:
            base_value = base_row["hpi_raw"].iloc[0]
        g["hpi_index"] = 100.0 * g["hpi_raw"] / base_value
        g["hpi_rebase_used_first_available"] = used_first_available

        g["delta_uer"] = g["uer"].diff()
        g["hpi_growth"] = np.log(g["hpi_raw"]).diff()

        g["uer_lag1"] = g["uer"].shift(1)
        g["delta_uer_lag1"] = g["delta_uer"].shift(1)
        g["hpi_growth_lag1"] = g["hpi_growth"].shift(1)

        out_frames.append(g)

    return pd.concat(out_frames, ignore_index=True)


def build_state_macro_panel(
    states: list[str] | None = None,
    api_key: str | None = None,
    cache_dir: Path = MACRO_CACHE_DIR,
) -> pd.DataFrame:
    """Build the full state x month macro panel (network on cache-miss only)."""
    if states is None:
        states = get_states_in_data()

    frames = []
    for state in states:
        ur_id, ur_is_fb, hpi_id, hpi_is_fb = resolve_series_ids(state)

        ur_raw = fetch_fred_series(ur_id, api_key=api_key, cache_dir=cache_dir)
        hpi_raw = fetch_fred_series(hpi_id, api_key=api_key, cache_dir=cache_dir)

        ur_monthly = ur_raw.assign(month=ur_raw["date"].dt.to_period("M").dt.to_timestamp())
        ur_monthly = ur_monthly.set_index("month")["value"].rename("uer")

        hpi_q = hpi_raw.assign(month=hpi_raw["date"].dt.to_period("M").dt.to_timestamp())
        hpi_q = hpi_q.set_index("month")["value"].rename("hpi_raw")

        start = min(ur_monthly.index.min(), hpi_q.index.min())
        end = max(ur_monthly.index.max(), hpi_q.index.max())
        idx = pd.date_range(start, end, freq="MS")

        uer = ur_monthly.reindex(idx)
        # STEP-FORWARD-FILL: see module docstring "QUARTERLY -> MONTHLY CHOICE".
        hpi_stepped = hpi_q.reindex(idx).ffill()

        df = pd.DataFrame({"month": idx, "uer": uer.values, "hpi_raw": hpi_stepped.values})
        df["property_state"] = state
        df["uer_is_national_fallback"] = ur_is_fb
        df["hpi_is_national_fallback"] = hpi_is_fb
        frames.append(df)

    panel = pd.concat(frames, ignore_index=True)
    return _add_derived_columns(panel)


def save_state_macro_panel(panel: pd.DataFrame, path: Path = STATE_PANEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(path, index=False)


def load_state_macro_panel(path: Path = STATE_PANEL_PATH) -> pd.DataFrame:
    return pd.read_parquet(path)


def get_or_build_state_macro_panel(
    refresh: bool = False,
    states: list[str] | None = None,
    api_key: str | None = None,
    path: Path = STATE_PANEL_PATH,
) -> pd.DataFrame:
    """Primary entry point: load the cached panel, or build (+ cache) it once."""
    if path.exists() and not refresh:
        return load_state_macro_panel(path)
    panel = build_state_macro_panel(states=states, api_key=api_key)
    save_state_macro_panel(panel, path)
    return panel


# ==========================================================================
# 4. Merge helper
# ==========================================================================
def _yyyymm_to_month_start(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype("Int64").astype(str), format="%Y%m")


def merge_macro(
    panel: pd.DataFrame,
    macro: pd.DataFrame | None = None,
    state_col: str = "property_state",
    month_col: str = "monthly_reporting_period",
) -> pd.DataFrame:
    """Merge state-month macro features onto a loan panel.

    Requires `panel` to carry `state_col` (postal code) and `month_col`
    (yyyymm, int or string). If orig_ltv/orig_upb/current_upb/
    first_payment_date are ALSO present, also computes updated_ltv (see
    module docstring, "UPDATED LTV").
    """
    if macro is None:
        macro = get_or_build_state_macro_panel()

    merged = panel.copy()
    merged["_month"] = _yyyymm_to_month_start(merged[month_col])

    macro_cur = macro.rename(columns={"hpi_index": "state_hpi_now", "property_state": state_col, "month": "_month"})
    keep_cols = [
        state_col,
        "_month",
        "uer",
        "delta_uer",
        "state_hpi_now",
        "hpi_growth",
        "uer_lag1",
        "delta_uer_lag1",
        "hpi_growth_lag1",
        "uer_is_national_fallback",
        "hpi_is_national_fallback",
    ]
    merged = merged.merge(macro_cur[keep_cols], on=[state_col, "_month"], how="left")

    if REQUIRED_LTV_COLS.issubset(panel.columns):
        merged["_orig_month"] = _yyyymm_to_month_start(merged["first_payment_date"])
        macro_orig = macro.rename(
            columns={"hpi_index": "state_hpi_orig", "property_state": state_col, "month": "_orig_month"}
        )[[state_col, "_orig_month", "state_hpi_orig"]]
        merged = merged.merge(macro_orig, on=[state_col, "_orig_month"], how="left")

        # NOTE: orig_upb <= 0 (missing-coded) makes this undefined (inf/NaN);
        # DCR's build_panel.py step 5 drops such loans upstream -- out of
        # scope for this merge helper, deferred to the ingest module.
        merged["updated_ltv"] = (
            merged["orig_ltv"]
            * (merged["current_upb"] / merged["orig_upb"])
            * (merged["state_hpi_orig"] / merged["state_hpi_now"])
        )
        merged = merged.drop(columns=["_orig_month"])
    else:
        logger.debug("merge_macro: skipping updated_ltv, missing one of %s", REQUIRED_LTV_COLS)

    return merged.drop(columns=["_month"])


# ==========================================================================
# 5. Exhibits
# ==========================================================================
def make_macro_exhibits(macro: pd.DataFrame | None = None, out_dir: Path = EXHIBIT_DIR) -> list[Path]:
    """State UER and HPI-growth small-multiple/spaghetti exhibits, 2000-2025.

    The point is visible state heterogeneity (NV's 2008-2011 crash and slow
    recovery vs. ND's shale-boom-era HPI growth and low UER), plotted
    against the FRED national anchors for context.
    """
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style

    apply_textbook_style()
    out_dir.mkdir(parents=True, exist_ok=True)

    if macro is None:
        macro = get_or_build_state_macro_panel()

    window = macro[(macro["month"] >= "2000-01-01") & (macro["month"] <= "2025-12-31")]

    national_ur = fetch_fred_series(NATIONAL_UR_SERIES, cache_dir=MACRO_CACHE_DIR)
    national_ur = national_ur[(national_ur["date"] >= "2000-01-01") & (national_ur["date"] <= "2025-12-31")]

    highlight_colors = {
        "CA": COLORS["accent"],
        "TX": COLORS["orange"],
        "FL": COLORS["purple"],
        "NV": COLORS["warn"],
        "ND": COLORS["good"],
    }

    written: list[Path] = []

    # --- Panel A: state UER spaghetti ------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    for state, g in window.groupby("property_state"):
        if state in HIGHLIGHT_STATES:
            continue
        ax.plot(g["month"], g["uer"], color=COLORS["gray"], alpha=0.18, linewidth=0.7, zorder=1)
    for state in HIGHLIGHT_STATES:
        g = window[window["property_state"] == state]
        ax.plot(g["month"], g["uer"], color=highlight_colors[state], linewidth=1.8, label=state, zorder=3)
    ax.plot(
        national_ur["date"], national_ur["value"], color="black", linestyle="--", linewidth=1.4,
        label="US (UNRATE)", zorder=4,
    )
    ax.set_title("State unemployment rate, 2000-2025 (highlighted: CA/TX/FL/NV/ND)")
    ax.set_ylabel("Unemployment rate (%)")
    ax.legend(loc="upper left", ncol=3, frameon=False)
    path_a = out_dir / "state_uer_2000_2025.png"
    fig.savefig(path_a)
    plt.close(fig)
    written.append(path_a)

    # --- Panel B: state HPI growth (trailing 12-month log growth) --------
    # Trailing 12m sum of the monthly log-diff = YoY log growth; this
    # smooths the step-function forward-fill artifact (see module
    # docstring) into a readable annual-growth line.
    fig, ax = plt.subplots(figsize=(9, 5))
    for state, g in window.groupby("property_state"):
        g = g.sort_values("month")
        yoy = g["hpi_growth"].rolling(12, min_periods=12).sum()
        if state in HIGHLIGHT_STATES:
            continue
        ax.plot(g["month"], yoy, color=COLORS["gray"], alpha=0.18, linewidth=0.7, zorder=1)
    national_hpi = fetch_fred_series(NATIONAL_HPI_SERIES, cache_dir=MACRO_CACHE_DIR).sort_values("date")
    national_hpi = national_hpi[(national_hpi["date"] >= "1999-01-01") & (national_hpi["date"] <= "2025-12-31")]
    nat_monthly_idx = pd.date_range(national_hpi["date"].min(), national_hpi["date"].max(), freq="MS")
    nat_series = national_hpi.set_index("date")["value"].reindex(nat_monthly_idx).ffill()
    nat_yoy = np.log(nat_series).diff().rolling(12, min_periods=12).sum()
    nat_yoy = nat_yoy[(nat_yoy.index >= "2000-01-01") & (nat_yoy.index <= "2025-12-31")]

    for state in HIGHLIGHT_STATES:
        g = window[window["property_state"] == state].sort_values("month")
        yoy = g["hpi_growth"].rolling(12, min_periods=12).sum()
        ax.plot(g["month"], yoy, color=highlight_colors[state], linewidth=1.8, label=state, zorder=3)
    ax.plot(nat_yoy.index, nat_yoy.values, color="black", linestyle="--", linewidth=1.4, label="US (USSTHPI)", zorder=4)
    ax.axhline(0, color=COLORS["gray"], linewidth=0.6)
    ax.set_title("State HPI growth, trailing 12m log growth, 2000-2025 (highlighted: CA/TX/FL/NV/ND)")
    ax.set_ylabel("YoY log HPI growth")
    ax.legend(loc="lower left", ncol=3, frameon=False)
    path_b = out_dir / "state_hpi_growth_2000_2025.png"
    fig.savefig(path_b)
    plt.close(fig)
    written.append(path_b)

    return written


# ==========================================================================
# 6. Script entry point
# ==========================================================================
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    api_key = os.environ.get("FRED_API_KEY")

    states = get_states_in_data()
    logger.info("states in SFLLD data (%d): %s", len(states), states)

    coverage = build_coverage_note(states)
    MACRO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    COVERAGE_NOTE_PATH.write_text(json.dumps(coverage, indent=2))
    logger.info(
        "coverage note written -> %s (UR fallback: %s, HPI fallback: %s)",
        COVERAGE_NOTE_PATH,
        coverage["ur_fallback_states"],
        coverage["hpi_fallback_states"],
    )

    panel = build_state_macro_panel(states=states, api_key=api_key)
    save_state_macro_panel(panel)
    logger.info("state macro panel: %d rows, %d states -> %s", len(panel), panel["property_state"].nunique(), STATE_PANEL_PATH)

    paths = make_macro_exhibits(panel)
    for p in paths:
        logger.info("exhibit written -> %s", p)


if __name__ == "__main__":
    main()
