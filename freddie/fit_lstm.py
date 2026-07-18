"""Fit + score the LSTM path-dependence challenger against the SFLLD champion
hazard (rung 3). Read freddie/lstm.py FIRST -- this module is pure
orchestration (paths, checkpointing, exhibits); the model/sequence logic
lives there.

Isolation: freddie/ namespace only. Reads panel_monthly.parquet,
loan_orig.parquet (via predicate-pushdown vintage filters, mirroring
freddie/fit_hazard.py's memory-lean per-vintage pattern) and the cached
champion hazard fit (data/processed/freddie/hazard/champion_model.pkl,
read-only). NEVER touches engine/, agent/, app/, analysis/, challenger/, or
any existing test file.

--------------------------------------------------------------------------
THE QUESTION (outputs/freddie/lstm/lstm_report.md)
--------------------------------------------------------------------------
Does delinquency-PATH memory (the LSTM's trailing 24-month dlq/UPB history)
add discrimination beyond the champion hazard's current-state-only view?
Answered by scoring BOTH models on the IDENTICAL eval set -- the champion's
own train (perf month <= freddie.fit_hazard.TRAIN_CUTOFF) / OOT (perf month
> TRAIN_CUTOFF) split, same NaN-covariate row exclusion rule -- then:
  1. headline train/OOT AUC, champion vs LSTM
  2. calibration-by-calendar-year, both models
  3. lift split: OOT AUC on loans WITH a prior delinquency spell in their
     trailing 24-month window (freddie.lstm.has_prior_delinquency) vs
     clean-history loans -- this is the sharpest test of the path-memory
     hypothesis, since the champion CANNOT distinguish these two groups by
     construction (dlq_num is not one of its covariates at all) while the
     LSTM's whole premise is that it should.

--------------------------------------------------------------------------
CHECKPOINT DISCIPLINE (mirrors freddie/fit_hazard.py)
--------------------------------------------------------------------------
Every expensive stage is persisted the moment it completes and skipped on
re-invocation unless --refresh: base_frame_vintage.parquet (model frame +
vintage), train/val tensors + scaler, trained model weights + training
history, and PER-VINTAGE scored parquet files under data/processed/freddie/
lstm/scored/ (so an interrupted full-panel scoring run resumes from the
last completed vintage rather than restarting). Several short `uv run`
invocations are expected across a session, not one monolithic run.

Run as a module:
    cd <repo root> && uv run --no-sync python -m freddie.fit_lstm
"""
from __future__ import annotations

import argparse
import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score

from freddie import fit_hazard as fh
from freddie import lstm as fl

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Paths -- rung-3 isolation
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL_PATH = fh.PANEL_PATH
ORIG_PATH = fh.ORIG_PATH
CACHE_DIR = REPO_ROOT / "data" / "processed" / "freddie" / "lstm"
OUT_DIR = REPO_ROOT / "outputs" / "freddie" / "lstm"
SCORED_DIR = CACHE_DIR / "scored"

BASE_FRAME_CACHE = CACHE_DIR / "base_frame_vintage.parquet"
TRAIN_TENSORS_CACHE = CACHE_DIR / "train_tensors.npz"
VAL_TENSORS_CACHE = CACHE_DIR / "val_tensors.npz"
SCALER_CACHE = CACHE_DIR / "scaler.pkl"
MODEL_CACHE = CACHE_DIR / "lstm_model.pt"
TRAIN_HISTORY_CACHE = CACHE_DIR / "training_history.json"

PANEL_SEQ_COLS = ["loan_sequence_number", "monthly_reporting_period", "dlq_num", "current_actual_upb"]

INFERENCE_DEVICE = fl.TrainConfig().device


# ==========================================================================
# 1. Base frame: champion's cached model frame + vintage (for chunking)
# ==========================================================================
def base_frame(refresh: bool = False) -> pd.DataFrame:
    if BASE_FRAME_CACHE.exists() and not refresh:
        logger.info("Loading cached base frame from %s", BASE_FRAME_CACHE)
        return pd.read_parquet(BASE_FRAME_CACHE)

    df = fh.get_model_frame(refresh=refresh)
    orig_vintage = pd.read_parquet(fh._fast_local(ORIG_PATH), columns=["loan_sequence_number", "vintage"])
    df = df.merge(orig_vintage, on="loan_sequence_number", how="left", validate="many_to_one")
    n_missing_vintage = int(df["vintage"].isna().sum())
    if n_missing_vintage:
        logger.warning("%d rows have no resolvable vintage (dropped from LSTM scope)", n_missing_vintage)
        df = df.dropna(subset=["vintage"])
    df["vintage"] = df["vintage"].astype("int16")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(BASE_FRAME_CACHE, index=False)
    return df


# ==========================================================================
# 2. Sequence assembly for a (small, case-control-sampled) row subset,
#    vintage-chunked against the raw panel for the transient lag computation
# ==========================================================================
def _assemble_tensors_for_rows(keys_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """keys_df: rows drawn from base_frame() (carries vintage, d90_event,
    REQUIRED_STATIC_COLS, monthly_reporting_period, loan_sequence_number).
    Returns (seq, static, y, has_prior_dlq) -- raw (pre-scaler) sequence and
    static design, row-aligned to the SAME order the caller's vintage-sorted
    groupby produces (not keys_df's original order)."""
    keys_df = keys_df.dropna(subset=fl.REQUIRED_STATIC_COLS).copy()
    seq_parts, static_parts, y_parts = [], [], []

    for v, keys_v in keys_df.groupby("vintage", sort=True):
        v = int(v)
        panel_v = pd.read_parquet(
            fh._fast_local(PANEL_PATH), columns=PANEL_SEQ_COLS, filters=[("vintage", "==", v)],
        )
        orig_v = pd.read_parquet(
            fh._fast_local(ORIG_PATH), columns=["loan_sequence_number", "orig_upb"], filters=[("vintage", "==", v)],
        )
        keys_all, seq_all = fl.add_sequence_features(panel_v, orig_v)
        del panel_v, orig_v
        keys_all = keys_all.reset_index().rename(columns={"index": "_pos"})

        merged = keys_v[["loan_sequence_number", "monthly_reporting_period"]].merge(
            keys_all, on=["loan_sequence_number", "monthly_reporting_period"], how="left", validate="one_to_one",
        )
        n_missing = int(merged["_pos"].isna().sum())
        if n_missing:
            raise AssertionError(
                f"vintage {v}: {n_missing} rows had no matching panel-history row -- "
                "base_frame() and the raw panel have diverged"
            )
        pos_idx = merged["_pos"].to_numpy(dtype="int64")
        seq_v = seq_all[pos_idx]
        del seq_all

        seq_parts.append(seq_v)
        static_parts.append(fl.build_static_design(keys_v))
        y_parts.append(keys_v["d90_event"].to_numpy(dtype="float32"))
        logger.info("  vintage %d: %d rows assembled", v, len(keys_v))

    seq = np.concatenate(seq_parts, axis=0) if seq_parts else np.zeros((0, fl.HISTORY_LEN, fl.SEQ_CHANNELS), "float32")
    static = np.concatenate(static_parts, axis=0) if static_parts else np.zeros((0, fl.STATIC_DIM), "float32")
    y = np.concatenate(y_parts, axis=0) if y_parts else np.zeros(0, "float32")
    has_prior = fl.has_prior_delinquency(seq)
    return seq, static, y, has_prior


# ==========================================================================
# 3. Train/val tensors (case-control sample, time-based train/val split)
# ==========================================================================
def get_training_tensors(df: pd.DataFrame, refresh: bool = False):
    if (not refresh and TRAIN_TENSORS_CACHE.exists() and VAL_TENSORS_CACHE.exists() and SCALER_CACHE.exists()):
        logger.info("Loading cached train/val tensors + scaler")
        tr = np.load(TRAIN_TENSORS_CACHE)
        va = np.load(VAL_TENSORS_CACHE)
        with open(SCALER_CACHE, "rb") as f:
            scaler = pickle.load(f)
        return (tr["seq"], tr["static"], tr["y"]), (va["seq"], va["static"], va["y"]), scaler

    logger.info("Building case-control sample (same rate/seed as the champion) for the LSTM train window...")
    train_window = df.loc[df["monthly_reporting_period"] <= fh.TRAIN_CUTOFF]
    sample = fh.sample_case_control(train_window, rate=fh.CONTROL_SAMPLE_RATE, seed=fh.SEED_A)

    # TIME-based validation split, strictly inside the champion's train
    # window -- see freddie/lstm.py's VAL_CUTOFF docstring.
    sample_train = sample.loc[sample["monthly_reporting_period"] <= fl.VAL_CUTOFF].reset_index(drop=True)
    sample_val = sample.loc[sample["monthly_reporting_period"] > fl.VAL_CUTOFF].reset_index(drop=True)
    logger.info(
        "sample_train rows=%d (events=%d), sample_val rows=%d (events=%d)",
        len(sample_train), int(sample_train["d90_event"].sum()),
        len(sample_val), int(sample_val["d90_event"].sum()),
    )

    seq_train, static_train, y_train, _ = _assemble_tensors_for_rows(sample_train)
    seq_val, static_val, y_val, _ = _assemble_tensors_for_rows(sample_val)

    # Scaler fit on TRAIN ONLY (no-leakage) -- see tests/test_freddie_lstm.py.
    scaler = fl.SequenceScaler().fit(seq_train, static_train)
    seq_train_s, static_train_s = scaler.transform(seq_train, static_train)
    seq_val_s, static_val_s = scaler.transform(seq_val, static_val)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(TRAIN_TENSORS_CACHE, seq=seq_train_s, static=static_train_s, y=y_train)
    np.savez_compressed(VAL_TENSORS_CACHE, seq=seq_val_s, static=static_val_s, y=y_val)
    with open(SCALER_CACHE, "wb") as f:
        pickle.dump(scaler, f)

    return (seq_train_s, static_train_s, y_train), (seq_val_s, static_val_s, y_val), scaler


# ==========================================================================
# 4. Train (or load) the model
# ==========================================================================
def get_trained_model(train_t, val_t, refresh: bool = False) -> tuple[fl.LSTMChallenger, dict]:
    # control_rate is wired through explicitly from fh.CONTROL_SAMPLE_RATE (the
    # rate get_training_tensors() ACTUALLY sampled at) rather than left to
    # TrainConfig's own default (fl.DEFAULT_CASE_CONTROL_RATE) -- the two are
    # independently-declared literals (see freddie/lstm.py's REQUIRED_STATIC_COLS
    # note on import-order independence) that currently agree by construction
    # but are not otherwise enforced to; the pos_weight calibration identity
    # documented in freddie/lstm.py's module docstring silently breaks if they
    # drift apart, so this call is the single source of truth for the rate.
    config = fl.TrainConfig(control_rate=fh.CONTROL_SAMPLE_RATE)
    if not refresh and MODEL_CACHE.exists() and TRAIN_HISTORY_CACHE.exists():
        logger.info("Loading cached LSTM weights from %s", MODEL_CACHE)
        model = fl.LSTMChallenger(
            static_dim=fl.STATIC_DIM, hidden_size=config.hidden_size, num_layers=config.num_layers,
        )
        model.load_state_dict(torch.load(MODEL_CACHE, map_location="cpu"))
        history = json.loads(TRAIN_HISTORY_CACHE.read_text())
        return model, history

    seq_train, static_train, y_train = train_t
    seq_val, static_val, y_val = val_t
    logger.info(
        "Training LSTM: %d train rows / %d val rows, device=%s", len(y_train), len(y_val), config.device,
    )
    model, history = fl.train_lstm(seq_train, static_train, y_train, seq_val, static_val, y_val, config=config)
    logger.info("Training done: best_epoch=%d best_val_auc=%.4f", history["best_epoch"], history["best_val_auc"])

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_CACHE)
    TRAIN_HISTORY_CACHE.write_text(json.dumps(history, indent=2))
    return model, history


# ==========================================================================
# 5. Full-panel scoring, vintage-chunked, checkpointed per vintage
# ==========================================================================
def score_all(
    df: pd.DataFrame, model: fl.LSTMChallenger, scaler: fl.SequenceScaler, champion: fh.HazardModel,
    refresh: bool = False,
) -> pd.DataFrame:
    SCORED_DIR.mkdir(parents=True, exist_ok=True)
    device = torch.device(INFERENCE_DEVICE)
    frames = []

    vintages = sorted(int(v) for v in df["vintage"].dropna().unique())
    for v in vintages:
        out_path = SCORED_DIR / f"vintage_{v}.parquet"
        if out_path.exists() and not refresh:
            frames.append(pd.read_parquet(out_path))
            continue

        keys_v = df.loc[df["vintage"] == v].dropna(subset=fl.REQUIRED_STATIC_COLS).copy()
        if keys_v.empty:
            logger.warning("vintage %d: no usable rows after dropna, skipping", v)
            continue

        panel_v = pd.read_parquet(
            fh._fast_local(PANEL_PATH), columns=PANEL_SEQ_COLS, filters=[("vintage", "==", v)],
        )
        orig_v = pd.read_parquet(
            fh._fast_local(ORIG_PATH), columns=["loan_sequence_number", "orig_upb"], filters=[("vintage", "==", v)],
        )
        keys_all, seq_all = fl.add_sequence_features(panel_v, orig_v)
        del panel_v, orig_v
        keys_all = keys_all.reset_index().rename(columns={"index": "_pos"})

        merged = keys_v[["loan_sequence_number", "monthly_reporting_period"]].merge(
            keys_all, on=["loan_sequence_number", "monthly_reporting_period"], how="left", validate="one_to_one",
        )
        n_missing = int(merged["_pos"].isna().sum())
        if n_missing:
            raise AssertionError(f"vintage {v}: {n_missing} scoring rows had no matching panel-history row")
        pos_idx = merged["_pos"].to_numpy(dtype="int64")
        seq_v = seq_all[pos_idx]
        del seq_all

        has_prior = fl.has_prior_delinquency(seq_v)
        static_v = fl.build_static_design(keys_v)
        seq_v_s, static_v_s = scaler.transform(seq_v, static_v)
        lstm_pred = fl.predict_lstm(model, seq_v_s, static_v_s, device=device)
        del seq_v, seq_v_s, static_v, static_v_s

        champ_pred = fh.predict_hazard(champion, keys_v).to_numpy(dtype="float32")

        out = pd.DataFrame({
            "monthly_reporting_period": keys_v["monthly_reporting_period"].to_numpy(),
            "y": keys_v["d90_event"].to_numpy(dtype="uint8"),
            "champion_pred": champ_pred,
            "lstm_pred": lstm_pred,
            "has_prior_dlq": has_prior,
        })
        out.to_parquet(out_path, index=False)
        frames.append(out)
        logger.info("scored vintage %d: %d rows", v, len(out))
        del keys_v

    return pd.concat(frames, ignore_index=True)


# ==========================================================================
# 6. Metrics: champion-vs-LSTM AUC (identical eval set), lift split
# ==========================================================================
def _safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    ok = ~np.isnan(p)
    y_ok, p_ok = y[ok], p[ok]
    if len(y_ok) == 0 or y_ok.sum() == 0 or y_ok.sum() == len(y_ok):
        return float("nan")
    return float(roc_auc_score(y_ok, p_ok))


def compute_metrics(scored: pd.DataFrame) -> dict:
    scored = scored.copy()
    scored["split"] = np.where(
        scored["monthly_reporting_period"] <= fh.TRAIN_CUTOFF, "train", "oot",
    )
    metrics: dict = {}
    for split in ("train", "oot"):
        sub = scored.loc[scored["split"] == split]
        y = sub["y"].to_numpy()
        metrics[f"{split}_n"] = int(len(sub))
        metrics[f"{split}_events"] = int(sub["y"].sum())
        metrics[f"{split}_champion_auc"] = _safe_auc(y, sub["champion_pred"].to_numpy())
        metrics[f"{split}_lstm_auc"] = _safe_auc(y, sub["lstm_pred"].to_numpy())

    # ---- lift split (the sharpest path-memory test): OOT AUC, loans WITH a
    # prior delinquency spell in their trailing 24mo window vs clean-history.
    oot = scored.loc[scored["split"] == "oot"]
    for flag, label in ((True, "prior_dlq"), (False, "clean_history")):
        sub = oot.loc[oot["has_prior_dlq"] == flag]
        y = sub["y"].to_numpy()
        metrics[f"oot_{label}_n"] = int(len(sub))
        metrics[f"oot_{label}_events"] = int(sub["y"].sum())
        metrics[f"oot_{label}_champion_auc"] = _safe_auc(y, sub["champion_pred"].to_numpy())
        metrics[f"oot_{label}_lstm_auc"] = _safe_auc(y, sub["lstm_pred"].to_numpy())

    return metrics


def calibration_by_year(scored: pd.DataFrame) -> pd.DataFrame:
    yr = scored["monthly_reporting_period"].dt.year
    rows = []
    for y, g in scored.groupby(yr):
        rows.append({
            "year": int(y),
            "n": len(g),
            "n_events": int(g["y"].sum()),
            "observed_hazard": float(g["y"].mean()),
            "champion_predicted": float(np.nanmean(g["champion_pred"])),
            "lstm_predicted": float(np.nanmean(g["lstm_pred"])),
        })
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


# ==========================================================================
# 7. Exhibits
# ==========================================================================
def plot_calibration_comparison(calib: pd.DataFrame, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    fig, ax = plt.subplots(figsize=(9, 4.8))
    x = calib["year"]
    ax.plot(x, calib["observed_hazard"] * 100, marker="o", color=COLORS["gray"], label="Observed D90 hazard", linewidth=2)
    ax.plot(x, calib["champion_predicted"] * 100, marker="s", color=COLORS["accent"], linestyle="--", label="Champion (GLM) predicted")
    ax.plot(x, calib["lstm_predicted"] * 100, marker="^", color=COLORS["warn"], linestyle="--", label="LSTM challenger predicted")
    ax.axvspan(2020, 2021.75, color=COLORS["purple"], alpha=0.08, zorder=0, label="Forbearance window (2020-04..2021-09)")
    ax.set_xlabel("Calendar year")
    ax.set_ylabel("Monthly D90 hazard (%)")
    ax.set_title("Champion vs LSTM challenger: calibration by calendar year (identical eval set)")
    ax.legend(fontsize=7.5)
    fig.savefig(path)
    plt.close(fig)


def plot_lift_split(metrics: dict, path: Path) -> None:
    import matplotlib.pyplot as plt

    from analysis.mpl_style import COLORS, apply_textbook_style
    apply_textbook_style()

    groups = ["clean_history", "prior_dlq"]
    labels = ["Clean history\n(no dlq in trailing 24mo)", "Prior delinquency spell\n(in trailing 24mo)"]
    champ = [metrics[f"oot_{g}_champion_auc"] for g in groups]
    lstm = [metrics[f"oot_{g}_lstm_auc"] for g in groups]

    fig, ax = plt.subplots(figsize=(7, 4.8))
    x = np.arange(len(groups))
    width = 0.35
    ax.bar(x - width / 2, champ, width, color=COLORS["accent"], label="Champion (GLM)")
    ax.bar(x + width / 2, lstm, width, color=COLORS["warn"], label="LSTM challenger")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("OOT AUC")
    ax.set_ylim(0.5, 1.0)
    ax.axhline(0.5, color=COLORS["gray"], linestyle=":", linewidth=1)
    ax.set_title("Lift split: OOT AUC by prior-delinquency-spell status")
    ax.legend(fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def write_lstm_report(metrics: dict, history: dict, calib: pd.DataFrame) -> None:
    lines = []
    lines.append("# LSTM Path-Dependence Challenger -- Scorecard\n")
    lines.append(
        "CHALLENGER-NEVER-CHAMPION: this is a scorecard exercise answering one question -- "
        "does delinquency-PATH memory (trailing 24-month dlq/UPB history) add discrimination "
        "beyond the champion hazard's current-state-only view? See `freddie/lstm.py` module "
        "docstring for the full architecture/methodology and `freddie/fit_hazard.py` for the "
        "champion this challenger is compared against. Both models are scored on the IDENTICAL "
        "eval set: the champion's own train (perf <= "
        f"{fh.TRAIN_CUTOFF.date()}) / OOT (perf > {fh.TRAIN_CUTOFF.date()}) split, same "
        "NaN-covariate row exclusion.\n"
    )

    lines.append("## 1. Headline AUC: champion vs LSTM (identical eval set)\n")
    lines.append("| split | n | events | champion AUC | LSTM AUC | delta (LSTM - champion) |\n")
    lines.append("|---|---:|---:|---:|---:|---:|\n")
    for split in ("train", "oot"):
        c = metrics[f"{split}_champion_auc"]
        l = metrics[f"{split}_lstm_auc"]
        delta = l - c if np.isfinite(c) and np.isfinite(l) else float("nan")
        lines.append(
            f"| {split.upper()} | {metrics[f'{split}_n']:,} | {metrics[f'{split}_events']:,} | "
            f"{c:.4f} | {l:.4f} | {delta:+.4f} |\n"
        )
    lines.append(
        "\nTraining: early-stopped on a TIME-based validation split "
        f"(`freddie.lstm.VAL_CUTOFF` = {fl.VAL_CUTOFF.date()}, strictly inside the champion's "
        f"train window) -- best epoch {history['best_epoch']} of {history['n_epochs_run']} run, "
        f"best val AUC {history['best_val_auc']:.4f} (`outputs/freddie/lstm/training_history.json` "
        "via `data/processed/freddie/lstm/training_history.json`).\n"
    )

    lines.append("\n## 2. Calibration by calendar year (both models)\n")
    lines.append(
        "`calibration_comparison.png` / `.csv` -- observed vs each model's predicted monthly "
        "D90 hazard, real calendar-year axis, forbearance window shaded.\n"
    )

    lines.append("\n## 3. Lift split -- the sharpest path-memory test\n")
    lines.append(
        "The champion CANNOT distinguish these two groups by construction (`dlq_num` is not one "
        "of its covariates at all); the LSTM's whole premise is that it should. OOT AUC, split by "
        "whether the loan's trailing 24-month window (`freddie.lstm.has_prior_delinquency`) "
        "contains ANY prior delinquency:\n\n"
        "| group | n | events | champion AUC | LSTM AUC | delta |\n|---|---:|---:|---:|---:|---:|\n"
    )
    for g, label in (("clean_history", "Clean history"), ("prior_dlq", "Prior delinquency spell")):
        c = metrics[f"oot_{g}_champion_auc"]
        l = metrics[f"oot_{g}_lstm_auc"]
        delta = l - c if np.isfinite(c) and np.isfinite(l) else float("nan")
        lines.append(
            f"| {label} | {metrics[f'oot_{g}_n']:,} | {metrics[f'oot_{g}_events']:,} | "
            f"{c:.4f} | {l:.4f} | {delta:+.4f} |\n"
        )
    lines.append(
        "\n`lift_split.png` plots this bar comparison. If the LSTM's edge over the champion is "
        "materially LARGER on the prior-delinquency-spell group than on the clean-history group, "
        "that is the direct evidence for the path-dependence hypothesis -- the champion's current-"
        "state view genuinely under-serves loans with a non-trivial delinquency history, and a "
        "sequence model recovers some of that lost signal. If the two deltas are similar (or the "
        "clean-history delta is larger), the LSTM's edge -- if any -- is not really about PATH "
        "memory specifically.\n"
    )

    lines.append("\n## 4. COVID / forbearance caveat\n")
    lines.append(
        "Phase-A's roll-rate EDA (recorded in shared project facts) found the delinquency ladder "
        "itself distorted during forbearance: dlq climbs 2020-04..2021-09 while the 90+DPD-to-"
        "liquidation roll collapses >10x, because loans in payment-assistance programs were "
        "shielded from progressing through the normal ladder. The champion hazard never sees "
        "`dlq_num` at all, so it is insulated from this specific distortion (though its macro "
        "terms still saturate through the window -- see `outputs/freddie/hazard/hazard_report.md` "
        "section 3). The LSTM's entire feature set is delinquency-PATH history, so it is directly "
        "exposed: a loan reported 30-59 DPD in mid-2020 under forbearance administration is NOT "
        "economically comparable to a loan 30-59 DPD in 2015 under normal servicing, but this "
        "model has no way to tell the two apart. Any LSTM lift concentrated in OOT rows near or "
        "inside the 2020-2021 window should be read as a possible artifact of the forbearance-era "
        "delinquency-ladder distortion, not confirmed evidence of genuine path-dependence -- "
        "`calibration_comparison.png`'s shaded window is there for exactly this cross-check.\n"
    )

    lines.append("\n## 5. Simplifications (declared)\n")
    lines.append(
        "- Sequence lag is computed by SAME-LOAN POSITION, not calendar offset (rare reporting "
        "gaps would misalign the true calendar lag -- see `freddie/lstm.py` module docstring).\n"
        "- `dlq_num` capped at 6 before scaling (rare tail winsorised).\n"
        "- \"Prior delinquency spell\" (lift-split grouping) is defined over the SAME 24-month "
        "window the model sees, not the loan's full lifetime history.\n"
        "- Class imbalance / case-control bias handled via a single scalar `pos_weight = "
        f"{fl.DEFAULT_CASE_CONTROL_RATE}` (the case-control sampling rate) in the NN loss, the "
        "closed-form calibration identity documented in `freddie/lstm.py`'s module docstring -- "
        "NOT the champion's per-row WESML `freq_weight` inside a GLM likelihood (mechanically "
        "different because an SGD mini-batch loss has no `freq_weights` equivalent), but landing "
        "at the same result in spirit: a raw model output that is a population-calibrated "
        "probability, not a case-control-sample-conditional one.\n"
        "- Case-control subsample (same rate/seed as the champion's fit sample) for TRAINING only; "
        "the headline/lift AUCs above are scored on the full, un-subsampled train/OOT row "
        "populations (matching the champion's own score_by_year methodology exactly).\n"
        "- Modest architecture (1 LSTM layer, 64 hidden units, 2-layer MLP head) and a single "
        "seed/run -- no hyperparameter search, no ensembling, no second-seed stability check "
        "(unlike the champion's seed_stability.csv). Residual GPU-training nondeterminism is "
        "documented in `freddie/lstm.py`'s DETERMINISM section, not eliminated.\n"
        "- No competing-risk prepayment head, no LGD/EAD integration -- this module answers the "
        "discrimination question only, exactly like the champion hazard's own scope.\n"
    )

    (OUT_DIR / "lstm_report.md").write_text("".join(lines))


# ==========================================================================
# 8. Orchestration
# ==========================================================================
def main(refresh: bool = False) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    df = base_frame(refresh=refresh)

    train_t, val_t, scaler = get_training_tensors(df, refresh=refresh)
    model, history = get_trained_model(train_t, val_t, refresh=refresh)

    champion = fh._load_pickle(fh.CHAMPION_A_CACHE)

    logger.info("Scoring champion + LSTM over the full panel (vintage-chunked, checkpointed)...")
    scored = score_all(df, model, scaler, champion, refresh=refresh)

    metrics = compute_metrics(scored)
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    logger.info(
        "Champion AUC: train=%.4f oot=%.4f | LSTM AUC: train=%.4f oot=%.4f",
        metrics["train_champion_auc"], metrics["oot_champion_auc"],
        metrics["train_lstm_auc"], metrics["oot_lstm_auc"],
    )

    calib = calibration_by_year(scored)
    calib.to_csv(OUT_DIR / "calibration_comparison.csv", index=False)
    plot_calibration_comparison(calib, OUT_DIR / "calibration_comparison.png")
    plot_lift_split(metrics, OUT_DIR / "lift_split.png")

    write_lstm_report(metrics, history, calib)
    logger.info("Done. Deliverables in %s", OUT_DIR)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true",
        help="ignore cached tensors/model/scored-vintage artifacts and rebuild everything from scratch",
    )
    args = parser.parse_args()
    main(refresh=args.refresh)
