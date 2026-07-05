# Fit statistics -- cloglog hazards (one-quarter-ahead)

AUC is for the one-quarter-ahead event: per-row predicted hazard vs the row's event flag. All macro REGRESSORS are lagged (no lookahead); updated LTV and the rate incentive are loan-state variables indexed by the current quarter's HPI / market rate -- accepted collateral-indexation / option-moneyness exceptions documented in the engine/hazard.py TIMING CONVENTION. OOT (time 41-60, the stress + aftermath window) is scored strictly read-only -- fitted on train, no refit.

| Model | n (fit) | events | train AUC | OOT AUC | McFadden R2 |
|---|---|---|---|---|---|
| default | 418,418 | 11,354 | 0.7476 | 0.6609 | 0.0761 |
| prepay | 418,418 | 22,734 | 0.6839 | 0.5841 | 0.0503 |

Seasoning peak: fitted 12q vs empirical 10q (tolerance 8q; plausible window (4, 18)).

Double trigger: beta(centered ltv10 x centered uer_lag1) = -0.00597 (p = 3.75e-02, significant at 5%; identical to the uncentered x*y coefficient -- centering only reparametrises the main effects). Negative: the LTV slope flattens slightly at high unemployment -- in-sample the two triggers partially substitute (the main effects and momentum term already carry the joint stress response, and the worst-LTV loans default early in the stress window). Reported either way, per spec. Marginal LTV effect per 10pp: +0.2029 at mean UER (5.6%); +0.1766 at UER 10%.

Unemployment shock: A 1pp labour-market shock moves the unemployment level and its 4-quarter change one-for-one, so its hazard effect at mean LTV is beta(uer_lag1) + beta(uer_chg4_lag1) = -0.3668 + +0.6135 = +0.2467 (hazard ratio 1.280 per pp) -- PD RISES in unemployment. The negative level coefficient in isolation is the level-vs-momentum decomposition under 0.94 collinearity, not an economic sign.

All economic-sign sanity checks passed (FICO down, LTV up, unemployment shock up for default; incentive up for prepayment).