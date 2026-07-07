"""Tier-1 parameterised tools over the FROZEN IFRS 9 ECL engine.

Four PURE, deterministic functions the LLM router (Day 4) can call. Each
returns a JSON-serialisable dict whose every number comes straight from the
engine — THE GOVERNING RULE: the LLM never does arithmetic; it only routes,
parameterises and narrates. Pydantic argument models are the contract:
malformed arguments are rejected loudly BEFORE any engine code runs.

Tools
-----
shock_macro(var, shock, shape)
    Perturb the BASE scenario macro path (engine/scenarios.py), rerun the
    satellite -> Z -> PIT -> ECL chain for the t=60 book and compare against
    the unshocked base-scenario allowance.

    COHERENT-SHOCK CONVENTION (important, documented): the fitted satellite
    is Z = f(hpi_growth_lag1, gdp_growth_lag2) — the unemployment driver
    (duer) was EXCLUDED by the economic-sign governance constraint on this
    one-cycle panel (outputs/satellite/satellite_report.md). A univariate
    UER-only path move would therefore be invisible to the credit-cycle
    factor, which is not an economics statement ("unemployment does not
    matter") but a small-sample identification artifact. Supervisory
    scenarios are coherent multivariate paths, so the tool implements every
    shock as a CO-MOVING macro move along the DFAST severe-minus-base
    direction: the named variable moves by exactly `shock` (peak of the
    shape profile), and the other two concepts move by their co-movement
    loadings beta_c = <d_var, d_c> / <d_var, d_var> estimated from the
    severe-minus-base concept deltas over the 13q R&S window (beta of the
    named variable is exactly 1). The applied per-concept deltas are
    returned for full transparency.

    Shock units: UER in percentage points on the unemployment LEVEL;
    HPI in percentage points per quarter on the QUARTERLY HPI growth rate;
    GDP in percentage points per quarter on the QUARTERLY GDP growth rate.
    Bounds (validation errors beyond them): |UER| <= 10pp, |HPI| <= 5pp/q,
    |GDP| <= 5pp/q.

    Shapes: 'parallel' adds the shock uniformly over the whole 40q path (a
    sustained level move — the tail deliberately no longer reverts to the
    long-run mean); 'peak_revert' ramps linearly 0 -> shock over the first
    4 quarters, holds at the peak through the 13q R&S window, then decays
    linearly to 0 over the 8q reversion ramp (zero from h=21 on).

reweight_scenarios(w_up, w_base, w_down)
    Weights must be non-negative and sum to ~1 (tolerance 1e-6; then
    renormalised exactly). Weighted allowance recomputed from the three
    CACHED per-scenario ECL books; the Jensen denominator (ECL of the
    weighted-average macro path) uses the module cache for the adopted
    50/25/25 weights and otherwise one engine run on the weighted Z path
    (satellite linearity: Z of the weighted macro path == weighted Z paths,
    unit-tested in tests/test_satellite.py), memoised per weight vector.

rerun_ecl(segment)
    Scenario-weighted (adopted 50/25/25) allowance decomposed for a segment
    of the t=60 book: all | stage1 | stage2 | stage3 | investor (investor
    originations) | high_ltv (current updated LTV > 80).

decompose_waterfall(t0, t1)
    The FROZEN engine.ecl.movement_decomposition between two rung-1
    snapshots (1 <= t0 < t1 <= 60): opening + stage_migration +
    remeasurement + derecognitions + new_loans = closing (identity asserted
    inside the frozen engine).

Heavy artifacts + staleness rule
--------------------------------
All heavy state (fitted hazards + LGD, Z recovery, satellite, scenario set,
the four per-loan scenario ECL books, the t=60 staging table) is built ONCE,
lazily, on the first tool call (call `warm_up()` from the FastAPI lifespan
startup to pay the cost up front). The slow part — the three model fits,
~10-50s — is dumped via joblib to outputs/models/tier1_models.joblib for
warm starts, AFTER stripping the embedded statsmodels training arrays
(_strip_training_data: ~750MB -> a few MB; predict/design_info survive, and
the stripped copy is also what runs in-process so both start paths are
identical). STALENESS RULE: the cache is keyed by a fingerprint of
data/processed/panel.parquet (size + mtime), the bytes of engine/hazard.py
and engine/lgd.py, and CACHE_VERSION; a mismatch triggers a silent refit.
Those inputs are frozen, so if any OTHER upstream convention ever changes,
bump CACHE_VERSION (or delete outputs/models/) to force a refit. Everything
downstream of the fits (~5s) is recomputed at init, never cached to disk.

Audit trail
-----------
Every successful call appends one line to outputs/agent_log/tool_calls.jsonl:
{"seq", "ts", "tool", "args", "headline"} — the replayable audit trail. The
returned tool_call_id ("tc-<seq>") references that line. Validation
failures raise pydantic.ValidationError and are NOT logged (nothing ran).

Frozen-engine discipline: engine/{hazard,lgd,ead,staging,ecl}.py are
imported READ-ONLY and composed, never edited; Day-3 modules
engine/{vasicek,scenarios,satellite}.py are likewise only imported.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.ecl import EclConfig, ecl_for_snapshot, movement_decomposition
from engine.hazard import fit_default_hazard, fit_prepay_hazard
from engine.lgd import fit_lgd_models
from engine.satellite import (
    driver_frame,
    fit_satellite,
    recover_z,
    scenario_ecl_for_snapshot,
    scenario_z_paths,
    ttc_macro_means,
)
from engine.scenarios import (
    build_scenario_set,
    panel_macro_concepts,
    panel_time_to_period,
)
from engine.staging import assign_stages, build_macro_map

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = PROJECT_ROOT / "data" / "processed" / "panel.parquet"
MODELS_DIR = PROJECT_ROOT / "outputs" / "models"
LOG_PATH = PROJECT_ROOT / "outputs" / "agent_log" / "tool_calls.jsonl"

#: bump to invalidate outputs/models/tier1_models.joblib (staleness rule
#: in the module docstring); v3 = training payload stripped + frame pruned
CACHE_VERSION = 3

#: the reporting snapshot every Tier-1 tool answers about (~ 2015Q1)
T_SNAP = 60

#: current-LTV threshold defining the 'high_ltv' segment (percent)
HIGH_LTV_THRESHOLD = 80.0

#: shock bounds per macro variable, in the tool's pp units (docstring)
SHOCK_BOUNDS = {"UER": 10.0, "HPI": 5.0, "GDP": 5.0}

#: tool variable -> engine.scenarios concept column
VAR_TO_CONCEPT = {"UER": "uer", "HPI": "hpi_growth", "GDP": "gdp_growth"}

#: pp shock -> concept units (hpi_growth is a DECIMAL quarterly rate)
VAR_SCALE = {"UER": 1.0, "HPI": 0.01, "GDP": 1.0}

SHOCK_UNITS = {
    "UER": "percentage points on the unemployment level",
    "HPI": "percentage points per quarter on quarterly HPI growth",
    "GDP": "percentage points per quarter on quarterly GDP growth",
}

#: quarters of the linear ramp-up in the 'peak_revert' shock shape
RAMP_UP_Q = 4

#: satellite concept columns (order fixed)
_CONCEPT_COLS = ("uer", "hpi_growth", "gdp_growth")

SEGMENT_DEFS = {
    "all": "entire non-payoff book at the t=60 reporting date",
    "stage1": "Stage 1 loans (12-month ECL)",
    "stage2": "Stage 2 loans (lifetime ECL, SICR-triggered)",
    "stage3": "Stage 3 loans (credit-impaired; ECL = LGD x balance, "
              "scenario-invariant)",
    "investor": "investor-occupancy originations (investor_orig_time == 1)",
    "high_ltv": f"current updated LTV > {HIGH_LTV_THRESHOLD:.0f}",
}


# ---------------------------------------------------------------------------
# argument contracts (pydantic = the schema; validation BEFORE the engine)
# ---------------------------------------------------------------------------

class ShockMacroArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    var: Literal["UER", "HPI", "GDP"]
    shock: float = Field(allow_inf_nan=False,
                         description="shock size in pp (SHOCK_UNITS)")
    shape: Literal["parallel", "peak_revert"] = "parallel"

    @model_validator(mode="after")
    def _within_bounds(self) -> "ShockMacroArgs":
        bound = SHOCK_BOUNDS[self.var]
        if abs(self.shock) > bound:
            raise ValueError(
                f"|{self.var} shock| must be <= {bound:g}pp "
                f"({SHOCK_UNITS[self.var]}); got {self.shock:g}")
        return self


class ReweightArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    w_up: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    w_base: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    w_down: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _sums_to_one(self) -> "ReweightArgs":
        s = self.w_up + self.w_base + self.w_down
        if abs(s - 1.0) > 1e-6:
            raise ValueError(
                f"scenario weights must sum to 1 (tolerance 1e-6); got "
                f"w_up={self.w_up:g} + w_base={self.w_base:g} + "
                f"w_down={self.w_down:g} = {s:g}")
        return self


class RerunEclArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment: Literal["all", "stage1", "stage2", "stage3", "investor",
                     "high_ltv"] = "all"


class DecomposeWaterfallArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    t0: int = Field(default=20, ge=1, le=T_SNAP)
    t1: int = Field(default=40, ge=1, le=T_SNAP)

    @model_validator(mode="after")
    def _ordered(self) -> "DecomposeWaterfallArgs":
        if not self.t0 < self.t1:
            raise ValueError(
                f"need 1 <= t0 < t1 <= {T_SNAP}; got t0={self.t0}, "
                f"t1={self.t1}")
        return self


# ---------------------------------------------------------------------------
# heavy engine state (lazy singleton; joblib warm start for the model fits)
# ---------------------------------------------------------------------------

@dataclass
class EngineState:
    """Everything the four tools need, built once (module docstring)."""

    panel: pd.DataFrame
    cfg: EclConfig
    models: dict
    res: object                       # BelkinResult (rho, z, mean_z)
    concepts: pd.DataFrame            # panel macro concept history (t=1..60)
    satm: object                      # SatelliteModel
    sset: object                      # ScenarioSet
    zpaths: pd.DataFrame              # scenario Z paths (h=1..40)
    staged: pd.DataFrame              # t=60 staging table (scenario-invariant)
    macro_means: pd.Series            # composition-adjusted TTC anchor state
    books: dict[str, pd.DataFrame]    # per-loan scenario ECL books
    scenario_totals: dict[str, float]  # reported allowance per scenario (USD)
    balance: float                    # t=60 book balance (EAD proxy for cov.)
    segments: pd.DataFrame            # id, investor flag, updated LTV
    betas: dict[str, dict[str, float]]  # co-movement loadings per shock var
    at_avg_cache: dict[tuple, float] = field(default_factory=dict)
    frozen_books: dict[int, pd.DataFrame] = field(default_factory=dict)


_STATE: EngineState | None = None
_STATE_LOCK = threading.Lock()


def _fingerprint() -> str:
    """Cache key: panel size+mtime, hazard/LGD source bytes, CACHE_VERSION."""
    h = hashlib.sha256()
    h.update(f"tier1-cache-v{CACHE_VERSION}".encode())
    st = PANEL_PATH.stat()
    h.update(f"|panel:{st.st_size}:{st.st_mtime_ns}".encode())
    for name in ("hazard.py", "lgd.py"):
        h.update((PROJECT_ROOT / "engine" / name).read_bytes())
    return h.hexdigest()[:16]


def _formula_columns(formula: str, frame: pd.DataFrame) -> list[str]:
    """Frame columns the patsy formula references by name (word-boundary)."""
    return [c for c in frame.columns
            if re.search(rf"\b{re.escape(c)}\b", formula)]


def _strip_training_data(models: dict) -> dict:
    """Deep-copy the fitted models and shed the embedded training payload.

    statsmodels results drag the full estimation sample along (~750MB on
    this panel). Every downstream engine call uses only result.params,
    formula-based result.predict(new_df) and result.model.data.design_info,
    so three official/structural reductions are safe:

      1. remove_data() — drops the nobs-length arrays (endog/exog, working
         weights, residuals, fitted values). Scalar diagnostics (llf,
         llnull — so HazardModel.mcfadden_r2 keeps working) are touched
         first so they are cached before the data disappears.
      2. data.frame pruned to the COLUMNS the formula references, SAME
         rows: patsy design_info cannot be pickled, so statsmodels
         __setstate__ rebuilds it at load time via dmatrices(formula,
         frame) — the stateful transforms (cr() spline knots, center()
         means) are re-derived from these exact rows, giving a
         bit-identical design_info.
      3. orig_endog / orig_exog nulled — __setstate__ only falls back to
         them when `frame` is absent, and no engine path reads them.

    The STRIPPED copy is what gets dumped AND used in-process, so
    warm-started and freshly-fitted sessions run identical objects (the
    published-number identities in tests/test_tools.py pin this).
    """
    slim = copy.deepcopy(models)
    for res in (slim["default"].result, slim["prepay"].result,
                slim["lgd"].cure_result, slim["lgd"].severity_result):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # bic-formula FutureWarning etc.
            for attr in ("llf", "llnull", "aic", "bic"):
                try:
                    getattr(res, attr)
                except Exception:      # diagnostic not defined for family
                    pass
            res.remove_data()
        data = res.model.data
        if getattr(data, "frame", None) is not None:
            data.frame = data.frame[
                _formula_columns(res.model.formula, data.frame)]
        data.orig_endog = None
        data.orig_exog = None
    return slim


def _fit_or_load_models(panel: pd.DataFrame) -> dict:
    """Joblib warm start for the ~10-50s model fits (staleness rule above)."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    cache = MODELS_DIR / "tier1_models.joblib"
    fp = _fingerprint()
    if cache.exists():
        try:
            with warnings.catch_warnings():
                # joblib's numpy_pickle trips a NumPy 2.5 deprecation
                warnings.simplefilter("ignore", DeprecationWarning)
                payload = joblib.load(cache)
            if payload.get("fingerprint") == fp:
                return payload["models"]
        except Exception:
            pass                       # unreadable cache -> refit below
    train = panel[panel["split"] == "train"]
    models = _strip_training_data({
        "default": fit_default_hazard(train),
        "prepay": fit_prepay_hazard(train),
        "lgd": fit_lgd_models(panel),
    })
    joblib.dump({"fingerprint": fp, "models": models}, cache)
    return models


def _comovement_betas(sset) -> dict[str, dict[str, float]]:
    """Severe-minus-base co-movement loadings over the 13q R&S window.

    beta[v][c] = <d_v, d_c> / <d_v, d_v> on the concept delta paths, so a
    1-unit move in v carries beta[v][c] units of c (beta[v][v] == 1). This
    is the DFAST co-movement structure the scenario set was built to
    preserve — the coherent-shock convention of shock_macro.
    """
    rs = int(sset.rs_window)
    d = {c: (sset.paths["down"][c].to_numpy(dtype=float)[:rs]
             - sset.paths["base"][c].to_numpy(dtype=float)[:rs])
         for c in _CONCEPT_COLS}
    betas: dict[str, dict[str, float]] = {}
    for v in _CONCEPT_COLS:
        denom = float(np.dot(d[v], d[v]))
        if denom <= 0.0:
            raise RuntimeError(f"degenerate severe-minus-base delta for {v}")
        betas[v] = {c: float(np.dot(d[v], d[c]) / denom)
                    for c in _CONCEPT_COLS}
    return betas


def _build_state() -> EngineState:
    """The full macro -> satellite -> Z -> PIT -> ECL chain, once.

    Mirrors analysis/run_scenarios.py exactly (same calls, same order), so
    the cached books reproduce outputs/scenario_ecl/scenario_ecl_summary.csv.
    """
    cfg = EclConfig()
    panel = pd.read_parquet(PANEL_PATH)
    models = _fit_or_load_models(panel)

    res, tab = recover_z(panel, models["default"])
    concepts = panel_macro_concepts(build_macro_map(panel))
    satm = fit_satellite(pd.Series(res.z, index=tab.index),
                         driver_frame(concepts))
    if not satm.fit_meta["sign_valid"]:
        raise RuntimeError("no sign-admissible satellite spec found")
    sset = build_scenario_set()
    zpaths = scenario_z_paths(satm, sset, concepts)

    hz = {"default": models["default"], "prepay": models["prepay"]}
    staged = assign_stages(panel.loc[panel["time"] <= T_SNAP], hz,
                           cfg.staging, snapshot_time=T_SNAP)
    macro_means = ttc_macro_means(panel)

    books = {
        name: scenario_ecl_for_snapshot(
            panel, T_SNAP, models, z_path=zpaths[name].to_numpy(dtype=float),
            rho=res.rho, macro_means=macro_means, staged=staged, config=cfg)
        for name in ("up", "base", "down", "weighted")
    }
    scenario_totals = {n: float(b["ecl_reported"].sum())
                       for n, b in books.items()}
    balance = float(books["base"]["balance"].sum())

    segments = (panel.loc[(panel["time"] == T_SNAP)
                          & (panel["payoff_event"] == 0),
                          ["id", "investor_orig_time", "updated_ltv"]]
                .sort_values("id").reset_index(drop=True))
    if not (segments["id"].to_numpy()
            == books["base"]["id"].to_numpy()).all():
        raise RuntimeError("segment frame misaligned with the ECL book")

    state = EngineState(
        panel=panel, cfg=cfg, models=models, res=res, concepts=concepts,
        satm=satm, sset=sset, zpaths=zpaths, staged=staged,
        macro_means=macro_means, books=books,
        scenario_totals=scenario_totals, balance=balance,
        segments=segments, betas=_comovement_betas(sset),
    )
    # seed the Jensen denominator for the adopted weights from the init run
    state.at_avg_cache[_weights_key(sset.weights["up"], sset.weights["base"],
                                    sset.weights["down"])] \
        = scenario_totals["weighted"]
    return state


def _state() -> EngineState:
    global _STATE
    if _STATE is None:
        with _STATE_LOCK:
            if _STATE is None:
                _STATE = _build_state()
    return _STATE


def warm_up() -> None:
    """Build (or joblib warm-load) the engine state now.

    Call from the FastAPI lifespan startup so the first user question
    answers in seconds, not tens of seconds.
    """
    _state()


# ---------------------------------------------------------------------------
# audit trail (outputs/agent_log/tool_calls.jsonl)
# ---------------------------------------------------------------------------

_LOG_LOCK = threading.Lock()
_SEQ: int | None = None


def _last_logged_seq(path: Path) -> int:
    if not path.exists():
        return 0
    last = None
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last = line
    if last is None:
        return 0
    try:
        return int(json.loads(last)["seq"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return sum(1 for _ in path.open("r", encoding="utf-8"))


def _log_call(tool: str, args: dict, headline: str) -> str:
    """Append one audit line; return the tool_call_id referencing it."""
    global _SEQ
    with _LOG_LOCK:
        path = Path(LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        if _SEQ is None:
            _SEQ = _last_logged_seq(path)
        _SEQ += 1
        entry = {"seq": _SEQ,
                 "ts": datetime.now(timezone.utc)
                               .isoformat(timespec="seconds"),
                 "tool": tool, "args": args, "headline": headline}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return f"tc-{_SEQ:06d}"


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------

def _weights_key(w_up: float, w_base: float, w_down: float) -> tuple:
    return (round(float(w_up), 9), round(float(w_base), 9),
            round(float(w_down), 9))


def _z_for_macro_path(state: EngineState, path_df: pd.DataFrame) -> np.ndarray:
    """Satellite Z for a 40q concept path, history spliced for the lags.

    The identical splice convention to engine.satellite.scenario_z_paths:
    the panel's own concept history goes IN FRONT so the h=1,2 driver lags
    reach back into observed quarters.
    """
    cols = list(_CONCEPT_COLS)
    hist = state.concepts[cols].reset_index(drop=True)
    fut = path_df[cols].reset_index(drop=True)
    drv = driver_frame(pd.concat([hist, fut], ignore_index=True)) \
        .iloc[len(hist):]
    z = state.satm.predict(drv)
    if not np.isfinite(z).all():
        raise RuntimeError("non-finite satellite Z on the shocked path")
    return z


def _run_book(state: EngineState, z_path: np.ndarray) -> pd.DataFrame:
    """One scenario-conditional ECL run of the t=60 book (frozen engine)."""
    return scenario_ecl_for_snapshot(
        state.panel, T_SNAP, state.models,
        z_path=np.asarray(z_path, dtype=float), rho=state.res.rho,
        macro_means=state.macro_means, staged=state.staged, config=state.cfg)


def _shock_profile(shape: str, horizon: int, rs_window: int,
                   reversion: int) -> np.ndarray:
    """Per-quarter multiplier of the shock (module docstring shapes)."""
    if shape == "parallel":
        return np.ones(horizon, dtype=float)
    h = np.arange(1, horizon + 1, dtype=float)
    ramp_up = np.clip(h / RAMP_UP_Q, 0.0, 1.0)
    decay = np.clip(1.0 - (h - rs_window) / reversion, 0.0, 1.0)
    return np.minimum(ramp_up, decay)


def _stage_mix(book: pd.DataFrame) -> dict:
    """Loan counts + reported allowance by IFRS 9 stage (JSON-ready)."""
    rep = book["ecl_reported"].to_numpy(dtype=float)
    stage = book["stage"].to_numpy()
    total = float(rep.sum())
    out = {}
    for s in (1, 2, 3):
        m = stage == s
        amt = float(rep[m].sum())
        out[f"stage{s}"] = {
            "n_loans": int(m.sum()),
            "allowance": amt,
            "allowance_pct_of_total": (100.0 * amt / total) if total else 0.0,
        }
    return out


def _waterfall_rows(wf: pd.DataFrame) -> list[dict]:
    return [{"component": str(r["component"]), "amount": float(r["amount"]),
             "n_loans": int(r["n_loans"]), "kind": str(r["kind"])}
            for _, r in wf.iterrows()]


def _m(x: float) -> str:
    """Dollars -> '$Xm' display string (the tool narrates, not the LLM)."""
    return f"${x / 1e6:,.1f}m"


# ---------------------------------------------------------------------------
# tool 1: shock_macro
# ---------------------------------------------------------------------------

def shock_macro(var: Literal["UER", "HPI", "GDP"], shock: float,
                shape: Literal["parallel", "peak_revert"] = "parallel"
                ) -> dict:
    """Coherent macro shock of the base scenario -> re-run ECL chain.

    See the module docstring for the co-movement convention, units, bounds
    and shapes. Returns baseline vs shocked reported allowance for the t=60
    book, the stage mix of the shocked book (staging is frozen at the
    reporting date, so loan counts match the baseline by construction — only
    the allowances move), and the frozen-engine movement decomposition vs
    the unshocked base scenario (same book, same stages: the entire delta
    lands in 'remeasurement', which is exactly the point).
    """
    args = ShockMacroArgs(var=var, shock=shock, shape=shape)
    state = _state()
    sset = state.sset

    concept_v = VAR_TO_CONCEPT[args.var]
    s_units = args.shock * VAR_SCALE[args.var]
    profile = _shock_profile(args.shape, int(sset.horizon),
                             int(sset.rs_window), int(sset.reversion))

    path = sset.paths["base"].copy()
    applied: dict[str, float] = {}
    for c in _CONCEPT_COLS:
        delta = s_units * state.betas[concept_v][c] * profile
        path[c] = path[c].to_numpy(dtype=float) + delta
        peak = float(delta[int(np.argmax(np.abs(delta)))])
        # report peak applied delta in pp units (hpi_growth is decimal)
        applied[c] = peak * 100.0 if c == "hpi_growth" else peak
    path["uer"] = path["uer"].clip(lower=0.0)   # physical floor

    shocked_book = _run_book(state, _z_for_macro_path(state, path))

    baseline = state.scenario_totals["base"]
    shocked = float(shocked_book["ecl_reported"].sum())
    delta_usd = shocked - baseline
    coverage = shocked / state.balance

    wf = movement_decomposition(
        state.books["base"], shocked_book,
        label_t0="base scenario (t=60)",
        label_t1=f"{args.var}{args.shock:+g}pp {args.shape}")

    headline = (
        f"{args.var} {args.shock:+g}pp ({args.shape}) coherent shock of the "
        f"base scenario: reported allowance {_m(baseline)} -> {_m(shocked)} "
        f"(delta {delta_usd / 1e6:+,.1f}m, "
        f"{100.0 * delta_usd / baseline:+.1f}%), shocked coverage "
        f"{coverage:.2%}")

    result = {
        "tool": "shock_macro",
        "var": args.var,
        "shock": float(args.shock),
        "shape": args.shape,
        "shock_units": SHOCK_UNITS[args.var],
        "applied_peak_deltas_pp": applied,
        "baseline_allowance": float(baseline),
        "shocked_allowance": shocked,
        "delta": delta_usd,
        "delta_pct": 100.0 * delta_usd / baseline,
        "baseline_coverage": float(baseline / state.balance),
        "coverage": coverage,
        "stage_mix": _stage_mix(shocked_book),
        "waterfall_vs_baseline": _waterfall_rows(wf),
        "amounts_in": "USD",
        "headline": headline,
    }
    result["tool_call_id"] = _log_call("shock_macro", args.model_dump(),
                                       headline)
    return result


# ---------------------------------------------------------------------------
# tool 2: reweight_scenarios
# ---------------------------------------------------------------------------

def reweight_scenarios(w_up: float, w_base: float, w_down: float) -> dict:
    """Reweight the three cached scenario ECLs; report the Jensen gap.

    Weighted allowance = sum of weights x CACHED per-scenario reported
    allowances (no refit, no re-run). Jensen ratio = weighted allowance /
    allowance at the weighted-AVERAGE macro path — the denominator comes
    from the init cache (adopted weights) or one memoised engine run on the
    weighted Z path (module docstring).
    """
    args = ReweightArgs(w_up=w_up, w_base=w_base, w_down=w_down)
    state = _state()
    s = args.w_up + args.w_base + args.w_down
    w = {"up": args.w_up / s, "base": args.w_base / s, "down": args.w_down / s}

    tot = state.scenario_totals
    weighted = sum(w[n] * tot[n] for n in ("up", "base", "down"))

    key = _weights_key(w["up"], w["base"], w["down"])
    if key not in state.at_avg_cache:
        z_avg = (w["up"] * state.zpaths["up"].to_numpy(dtype=float)
                 + w["base"] * state.zpaths["base"].to_numpy(dtype=float)
                 + w["down"] * state.zpaths["down"].to_numpy(dtype=float))
        state.at_avg_cache[key] = float(
            _run_book(state, z_avg)["ecl_reported"].sum())
    at_avg = state.at_avg_cache[key]
    jensen = weighted / at_avg

    aw = state.sset.weights
    adopted = sum(aw[n] * tot[n] for n in ("up", "base", "down"))
    delta_vs_adopted_pct = 100.0 * (weighted / adopted - 1.0)

    headline = (
        f"weights up/base/down = {w['up']:.2f}/{w['base']:.2f}/"
        f"{w['down']:.2f}: weighted allowance {_m(weighted)} "
        f"({delta_vs_adopted_pct:+.1f}% vs adopted 25/50/25 {_m(adopted)}); "
        f"Jensen ratio {jensen:.3f}x vs {_m(at_avg)} at the averaged path")

    result = {
        "tool": "reweight_scenarios",
        "weights": {k: float(v) for k, v in w.items()},
        "per_scenario": {n: {"weight": float(w[n]), "allowance": float(tot[n])}
                         for n in ("up", "base", "down")},
        "weighted_allowance": float(weighted),
        "allowance_at_average_path": float(at_avg),
        "jensen_ratio": float(jensen),
        "coverage": float(weighted / state.balance),
        "adopted_weights": {n: float(aw[n]) for n in ("up", "base", "down")},
        "adopted_weighted_allowance": float(adopted),
        "delta_vs_adopted_pct": float(delta_vs_adopted_pct),
        "amounts_in": "USD",
        "headline": headline,
    }
    result["tool_call_id"] = _log_call("reweight_scenarios",
                                       args.model_dump(), headline)
    return result


# ---------------------------------------------------------------------------
# tool 3: rerun_ecl
# ---------------------------------------------------------------------------

def _segment_mask(state: EngineState, segment: str) -> np.ndarray:
    book = state.books["base"]
    if segment == "all":
        return np.ones(len(book), dtype=bool)
    if segment in ("stage1", "stage2", "stage3"):
        return book["stage"].to_numpy() == int(segment[-1])
    if segment == "investor":
        return state.segments["investor_orig_time"].to_numpy() == 1
    if segment == "high_ltv":
        ltv = state.segments["updated_ltv"].to_numpy(dtype=float)
        return ltv > HIGH_LTV_THRESHOLD          # NaN compares False
    raise ValueError(f"unknown segment {segment!r}")   # unreachable (pydantic)


def rerun_ecl(segment: Literal["all", "stage1", "stage2", "stage3",
                               "investor", "high_ltv"] = "all") -> dict:
    """Scenario-weighted allowance for a segment of the t=60 book.

    Filters the CACHED per-loan scenario books (identical row order across
    scenarios — staging and population are scenario-invariant) and weights
    with the adopted 50/25/25. No refit, no re-run: pure decomposition of
    already-engine-computed numbers.
    """
    args = RerunEclArgs(segment=segment)
    state = _state()
    mask = _segment_mask(state, args.segment)
    w = state.sset.weights

    per_scen = {n: float(state.books[n].loc[mask, "ecl_reported"].sum())
                for n in ("up", "base", "down")}
    weighted = sum(w[n] * per_scen[n] for n in ("up", "base", "down"))
    book_total = sum(w[n] * state.scenario_totals[n]
                     for n in ("up", "base", "down"))

    base_seg = state.books["base"].loc[mask]
    seg_balance = float(base_seg["balance"].sum())
    n_loans = int(mask.sum())

    stage_arr = state.books["base"]["stage"].to_numpy()
    stage_mix = {}
    for s in (1, 2, 3):
        sm = mask & (stage_arr == s)
        amt = float(sum(
            w[n] * float(state.books[n].loc[sm, "ecl_reported"].sum())
            for n in ("up", "base", "down")))
        stage_mix[f"stage{s}"] = {
            "n_loans": int(sm.sum()),
            "allowance": amt,
            "allowance_pct_of_segment": (100.0 * amt / weighted)
            if weighted else 0.0,
        }

    headline = (
        f"segment '{args.segment}' ({SEGMENT_DEFS[args.segment]}): "
        f"{n_loans:,} loans, balance {_m(seg_balance)}, scenario-weighted "
        f"allowance {_m(weighted)} "
        f"({100.0 * weighted / book_total:.1f}% of the book allowance), "
        f"coverage "
        f"{(weighted / seg_balance) if seg_balance else float('nan'):.2%}")

    result = {
        "tool": "rerun_ecl",
        "segment": args.segment,
        "segment_definition": SEGMENT_DEFS[args.segment],
        "weights": {n: float(w[n]) for n in ("up", "base", "down")},
        "n_loans": n_loans,
        "balance": seg_balance,
        "weighted_allowance": float(weighted),
        "coverage": float(weighted / seg_balance) if seg_balance else None,
        "share_of_book_allowance_pct": float(100.0 * weighted / book_total),
        "per_scenario_allowance": per_scen,
        "stage_mix": stage_mix,
        "amounts_in": "USD",
        "headline": headline,
    }
    result["tool_call_id"] = _log_call("rerun_ecl", args.model_dump(),
                                       headline)
    return result


# ---------------------------------------------------------------------------
# tool 4: decompose_waterfall
# ---------------------------------------------------------------------------

def _frozen_book(state: EngineState, t: int) -> pd.DataFrame:
    """Frozen rung-1 ECL book at snapshot t, memoised per t."""
    if t not in state.frozen_books:
        state.frozen_books[t] = ecl_for_snapshot(state.panel, t,
                                                 state.models, state.cfg)
    return state.frozen_books[t]


def decompose_waterfall(t0: int = 20, t1: int = 40) -> dict:
    """Frozen-engine allowance movement decomposition between two snapshots.

    opening + stage_migration + remeasurement + derecognitions + new_loans
    = closing; the identity is asserted inside the frozen
    engine.ecl.movement_decomposition (order-dependent attribution, see its
    docstring). Snapshots are rung-1 (unconditioned) books, matching the
    published outputs/ecl/ waterfall at the default (20, 40).
    """
    args = DecomposeWaterfallArgs(t0=t0, t1=t1)
    state = _state()

    wf = movement_decomposition(_frozen_book(state, args.t0),
                                _frozen_book(state, args.t1),
                                label_t0=f"t={args.t0}",
                                label_t1=f"t={args.t1}")
    rows = _waterfall_rows(wf)
    comp = {r["component"]: r["amount"] for r in rows}
    identity_gap = comp["closing"] - (
        comp["opening"] + comp["stage_migration"] + comp["remeasurement"]
        + comp["derecognitions"] + comp["new_loans"])

    p0, p1 = panel_time_to_period(args.t0), panel_time_to_period(args.t1)
    headline = (
        f"allowance waterfall t={args.t0} ({p0}) -> t={args.t1} ({p1}): "
        f"opening {_m(comp['opening'])}, stage migration "
        f"{comp['stage_migration'] / 1e6:+,.1f}m, remeasurement "
        f"{comp['remeasurement'] / 1e6:+,.1f}m, derecognitions "
        f"{comp['derecognitions'] / 1e6:+,.1f}m, new loans "
        f"{comp['new_loans'] / 1e6:+,.1f}m, closing {_m(comp['closing'])}")

    result = {
        "tool": "decompose_waterfall",
        "t0": int(args.t0),
        "t1": int(args.t1),
        "period_t0": str(p0),
        "period_t1": str(p1),
        "opening_allowance": comp["opening"],
        "closing_allowance": comp["closing"],
        "components": rows,
        "identity_gap": float(identity_gap),
        "amounts_in": "USD",
        "headline": headline,
    }
    result["tool_call_id"] = _log_call("decompose_waterfall",
                                       args.model_dump(), headline)
    return result


# ---------------------------------------------------------------------------
# registry (the Day-4 router binds to these)
# ---------------------------------------------------------------------------

TIER1_TOOLS = {
    "shock_macro": shock_macro,
    "reweight_scenarios": reweight_scenarios,
    "rerun_ecl": rerun_ecl,
    "decompose_waterfall": decompose_waterfall,
}

TIER1_ARG_MODELS = {
    "shock_macro": ShockMacroArgs,
    "reweight_scenarios": ReweightArgs,
    "rerun_ecl": RerunEclArgs,
    "decompose_waterfall": DecomposeWaterfallArgs,
}
