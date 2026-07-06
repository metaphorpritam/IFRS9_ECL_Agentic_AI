"""Scenario set for scenario-conditional ECL (plan section 2.6; notes section 9).

Builds the three probability-weighted macro scenarios (base / down / up) that
the forward-looking layer conditions on, as 40-quarter paths of the panel
concepts uer, hpi_growth, gdp_growth, mortgage_rate (data/ingest/dfast.py).

--------------------------------------------------------------------------------
REBASING CONVENTION — DFAST deltas transplanted onto the panel's t=60 state
--------------------------------------------------------------------------------
The panel's clock ends at t=60 ~ 2015Q1 (calendar anchoring verified against
FRED UNRATE, corr 0.9963), while the DFAST 2026 paths run 2026Q1-2029Q1.  The
supervisory paths are therefore NOT usable as levels — but their value is the
supervisor-designed coherent multivariate SHAPE (unemployment, HPI, GDP and
rates move together sensibly).  Convention:

    scenario_h(c) = panel_t60_level(c) + [ dfast_h(c) - dfast_jumpoff(c) ]

i.e. each variable's change-from-jump-off (jump-off = 2025Q4, the last
historic actual) is added to the panel's reporting-date (t=60) level.  The
additive delta is applied uniformly to every concept — levels (uer,
mortgage_rate) and quarterly growth rates (hpi_growth, gdp_growth) alike —
which preserves the DFAST co-movement structure exactly while anchoring all
paths at the reporting date's macro state.  This is a SHAPE TRANSPLANT, not a
forecast made in 2015 (documented simplification).

UPSIDE SCENARIO (judgmental construction): DFAST publishes no upside, so the
up path is a DAMPED MIRROR of the severely-adverse deltas with factor -0.35:
a mild boom in which UER drifts down (floored at 3.5pp, roughly the postwar
full-employment trough) and HPI appreciates.  The mirror inherits DFAST's
co-movement, and the damping reflects the empirical asymmetry of the cycle
(booms are shallower than busts).  NAMED ENHANCEMENT (plan section 2.6): a
defensible upgrade is to anchor the upside to Philadelphia-Fed SPF forecaster
distribution percentiles (e.g. the 25th percentile of the unemployment
distribution) instead of a judgmental mirror; the convention here is the
governance-documented placeholder for that.

R&S WINDOW + REVERSION (notes section 9.4): scenarios are reasonable and
supportable only over the 13-quarter DFAST window.  Beyond it each path
reverts LINEARLY to the panel's own long-run means over 8 quarters, then
holds at the long-run mean out to the 40-quarter horizon — the standard
"condition PIT over the R&S window, revert to TTC" construction.  All three
scenarios share the same long-run tail, so scenario differentiation lives
entirely in the 13q path + 8q ramp.

WEIGHTS: 50/25/25 (base/down/up) — plan section 2.6's governance-committee
convention.  Scenario probabilities are not statistically identified; the
deliverable is the documented rationale plus weight-sensitivity exhibits,
not the number itself.  Weights must sum to 1 (validated).

Jump-off macro state (panel t=60, verified): uer 5.7pp, quarterly hpi_growth
+1.15%, mortgage rate (quarterly median of rate_time) 4.62%; panel long-run
means: uer 6.39pp, hpi_growth +0.96%/q, mortgage rate 4.63%.

Unit conventions: uer and mortgage_rate in percentage points; hpi_growth a
DECIMAL quarterly log-diff (matches the panel's hpi_growth_lag1); gdp_growth
a plain quarterly percentage.  The panel's gdp_time is a YEAR-OVER-YEAR
growth rate (trough -4.15 in 2009, matching YoY real GDP, not the -8.5 SAAR
trough), so it is converted to a quarterly-equivalent geometric rate with the
same fourth-root formula used for the DFAST SAAR series — the intra-year
quarterly profile is unidentified from YoY alone (documented simplification).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from data.ingest.dfast import CONCEPTS, load_dfast, saar_to_quarterly
from engine.staging import build_macro_map

PANEL_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "panel.parquet"

#: Panel clock t=1 corresponds to calendar 2000Q2 (empirically verified vs
#: FRED UNRATE, corr 0.9963); hence t=60 ~ 2015Q1.
PANEL_T1_PERIOD = pd.Period("2000Q2", freq="Q")

DEFAULT_WEIGHTS: dict[str, float] = {"base": 0.50, "down": 0.25, "up": 0.25}

#: Damping factor for the judgmental upside mirror of severely-adverse deltas.
UPSIDE_MIRROR_FACTOR = -0.35

#: Floor on the upside unemployment path, percentage points.
UER_FLOOR_PP = 3.5


def panel_time_to_period(t: int) -> pd.Period:
    """Panel clock quarter t (1..60) -> calendar quarter (t=1 ~ 2000Q2)."""
    return PANEL_T1_PERIOD + (int(t) - 1)


def panel_macro_concepts(macro_map: pd.DataFrame) -> pd.DataFrame:
    """engine.staging.build_macro_map output -> per-quarter concept frame.

    Columns produced (CONCEPTS): uer (pp), hpi_growth (decimal quarterly
    log-diff; NaN at the first panel quarter), gdp_growth (quarterly %,
    converted from the panel's YoY gdp_time — module docstring), and
    mortgage_rate (pp; the panel's quarterly MEDIAN rate_time, same
    market-rate convention as engine.staging.build_macro_map).
    """
    return pd.DataFrame(
        {
            "uer": macro_map["uer"],
            "hpi_growth": np.log(macro_map["hpi"]).diff(),
            "gdp_growth": saar_to_quarterly(macro_map["gdp"]),
            "mortgage_rate": macro_map["rate_med"],
        },
        index=macro_map.index,
    )


@dataclass(frozen=True)
class ScenarioSet:
    """Named macro scenario paths + probability weights (validated).

    paths   : name -> frame indexed by horizon quarter h = 1..horizon with a
              'period' column (real calendar quarter, jump-off + h) and the
              CONCEPTS columns.
    weights : name -> probability; keys must match paths; must sum to 1.
    jumpoff : panel t=60 concept levels the paths are rebased onto (h=0 row).
    longrun : panel long-run concept means (the shared reversion target).
    rs_window / reversion: quarters of DFAST path / linear-reversion ramp.
    """

    paths: Mapping[str, pd.DataFrame]
    weights: Mapping[str, float] = field(
        default_factory=lambda: dict(DEFAULT_WEIGHTS))
    jumpoff: pd.Series = None
    longrun: pd.Series = None
    horizon: int = 40
    rs_window: int = 13
    reversion: int = 8
    jumpoff_time: int = 60

    def __post_init__(self) -> None:
        if set(self.paths) != set(self.weights):
            raise ValueError(
                f"scenario names mismatch: paths={sorted(self.paths)} "
                f"weights={sorted(self.weights)}")
        w = pd.Series(self.weights, dtype=float)
        if (w < 0).any():
            raise ValueError(f"negative scenario weight: {self.weights}")
        if abs(w.sum() - 1.0) > 1e-9:
            raise ValueError(f"scenario weights must sum to 1, got {w.sum()}")
        for name, df in self.paths.items():
            missing = [c for c in CONCEPTS if c not in df.columns]
            if missing:
                raise ValueError(f"{name}: missing concept columns {missing}")
            if len(df) != self.horizon:
                raise ValueError(
                    f"{name}: path length {len(df)} != horizon {self.horizon}")
            vals = df[list(CONCEPTS)].to_numpy(dtype=float)
            if not np.isfinite(vals).all():
                raise ValueError(f"{name}: non-finite values in path")

    @property
    def jumpoff_period(self) -> pd.Period:
        return panel_time_to_period(self.jumpoff_time)

    def path(self, name: str) -> pd.DataFrame:
        return self.paths[name]

    def weighted_path(self) -> pd.DataFrame:
        """Probability-weighted AVERAGE macro path (exhibit / sanity use only).

        WARNING (notes section 9.2, Jensen): ECL must be the weighted average
        of the per-scenario ECLs, NEVER the ECL of this averaged path —
        convexity makes the latter systematically understate expected loss.
        """
        first = next(iter(self.paths.values()))
        acc = sum(self.weights[n] * self.paths[n][list(CONCEPTS)]
                  for n in self.paths)
        out = acc.copy()
        out.insert(0, "period", first["period"])
        return out

    def as_long_frame(self) -> pd.DataFrame:
        """Tidy long frame (scenario, h, period, concept columns) for exhibits."""
        rows = []
        for name, df in self.paths.items():
            d = df.copy()
            d.insert(0, "scenario", name)
            d.insert(1, "h", d.index)
            rows.append(d)
        return pd.concat(rows, ignore_index=True)


def _extend_with_reversion(rs_path: np.ndarray, longrun: np.ndarray,
                           horizon: int, reversion: int) -> np.ndarray:
    """R&S path (n x k) -> horizon x k: linear reversion to longrun, then hold."""
    n = rs_path.shape[0]
    if horizon < n:
        raise ValueError(f"horizon {horizon} shorter than R&S window {n}")
    out = np.empty((horizon, rs_path.shape[1]), dtype=float)
    out[:n] = rs_path
    v_end = rs_path[-1]
    for j in range(1, min(reversion, horizon - n) + 1):
        out[n + j - 1] = v_end + (j / reversion) * (longrun - v_end)
    if n + reversion < horizon:
        out[n + reversion:] = longrun
    return out


def build_scenario_set(panel_path: str | Path = PANEL_PATH,
                       horizon: int = 40,
                       reversion: int = 8,
                       mirror_factor: float = UPSIDE_MIRROR_FACTOR,
                       uer_floor: float = UER_FLOOR_PP,
                       weights: Mapping[str, float] | None = None,
                       ) -> ScenarioSet:
    """Build the base/down/up ScenarioSet at the panel's t=60 reporting date.

    base : DFAST supervisory-baseline deltas rebased onto t=60 levels
    down : DFAST severely-adverse deltas rebased onto t=60 levels
    up   : damped mirror (mirror_factor, default -0.35) of the severely-
           adverse deltas, UER floored at uer_floor (default 3.5pp)

    All paths extend past the 13q R&S window by linear reversion to the
    panel long-run means over `reversion` quarters, then hold to `horizon`.
    """
    panel = pd.read_parquet(
        panel_path,
        columns=["time", "uer_time", "gdp_time", "hpi_time", "rate_time"])
    concepts = panel_macro_concepts(build_macro_map(panel))

    t_jump = int(concepts.index.max())
    jumpoff = concepts.loc[t_jump, list(CONCEPTS)].astype(float)
    longrun = concepts[list(CONCEPTS)].mean()  # skips the t=1 hpi_growth NaN
    jump_period = panel_time_to_period(t_jump)

    dfast = load_dfast()
    rs_window = len(dfast.baseline)
    deltas = {
        "base": dfast.baseline[list(CONCEPTS)] - dfast.jumpoff[list(CONCEPTS)],
        "down": (dfast.severely_adverse[list(CONCEPTS)]
                 - dfast.jumpoff[list(CONCEPTS)]),
    }
    deltas["up"] = mirror_factor * deltas["down"]

    paths: dict[str, pd.DataFrame] = {}
    for name, delta in deltas.items():
        rs = jumpoff.to_numpy() + delta.to_numpy(dtype=float)
        full = _extend_with_reversion(rs, longrun.to_numpy(), horizon, reversion)
        df = pd.DataFrame(full, columns=list(CONCEPTS),
                          index=pd.RangeIndex(1, horizon + 1, name="h"))
        df["uer"] = df["uer"].clip(lower=uer_floor)
        df.insert(0, "period",
                  pd.PeriodIndex([jump_period + h for h in df.index], freq="Q"))
        paths[name] = df

    return ScenarioSet(
        paths=paths,
        weights=dict(weights) if weights is not None else dict(DEFAULT_WEIGHTS),
        jumpoff=jumpoff,
        longrun=longrun,
        horizon=horizon,
        rs_window=rs_window,
        reversion=reversion,
        jumpoff_time=t_jump,
    )
