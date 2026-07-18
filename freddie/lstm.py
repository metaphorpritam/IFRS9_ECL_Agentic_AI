"""LSTM path-dependence challenger to the SFLLD champion hazard (rung 3).

CHALLENGER-NEVER-CHAMPION: this module (+ freddie/fit_lstm.py) exists to
answer a single question -- "does delinquency-PATH memory add discrimination
beyond the champion hazard's current-state-only view?" -- not to replace the
champion. The champion (freddie/fit_hazard.py) is an interpretable,
coefficient-auditable, regulator-legible cloglog GLM; nothing here is a
candidate to sit in front of it in production. See outputs/freddie/lstm/
lstm_report.md (written by fit_lstm.py) for the scorecard verdict.

--------------------------------------------------------------------------
LIKE-FOR-LIKE WITH THE CHAMPION (freddie/fit_hazard.py, read first)
--------------------------------------------------------------------------
Static covariates: the IDENTICAL set the champion's BASE_RHS uses --
loan_age, fico_s, dti_s, ltv10, occupancy_status, loan_purpose, channel,
uer_lag1, delta_uer_lag1, hpi_growth_lag1 (`freddie.fit_hazard.REQUIRED_COLS`)
-- one-hot encoded here (NN, not a Treatment-coded GLM design) with the SAME
reference levels the champion drops (occupancy 'P', loan_purpose 'P',
channel 'R'), so a coefficient-free NN and an interpretable GLM are reading
the exact same static information.
Split: champion TRAIN_CUTOFF (2016-12) / OOT boundary is reused verbatim
(`freddie.fit_hazard.TRAIN_CUTOFF`) so champion-vs-LSTM OOT AUC is scored on
the IDENTICAL eval set (see freddie/fit_lstm.py). This module adds ONE
internal cut, VAL_CUTOFF (2015-12), strictly inside the champion's train
window, for time-based early-stopping validation -- the champion itself has
no such cut (a GLM doesn't need one); it never touches OOT.
Case-control sampling: reuses `freddie.fit_hazard.sample_case_control` at
the SAME CONTROL_SAMPLE_RATE and SEED_A, for the same reason the champion
uses it (39.5M rows is impractical to build 24-step sequences for at fit
time) -- see that module's WESML docstring section. Unlike the GLM, this NN
does NOT use a per-row freq_weight in its loss (WESML's likelihood-
reweighting argument is specific to a likelihood-based estimator); instead
`pos_weight` in `BCEWithLogitsLoss` is set to the case-control sampling RATE
itself (`TrainConfig.control_rate`, matching `fh.CONTROL_SAMPLE_RATE`), not
the sample's raw n_neg/n_pos ratio. This is the SAME correction the
champion's WESML applies, in spirit (both exist because BOTH models are fit
on a case-control-subsampled dataset, not the true population), just landing
at a different point in the pipeline for a mechanical reason -- statsmodels'
GLM takes a per-row `freq_weights` array inside its likelihood; an SGD
mini-batch loss has no equivalent, so the single scalar `pos_weight=rate`
is used instead. Why `rate`, not `n_neg/n_pos`: with every event kept
(selection prob. 1) and every control kept at probability `rate`, the
BCEWithLogitsLoss-minimising sigmoid at any x satisfies
`sigma*(x) = w*p(x) / (w*p(x) + rate*(1-p(x)))` for pos_weight `w` (p(x) =
the TRUE population P(y=1|x)); setting `w = rate` makes this collapse to
`sigma*(x) = p(x)` exactly -- the network's raw sigmoid output is then
already a POPULATION-calibrated probability, needing no post-hoc case-
control correction for the calibration exhibit. `w = n_neg/n_pos` (the
sample's own class ratio, a much LARGER number) instead pulls sigma*(x)
towards ~0.5 (pure sample-rebalancing, good for training stability /
gradient signal on a rare-event target, useless for calibration) --
verified analytically and by a small closed-form simulation in
`tests/test_freddie_lstm.py::test_pos_weight_rate_recovers_calibration`.

--------------------------------------------------------------------------
THE NEW INFORMATION: delinquency-PATH memory (HISTORY_LEN=24 months)
--------------------------------------------------------------------------
The champion hazard never sees `dlq_num` (the monthly delinquency ladder)
AT ALL -- its only time-dependent input is `loan_age` (baseline seasoning
spline) and current-month `updated_ltv`. This module's whole premise is
that TWO loans with identical current state (same FICO/DTI/LTV/age/macro)
can carry very different forward risk depending on whether one of them was
30-59 DPD eight months ago and cured, while the other has been current the
entire time -- a distinction the champion's design cannot represent. Per
loan-month row t (t = the SAME `monthly_reporting_period` the champion
scores, i.e. this predicts the SAME `d90_event` target, not a shifted
"next-month" label -- see `add_sequence_features`'s docstring for why),
the sequence input is the loan's own trailing HISTORY_LEN=24 months
(t-24 .. t-1, chronological order, current month t itself NEVER included --
no lookahead) of:
  channel 0  dlq rung   = clip(dlq_num, 0, DLQ_CAP) / DLQ_SCALE
                          (DLQ_CAP=6, DLQ_SCALE=3.0 -- so the D90 trigger
                          threshold, dlq_num==3, lands at exactly 1.0 in
                          this scaled space; SIMPLIFICATION: caps the rare
                          dlq_num>6 tail, documented in fit_lstm.py)
  channel 1  UPB ratio  = current_actual_upb / orig_upb (paydown / negative-
                          amortization trajectory -- the LSTM's only view of
                          collateral/curtailment dynamics, since it does NOT
                          get updated_ltv or any macro-lag as a sequence
                          input, only as a static feature at time t)
  channel 2  validity   = 1.0 where a genuine same-loan prior-month row
                          exists, 0.0 for PADDING (a loan younger than
                          HISTORY_LEN months at row t has fewer than 24 real
                          prior months; the missing entries are zero-filled
                          on channels 0/1 and flagged 0.0 here rather than
                          silently read as "current, 0 DPD" -- the network
                          can learn to treat mask==0 as "no history", not
                          "history observed to be clean").
Rows earlier than the loan's own first row can never be referenced (the
lag is computed by same-loan POSITION, not calendar offset -- see
`add_sequence_features`), and `panel_monthly.parquet` is itself already
absorbing-D90-truncated (freddie/build_panel.py: no loan-month after a
loan's first D90 event exists in this table at all), so no sequence here
can ever see a loan's own post-default history either.

SIMPLIFICATION (lag-vs-gap): lag k is computed by POSITION within a loan's
sorted rows, not by calendar offset. `panel_monthly.parquet` is a monthly
panel with essentially no missing intermediate months in practice (a loan
either reports every month up to censorship/event or terminates), but if a
rare reporting gap exists, "lag 3" silently becomes "3 rows back" rather
than "3 calendar months back" for that loan. Not corrected here.

--------------------------------------------------------------------------
ARCHITECTURE (modest, per spec -- this is a challenger scorecard exercise,
not a production model search)
--------------------------------------------------------------------------
1-layer LSTM (default HIDDEN_SIZE=64) over the 3-channel, 24-step sequence,
its FINAL hidden state concatenated with the static design vector (14 dims:
7 numeric + 7 one-hot dummy), fed through a 2-layer MLP head (32 -> 1
logit). See `LSTMChallenger`.

--------------------------------------------------------------------------
DETERMINISM (fixed seeds, residual nondeterminism documented, not eliminated)
--------------------------------------------------------------------------
`set_determinism` seeds Python's `random`, numpy, and torch (CPU + all CUDA
devices) and disables cuDNN's autotuner/nondeterministic kernel selection
(`cudnn.deterministic=True`, `cudnn.benchmark=False`). This makes an
EVAL-MODE forward pass (no dropout, no backward) exactly reproducible on a
fixed device (tests/test_freddie_lstm.py locks this down on CPU). It does
NOT eliminate every source of GPU nondeterminism in TRAINING: cuDNN's RNN
(LSTM) backward kernels use atomic adds internally on CUDA, whose
floating-point summation order is not guaranteed bit-identical run to run
even with the flags above (a documented, long-standing PyTorch/cuDNN
limitation, not a bug in this module) -- so two full training runs on GPU
with the same seed can converge to SLIGHTLY different final weights, though
metrics (AUC to ~3 decimal places) are stable in practice. Recorded here
rather than silently claimed away.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score

# ==========================================================================
# Spec constants
# ==========================================================================
HISTORY_LEN = 24          # months of trailing delinquency/UPB history
DLQ_CAP = 6.0              # winsorise the rare dlq_num>6 tail (see module docstring)
DLQ_SCALE = 3.0            # dlq_num==3 (the D90 trigger) -> 1.0 in scaled space
SEQ_CHANNELS = 3           # dlq rung, upb ratio, validity mask

HIDDEN_SIZE = 64
NUM_LAYERS = 1
HEAD_HIDDEN = 32
DROPOUT = 0.0

SEED = 42

#: time-based validation cutoff for early stopping -- strictly inside the
#: champion's train window (<= freddie.fit_hazard.TRAIN_CUTOFF, 2016-12).
#: See module docstring's "LIKE-FOR-LIKE WITH THE CHAMPION" section.
VAL_CUTOFF = pd.Timestamp("2015-12-01")

#: static design -- IDENTICAL covariate set to freddie.fit_hazard.REQUIRED_COLS,
#: one-hot encoded with the SAME reference levels the champion's Treatment()
#: coding drops (occupancy 'P', loan_purpose 'P', channel 'R').
STATIC_NUMERIC_COLS = [
    "loan_age", "fico_s", "dti_s", "ltv10",
    "uer_lag1", "delta_uer_lag1", "hpi_growth_lag1",
]
_OCC_LEVELS = ["I", "S"]        # reference: P (owner-occupied)
_PURPOSE_LEVELS = ["C", "N"]    # reference: P (purchase)
_CHANNEL_LEVELS = ["B", "C", "T"]  # reference: R (retail)
STATIC_DUMMY_COLS = (
    [f"occ_{v}" for v in _OCC_LEVELS]
    + [f"purpose_{v}" for v in _PURPOSE_LEVELS]
    + [f"channel_{v}" for v in _CHANNEL_LEVELS]
)
STATIC_COLUMNS = STATIC_NUMERIC_COLS + STATIC_DUMMY_COLS
STATIC_NUMERIC_DIM = len(STATIC_NUMERIC_COLS)
STATIC_DIM = len(STATIC_COLUMNS)

#: raw covariates a frame must carry (post freddie.fit_hazard.build_model_frame
#: derivation) before build_static_design can run -- identical set to
#: freddie.fit_hazard.REQUIRED_COLS, restated here so this module has no
#: import-order dependency on fit_hazard for its own correctness.
REQUIRED_STATIC_COLS = [
    "loan_age", "fico_s", "dti_s", "ltv10",
    "occupancy_status", "loan_purpose", "channel",
    "uer_lag1", "delta_uer_lag1", "hpi_growth_lag1",
]


# ==========================================================================
# 1. Static design matrix (NN one-hot equivalent of the champion's formula)
# ==========================================================================
def build_static_design(df: pd.DataFrame) -> np.ndarray:
    """(n, STATIC_DIM) float32 design matrix. Caller must already have
    dropped rows with NaN in REQUIRED_STATIC_COLS (mirrors
    freddie.fit_hazard.fit_hazard's `dropna(subset=need)`) -- this function
    does not check for NaN itself, matching predict_hazard's contract."""
    n = len(df)
    out = np.zeros((n, STATIC_DIM), dtype="float32")
    for i, c in enumerate(STATIC_NUMERIC_COLS):
        out[:, i] = df[c].to_numpy(dtype="float32")
    j = STATIC_NUMERIC_DIM
    occ = df["occupancy_status"].astype(str)
    for k, lvl in enumerate(_OCC_LEVELS):
        out[:, j + k] = (occ == lvl).to_numpy(dtype="float32")
    j += len(_OCC_LEVELS)
    purp = df["loan_purpose"].astype(str)
    for k, lvl in enumerate(_PURPOSE_LEVELS):
        out[:, j + k] = (purp == lvl).to_numpy(dtype="float32")
    j += len(_PURPOSE_LEVELS)
    chan = df["channel"].astype(str)
    for k, lvl in enumerate(_CHANNEL_LEVELS):
        out[:, j + k] = (chan == lvl).to_numpy(dtype="float32")
    return out


# ==========================================================================
# 2. Sequence features (vectorised same-loan lag, no python per-loan loop)
# ==========================================================================
def add_sequence_features(
    panel_chunk: pd.DataFrame,
    orig_upb: pd.DataFrame,
    history_len: int = HISTORY_LEN,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Build the (n, history_len, 3) trailing-history tensor for EVERY row of
    `panel_chunk` (a full per-loan-history slice -- e.g. one origination
    vintage, so every loan's complete life is present; see freddie/
    fit_lstm.py's vintage-chunked callers).

    `panel_chunk` needs: loan_sequence_number, monthly_reporting_period,
    dlq_num, current_actual_upb. `orig_upb` needs: loan_sequence_number,
    orig_upb (one row per loan).

    Returns (keys, seq): `keys` is a DataFrame with loan_sequence_number +
    monthly_reporting_period, row-aligned with `seq`, sorted
    (loan_sequence_number, monthly_reporting_period) -- NOT the caller's
    original row order, so callers merge back on these keys rather than
    assuming positional alignment with their own input frame.

    MEMORY-LEAN, no per-loan python loop: rows are sorted once so every
    loan's history is contiguous, then each of the `history_len` lags is
    computed with a single GLOBAL numpy slice-shift (O(1) per lag, not a
    groupby().shift() re-grouping HISTORY_LEN times) -- correctness of the
    global shift is recovered by masking on `pos_in_loan >= k`: a row with
    fewer than k rows before it IN ITS OWN LOAN cannot have a valid lag-k
    value regardless of what garbage the naive global shift produced at that
    position (which, if pos>=k, is guaranteed by the sort to be the correct
    same-loan row, and if pos<k, is masked out unconditionally).

    NO LOOKAHEAD: lag k in {1..history_len} always reads a STRICTLY PRIOR
    row of the SAME loan; the row's own month is never in its own sequence.
    Sequence index 0 = oldest (lag history_len), index history_len-1 =
    most recent (lag 1) -- chronological order for the LSTM to consume.

    SAME-MONTH TARGET (not "next month" despite the module docstring's plain
    -English framing): this predicts d90_event AT month t from months
    t-history_len..t-1, exactly mirroring the champion hazard's own
    discrete-time framing (hazard of the event THIS month, given
    information available through last month) -- freddie/fit_hazard.py's
    macro lags are on the identical one-month-back convention. "Predict
    next-month D90 from last-24-month history" in the task spec is this
    same construction stated informally: the last KNOWN month is t-1, the
    thing being predicted is the FIRST unknown month, t.
    """
    need_panel = {"loan_sequence_number", "monthly_reporting_period", "dlq_num", "current_actual_upb"}
    missing = need_panel - set(panel_chunk.columns)
    if missing:
        raise KeyError(f"panel_chunk missing required columns: {sorted(missing)}")

    df = panel_chunk.merge(
        orig_upb[["loan_sequence_number", "orig_upb"]], on="loan_sequence_number", how="left",
    )
    df = df.sort_values(["loan_sequence_number", "monthly_reporting_period"]).reset_index(drop=True)

    pos = df.groupby("loan_sequence_number", sort=False).cumcount().to_numpy()
    dlq = (df["dlq_num"].astype("float64").clip(lower=0, upper=DLQ_CAP) / DLQ_SCALE).to_numpy(dtype="float32")
    upb_ratio = (df["current_actual_upb"].astype("float64") / df["orig_upb"].astype("float64")).to_numpy(dtype="float32")

    n = len(df)
    seq = np.zeros((n, history_len, SEQ_CHANNELS), dtype="float32")
    for k in range(1, history_len + 1):
        shifted_dlq = np.full(n, np.nan, dtype="float32")
        shifted_upb = np.full(n, np.nan, dtype="float32")
        if n > k:
            shifted_dlq[k:] = dlq[: n - k]
            shifted_upb[k:] = upb_ratio[: n - k]
        valid = (pos >= k) & np.isfinite(shifted_dlq) & np.isfinite(shifted_upb)
        i = history_len - k
        seq[:, i, 0] = np.where(valid, shifted_dlq, 0.0)
        seq[:, i, 1] = np.where(valid, shifted_upb, 0.0)
        seq[:, i, 2] = valid.astype("float32")

    keys = df[["loan_sequence_number", "monthly_reporting_period"]].copy()
    return keys, seq


def has_prior_delinquency(seq: np.ndarray) -> np.ndarray:
    """Bool array: did this row's trailing HISTORY_LEN-month window contain
    ANY valid, delinquent (dlq rung > 0) prior month? SIMPLIFICATION: "prior
    delinquency spell" is defined over the same HISTORY_LEN=24-month window
    the model itself sees, not the loan's full lifetime history -- a loan
    delinquent >24 months before row t reads as "clean" by this flag. Used
    for the lift-split exhibit (freddie/fit_lstm.py), computed on the RAW
    (pre-scaler) sequence array so it is unaffected by standardisation."""
    dlq_present = seq[:, :, 0] > 1e-6
    valid = seq[:, :, 2] > 0.5
    return (dlq_present & valid).any(axis=1)


# ==========================================================================
# 3. Scaler (fit on TRAIN only -- see freddie/fit_lstm.py's no-leakage tests)
# ==========================================================================
@dataclass
class SequenceScaler:
    """Standardises the static NUMERIC columns and the sequence UPB-ratio
    channel; static dummy columns and the dlq-rung/validity channels are
    left untouched (already bounded [0, 1] / [0, DLQ_CAP/DLQ_SCALE]).
    MUST be fit on TRAIN rows only (no-leakage) -- see
    tests/test_freddie_lstm.py::test_scaler_fit_on_train_only."""

    static_mean: np.ndarray = field(default=None)
    static_std: np.ndarray = field(default=None)
    upb_mean: float = 0.0
    upb_std: float = 1.0
    fitted_: bool = False

    def fit(self, seq: np.ndarray, static: np.ndarray) -> "SequenceScaler":
        num = static[:, :STATIC_NUMERIC_DIM]
        mean = num.mean(axis=0)
        std = num.std(axis=0)
        std[std < 1e-6] = 1.0
        self.static_mean = mean.astype("float64")
        self.static_std = std.astype("float64")

        valid = seq[:, :, 2] > 0.5
        upb_vals = seq[:, :, 1][valid]
        self.upb_mean = float(upb_vals.mean()) if upb_vals.size else 0.0
        self.upb_std = float(upb_vals.std()) if upb_vals.size else 1.0
        if self.upb_std < 1e-6:
            self.upb_std = 1.0
        self.fitted_ = True
        return self

    def transform(self, seq: np.ndarray, static: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if not self.fitted_:
            raise RuntimeError("SequenceScaler.transform called before fit")
        static_s = static.copy().astype("float64")
        static_s[:, :STATIC_NUMERIC_DIM] = (
            static_s[:, :STATIC_NUMERIC_DIM] - self.static_mean
        ) / self.static_std

        seq_s = seq.copy()
        valid = seq[:, :, 2] > 0.5
        upb_scaled = (seq[:, :, 1].astype("float64") - self.upb_mean) / self.upb_std
        seq_s[:, :, 1] = np.where(valid, upb_scaled, 0.0).astype("float32")

        return seq_s.astype("float32"), static_s.astype("float32")


# ==========================================================================
# 4. Model
# ==========================================================================
class LSTMChallenger(nn.Module):
    """1-2 layer LSTM over (batch, HISTORY_LEN, SEQ_CHANNELS), final hidden
    state concatenated with the static design vector, 2-layer MLP head."""

    def __init__(
        self,
        static_dim: int = STATIC_DIM,
        hidden_size: int = HIDDEN_SIZE,
        num_layers: int = NUM_LAYERS,
        head_hidden: int = HEAD_HIDDEN,
        dropout: float = DROPOUT,
    ) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(
            input_size=SEQ_CHANNELS, hidden_size=hidden_size, num_layers=num_layers,
            batch_first=True, dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(hidden_size + static_dim, head_hidden),
            nn.ReLU(),
            nn.Linear(head_hidden, 1),
        )

    def forward(self, seq: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        _, (h_n, _) = self.lstm(seq)
        last_hidden = h_n[-1]                       # (batch, hidden_size) -- top layer
        x = torch.cat([last_hidden, static], dim=1)
        return self.head(x).squeeze(-1)              # logits


def _apply_wsl2_cudnn_rnn_workaround() -> None:
    """Disable cuDNN (globally, torch-process-wide) as a documented
    environment workaround, NOT the spec's CPU/sklearn "CUDA breaks" fallback
    -- CUDA itself is fine here; only cuDNN's fused/persistent RNN kernel is
    broken on this WSL2 + RTX 4060 build. Verified by a minimal reproduction
    (2026-07-18, this environment): `torch.nn.LSTM(3, 64, 1)` over a single
    (82887, 24, 3) float32 CUDA tensor (~19MB, nowhere near the 8GB VRAM
    budget) raises `RuntimeError: CUDA driver error: out of memory` with
    `cudnn.enabled=True`; the IDENTICAL call succeeds instantly with it
    False. This is a known class of WSL2/WDDM cuDNN-RNN-workspace-paging
    issue, not a real memory shortage (nvidia-smi shows 0MiB used both
    immediately before and after the crash). PyTorch's non-cuDNN CUDA RNN
    kernel is used instead; for this module's tiny model (1 layer, 64
    units) the cost is negligible -- benchmarked at ~28ms per 4096-row
    batch, i.e. GPU training stays fully viable (~5s/epoch on the full
    production case-control sample), so this is NOT a CPU fallback."""
    torch.backends.cudnn.enabled = False


def set_determinism(seed: int = SEED) -> None:
    """Seed Python/numpy/torch (CPU+CUDA) and disable cuDNN's nondeterministic
    kernel autotuning (moot once cuDNN itself is disabled below, kept for
    robustness if a future environment re-enables it). See module docstring's
    DETERMINISM section for what this does and does NOT guarantee."""
    import random

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    _apply_wsl2_cudnn_rnn_workaround()


# ==========================================================================
# 5. Inference (chunked internally -- safe for a whole vintage's worth of rows)
# ==========================================================================
def predict_lstm(
    model: LSTMChallenger,
    seq: np.ndarray,
    static: np.ndarray,
    device: torch.device | str = "cpu",
    batch_size: int = 65536,
) -> np.ndarray:
    """Predicted P(d90_event) for every row of (seq, static) -- already
    scaler-transformed. Internally mini-batched so a caller can pass a whole
    vintage chunk's rows (millions) without exceeding GPU VRAM: the naive
    single-shot forward over e.g. 2.5M rows x 24 steps x 64 hidden would
    transiently need the full per-timestep hidden-state tensor
    (2.5M*24*64*4B ~ 15GB) -- far past the RTX 4060's 8GB budget."""
    if torch.device(device).type == "cuda":
        _apply_wsl2_cudnn_rnn_workaround()  # standalone-inference safety net, see set_determinism
    model.eval()
    dev = torch.device(device)
    model.to(dev)
    outs = []
    n = len(seq)
    with torch.no_grad():
        for start in range(0, n, batch_size):
            end = min(start + batch_size, n)
            sb = torch.from_numpy(seq[start:end]).to(dev)
            xb = torch.from_numpy(static[start:end]).to(dev)
            logits = model(sb, xb)
            outs.append(torch.sigmoid(logits).detach().cpu().numpy())
    return np.concatenate(outs).astype("float32") if outs else np.zeros(0, dtype="float32")


# ==========================================================================
# 6. Training (early stopping on a TIME-based validation split)
# ==========================================================================
#: must match freddie.fit_hazard.CONTROL_SAMPLE_RATE; restated (not imported)
#: to keep this module's own import-order independence from fit_hazard, per
#: the REQUIRED_STATIC_COLS note above. Callers that use a DIFFERENT sampling
#: rate (e.g. tests/test_freddie_lstm.py's richer TEST_CONTROL_RATE) MUST
#: override `TrainConfig.control_rate` to match, or the pos_weight
#: calibration identity above no longer holds.
DEFAULT_CASE_CONTROL_RATE = 0.05


@dataclass
class TrainConfig:
    epochs: int = 30
    batch_size: int = 4096
    lr: float = 1e-3
    patience: int = 5
    seed: int = SEED
    hidden_size: int = HIDDEN_SIZE
    num_layers: int = NUM_LAYERS
    control_rate: float = DEFAULT_CASE_CONTROL_RATE
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


def train_lstm(
    seq_train: np.ndarray, static_train: np.ndarray, y_train: np.ndarray,
    seq_val: np.ndarray, static_val: np.ndarray, y_val: np.ndarray,
    config: TrainConfig = TrainConfig(),
) -> tuple[LSTMChallenger, dict]:
    """Trains with early stopping on VAL AUC (VAL_CUTOFF-split rows -- see
    module docstring). Class imbalance / case-control calibration handled via
    `pos_weight = config.control_rate` in BCEWithLogitsLoss -- see module
    docstring's "Case-control sampling" section for why this specific choice
    (not the sample's raw n_neg/n_pos ratio) makes the network's raw sigmoid
    output a population-calibrated probability. Returns the BEST-val-AUC
    epoch's weights (not necessarily the last epoch's)."""
    set_determinism(config.seed)
    device = torch.device(config.device)

    model = LSTMChallenger(
        static_dim=static_train.shape[1], hidden_size=config.hidden_size, num_layers=config.num_layers,
    ).to(device)

    pos_weight = torch.tensor([config.control_rate], dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.Adam(model.parameters(), lr=config.lr)

    seq_train_t = torch.from_numpy(seq_train)
    static_train_t = torch.from_numpy(static_train)
    y_train_t = torch.from_numpy(y_train.astype("float32"))
    n = len(y_train)

    seq_val_dev = torch.from_numpy(seq_val).to(device)
    static_val_dev = torch.from_numpy(static_val).to(device)
    y_val_dev = torch.from_numpy(y_val.astype("float32")).to(device)

    best_val_auc = -np.inf
    best_state = None
    best_epoch = -1
    epochs_no_improve = 0
    history: dict = {"train_loss": [], "val_loss": [], "val_auc": []}

    rng = np.random.default_rng(config.seed)
    for epoch in range(config.epochs):
        model.train()
        perm = rng.permutation(n)
        epoch_loss = 0.0
        for start in range(0, n, config.batch_size):
            idx = perm[start:start + config.batch_size]
            sb = seq_train_t[idx].to(device)
            xb = static_train_t[idx].to(device)
            yb = y_train_t[idx].to(device)
            opt.zero_grad()
            logits = model(sb, xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            opt.step()
            epoch_loss += loss.item() * len(idx)
        epoch_loss /= max(n, 1)

        model.eval()
        with torch.no_grad():
            val_logits = model(seq_val_dev, static_val_dev)
            val_loss = nn.functional.binary_cross_entropy_with_logits(
                val_logits, y_val_dev, pos_weight=pos_weight,
            ).item()
            val_probs = torch.sigmoid(val_logits).cpu().numpy()
        val_auc = (
            float(roc_auc_score(y_val, val_probs)) if len(np.unique(y_val)) > 1 else float("nan")
        )

        history["train_loss"].append(epoch_loss)
        history["val_loss"].append(val_loss)
        history["val_auc"].append(val_auc)

        improved = np.isfinite(val_auc) and val_auc > best_val_auc
        if improved:
            best_val_auc = val_auc
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
            best_epoch = epoch
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= config.patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    history["best_epoch"] = best_epoch
    history["best_val_auc"] = best_val_auc
    history["n_epochs_run"] = len(history["train_loss"])
    return model, history
