# Hazard-ratio tables -- discrete-time cloglog hazards

Loan-quarter panel, training split only (time <= 40; lag warm-up rows dropped). cloglog link = grouped-duration Cox, so exp(coef) is a hazard ratio. Baseline age effect: natural cubic spline cr(loan_age, df=5) -- basis coefficients omitted here (not individually interpretable); the fitted curve is exhibit age_baseline.png. The LTV x unemployment interaction components are centered at training means, so the LTV and UER main effects read as marginal effects at the partner's training mean; updated LTV is winsorised at 300% (engine/hazard.py docstring).

## Default hazard (y = default_event)

n = 418,418 loan-quarters, events = 11,354, McFadden pseudo-R2 = 0.0761

| Covariate | family | HR = exp(coef) | 95% CI | p |
|---|---|---|---|---|
| Intercept | baseline | 0.2658 | [0.1534, 0.4608] | 2.35e-06 |
| FICO at orig. (per 100 pts) | borrower | 0.6314 | [0.6130, 0.6505] | <1e-16 |
| Updated LTV (per 10pp, at mean UER) | collateral | 1.2250 | [1.2100, 1.2402] | <1e-16 |
| Rate incentive (pp) | incentive | 1.1424 | [1.1317, 1.1532] | <1e-16 |
| Investor loan | borrower | 1.2091 | [1.1425, 1.2796] | 5.05e-11 |
| Condo | borrower | 1.0649 | [0.9793, 1.1580] | 1.41e-01 |
| Planned urban dev. | borrower | 1.0852 | [1.0129, 1.1626] | 2.01e-02 |
| Single family | borrower | 0.9909 | [0.9433, 1.0408] | 7.15e-01 |
| Unemployment level (lag 1) | macro | 0.6930 | [0.6544, 0.7338] | <1e-16 |
| Unemployment 4q change (lag 1) | macro | 1.8468 | [1.6989, 2.0077] | <1e-16 |
| HPI growth (lag 1) | macro | 0.0318 | [0.0148, 0.0683] | <1e-16 |
| GDP growth (lag 1) | macro | 1.0895 | [1.0645, 1.1151] | 4.47e-13 |
| DOUBLE TRIGGER: LTV(10pp) x UER (centered) | collateral | 0.9940 | [0.9885, 0.9997] | 3.75e-02 |

**Family stories**

- **baseline** -- Seasoning: hazard climbs over the first ~2-3 years on book, then burns out (spline coefficients are basis weights, not individually interpretable -- see age_baseline.png).
- **borrower** -- Borrower quality: cleaner credit at origination defaults less; investors walk away from underwater rentals faster than owner-occupiers.
- **collateral** -- Collateral / double trigger: negative equity is the ability-to-sell trigger; its bite varies with the labour market via the LTV x unemployment interaction.
- **macro** -- Macro (all lagged, no lookahead): a labour-market shock moves level AND 4q momentum together and raises default risk (their coefficient SUM is the shock effect; the level coefficient alone, conditional on momentum, is a decomposition artifact -- the two correlate at 0.94 in-sample). Falling house prices raise default risk (HPI-growth HR is per full log-unit -- read exp(coef/100) per 1% quarterly growth). Satellites will scenario-condition these at a later rung.
- **incentive** -- Rate incentive: note rate above market -> refinancing pays; the star prepayment driver, and for default it proxies a high contractual debt-service burden.

## Prepayment hazard (y = payoff_event)

n = 418,418 loan-quarters, events = 22,734, McFadden pseudo-R2 = 0.0503

| Covariate | family | HR = exp(coef) | 95% CI | p |
|---|---|---|---|---|
| Intercept | baseline | 0.1336 | [0.1027, 0.1737] | <1e-16 |
| FICO at orig. (per 100 pts) | borrower | 0.9191 | [0.9003, 0.9383] | 1.37e-15 |
| Updated LTV (per 10pp, at mean UER) | collateral | 0.8776 | [0.8686, 0.8867] | <1e-16 |
| Rate incentive (pp) | incentive | 1.0846 | [1.0765, 1.0927] | <1e-16 |
| Investor loan | borrower | 0.7386 | [0.7068, 0.7719] | <1e-16 |
| Condo | borrower | 1.0788 | [1.0162, 1.1453] | 1.29e-02 |
| Planned urban dev. | borrower | 0.9928 | [0.9444, 1.0436] | 7.76e-01 |
| Single family | borrower | 1.0243 | [0.9900, 1.0598] | 1.67e-01 |
| Unemployment level (lag 1) | macro | 1.0678 | [1.0237, 1.1139] | 2.30e-03 |
| Unemployment 4q change (lag 1) | macro | 0.7275 | [0.6835, 0.7744] | <1e-16 |
| HPI growth (lag 1) | macro | 1417.6161 | [664.3238, 3025.0842] | <1e-16 |
| GDP growth (lag 1) | macro | 0.9481 | [0.9267, 0.9699] | 4.26e-06 |
| DOUBLE TRIGGER: LTV(10pp) x UER (centered) | collateral | 0.9615 | [0.9566, 0.9664] | <1e-16 |

**Family stories**

- **baseline** -- Seasoning: refinancing needs time to become worthwhile (points/fees amortise), so the prepay hazard also humps with age.
- **borrower** -- Borrower quality: investors prepay LESS (buy-and-hold rentals, harder underwriting on refis); higher FICO here mildly lowers prepayment conditional on the incentive.
- **collateral** -- Collateral gates refinancing: underwater borrowers cannot remortgage, so prepayment FALLS in updated LTV -- and falls fastest when unemployment is high (negative interaction).
- **macro** -- Macro: a hot housing market (HPI growth; HR is per full log-unit -- read exp(coef/100) per 1% growth) fuels turnover and cash-out refis; deteriorating labour momentum freezes the refi market.
- **incentive** -- Rate incentive: note rate above market -> refinancing pays; the star prepayment driver, positive as required.

## Double-trigger reading (default model)

beta(centered ltv10 x centered uer_lag1) = -0.00597 (p = 3.75e-02, significant at 5%; identical to the uncentered x*y coefficient -- centering only reparametrises the main effects). Negative: the LTV slope flattens slightly at high unemployment -- in-sample the two triggers partially substitute (the main effects and momentum term already carry the joint stress response, and the worst-LTV loans default early in the stress window). Reported either way, per spec. Marginal LTV effect per 10pp: +0.2029 at mean UER (5.6%); +0.1766 at UER 10%.

## Unemployment-shock reading (default model)

A 1pp labour-market shock moves the unemployment level and its 4-quarter change one-for-one, so its hazard effect at mean LTV is beta(uer_lag1) + beta(uer_chg4_lag1) = -0.3668 + +0.6135 = +0.2467 (hazard ratio 1.280 per pp) -- PD RISES in unemployment. The negative level coefficient in isolation is the level-vs-momentum decomposition under 0.94 collinearity, not an economic sign.
