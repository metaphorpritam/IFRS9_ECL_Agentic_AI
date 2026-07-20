"""Recompute champion + challenger reliability-curve bin data (Ch.7,
notes/chapters/ch07_challengers.html): the "recompute every number" law
applied to the scorecard, per notes/plan/conventions.md section 5 --
READ-ONLY use of engine/, challenger/, data/ (campaign off-limits rule;
nothing here is written back into those dirs, only into notes/assets/img/ch07/).

Champion: refit via engine.hazard.fit_default_hazard(train) (deterministic
IRLS, bitwise-identical to analysis/fit_challenger.py's own refit -- verified
below: AUC train 0.7476 / OOT 0.6609 match outputs/challenger/scorecard.md).
Challenger: NOT retrained -- load the saved torch checkpoint
outputs/challenger/mlp_challenger.pt (state_dict + scaler + meta) and run
inference only, reproducing analysis/fit_challenger.py's predict_from_features
bitwise (same seed=0 weights, no stochastic step at inference time; AUC
train 0.7632 / OOT 0.6417 also match the scorecard exactly).

Run: cd <repo root> && uv run --no-sync python
     notes/assets/img/ch07/recompute_challenger_scoring.py
(several minutes -- champion IRLS refit + a full-panel forward pass through
the challenger checkpoint on ~620k loan-quarter rows). Writes three JSON
files consumed by build_diagrams.py's Exhibits 7.3, 7.4, 7.6 and by the
chapter's own reliability-comparator widget (its bin data is inlined from
reliability_bins.json's oot_champion/oot_challenger arrays):
  reliability_bins.json  20 score-quantile bins, pred%/obs%/n, train + OOT, both models
  psi_bands.json         10 train-score-decile bins, train/OOT population share + PSI contribution
  age_pdp.json           loan_age partial dependence, 0..80 quarters step 2, both models
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score

ROOT = Path("/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI")
sys.path.insert(0, str(ROOT))

from engine.hazard import fit_default_hazard, predict_hazard  # noqa: E402
from challenger.mlp import (  # noqa: E402
    FEATURES, MLPHazard, Standardiser, build_features, predict_from_features,
)
from challenger.mlp import _make_net  # noqa: E402

PANEL = ROOT / "data" / "processed" / "panel.parquet"
CKPT = ROOT / "outputs" / "challenger" / "mlp_challenger.pt"
N_BINS = 20

panel = pd.read_parquet(PANEL)
train = panel[panel["split"] == "train"]
oot = panel[panel["split"] == "oot"]
train_fit = train[train["lag_warmup"] == 0]
y_tr = train_fit["default_event"].to_numpy(dtype=float)
y_oo = oot["default_event"].to_numpy(dtype=float)
print(f"train_fit {len(train_fit):,} rows | oot {len(oot):,} rows")

# ---- champion: refit (deterministic IRLS, identical to production) --------
m_def = fit_default_hazard(train)
p_tr_champ = predict_hazard(m_def, train_fit)
p_oo_champ = predict_hazard(m_def, oot)
auc_champ = {"train": roc_auc_score(y_tr, p_tr_champ),
             "oot": roc_auc_score(y_oo, p_oo_champ)}
print("champion AUC", auc_champ)

# ---- challenger: load checkpoint, inference only, no retraining ----------
ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
d_in = len(FEATURES)
net = _make_net(d_in, tuple(ckpt["meta"]["hidden"]), ckpt["meta"]["dropout"],
                 ckpt["meta"]["seed"])
net.load_state_dict(ckpt["state_dict"])
scaler = Standardiser(mean=ckpt["scaler_mean"], std=ckpt["scaler_std"],
                       n_rows=ckpt["scaler_n_rows"],
                       time_range=tuple(ckpt["scaler_time_range"]))
mlp = MLPHazard(net=net, scaler=scaler, event_col="default_event",
                 backend="torch", log_pos_weight=ckpt["log_pos_weight"],
                 age_max=ckpt["age_max"], meta=dict(ckpt["meta"], device="cpu"))

F_tr = build_features(train_fit)
F_oo = build_features(oot)
p_tr_mlp = predict_from_features(mlp, F_tr)
p_oo_mlp = predict_from_features(mlp, F_oo)
auc_mlp = {"train": roc_auc_score(y_tr, p_tr_mlp),
           "oot": roc_auc_score(y_oo, p_oo_mlp)}
print("challenger AUC (checkpoint, no retrain)", auc_mlp)
print("checkpoint best_epoch", ckpt["meta"]["best_epoch"],
      "best_val_auc", ckpt["meta"]["best_val_auc"])


def reliability_bins(y, p, n_bins=N_BINS):
    q = pd.qcut(pd.Series(p), n_bins, labels=False, duplicates="drop")
    g = pd.DataFrame({"y": y, "p": p, "bin": q}).groupby("bin")
    tab = pd.DataFrame({"pred": g["p"].mean(), "obs": g["y"].mean(),
                         "n": g.size()})
    return tab


out = {}
for split, y, pc, pm in [("train", y_tr, p_tr_champ, p_tr_mlp),
                          ("oot", y_oo, p_oo_champ, p_oo_mlp)]:
    bc = reliability_bins(y, pc)
    bm = reliability_bins(y, pm)
    out[f"{split}_champion"] = [
        {"pred": round(float(r.pred) * 100, 5), "obs": round(float(r.obs) * 100, 5),
         "n": int(r.n)} for r in bc.itertuples()]
    out[f"{split}_challenger"] = [
        {"pred": round(float(r.pred) * 100, 5), "obs": round(float(r.obs) * 100, 5),
         "n": int(r.n)} for r in bm.itertuples()]

out["auc"] = {"champion": auc_champ, "challenger": auc_mlp}
out["checkpoint_meta"] = {k: ckpt["meta"][k] for k in
                           ("hidden", "dropout", "best_epoch", "best_val_auc",
                            "pos_weight")}

outp = Path("notes/assets/img/ch07/reliability_bins.json")
outp.write_text(json.dumps(out, indent=1))
print("wrote", outp)

# ---- PSI band tables (N_PSI_BINS=10, matches analysis/fit_challenger.py) --
def psi_bands(train_scores, oot_scores, n_bins=10):
    edges = np.quantile(train_scores, np.linspace(0, 1, n_bins + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    p = np.histogram(train_scores, bins=edges)[0] / len(train_scores)
    q = np.histogram(oot_scores, bins=edges)[0] / len(oot_scores)
    p2, q2 = np.clip(p, 1e-6, None), np.clip(q, 1e-6, None)
    contrib = (p2 - q2) * np.log(p2 / q2)
    return p, q, contrib, edges

p_c, q_c, contrib_c, edges_c = psi_bands(p_tr_champ, p_oo_champ)
p_m, q_m, contrib_m, edges_m = psi_bands(p_tr_mlp, p_oo_mlp)
print("champion PSI total", contrib_c.sum())
print("challenger PSI total", contrib_m.sum())

out2 = {
    "champion": {"train_share": p_c.tolist(), "oot_share": q_c.tolist(),
                 "contrib": contrib_c.tolist(), "total": float(contrib_c.sum())},
    "challenger": {"train_share": p_m.tolist(), "oot_share": q_m.tolist(),
                   "contrib": contrib_m.tolist(), "total": float(contrib_m.sum())},
}
outp2 = Path("notes/assets/img/ch07/psi_bands.json")
outp2.write_text(json.dumps(out2, indent=1))
print("wrote", outp2)

# ---- seasoning-hump PDP: loan_age, champion vs challenger ------------------
rng = np.random.default_rng(0)
sample_idx = rng.choice(len(train_fit), size=20_000, replace=False)
sample = train_fit.iloc[sample_idx].copy()

age_grid = np.arange(0, 81, 2)
pdp_rows = []
for v in age_grid:
    s = sample.copy()
    s["loan_age"] = v
    champ_h = float(predict_hazard(m_def, s).mean())
    mlp_h = float(predict_from_features(mlp, build_features(s)).mean())
    pdp_rows.append({"age": int(v), "champion": champ_h * 100, "challenger": mlp_h * 100})

out3 = {"age_pdp": pdp_rows}
outp3 = Path("notes/assets/img/ch07/age_pdp.json")
outp3.write_text(json.dumps(out3, indent=1))
print("wrote", outp3)
print("challenger age PDP peak at age", age_grid[np.argmax([r['challenger'] for r in pdp_rows])])
print("champion age PDP peak at age", age_grid[np.argmax([r['champion'] for r in pdp_rows])])
