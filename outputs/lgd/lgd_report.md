# Two-stage workout LGD -- fit report

Model: `engine/lgd.py` -- cure logit x fractional-logit severity, explicit
beyond-EAD excess-loss loading. Methodology: notes section 10 (workout LGD is
bimodal; one regression through it predicts a value that never occurs).
Fit sample: TRAIN split, resolved defaults only (9,496 rows =
11,420 train default rows - 1,921
unresolved workouts - 3 NaN-covariate rows).
Cure threshold 0.05: 1,162 cures /
8,334 non-cures (cure rate 12.2%).

## Why resolved-only (incomplete-workout trap, notes section 10.3)

24.6% of all default rows have `res_time = NaN` -- open workouts at the window
end; 58% of their `lgd_time` values are coded exactly 0 (mean 0.19 vs 0.60 for
resolved). Treating them as realised would import a fake cure spike
concentrated in the OOT quarters (48% of OOT defaults are open vs 17% of
train). Residual selection bias (documented): resolved-only over-represents
fast workouts, and cures resolve faster (median 3q vs 5q for write-offs), so
cure is biased up / severity down for cohorts near the window end.

## Stage 1 -- cure logit  `cure ~ ltv10 + uer_lag1 + fico_s + loan_age`

|  | coef | se | z | p | odds_ratio |
|---|---|---|---|---|---|
| Intercept | 4.4489 | 0.3402 | 13.0783 | 0.0000 | 85.5337 |
| ltv10 | -0.7640 | 0.0252 | -30.2588 | 0.0000 | 0.4658 |
| uer_lag1 | 0.2774 | 0.0334 | 8.3086 | 0.0000 | 1.3197 |
| fico_s | -0.1402 | 0.0555 | -2.5280 | 0.0115 | 0.8692 |
| loan_age | -0.0727 | 0.0064 | -11.4393 | 0.0000 | 0.9299 |

Signs: **cure FALLS in updated LTV** (ltv10 -0.764,
asserted -- the collateral channel: equity lets a distressed borrower sell or
refinance out of default). loan_age -0.073
(seasoned defaulters cure less -- burnout). fico_s
-0.140 (weak; conditional on current LTV,
origination score adds little to the cure margin). **uer_lag1
+0.277 is POSITIVE** -- reported honestly, not
sign-asserted: conditional on updated LTV (which already carries the HPI
collapse -- the PD-LGD correlation channel of notes section 10.2),
stress-cohort defaulters at a given LTV are macro-driven rather than
idiosyncratically impaired and cure more; the sign is robust in a
fixed-28-quarter-resolution-runway subsample (defaults at t <= 32, coef
+1.02), so it is NOT a resolution-censoring artefact. Note the direction of
the raw stress effect on cure is still negative through LTV: the stress
episode raises updated LTV, and the LTV coefficient dominates (OOT realised
cure rate falls to 7.2% from 12.2% in train).

Cure AUC: train 0.837, OOT 0.769.

## Stage 2 -- fractional-logit severity  `sev_capped ~ ltv10 + uer_lag1 + fico_s + loan_age` (HC1 robust SEs)

|  | coef | se(HC1) | z | p |
|---|---|---|---|---|
| Intercept | 1.4274 | 0.1347 | 10.6010 | 0.0000 |
| ltv10 | 0.1074 | 0.0082 | 13.1763 | 0.0000 |
| uer_lag1 | -0.0416 | 0.0104 | -4.0031 | 0.0001 |
| fico_s | -0.2532 | 0.0202 | -12.5228 | 0.0000 |
| loan_age | 0.0093 | 0.0036 | 2.5417 | 0.0110 |

Signs: **severity RISES in updated LTV** (ltv10
+0.107, asserted -- less equity, bigger
foreclosure shortfall). fico_s -0.253
(better borrowers keep the property in better shape / cooperate in workout).
uer_lag1 -0.042 (small negative; the
collateral-value channel that drives mortgage severity is already inside
updated LTV, so the residual labour-market effect is a decomposition
artifact, not the total stress effect). loan_age
+0.009 (small).

## Excess-loss loading (losses beyond EAD -- never silently clipped)

14.2% of train non-cure LGDs
exceed 1 (workout costs push losses past the defaulted balance);
mean excess among them 0.1790.
Loading = E[max(lgd-1,0) | non-cure] = **0.0255**, added
to every predicted severity. OOT validation: realised OOT non-cure excess
mass 0.0236 vs loading 0.0255.

## Cure-threshold sensitivity (refit at each threshold)

|  | sample | cure_rate_real | cure_rate_pred | mean_lgd_real | mean_lgd_pred | excess_loading |
|---|---|---|---|---|---|---|
| 0.0 | train | 0.0937 | 0.0937 | 0.5995 | 0.5994 | 0.0247 |
| 0.0 | oot | 0.0431 | 0.0352 | 0.6113 | 0.6500 | 0.0247 |
| 0.05 | train | 0.1224 | 0.1224 | 0.5995 | 0.5990 | 0.0255 |
| 0.05 | oot | 0.0716 | 0.0499 | 0.6113 | 0.6583 | 0.0255 |
| 0.1 | train | 0.1352 | 0.1352 | 0.5995 | 0.5980 | 0.0259 |
| 0.1 | oot | 0.0820 | 0.0592 | 0.6113 | 0.6606 | 0.0259 |

The expected-LGD decomposition is nearly invariant to the threshold (mass
moved out of the cure spike reappears in the severity average) -- the 0.05
choice is a labelling convention, not a lever.

## OOT calibration (resolved OOT defaults, n = 1,927)

| metric | train | OOT |
|---|---|---|
| mean realised LGD | 0.5995 | 0.6113 |
| mean predicted LGD | 0.5990 | 0.6583 |
| gap (pred - real) | -0.0005 | +0.0471 |
| cure rate realised | 0.1224 | 0.0716 |
| cure rate predicted | 0.1224 | 0.0499 |
| mean sev (non-cure) realised | 0.6825 | 0.6581 |
| mean sev (non-cure) predicted | 0.6825 | 0.6926 |
| decile MAE (LGD) | 0.0203 | 0.0571 |

OOT mean tolerance |pred - real| <= 0.05: gap +0.0471
-> **PASS** (within tolerance). Decomposition of the OOT gap: cures are UNDER-predicted
(5.0% vs 7.2% realised,
pulling predicted LGD UP) and non-cure severity is OVER-predicted
(0.693 vs 0.658), both
conservative in the stress window; the two overshoots stack to the reported
gap. Honest caveat: the resolved OOT sample itself over-represents fast
workouts (48% of OOT defaults are still open), so OOT "realised" is itself a
biased-down preview of ultimate OOT severity.

### Calibration by updated-LTV decile (train edges applied to both samples)

train
|  | n | ltv_mid | real_lgd | pred_lgd | real_cure | pred_cure |
|---|---|---|---|---|---|---|
| (-inf, 66.384] | 950 | 53.7768 | 0.3698 | 0.3278 | 0.4674 | 0.4809 |
| (66.384, 77.129] | 950 | 72.1850 | 0.4257 | 0.4733 | 0.3158 | 0.2657 |
| (77.129, 82.953] | 949 | 80.5174 | 0.5295 | 0.5476 | 0.1675 | 0.1624 |
| (82.953, 88.78] | 950 | 85.7168 | 0.5855 | 0.5870 | 0.0779 | 0.1102 |
| (88.78, 95.383] | 949 | 92.1346 | 0.6518 | 0.6269 | 0.0674 | 0.0727 |
| (95.383, 100.101] | 950 | 97.6120 | 0.6530 | 0.6494 | 0.0389 | 0.0464 |
| (100.101, 106.667] | 949 | 103.0514 | 0.7017 | 0.6727 | 0.0358 | 0.0342 |
| (106.667, 112.335] | 950 | 109.7130 | 0.6824 | 0.6819 | 0.0221 | 0.0248 |
| (112.335, 118.388] | 949 | 115.3955 | 0.6948 | 0.6912 | 0.0105 | 0.0181 |
| (118.388, inf] | 950 | 127.5377 | 0.7006 | 0.7324 | 0.0200 | 0.0081 |

OOT
|  | n | ltv_mid | real_lgd | pred_lgd | real_cure | pred_cure |
|---|---|---|---|---|---|---|
| (-inf, 66.384] | 71 | 49.3667 | 0.4431 | 0.3721 | 0.4789 | 0.3910 |
| (66.384, 77.129] | 70 | 71.9532 | 0.5211 | 0.5173 | 0.2571 | 0.1817 |
| (77.129, 82.953] | 49 | 80.4342 | 0.4877 | 0.5676 | 0.2041 | 0.1241 |
| (82.953, 88.78] | 97 | 85.7967 | 0.5292 | 0.5884 | 0.1237 | 0.0967 |
| (88.78, 95.383] | 142 | 92.2918 | 0.4906 | 0.6158 | 0.1408 | 0.0645 |
| (95.383, 100.101] | 123 | 97.9735 | 0.6006 | 0.6383 | 0.0813 | 0.0464 |
| (100.101, 106.667] | 215 | 103.5513 | 0.5877 | 0.6590 | 0.0465 | 0.0353 |
| (106.667, 112.335] | 338 | 109.7757 | 0.6316 | 0.6667 | 0.0178 | 0.0263 |
| (112.335, 118.388] | 329 | 115.0823 | 0.6536 | 0.6945 | 0.0213 | 0.0160 |
| (118.388, inf] | 493 | 127.9116 | 0.6822 | 0.7294 | 0.0223 | 0.0073 |

## Documented simplifications

* LGD_cure = 0; realised mean LGD among train cures = 0.0036
  (understates expected LGD by ~0.0004 of EAD).
* Constant (not covariate-driven) excess-loss loading.
* Resolved workouts only; no completion model for open cases yet.
* `lgd_time` taken as the vendor's realised workout LGD (EIR discounting of
  notes section 10.1 assumed embedded; no post-default cash flows in panel).
* Severity is a conditional-mean model; ECL only consumes the mean.
* Point-in-time, no downturn add-on (IFRS 9 wants unbiased PIT LGD).
* ECL assembly reminder: S(t) already includes prepayment survival, so the
  EAD_t that multiplies this LGD must be the CONTRACTUAL amortisation
  balance, never prepay-scaled (see engine/lgd.py docstring).
