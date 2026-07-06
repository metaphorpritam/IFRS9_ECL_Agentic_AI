"""MLP hazard PD model -- the deep-learning CHALLENGER (never champion).

ROLE (plan section 5)
----------------------------------------------------------------------
A two-hidden-layer MLP fitted on EXACTLY the champion's loan-quarter hazard
framing (engine/hazard.py): same at-risk rows, same one-quarter-ahead
default_event target, same covariate information set, same timing convention
(all macro regressors lagged; updated LTV / prepay incentive as the two
accepted state-variable exceptions). The comparison is like-for-like BY
CONSTRUCTION: the MLP receives the champion's raw covariates -- no spline, no
hand-built interaction, no extra features -- so anything nonlinear it finds
(the seasoning hump, the double-trigger LTV steepening) is LEARNED, not
specified. That is the point of the exercise: the challenger probes the
champion's functional form; it never produces production numbers.

FEATURES (12 = champion information set, champion scalings)
----------------------------------------------------------------------
    loan_age            raw quarters on book (champion: cr(loan_age, df=5))
    fico_s              FICO_orig_time / 100          (champion scaling)
    ltv10               updated_ltv clipped at LTV_CAP, / 10  (champion
                        winsorisation reused via engine.hazard.LTV_CAP)
    prepay_incentive    note rate - current market rate (pp)
    investor_orig_time, REtype_{CO,PU,SF}_orig_time   binary flags
    uer_lag1, uer_chg4_lag1, hpi_growth_lag1, gdp_lag1  lagged macro
The champion's centered ltv10 x uer_lag1 interaction is deliberately NOT
given to the MLP -- rediscovering it is a scorecard question.

TRAINING PROTOCOL
----------------------------------------------------------------------
* Standardisation: continuous features are z-scored with means/stds fitted
  on the TRAINING data only (enforced: fit_mlp_hazard raises if the input
  frame carries non-train rows; the Standardiser records what it saw).
  Binary flags pass through unscaled.
* Class imbalance (~2.7% event rate): weighted BCE with
  pos_weight = n_neg / n_pos. Because weighting biases the fitted
  probability upward (the pointwise optimum of weighted BCE is
  p_w = w*p / (w*p + 1 - p)), predictions apply the EXACT prior correction
  sigmoid(logit - ln pos_weight), recovering a calibrated hazard scale --
  reliability curves and the staging swap need absolute PDs, not just ranks.
* Early stopping BY TIME, not by random rows: the model trains on
  t <= val_time_range[0]-1 and is scored each epoch on the held-out
  t = 33..40 validation window (within-train, so OOT t=41..60 stays
  untouched). A random row split would leak calendar-quarter information
  across the split (same-quarter rows share the macro state).
* Refit-on-full-train: after early stopping picks best_epoch on the time
  split, the final network retrains on the FULL training window for
  best_epoch epochs (fresh seeded init). Without this the challenger would
  never see the t=33..40 stress onset the champion trained on, breaking
  like-for-like data parity.
* Regularisation: dropout between hidden layers + AdamW weight decay.

DETERMINISM
----------------------------------------------------------------------
Fixed seeds (numpy shuffling + torch init/dropout), CUBLAS_WORKSPACE_CONFIG
set before CUDA init, torch.use_deterministic_algorithms(True) where the op
set allows it (recorded in meta['deterministic_algorithms']). Residual
nondeterminism, documented: results are bitwise-reproducible on the SAME
device/build but differ across CPU vs GPU and across torch/CUDA versions
(different kernels, different float reduction orders).

TAIL / EXTRAPOLATION (documented challenger weakness)
----------------------------------------------------------------------
The champion's natural-spline age baseline extrapolates linearly on the
cloglog scale beyond the training age support. An MLP has no disciplined
extrapolation, so at predict time loan_age is CLAMPED to the training
support maximum -- the hazard levels off at its last supported age value.
This mirrors the plan's accepted "level-off at the last observed hazard"
tail default, and is one reason the challenger stays a challenger.

FALLBACK: if torch is unavailable the same protocol runs on sklearn's
MLPClassifier (no dropout, no class weighting -- meta records the backend).
"""

from __future__ import annotations

import os

# must be set before the first CUDA/cuBLAS call for deterministic matmuls
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.hazard import LTV_CAP, REQUIRED_COLS, HazardModel

try:  # torch backend preferred; sklearn fallback documented in module docstring
    import torch
    from torch import nn

    _HAS_TORCH = True
except Exception:  # pragma: no cover - exercised only on torch-less installs
    _HAS_TORCH = False

#: model inputs -- the champion's covariate information set, champion scalings
FEATURES = [
    "loan_age", "fico_s", "ltv10", "prepay_incentive",
    "investor_orig_time", "REtype_CO_orig_time", "REtype_PU_orig_time",
    "REtype_SF_orig_time",
    "uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1", "gdp_lag1",
]
#: standardised (z-scored) inputs; binary flags pass through
CONT_FEATURES = ["loan_age", "fico_s", "ltv10", "prepay_incentive",
                 "uer_lag1", "uer_chg4_lag1", "hpi_growth_lag1", "gdp_lag1"]
BIN_FEATURES = [c for c in FEATURES if c not in CONT_FEATURES]

#: covariate families for permutation-importance exhibits (challenger-side
#: mirror of the champion's hazard-ratio table families)
FEATURE_FAMILY = {
    "loan_age": "age", "fico_s": "borrower", "investor_orig_time": "borrower",
    "REtype_CO_orig_time": "borrower", "REtype_PU_orig_time": "borrower",
    "REtype_SF_orig_time": "borrower", "ltv10": "collateral",
    "prepay_incentive": "incentive", "uer_lag1": "macro",
    "uer_chg4_lag1": "macro", "hpi_growth_lag1": "macro", "gdp_lag1": "macro",
}

#: same per-period exit-probability cap as engine.hazard.pd_term_structure
_EXIT_CAP = 0.999999


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Champion-scaled feature frame (mirror of engine.hazard._prepare).

    Validates REQUIRED_COLS, applies the champion's LTV winsorisation
    (LTV_CAP) and scalings, returns the FEATURES columns as float64.
    Raises on NaN rows -- silent drops would misalign predictions.
    """
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise KeyError(f"feature frame is missing required columns: {missing}")
    out = pd.DataFrame(index=df.index)
    out["loan_age"] = df["loan_age"].astype(float)
    out["fico_s"] = df["FICO_orig_time"].astype(float) / 100.0
    out["ltv10"] = df["updated_ltv"].clip(upper=LTV_CAP).astype(float) / 10.0
    for c in FEATURES:
        if c not in out.columns:
            out[c] = df[c].astype(float)
    bad = int(out.isna().any(axis=1).sum())
    if bad:
        raise ValueError(f"{bad} feature rows carry NaN -- clean upstream "
                         "(lag warm-up quarter?)")
    return out[FEATURES]


@dataclass(frozen=True)
class Standardiser:
    """Train-only z-scoring of CONT_FEATURES (binary flags untouched).

    Frozen dataclass: fitted once in fit_mlp_hazard and immutable afterwards
    -- predicting cannot silently refit it. Records provenance (n_rows,
    time_range) so tests can assert the train-only contract.
    """

    mean: np.ndarray            # over CONT_FEATURES
    std: np.ndarray
    n_rows: int
    time_range: tuple[int, int]  # (min, max) panel time of the fit rows

    @classmethod
    def fit(cls, feats: pd.DataFrame, times: np.ndarray) -> "Standardiser":
        x = feats[CONT_FEATURES].to_numpy(dtype=float)
        std = x.std(axis=0, ddof=0)
        # scale-aware zero test: a constant column's std comes back as float
        # dust (~1e-16 * level), not exactly 0.0
        tol = 1e-12 * np.maximum(1.0, np.abs(x).max(axis=0))
        degenerate = std <= tol
        if degenerate.any():
            bad = [c for c, d in zip(CONT_FEATURES, degenerate) if d]
            raise ValueError(f"degenerate (constant) features: {bad}")
        return cls(mean=x.mean(axis=0), std=std, n_rows=len(feats),
                   time_range=(int(times.min()), int(times.max())))

    def transform(self, feats: pd.DataFrame) -> np.ndarray:
        """FEATURES frame -> float32 design matrix (cont z-scored)."""
        x = feats[FEATURES].to_numpy(dtype=float)
        idx = [FEATURES.index(c) for c in CONT_FEATURES]
        x[:, idx] = (x[:, idx] - self.mean) / self.std
        return x.astype(np.float32)


@dataclass
class MLPHazard:
    """A fitted MLP challenger hazard (torch or sklearn backend)."""

    net: object                  # torch nn.Module | sklearn MLPClassifier
    scaler: Standardiser
    event_col: str
    backend: str                 # 'torch' | 'sklearn'
    log_pos_weight: float        # prior correction; 0.0 for sklearn backend
    age_max: float               # training loan_age support (predict clamp)
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# torch backend
# ---------------------------------------------------------------------------

def _make_net(d_in: int, hidden: tuple[int, ...], dropout: float,
              seed: int) -> "nn.Module":
    torch.manual_seed(seed)          # deterministic init AND dropout stream
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    layers: list = []
    prev = d_in
    for h in hidden:
        layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(dropout)]
        prev = h
    layers.append(nn.Linear(prev, 1))
    return nn.Sequential(*layers)


def _forward_np(net: "nn.Module", X: np.ndarray, device: str,
                batch: int = 262_144) -> np.ndarray:
    """Batched eval-mode logits -> float64 numpy."""
    net.eval()
    outs = []
    with torch.no_grad():
        for lo in range(0, len(X), batch):
            xb = torch.from_numpy(X[lo:lo + batch]).to(device)
            outs.append(net(xb).squeeze(-1).float().cpu().numpy())
    return np.concatenate(outs).astype(np.float64) if outs else np.empty(0)


def _train_torch(X: np.ndarray, y: np.ndarray, Xv: np.ndarray | None,
                 yv: np.ndarray | None, *, hidden, dropout, weight_decay, lr,
                 batch_size, n_epochs, patience, seed, device,
                 ) -> tuple["nn.Module", dict]:
    """One training stage. With (Xv, yv): early-stop on val AUC, return the
    best-epoch weights. Without: run exactly n_epochs (the refit stage)."""
    from sklearn.metrics import roc_auc_score

    try:
        torch.use_deterministic_algorithms(True)
        det = True
    except Exception:                       # pragma: no cover
        det = False
    net = _make_net(X.shape[1], hidden, dropout, seed).to(device)
    n_pos, n_neg = float(y.sum()), float(len(y) - y.sum())
    pos_weight = n_neg / n_pos
    lossf = nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(pos_weight, device=device))
    opt = torch.optim.AdamW(net.parameters(), lr=lr,
                            weight_decay=weight_decay)
    Xt = torch.from_numpy(X).to(device)
    yt = torch.from_numpy(y.astype(np.float32)).to(device)
    rng = np.random.default_rng(seed)       # epoch shuffling (device-free)

    best = {"auc": -np.inf, "epoch": 0, "state": None}
    history, bad_epochs = [], 0
    for epoch in range(1, n_epochs + 1):
        net.train()
        perm = rng.permutation(len(Xt))
        for lo in range(0, len(perm), batch_size):
            idx = torch.from_numpy(perm[lo:lo + batch_size]).to(device)
            opt.zero_grad()
            loss = lossf(net(Xt[idx]).squeeze(-1), yt[idx])
            loss.backward()
            opt.step()
        if Xv is None:
            continue
        auc = roc_auc_score(yv, _forward_np(net, Xv, device))
        history.append(float(auc))
        if auc > best["auc"]:
            best = {"auc": float(auc), "epoch": epoch,
                    "state": {k: v.detach().clone()
                              for k, v in net.state_dict().items()}}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                break
    if Xv is not None and best["state"] is not None:
        net.load_state_dict(best["state"])
    info = {"pos_weight": pos_weight, "val_auc_history": history,
            "best_epoch": best["epoch"] if Xv is not None else n_epochs,
            "best_val_auc": best["auc"] if Xv is not None else None,
            "deterministic_algorithms": det}
    return net, info


# ---------------------------------------------------------------------------
# sklearn fallback backend
# ---------------------------------------------------------------------------

def _train_sklearn(X, y, Xv, yv, *, hidden, weight_decay, lr, batch_size,
                   n_epochs, patience, seed):
    """Warm-start epoch loop on MLPClassifier; time-split early stopping.

    Documented fallback losses vs torch: no dropout, no class weighting
    (MLPClassifier supports neither) -- ranks survive, absolute calibration
    relies on the unweighted BCE optimum instead of prior correction."""
    import warnings

    from sklearn.exceptions import ConvergenceWarning
    from sklearn.metrics import roc_auc_score
    from sklearn.neural_network import MLPClassifier

    def make(n_iter):
        return MLPClassifier(
            hidden_layer_sizes=hidden, alpha=weight_decay,
            learning_rate_init=lr, batch_size=min(batch_size, len(X)),
            max_iter=n_iter, warm_start=(n_iter == 1), random_state=seed,
            early_stopping=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        if Xv is None:
            clf = make(n_epochs)
            clf.warm_start = False
            clf.fit(X, y)
            return clf, {"best_epoch": n_epochs, "best_val_auc": None,
                         "pos_weight": 1.0, "val_auc_history": []}
        clf = make(1)
        best_auc, best_epoch, history, bad = -np.inf, 0, [], 0
        for epoch in range(1, n_epochs + 1):
            clf.fit(X, y)                    # warm start: +1 epoch
            auc = roc_auc_score(yv, clf.predict_proba(Xv)[:, 1])
            history.append(float(auc))
            if auc > best_auc:
                best_auc, best_epoch, bad = float(auc), epoch, 0
            else:
                bad += 1
                if bad >= patience:
                    break
    return clf, {"best_epoch": best_epoch, "best_val_auc": best_auc,
                 "pos_weight": 1.0, "val_auc_history": history}


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def fit_mlp_hazard(train_df: pd.DataFrame, *, event_col: str = "default_event",
                   hidden: tuple[int, ...] = (64, 32), dropout: float = 0.20,
                   weight_decay: float = 1e-4, lr: float = 1e-3,
                   batch_size: int = 8192, max_epochs: int = 80,
                   patience: int = 6, val_time_range: tuple[int, int] = (33, 40),
                   refit_full: bool = True, seed: int = 0,
                   device: str | None = None, backend: str = "auto",
                   ) -> MLPHazard:
    """Fit the challenger MLP hazard on TRAINING loan-quarter rows.

    train_df must be the training split only (raises if a 'split' column
    shows anything else -- the standardiser train-only contract). Rows in the
    lag warm-up window are dropped, mirroring the champion. Early stopping
    uses the within-train TIME window val_time_range (module docstring);
    with refit_full=True (default) the final net retrains on the whole
    training window for the early-stopped epoch count.
    """
    if "split" in train_df.columns and (train_df["split"] != "train").any():
        raise ValueError("fit_mlp_hazard expects the TRAINING split only -- "
                         "the standardiser must never see non-train rows")
    d = train_df
    if "lag_warmup" in d.columns:
        d = d[d["lag_warmup"] == 0]
    if event_col not in d.columns:
        raise KeyError(f"missing event column {event_col!r}")
    feats = build_features(d)
    y = d[event_col].to_numpy(dtype=float)
    times = d["time"].to_numpy()

    scaler = Standardiser.fit(feats, times)
    X = scaler.transform(feats)

    lo, hi = val_time_range
    val_mask = (times >= lo) & (times <= hi)
    if not val_mask.any() or val_mask.all():
        raise ValueError(f"validation window {val_time_range} does not split "
                         f"the training times {times.min()}..{times.max()}")
    Xc, yc = X[~val_mask], y[~val_mask]
    Xv, yv = X[val_mask], y[val_mask]

    if backend == "auto":
        backend = "torch" if _HAS_TORCH else "sklearn"
    if backend == "torch" and not _HAS_TORCH:
        raise RuntimeError("torch backend requested but torch is unavailable")

    if backend == "torch":
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        net, info = _train_torch(
            Xc, yc, Xv, yv, hidden=hidden, dropout=dropout,
            weight_decay=weight_decay, lr=lr, batch_size=batch_size,
            n_epochs=max_epochs, patience=patience, seed=seed, device=device)
        stage1 = dict(info)
        if refit_full:
            net, info = _train_torch(
                X, y, None, None, hidden=hidden, dropout=dropout,
                weight_decay=weight_decay, lr=lr, batch_size=batch_size,
                n_epochs=max(stage1["best_epoch"], 1), patience=patience,
                seed=seed, device=device)
        log_pw = float(np.log(info["pos_weight"]))
    else:
        device = "cpu"
        net, info = _train_sklearn(
            Xc, yc, Xv, yv, hidden=hidden, weight_decay=weight_decay, lr=lr,
            batch_size=batch_size, n_epochs=max_epochs, patience=patience,
            seed=seed)
        stage1 = dict(info)
        if refit_full:
            net, info = _train_sklearn(
                X, y, None, None, hidden=hidden, weight_decay=weight_decay,
                lr=lr, batch_size=batch_size,
                n_epochs=max(stage1["best_epoch"], 1), patience=patience,
                seed=seed)
        log_pw = 0.0   # unweighted fit -> no prior correction (docstring)

    meta = {
        "backend": backend, "device": device, "seed": seed,
        "hidden": tuple(hidden), "dropout": dropout,
        "weight_decay": weight_decay, "lr": lr, "batch_size": batch_size,
        "event_col": event_col, "event_rate": float(y.mean()),
        "n_fit_rows": len(X), "n_core": int((~val_mask).sum()),
        "n_val": int(val_mask.sum()), "val_time_range": (lo, hi),
        "refit_full": refit_full,
        "best_epoch": stage1["best_epoch"],
        "best_val_auc": stage1["best_val_auc"],
        "val_auc_history": stage1["val_auc_history"],
        "pos_weight": info["pos_weight"],
        "scaler_time_range": scaler.time_range,
        "deterministic_algorithms": stage1.get("deterministic_algorithms"),
        "class_weighting": ("pos_weight BCE + prior correction"
                            if backend == "torch" else
                            "none (sklearn fallback limitation)"),
    }
    return MLPHazard(net=net, scaler=scaler, event_col=event_col,
                     backend=backend, log_pos_weight=log_pw,
                     age_max=float(feats["loan_age"].max()), meta=meta)


def predict_from_features(model: MLPHazard, feats: pd.DataFrame) -> np.ndarray:
    """Calibrated hazard from an already-built FEATURES frame.

    Applies the level-off age clamp (module docstring) and, on the torch
    backend, the exact prior correction sigmoid(z - ln pos_weight) that
    undoes the class-weighting calibration bias.
    """
    f = feats[FEATURES].copy()
    f["loan_age"] = f["loan_age"].clip(upper=model.age_max)
    X = model.scaler.transform(f)
    if model.backend == "torch":
        z = _forward_np(model.net, X, model.meta["device"])
        z = z - model.log_pos_weight
        p = 1.0 / (1.0 + np.exp(-z))
    else:
        p = model.net.predict_proba(X)[:, 1].astype(np.float64)
    if not np.isfinite(p).all():
        raise FloatingPointError("non-finite challenger hazard predictions")
    return p


def predict_mlp_hazard(model: MLPHazard, df: pd.DataFrame) -> np.ndarray:
    """Per-row one-quarter-ahead hazard, champion predict_hazard analogue."""
    return predict_from_features(model, build_features(df))


# ---------------------------------------------------------------------------
# challenger lifetime PD (for the staging swap)
# ---------------------------------------------------------------------------

def cum_default_pd_mlp(model: MLPHazard, prepay: HazardModel,
                       frame: pd.DataFrame, horizons: np.ndarray,
                       chunk_loans: int = 4096) -> np.ndarray:
    """Competing-risk cumulative default PD with the CHALLENGER default
    hazard and the frozen CHAMPION prepayment hazard.

    Mirror of engine.staging._cum_default_pd (same conventions: frame rows
    carry REQUIRED_COLS with loan_age = age at the reporting quarter;
    projection starts at loan_age + 1; per-period exit = lam_d + lam_p capped
    at the engine's _EXIT_CAP; survival cumprod; marginal = S(t-1) * lam_d).
    Only the DEFAULT hazard is swapped -- keeping the champion's prepayment
    leg isolates the PD-model difference in the staging comparison.
    Covariates other than loan_age are frozen (rung-1 tail assumption);
    challenger ages are clamped at the training support (level-off tail).
    """
    # read-only reuse of the frozen engine's exact prepay factorisation
    from engine.staging import _age_curve, _design_matrix, _spline_cols

    ages0 = frame["loan_age"].to_numpy()
    if not np.allclose(ages0, np.round(ages0)):
        raise ValueError("loan_age must be integral quarters")
    ages0 = np.round(ages0).astype(int)
    R = np.asarray(horizons, dtype=int)
    if len(R) != len(frame):
        raise ValueError("horizons must align with frame rows")
    if (R < 1).any():
        raise ValueError("horizons must be >= 1 (floor R upstream)")

    # champion prepay: age-free offset per loan + shared seasoning curve
    max_age = int(ages0.max() + R.max())
    beta = prepay.result.params.to_numpy()
    sp = _spline_cols(prepay)
    Xp = _design_matrix(prepay, frame)
    off_p = Xp @ beta - Xp[:, sp] @ beta[sp]
    curve_p = _age_curve(prepay, max_age)

    # challenger default: standardised feature matrix, only loan_age varies
    feats = build_features(frame)
    F = model.scaler.transform(feats)                    # (n, d) float32
    age_col = FEATURES.index("loan_age")
    a_mean = model.scaler.mean[CONT_FEATURES.index("loan_age")]
    a_std = model.scaler.std[CONT_FEATURES.index("loan_age")]

    out = np.empty(len(R), dtype=float)
    for lo in range(0, len(R), chunk_loans):
        sl = slice(lo, min(lo + chunk_loans, len(R)))
        a0, r = ages0[sl], R[sl]
        k = np.arange(int(r.max()))
        ages = a0[:, None] + 1 + k[None, :]              # (m, maxR)
        on = k[None, :] < r[:, None]
        # challenger default hazard on the fan (level-off age clamp)
        m, T = ages.shape
        Fk = np.repeat(F[sl], T, axis=0)                 # (m*T, d)
        ages_c = np.minimum(ages, model.age_max).astype(float)
        Fk[:, age_col] = ((ages_c.reshape(-1) - a_mean) / a_std
                          ).astype(np.float32)
        if model.backend == "torch":
            z = _forward_np(model.net, Fk, model.meta["device"])
            lam_d = 1.0 / (1.0 + np.exp(-(z - model.log_pos_weight)))
        else:
            lam_d = model.net.predict_proba(Fk)[:, 1].astype(np.float64)
        lam_d = np.where(on, lam_d.reshape(m, T), 0.0)
        # champion prepay hazard on the same fan
        with np.errstate(over="ignore"):
            lam_p = np.where(
                on, 1.0 - np.exp(-np.exp(off_p[sl][:, None] + curve_p[ages])),
                0.0)
        exit_p = np.clip(lam_d + lam_p, 0.0, _EXIT_CAP)
        surv = np.cumprod(1.0 - exit_p, axis=1)
        surv_prev = np.hstack([np.ones((m, 1)), surv[:, :-1]])
        out[sl] = (surv_prev * lam_d).sum(axis=1)
    return out
