"""DFAST 2026 supervisory-scenario ingestion (plan section 2.6; notes section 9).

Input :  data/scenarios/2026_Final_Supervisory_{Baseline,Severely_Adverse}_Domestic.csv
         (13 quarters, 2026Q1-2029Q1) and 2026_Final_Historic_Domestic.csv
         (200 quarters of actuals, 1976Q1-2025Q4).
Output:  tidy per-scenario quarterly frames of the PANEL-CONCEPT series used by
         the scenario layer (engine/scenarios.py).

Why DFAST (plan section 2.6): the supervisory paths give 28 variables that a
supervisor designed to be COHERENT — unemployment, HPI, GDP and rates move
together sensibly.  Hand-rolling a coherent multivariate stress path is
genuinely hard, so we ingest the shapes rather than invent them.

--------------------------------------------------------------------------------
COLUMN -> PANEL CONCEPT MAPPING (the contract this module implements)
--------------------------------------------------------------------------------
DFAST column                     panel concept    transformation
-------------------------------  ---------------  --------------------------------
'Unemployment rate'              uer              level, percentage points, as-is
'House Price Index (Level)'      hpi_growth       quarterly LOG-DIFF of the level
                                                  (decimal), matching the panel's
                                                  hpi_growth_lag1 construction;
                                                  the first supervisory quarter
                                                  (2026Q1) is differenced against
                                                  the LAST HISTORIC actual level
                                                  (2025Q4) so no observation is lost
'Real GDP growth'                gdp_growth       DFAST publishes SAAR-annualised
                                                  quarterly growth (%); converted
                                                  to a plain quarterly rate via
                                                  100*((1+g/100)^(1/4)-1)
'Mortgage rate'                  mortgage_rate    level, percentage points, as-is

Date format: the CSVs write quarters as '2026 Q1'; parsed to a pandas
PeriodIndex (freq='Q') by stripping the space.

The module performs structural validation on load: the two supervisory paths
must start exactly one quarter after the last historic actual (2026Q1 after
2025Q4), be 13 quarters long, and contain no missing values in any concept
column.  The historic frame's first hpi_growth (1976Q1) is NaN by construction
(no prior level) and is the only NaN tolerated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Repo-root-anchored so the module works from any cwd.
SCENARIO_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"

FILES: dict[str, str] = {
    "historic": "2026_Final_Historic_Domestic.csv",
    "baseline": "2026_Final_Supervisory_Baseline_Domestic.csv",
    "severely_adverse": "2026_Final_Supervisory_Severely_Adverse_Domestic.csv",
}

#: Panel-concept columns produced by derive_concepts, in canonical order.
CONCEPTS: tuple[str, ...] = ("uer", "hpi_growth", "gdp_growth", "mortgage_rate")

# Raw DFAST columns consumed (kept explicit so a vintage change fails loudly).
_RAW_COLS = {
    "uer": "Unemployment rate",
    "hpi_level": "House Price Index (Level)",
    "gdp_saar": "Real GDP growth",
    "mortgage_rate": "Mortgage rate",
}


def parse_dfast_csv(path: str | Path) -> pd.DataFrame:
    """Read one DFAST CSV into a frame indexed by quarterly Period.

    Handles the '2026 Q1' date format; sorts by quarter; validates the
    expected raw columns are present.
    """
    df = pd.read_csv(path)
    missing = [c for c in _RAW_COLS.values() if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing expected DFAST columns {missing}")
    idx = pd.PeriodIndex(df["Date"].str.replace(" ", "", regex=False), freq="Q")
    df = df.set_index(idx).sort_index()
    if df.index.duplicated().any():
        raise ValueError(f"{path}: duplicate quarters in Date column")
    return df


def saar_to_quarterly(g_saar) -> np.ndarray | float:
    """SAAR-annualised growth (%) -> plain quarterly growth (%).

    DFAST publishes real GDP growth as a seasonally-adjusted ANNUALISED rate;
    the quarterly rate is the geometric fourth root:
    100*((1+g/100)^(1/4)-1).  saar_to_quarterly(4.0) ~= 0.985.
    """
    return 100.0 * ((1.0 + np.asarray(g_saar, dtype=float) / 100.0) ** 0.25 - 1.0)


def derive_concepts(raw: pd.DataFrame,
                    prior_hpi_level: float | None = None) -> pd.DataFrame:
    """Map one parsed DFAST frame to the panel-concept columns (CONCEPTS).

    prior_hpi_level: HPI level of the quarter immediately BEFORE raw's first
    row (the last historic actual when raw is a supervisory path), so the
    first quarter's hpi_growth is a real log-diff instead of NaN.
    """
    hpi = raw[_RAW_COLS["hpi_level"]].astype(float)
    hpi_lag = hpi.shift(1)
    if prior_hpi_level is not None:
        hpi_lag.iloc[0] = float(prior_hpi_level)
    return pd.DataFrame(
        {
            "uer": raw[_RAW_COLS["uer"]].astype(float),
            "hpi_growth": np.log(hpi / hpi_lag),
            "gdp_growth": saar_to_quarterly(raw[_RAW_COLS["gdp_saar"]]),
            "mortgage_rate": raw[_RAW_COLS["mortgage_rate"]].astype(float),
        },
        index=raw.index,
    )


@dataclass(frozen=True)
class DfastData:
    """Tidy panel-concept frames for the three DFAST CSVs.

    historic          : 1976Q1-2025Q4 actuals (hpi_growth NaN in 1976Q1 only)
    baseline          : 2026Q1-2029Q1 supervisory baseline path
    severely_adverse  : 2026Q1-2029Q1 supervisory severely-adverse path
    jumpoff           : the 2025Q4 actual concept values — the DFAST jump-off
                        row that scenario deltas are measured against
    """

    historic: pd.DataFrame
    baseline: pd.DataFrame
    severely_adverse: pd.DataFrame
    jumpoff: pd.Series


def load_dfast(scenario_dir: str | Path = SCENARIO_DIR) -> DfastData:
    """Parse and validate all three DFAST CSVs; return concept frames."""
    scenario_dir = Path(scenario_dir)
    raw = {k: parse_dfast_csv(scenario_dir / v) for k, v in FILES.items()}

    historic = derive_concepts(raw["historic"])
    prior_hpi = float(raw["historic"][_RAW_COLS["hpi_level"]].iloc[-1])
    baseline = derive_concepts(raw["baseline"], prior_hpi_level=prior_hpi)
    severe = derive_concepts(raw["severely_adverse"], prior_hpi_level=prior_hpi)

    # -- structural validation ------------------------------------------------
    last_hist = historic.index[-1]
    for name, path in (("baseline", baseline), ("severely_adverse", severe)):
        if path.index[0] != last_hist + 1:
            raise ValueError(
                f"{name}: path starts {path.index[0]}, expected "
                f"{last_hist + 1} (one quarter after last historic actual)")
        if len(path) != 13:
            raise ValueError(f"{name}: expected 13 quarters, got {len(path)}")
        if not (path.index == pd.period_range(path.index[0], periods=len(path),
                                              freq="Q")).all():
            raise ValueError(f"{name}: quarters are not contiguous")
        if path[list(CONCEPTS)].isna().any().any():
            raise ValueError(f"{name}: NaNs in derived concept columns")

    jumpoff = historic[list(CONCEPTS)].iloc[-1]
    if jumpoff.isna().any():
        raise ValueError("historic jump-off row (2025Q4) has NaN concepts")

    return DfastData(historic=historic, baseline=baseline,
                     severely_adverse=severe, jumpoff=jumpoff)
