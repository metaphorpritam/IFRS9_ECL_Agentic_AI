# LSTM Path-Dependence Challenger -- Scorecard
CHALLENGER-NEVER-CHAMPION: this is a scorecard exercise answering one question -- does delinquency-PATH memory (trailing 24-month dlq/UPB history) add discrimination beyond the champion hazard's current-state-only view? See `freddie/lstm.py` module docstring for the full architecture/methodology and `freddie/fit_hazard.py` for the champion this challenger is compared against. Both models are scored on the IDENTICAL eval set: the champion's own train (perf <= 2016-12-01) / OOT (perf > 2016-12-01) split, same NaN-covariate row exclusion.
## 1. Headline AUC: champion vs LSTM (identical eval set)
| split | n | events | champion AUC | LSTM AUC | delta (LSTM - champion) |
|---|---:|---:|---:|---:|---:|
| TRAIN | 16,059,126 | 24,611 | 0.8536 | 0.9964 | +0.1429 |
| OOT | 20,621,912 | 16,832 | 0.6847 | 0.9925 | +0.3078 |

Training: early-stopped on a TIME-based validation split (`freddie.lstm.VAL_CUTOFF` = 2015-12-01, strictly inside the champion's train window) -- best epoch 3 of 9 run, best val AUC 0.9963 (`outputs/freddie/lstm/training_history.json` via `data/processed/freddie/lstm/training_history.json`).

## 2. Calibration by calendar year (both models)
`calibration_comparison.png` / `.csv` -- observed vs each model's predicted monthly D90 hazard, real calendar-year axis, forbearance window shaded.

## 3. Lift split -- the sharpest path-memory test
The champion CANNOT distinguish these two groups by construction (`dlq_num` is not one of its covariates at all); the LSTM's whole premise is that it should. OOT AUC, split by whether the loan's trailing 24-month window (`freddie.lstm.has_prior_delinquency`) contains ANY prior delinquency:

| group | n | events | champion AUC | LSTM AUC | delta |
|---|---:|---:|---:|---:|---:|
| Clean history | 19,643,934 | 40 | 0.5386 | 0.5287 | -0.0098 |
| Prior delinquency spell | 977,978 | 16,792 | 0.5698 | 0.9570 | +0.3872 |

`lift_split.png` plots this bar comparison. If the LSTM's edge over the champion is materially LARGER on the prior-delinquency-spell group than on the clean-history group, that is the direct evidence for the path-dependence hypothesis -- the champion's current-state view genuinely under-serves loans with a non-trivial delinquency history, and a sequence model recovers some of that lost signal. If the two deltas are similar (or the clean-history delta is larger), the LSTM's edge -- if any -- is not really about PATH memory specifically.

## 4. COVID / forbearance caveat
Phase-A's roll-rate EDA (recorded in shared project facts) found the delinquency ladder itself distorted during forbearance: dlq climbs 2020-04..2021-09 while the 90+DPD-to-liquidation roll collapses >10x, because loans in payment-assistance programs were shielded from progressing through the normal ladder. The champion hazard never sees `dlq_num` at all, so it is insulated from this specific distortion (though its macro terms still saturate through the window -- see `outputs/freddie/hazard/hazard_report.md` section 3). The LSTM's entire feature set is delinquency-PATH history, so it is directly exposed: a loan reported 30-59 DPD in mid-2020 under forbearance administration is NOT economically comparable to a loan 30-59 DPD in 2015 under normal servicing, but this model has no way to tell the two apart. Any LSTM lift concentrated in OOT rows near or inside the 2020-2021 window should be read as a possible artifact of the forbearance-era delinquency-ladder distortion, not confirmed evidence of genuine path-dependence -- `calibration_comparison.png`'s shaded window is there for exactly this cross-check.

## 5. Simplifications (declared)
- Sequence lag is computed by SAME-LOAN POSITION, not calendar offset (rare reporting gaps would misalign the true calendar lag -- see `freddie/lstm.py` module docstring).
- `dlq_num` capped at 6 before scaling (rare tail winsorised).
- "Prior delinquency spell" (lift-split grouping) is defined over the SAME 24-month window the model sees, not the loan's full lifetime history.
- Class imbalance / case-control bias handled via a single scalar `pos_weight = 0.05` (the case-control sampling rate) in the NN loss, the closed-form calibration identity documented in `freddie/lstm.py`'s module docstring -- NOT the champion's per-row WESML `freq_weight` inside a GLM likelihood (mechanically different because an SGD mini-batch loss has no `freq_weights` equivalent), but landing at the same result in spirit: a raw model output that is a population-calibrated probability, not a case-control-sample-conditional one.
- Case-control subsample (same rate/seed as the champion's fit sample) for TRAINING only; the headline/lift AUCs above are scored on the full, un-subsampled train/OOT row populations (matching the champion's own score_by_year methodology exactly).
- Modest architecture (1 LSTM layer, 64 hidden units, 2-layer MLP head) and a single seed/run -- no hyperparameter search, no ensembling, no second-seed stability check (unlike the champion's seed_stability.csv). Residual GPU-training nondeterminism is documented in `freddie/lstm.py`'s DETERMINISM section, not eliminated.
- No competing-risk prepayment head, no LGD/EAD integration -- this module answers the discrimination question only, exactly like the champion hazard's own scope.
