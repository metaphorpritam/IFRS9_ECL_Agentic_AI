# ifrs9_credit_risk_notes.md

# IFRS 9 Credit Risk Modelling

> **Summary.** - The IFRS 9 standard: origins, scope, classification
> 
> - The impairment model: staging, default, SICR
> 
> - ECL mechanics: formula, term structure, worked example
> 
> - IFRS 9 vs Basel IRB vs CECL
> 
> - Data foundations: public datasets, macro series, scenarios
> 
> - PD modelling: scorecards, survival analysis, transition matrices
> 
> - Corporate & low-default PD: Merton, shadow ratings, Pluto–Tasche
> 
> - PIT vs TTC: the Vasicek one-factor framework
> 
> - Forward-looking scenarios: satellite models, weighting, overlays
> 
> - LGD modelling
> 
> - Realised losses: net credit loss, the 90-DPD trigger, discounting
> 
> - EAD modelling and behavioural life
> 
> - Validation, backtesting and staging effectiveness
> 
> - Governance, disclosure, capital interaction, hot topics
> 
> - Learning path, tooling, interview drill


## 1   The IFRS 9 Standard: Origins, Scope, Classification {#s1}

IFRS 9 *Financial Instruments* (IASB) replaced IAS 39 with effect from annual periods beginning on or after **1 January 2018**. The decisive reform is impairment: IAS 39's *incurred-loss* model recognised credit losses only after a loss event had occurred — judged "too little, too late" after 2008, and procyclical because losses arrived in a cliff at the worst point of the cycle. IFRS 9 replaces it with a forward-looking **expected credit loss (ECL)** model that provisions from initial recognition, before any default. The standard has three pillars: (i) classification & measurement, (ii) impairment, (iii) hedge accounting (with an optional IAS 39 carve-out retained for macro fair-value hedging).


### 1.1 Scope of the impairment model

ECL applies to: financial assets at **amortised cost** and debt instruments at **FVOCI**; **lease receivables** (IFRS 16); **contract assets** (IFRS 15); and **loan commitments** and **financial guarantee contracts** not measured at FVTPL. Equity instruments and anything at FVTPL are outside ECL scope (fair-value movements already absorb credit deterioration).


### 1.2 Classification & measurement: two tests

> **Definition.** **Business model test.** How the asset is managed: *hold to collect* contractual cash flows → amortised cost; *hold to collect and sell* → FVOCI; anything else (trading, fair-value management) → FVTPL. Unlike IAS 39's held-to-maturity rules there is no "tainting": occasional sales, e.g. on credit deterioration, do not break a hold-to-collect model.

> **Definition.** **SPPI test.** Contractual cash flows must be *solely payments of principal and interest*, where interest compensates only for time value of money, credit risk, liquidity, other basic lending costs and a profit margin — a "basic lending arrangement". Leverage (e.g. 2× benchmark), equity or commodity linkage, or non-genuine prepayment features fail SPPI → mandatory FVTPL. For financial *assets*, embedded derivatives are not separated; the whole instrument is assessed.

| Business model \ SPPI | Passes SPPI | Fails SPPI |
| --- | --- | --- |
| Hold to collect | **Amortised cost** | FVTPL |
| Hold to collect & sell | **FVOCI** (debt, with recycling) | FVTPL |
| Other (e.g. trading) | FVTPL | FVTPL |

Two elections complete the picture: non-trading **equity** may be irrevocably designated FVOCI *without* recycling; and the **fair-value option** may be used to remove an accounting mismatch. For FVOCI debt, interest (EIR), impairment and FX go to P&L; the residual fair-value change goes to OCI and recycles on derecognition — so *ECL measurement is identical for amortised-cost and FVOCI debt*; only presentation differs (FVOCI carries the asset at fair value, with the loss allowance recognised in OCI rather than netted off the carrying amount).


### 1.3 Two special regimes

**Simplified approach.** For trade receivables, contract assets and lease receivables, lifetime ECL is recognised at all times — no SICR tracking. It is mandatory for trade receivables/contract assets without a significant financing component, an accounting-policy choice for the rest. Implemented in practice as a **provision matrix**: historical loss rates by ageing bucket, adjusted for forward-looking information. Not available for ordinary loans.

**POCI** (purchased or originated credit-impaired) assets are credit-impaired at initial recognition. They never sit in Stages 1–3: the entity uses a **credit-adjusted EIR** (which builds initial lifetime ECL into the yield) and subsequently recognises only the *cumulative change* in lifetime ECL since initial recognition — which can be a gain.


## 2   The Impairment Model: Staging, Default, SICR {#s2}

![Fig. 1 — The general (three-stage) model: measurement horizon and interest-recognition basis by stage, with transfer triggers and backstops.](img/fig01.png)

*Fig. 1 — The general (three-stage) model: measurement horizon and interest-recognition basis by stage, with transfer triggers and backstops.*

**Stage 1** (no significant increase in credit risk since origination): **12-month ECL** — the portion of lifetime ECL arising from default events *possible within 12 months*, *not* a 12-month-truncated loss and not the loss only on loans certain to default. **Stage 2** (SICR, not credit-impaired): **lifetime ECL**, interest still on the gross carrying amount. **Stage 3** (credit-impaired/defaulted): lifetime ECL and interest unwound on the **net** carrying amount (gross − allowance).


### 2.1 Definition of default

> **Definition.** **Default (best practice = CRR Art. 178 / EBA/GL/2016/07 alignment).** An obligor is in default when either (i) it is **more than 90 days past due** on a material credit obligation, or (ii) **unlikeliness to pay (UTP)** indicators apply: distressed restructuring with diminished obligation (>1% NPV loss), bankruptcy, sale of the obligation at a material credit-related loss, non-accrual, specific credit-risk adjustment. Materiality is a *dual* threshold — absolute (≤ €100 retail, ≤ €500 non-retail) and relative (1% of on-balance exposure, cap 2.5%). Return from default requires a **probation** period: at least 3 months without UTP, at least 1 year after distressed restructuring.

Aligning the IFRS 9 default definition with the regulatory one keeps PD/LGD reference data consistent across accounting, capital and risk — a BCBS d350 expectation — and is assumed throughout these notes.


### 2.2 Significant increase in credit risk (SICR)

SICR is a *relative deterioration* test: compare the **lifetime PD over the remaining life at the reporting date** with the lifetime PD **expected for that same period at initial recognition**. It is not an absolute credit-quality test — a loan originated risky and still equally risky has not suffered SICR. Typical implementations combine:

- **Quantitative:** a relative threshold on (annualised) lifetime PD — a doubling (200% relative increase) is the most common convention, used in the EBA 2018 stress-test methodology and echoed in ECB backstop proposals (threefold 12-month PD increase, applied only above PD 0.3%, plus an absolute 12-month PD > 20% trigger) — usually paired with an **absolute** add-on so that tiny PDs do not flip stages on noise;
- **Qualitative:** watchlist, forbearance flags, internal downgrade beyond a set number of notches;
- **Backstop:** rebuttable presumption of SICR at **30 days past due**;
- **Low-credit-risk exemption:** investment-grade-equivalent exposures may be left in Stage 1 without full SICR assessment (widely used for bond books);
- **Cure:** transfer back to Stage 1 requires the SICR to have reversed, usually with a probation period to prevent oscillation.

> **Pitfall.** **Two traps.** (1) Stage 2 is *not* default and must not be reported as such under the CRR. (2) Staging is the single most consequential modelling choice in IFRS 9: crossing into Stage 2 switches the horizon from 12-month to lifetime, often multiplying the allowance several-fold with *no change in the loss expectation, only in the measurement window*. Thresholds should be risk-grade-sensitive (a 0.05%→0.12% move matters less than 5%→12% in absolute loss terms, yet both are "more than doubling"), and Stage 2 population size must balance early recognition against provision volatility.


## 3   ECL Mechanics: Formula, Term Structure, Worked Example {#s3}

> **Theorem.** **The ECL decomposition.** With discrete periods $t=1,\dots,T$ (remaining life), conditional default probability (hazard) $\lambda_t$, survival $S(t)=\prod_{k\le t}(1-\lambda_k)$, and discounting at the original **effective interest rate**: $$\mathrm{ECL}=\sum_{t=1}^{T}\underbrace{S(t-1)\,\lambda_t}_{\text{marginal PD}_t}\cdot LGD_t\cdot EAD_t\cdot (1+EIR)^{-t},$$ with **12-month ECL** truncating the sum at $t=12$ months. Distinguish: *conditional/forward PD* $\lambda_t$ (default in $t$ given survival to $t{-}1$); *marginal PD* $S(t-1)\lambda_t$ (unconditional default in period $t$); *cumulative PD* $F(t)=1-S(t)$. The PD/LGD/EAD decomposition is the dominant practice but IFRS 9 is principles-based: loss-rate, vintage and discounted-cash-flow approaches are equally permissible if unbiased, probability-weighted and forward-looking.

![Fig. 2 — A lifetime PD term structure. Left: conditional hazard with the typical retail "seasoning hump", and the marginal PD $S(t-1)\lambda_t$ which falls below it as survival depletes. Right: the implied survival and cumulative PD curves.](img/fig02.png)

*Fig. 2 — A lifetime PD term structure. Left: conditional hazard with the typical retail "seasoning hump", and the marginal PD $S(t-1)\lambda_t$ which falls below it as survival depletes. Right: the implied survival and cumulative PD curves.*

> **Worked Example.** | $t$ | $\lambda_t$ | $S(t{-}1)$ | marginal PD | $EAD_t$ (€) | $DF_t$ | $\mathrm{ECL}_t$ (€) |
> | --- | --- | --- | --- | --- | --- | --- |
> | 1 | 1.50% | 1.00000 | 0.01500 | 1,000,000 | 0.9434 | 4,952.83 |
> | 2 | 2.00% | 0.98500 | 0.01970 | 800,000 | 0.8900 | 4,909.22 |
> | 3 | 2.20% | 0.96530 | 0.02124 | 600,000 | 0.8396 | 3,744.44 |
> | 4 | 2.00% | 0.94406 | 0.01888 | 400,000 | 0.7921 | 2,093.80 |
> | 5 | 1.80% | 0.92518 | 0.01665 | 200,000 | 0.7473 | 871.10 |

> **Note.** **Intuition.** Each term of the sum is "probability the loan survives this far and then defaults × what is lost × what is at stake × time value". Everything downstream in these notes is the statistics of estimating those three curves — $\lambda_t$ (→ PD modelling), $LGD_t$, $EAD_t$ — and of conditioning them on forward-looking macro scenarios.


## 4   IFRS 9 vs Basel IRB vs CECL {#s4}

The most common interview discriminator and the most common implementation error: re-using Basel parameters in the ECL engine without removing their built-in conservatism. The philosophies differ on purpose:

| Dimension | IFRS 9 ECL | Basel IRB | US CECL (ASC 326) |
| --- | --- | --- | --- |
| Objective | accounting provision (expected loss) | capital for *unexpected* loss | accounting provision |
| PD horizon | 12-month (Stage 1) / lifetime (2–3) | always 12-month | lifetime for all assets, day 1 |
| PD philosophy | **point-in-time**, forward-looking | often through-the-cycle / hybrid | PIT + reversion to history beyond forecast horizon |
| LGD | unbiased, PIT, EIR-discounted | **downturn**, conservative, floors | unbiased lifetime |
| EAD | unbiased; behavioural life for revolvers (¶5.5.20) | downturn CCFs, regulatory floors | contractual life incl. prepayment; unconditionally cancellable undrawn excluded |
| Conservatism | neutral, probability-weighted | prudential margins + floors | neutral |
| Staging | 3 stages via SICR | — | none (single lifetime bucket) |

Subtleties worth quoting in review meetings: Basel workout LGD accumulates cash flows over the *full workout period* against exposure at default, while IFRS 9 references the exposure at the start of the reference period — one reason Basel LGD generally exceeds IFRS 9 LGD even before downturn add-ons. In downturns the ordering can flip for PD: PIT IFRS 9 PDs spike above TTC regulatory PDs. Empirically (Behn & Couaillier, ECB WP 2841, 2023), IFRS 9 provisions are higher before default and more shock-responsive than under IAS 39 — yet most provisioning still occurs at default, so the standard softened but did not remove cliff effects.

> **Pitfall.** **Pitfall.** "We already have IRB models, just plug them in" fails on four axes at once: horizon (12m→lifetime term structure needed), philosophy (TTC→PIT transformation needed, §8), bias (downturn LGD/EAD → unbiased), and floors (must be stripped). Each adjustment must be documented and validated separately.


## 5   Data Foundations: Public Datasets, Macro Series, Scenarios {#s5}

Everything in §§6–12 can be practised end-to-end on public data. The architecture is always the same: a loan-month panel, macro series merged on time (and geography), and scenario paths entering through the conditioning layer.

![Fig. 3 — The practice pipeline: loan-level panels + macro series → loan-month panel → PD/LGD/EAD models → Vasicek/Z conditioning fed by scenario paths → probability-weighted ECL and staging.](img/fig03.png)

*Fig. 3 — The practice pipeline: loan-level panels + macro series → loan-month panel → PD/LGD/EAD models → Vasicek/Z conditioning fed by scenario paths → probability-weighted ECL and staging.*


### 5.1 Ready-made panels (macros already merged) — start here

| Dataset | Contents | Best for | Access |
| --- | --- | --- | --- |
| **Credit Risk Analytics `mortgage`** (Baesens–Rösch–Scheule) | Panel: 50,000 US RMBS mortgage borrowers × 60 periods; origination + performance; `gdp_time`, `uer_time`, `hpi_time` already merged; realistic left truncation & right censoring | first discrete-time hazard PD with macro covariates; Vasicek Z fitting | creditriskanalytics.net (free; also `lgd.csv`, `ratings.csv`) |
| **Deep Credit Risk data** (Rösch–Scheule) | Same 50k×60q US mortgage universe, expanded: **15,000 defaults with workout losses**, payoff events, exposures | PD + workout LGD + EAD + competing-risk prepayment from one panel | deepcreditrisk.com (free; `dcr.py`/`dcr.R` helpers) |


### 5.2 Industry-scale loan-level data (build your own merge)

| Dataset | Contents | Notes |
| --- | --- | --- |
| **Freddie Mac SFLLD** | ~55m mortgages originated 1999–2025Q3; quarterly origination files + monthly performance to disposition; **actual-loss fields**: net sale proceeds, MI & non-MI recoveries, expenses, deferred UPB | free registration on Clarity Data Intelligence; start with the ~50k-loan sample files; quarterly refresh; the loss fields enable genuine workout-LGD modelling |
| **Fannie Mae SFLP** | Quarterly-acquisition CSVs; single-file 108-field layout mirroring CRT disclosures; static origination + dynamic monthly performance through liquidation/REO | free registration on Data Dynamics; HARP companion dataset with mapping file |
| **Retail scorecard sets** | Lending Club (Kaggle mirrors, 2007–2020, has issue date + state → vintage/macro merges), Home Credit Default Risk, Give Me Some Credit, UCI Taiwan credit cards | application/behavioural scorecards (§6.1); LC recovery fields allow rough unsecured LGD |
| **Corporate routes** | S&P / Moody's annual default & rating-transition studies (public aggregate matrices); listed-firm equity + EDGAR financials for Merton replication | public loan-level corporate data is scarce — use aggregate matrices for generator/Z work (§§6.3, 8) and Pluto–Tasche on sparse grades (§7.3) |


### 5.3 Macro series and scenario paths

- **FRED / ALFRED** (St. Louis Fed): national GDP, unemployment, rates, CPI; `fredapi` / `pandas-datareader` (Python), `fredr` (R). ALFRED's *vintage* series avoid look-ahead bias when reconstructing "information available at the reporting date".
- **BLS LAUS**: state-level unemployment, monthly — the single most powerful macro driver in the landmark 120-million-loan deep-learning mortgage study (Sirignano–Sadhwani–Giesecke).
- **FHFA HPI** (state/MSA, quarterly, free CSV) and Case-Shiller (via FRED): collateral indexation, current LTV, mortgage LGD. **Freddie Mac PMMS**: mortgage rates for prepayment incentive.
- **Fed DFAST supervisory scenarios**: baseline + severely adverse, 28 variables (domestic + international blocs), quarterly paths, published as CSVs each February (2026 set released 4 Feb 2026) — drop-in downside paths for a scenario-ECL exercise.
- **EBA/ECB EU-wide stress-test scenarios**: baseline + adverse at country granularity; the 2025 exercise spans 2025–27 with a −6.3% cumulative GDP adverse path and sectoral shock decomposition. Bank of England publishes comparable desk-based scenario paths.
- **Baseline sources** for genuine (non-stress) central paths: IMF WEO, consensus forecasts. **India:** RBI's DBIE database (GDP, CPI, policy rates, sectoral GNPA) supports an Ind AS 109-framed replica of the same pipeline.

> **Summary.** **Merge recipe.** Build the loan-month panel → join national macros on calendar quarter and state-level UER/HPI on property state → **lag macros 1–2 quarters** (publication delay + transmission) → store **macro-at-origination** columns (needed for the SICR "vs initial recognition" comparison) → HPI(now)/HPI(orig) × original LTV ≈ updated collateral cover for LGD.


### 5.4 Data-preparation essentials

- **Default flag** construction per §2.1, reconciled across source systems; consistent **performance/outcome windows** (12-month windows for application PD; full histories for lifetime models).
- **Left truncation and right censoring** handled explicitly in the panel (loans alive at window start; loans maturing/refinancing before default) — mishandling these is the classic survival-model bug.
- **Segmentation** into homogeneous pools by product, collateral and risk drivers; **low-default portfolios** (sovereigns, banks, large corporates) flagged early for §7.3 treatment.
- **Recovery data** for LGD: post-default cash flows, direct/indirect costs, collateral realisations, time-to-resolution, and a policy for **incomplete workouts**.


### 5.5 A modelling-variable dictionary

The variables below are the recurring building blocks of a retail (mortgage) PD/LGD/EAD model, with representative field names from the Freddie Mac SFLLD layout (Fannie Mae's are analogous; exact names vary by dataset, so always reconcile against the file layout you actually hold). The "feeds" column shows where each family enters the ECL engine.

> **Note.** **The three you asked about.** **Macro** = the merged economic covariates (GDP, unemployment, HPI, rates) that condition point-in-time PD/LGD (§§8–9). **Unpaid balance** = *Current Actual UPB* (alongside *Original UPB*) — the live exposure that drives EAD and, via the indexed property value, current LTV. **Cash indicator** is almost always a *cash-out refinance* flag derived from *Loan Purpose* (purchase / cash-out refinance / no-cash-out refinance); cash-out refinances are a well-documented higher-risk segment, so the flag earns its place as a PD covariate.

| Family | Representative fields | Feeds |
| --- | --- | --- |
| **Identifiers & time** | loan sequence number, monthly reporting period, loan age, remaining months to maturity, first-payment & maturity dates | panel keys; baseline hazard $\alpha(t)$ |
| **Borrower & underwriting** (origination) | credit score (FICO), DTI, original LTV & combined OCLTV, number of borrowers, first-time-buyer flag, occupancy status, documentation type | PD scorecard (WOE-binned) |
| **Loan & product** | original UPB, note rate, loan term, product type (FRM/ARM), **loan purpose → cash-out indicator**, channel (retail/broker/correspondent), prepayment-penalty (PPM) flag, MI %, units, property type, super-conforming flag | PD, EAD, prepayment |
| **Geography** | property state, MSA, 3-digit ZIP | join key for state HPI/UER; PD & LGD |
| **Dynamic performance** (monthly) | **current actual UPB**, current delinquency status, current interest rate, current deferred UPB, modification & step-mod flags, repurchase flag, zero-balance code & date, DDLPI | EAD; default/cure flags; staging |
| **Collateral / dynamic risk** | current/estimated LTV (ELTV) = balance ÷ HPI-indexed value | PD & LGD (mortgages) |
| **Loss components** (post-default) | default UPB, delinquent accrued interest, expenses (legal, maintenance, taxes & insurance, misc.), net sale proceeds, MI & non-MI recoveries, actual loss | LGD / NCL (§11) |
| **Macro** (merged) | real GDP growth, state unemployment (LAUS), HPI & HPI-ratio, mortgage rate (PMMS), policy rate, credit spread | PIT conditioning (§§8–9) |

**Feature-engineering reminders:** bin and WOE-transform the borrower/underwriting fields for a scorecard (§6.1); lag macros 1–2 quarters and *also* keep their origination snapshots for the SICR comparison (§5.3); build current LTV from the HPI ratio rather than trusting a stale origination LTV; and handle modification/forbearance and repurchase flags carefully — they reshape both the cash flows and the default definition itself.


## 6   PD Modelling: Scorecards, Survival Analysis, Transition Matrices {#s6}


### 6.1 Retail scorecards: WOE, IV, logistic regression

> **Definition.** **Weight of evidence & information value.** For bin $i$ of a characteristic, with $\mathrm{Dist}^G_i=g_i/G$ and $\mathrm{Dist}^B_i=b_i/B$ the shares of goods and bads falling in the bin: $$WOE_i=\ln\frac{\mathrm{Dist}^G_i}{\mathrm{Dist}^B_i},\qquad IV=\sum_i\left(\mathrm{Dist}^G_i-\mathrm{Dist}^B_i\right)WOE_i .$$ Siddiqi convention: $IV<0.02$ useless; $0.02$–$0.1$ weak; $0.1$–$0.3$ medium; $0.3$–$0.5$ strong; $>0.5$ suspicious (check leakage). WOE coarse-classing linearises the logit, absorbs non-linearity and missing values, and makes coefficients comparable — but it is a *binary-logit* device, not a general feature selector for tree ensembles.

> **Worked Example.** | LTV bin | goods | bads | bad rate | $\mathrm{Dist}^G$ | $\mathrm{Dist}^B$ | WOE | IV contrib. |
> | --- | --- | --- | --- | --- | --- | --- | --- |
> | ≤60% | 2,850 | 60 | 2.06% | 0.30 | 0.12 | +0.9163 | 0.1649 |
> | 60–80% | 3,800 | 150 | 3.80% | 0.40 | 0.30 | +0.2877 | 0.0288 |
> | 80–90% | 1,900 | 140 | 6.86% | 0.20 | 0.28 | −0.3365 | 0.0269 |
> | >90% | 950 | 150 | 13.64% | 0.10 | 0.30 | −1.0986 | 0.2197 |

The scorecard is then a logistic regression on WOE-transformed inputs; **discrimination** is summarised by $\mathrm{Gini}=2\,\mathrm{AUC}-1$ and the KS statistic (maximum gap between good/bad cumulative score distributions); **calibration** maps score bands to PDs anchored to a long-run *central tendency* via the linear score-to-log-odds relationship. Application scorecards use origination data; behavioural scorecards add account performance and dominate after ~6–12 months on book. Gradient boosting typically lifts Gini by several points but faces SR 11-7-style explainability expectations — common compromise: champion logit, ML challenger, SHAP for both.


### 6.2 Lifetime PD via discrete-time survival analysis

> **Theorem.** **Discrete-time hazard model.** On a loan-month panel, define $\lambda(t\mid x_{it})=P(T_i=t\mid T_i\ge t,\,x_{it})$ and fit a binary GLM on at-risk rows with a logit or complementary-log-log link: $$\operatorname{cloglog}\;\lambda(t\mid x_{it})=\ln\!\big(-\ln(1-\lambda)\big)=\alpha(t)+x_{it}'\beta+\gamma' m_{t},$$ where $\alpha(t)$ is the baseline (months-on-book dummies or splines → the seasoning hump of Fig. 2), $x_{it}$ are loan/borrower covariates (possibly time-varying: updated LTV, delinquency state) and $m_t$ are macro drivers. The cloglog link is the exact grouped-duration analogue of the continuous-time Cox model. Then $S(t\mid x)=\prod_{k\le t}(1-\lambda_k)$ and the marginal-PD term structure feeds the ECL sum directly. Continuous-time alternatives: Cox PH, AFT; tree-based: random survival forests (challenger role).

- **Why survival, not stacked logits:** one coherent model produces the whole term structure, handles censoring/truncation properly, and accepts time-varying macro covariates — the natural entry point for scenario conditioning.
- **Competing risks:** prepayment and default compete; estimate cause-specific hazards (the Deep Credit Risk panel is built for exactly this).
- **Extrapolation** beyond observed maturities is a flagged model-risk area: small hazard errors compound over long horizons — document the tail assumption (level-off, decay to long-run rate).


### 6.3 Transition matrices (Markov chains)

For rating-driven (especially wholesale) books: estimate a 1-year matrix $P$ by the **cohort** method or, better for sparse data, the **duration/generator** method — estimate intensity matrix $Q$ ($q_{ij}$ = migration intensities, rows sum to 0) and set $P(t)=e^{Qt}$, which yields PDs for any horizon and strictly positive default probabilities even for grades with no observed defaults. Multi-period PDs under time-homogeneity come from $P^n$; the cumulative PD of grade $g$ is the $(g,D)$ entry. Caveats: time-homogeneity and Markovianity hold only over limited horizons (test with likelihood-ratio tests; beware rating momentum/drift), and a valid generator may not exist for an empirically estimated annual matrix (the embedding problem) — regularisation is standard.

![Fig. 4 — Illustrative S&P-style 1-year transition matrix: diagonal-dominant, monotone default column, absorbing D state. Conditioning these matrices on the cycle (§8) produces PIT migration and PD term structures.](img/fig04.png)

*Fig. 4 — Illustrative S&P-style 1-year transition matrix: diagonal-dominant, monotone default column, absorbing D state. Conditioning these matrices on the cycle (§8) produces PIT migration and PD term structures.*

**Portfolio-level alternatives** for thin data: vintage (cohort) analysis tracking cumulative default curves by origination quarter, and roll-rate models chaining delinquency-bucket transition rates — both still standard for cards and as challenger benchmarks.


## 7   Corporate & Low-Default PD: Merton, Shadow Ratings, Pluto–Tasche {#s7}


### 7.1 Rating-based and shadow-rating approaches

Wholesale PD usually flows through an internal **rating**: financial-ratio + qualitative score → grade → long-run default rate per grade (the masterscale). Where internal defaults are too few to fit a default model, a **shadow-rating** model regresses external agency ratings on financials to replicate the agencies' ranking, then maps grades to agency long-run default rates. Hybrids blend a market-implied (Merton) signal with a financial-statement score for the non-listed book.


### 7.2 The Merton structural model

> **Theorem.** **Merton (1974).** Equity is a call option on firm assets $V$ with strike = face value of debt $D$ at horizon $T$. With asset drift $\mu$ and volatility $\sigma_A$, default occurs if $V_T<D$: $$DD=\frac{\ln(V/D)+(\mu-\tfrac12\sigma_A^2)T}{\sigma_A\sqrt{T}},\qquad PD=\Phi(-DD),$$ ($\Phi(-d_2)$ with $\mu\to r$ gives the risk-neutral PD). $V$ and $\sigma_A$ are unobservable: back them out from equity value/volatility via the simultaneous equations $E=V\Phi(d_1)-De^{-rT}\Phi(d_2)$ and $\sigma_E=(V/E)\Phi(d_1)\sigma_A$ (Crosbie–Bohn / KMV iteration). Moody's KMV-EDF replaces $\Phi$ with an empirical DD→default-frequency mapping, with the "default point" ≈ short-term debt + ½ long-term debt.

> **Worked Example.** **Worked example — distance to default.** $V$ = €120m, $D$ = €100m, $\sigma_A=20\%$, $\mu=8\%$, $T=1$y (`compute_pd.py`): $$DD=\frac{\ln(1.2)+(0.08-0.02)\cdot 1}{0.20}=\frac{0.18232+0.06}{0.20}=\mathbf{1.2116},\qquad PD=\Phi(-1.2116)=\mathbf{11.28\%}.$$ A leveraged, volatile firm sits close to its default barrier — structural PDs are inherently point-in-time because equity prices move with the cycle.


### 7.3 Low-default portfolios: Pluto–Tasche and Bayesian estimation

> **Theorem.** **Pluto–Tasche "most prudent estimation".** With grades ordered best→worst and few or zero defaults, estimate each grade's PD as the **upper confidence bound** at level $\gamma$ of the binomial likelihood, imposing monotonicity $p_A\le p_B\le\dots$ For grade $g$, pool all obligors in grade $g$ *and worse* ($n_{\ge g}$, defaults $d_{\ge g}$); with zero defaults the bound solves $(1-p)^{n_{\ge g}}=1-\gamma$: $$\hat p_g=1-(1-\gamma)^{1/n_{\ge g}}.$$ Extensions add cross-sectional asset correlation (one-factor) and multi-period autocorrelation; Bayesian alternatives (Jeffreys/expert priors, Tasche 2013) avoid the arbitrary choice of $\gamma$.

> **Worked Example.** **Worked example — two grades, zero defaults, $\gamma=90\%$.** Grade A: 80 obligors; grade B: 40. Then $\hat p_A=1-0.1^{1/120}=\mathbf{1.90\%}$ (pooling all 120) and $\hat p_B=1-0.1^{1/40}=\mathbf{5.59\%}$ — strictly positive, monotone PDs from a portfolio that has never defaulted.

> **Pitfall.** **Caveats.** Pluto–Tasche addresses PD only (not LGD/EAD), is sensitive to the confidence level, and is criticised as over-conservative — which conflicts with IFRS 9's *unbiased* requirement. In ECL engines it is better used as a calibration floor/benchmark with the conservatism explicitly quantified, or replaced by a Bayesian posterior mean.


## 8   PIT vs TTC: The Vasicek One-Factor Framework {#s8}

> **Definition.** **Philosophies.** A **TTC** PD is the cycle-neutral long-run average for the grade; a **PIT** PD reflects current and forecast conditions. IFRS 9 requires PIT, forward-looking parameters; Basel IRB systems are typically TTC or hybrid — hence a transformation layer is needed when leveraging IRB models.

> **Theorem.** **ASRF / Vasicek conditioning.** Standardised asset return $X_i=\sqrt{\rho}\,Z+\sqrt{1-\rho}\,\varepsilon_i$ with systematic factor $Z\sim N(0,1)$, idiosyncratic $\varepsilon_i\sim N(0,1)$, asset correlation $\rho$. Default iff $X_i<\Phi^{-1}(PD_{TTC})$. Conditioning on $Z$: $$PD_{PIT}(Z)=\Phi\!\left(\frac{\Phi^{-1}(PD_{TTC})-\sqrt{\rho}\,Z}{\sqrt{1-\rho}}\right).$$ Good times ($Z>0$) compress PDs; recessions ($Z<0$) inflate them, more than proportionally. The same kernel underlies Basel's capital formula (with $Z$ at the 99.9th percentile) and converts TTC migration matrices to PIT by shifting every transition threshold by $\sqrt{\rho}\,Z$.

> **Worked Example.** | $Z$ (cycle) | +2.0 | +1.0 | 0.0 | −1.0 | −2.0 | −2.5 |
> | --- | --- | --- | --- | --- | --- | --- |
> | $PD_{PIT}$ | 0.17% | 0.53% | 1.43% | 3.44% | 7.34% | 10.27% |

![Fig. 5 — $PD_{PIT}(Z)$ for three TTC anchors at $\rho=0.12$. Marked points are the worked-example values on the 2% curve; the shaded band marks downturn states.](img/fig05.png)

*Fig. 5 — $PD_{PIT}(Z)$ for three TTC anchors at $\rho=0.12$. Marked points are the worked-example values on the 2% curve; the shaded band marks downturn states.*

**Estimating $Z$ and $\rho$ (the Z-shift / Belkin approach):** from a history of grade-level default rates, invert the Vasicek formula each period to recover $Z_t$; calibrate $\rho$ so that $\operatorname{Var}(Z_t)=1$; then regress $Z_t$ on macro variables (the satellite model of §9) so that scenario macro paths map to $Z$ paths and hence to scenario-conditional PIT PD term structures and migration matrices. Documented caveats (e.g. Basson & van Vuuren 2023): naïve TTC↔PIT round-trips can be inconsistent if $\rho$, the default definition, or the cycle index differ between legs — fix conventions once and test the round trip.


## 9   Forward-Looking Scenarios: Satellite Models, Weighting, Overlays {#s9}


### 9.1 Satellite (macro-link) models

IFRS 9 (¶5.5.17(c)) requires *reasonable and supportable* forward-looking information. The standard architecture regresses a credit index — grade default rates, the recovered $Z_t$, portfolio LGD — on macro drivers (GDP growth, unemployment, HPI, rates). Econometric hygiene for the time-series layer, in the order an interviewer expects it:

- **Stationarity:** ADF (null: unit root) and KPSS (null: stationarity) are complementary — run both; difference or detrend I(1) series, or model levels via cointegration. Seasonal unit roots (HEGY/DHF) where quarterly seasonality matters.
- **Cointegration & dynamics:** Johansen rank tests for multivariate systems; **ARDL bounds** (Pesaran–Shin–Smith 2001) when regressors are a mix of I(0)/I(1); the error-correction term must be negative and significant — its magnitude is the adjustment speed.
- **Specification:** lag selection by AIC/SBC; macro variables entered with 1–2 quarter lags; crisis dummies/structural-break tests (Chow, CUSUM) — a satellite fitted through 2008–09 and 2020 without break handling will misbehave in both directions.
- **Transformation:** model logit/probit of the default rate (or $Z_t$ directly) so fitted values stay in range.


### 9.2 Multiple probability-weighted scenarios — why the base case is not enough

> **Theorem.** **Jensen's inequality applied to ECL.** ECL is a convex function of the macro state (Fig. 5/6): for convex $f$, $\mathbb{E}[f(X)]\ge f(\mathbb{E}[X])$. Hence the probability-weighted average of scenario ECLs *exceeds* the ECL of the probability-weighted (average) scenario — measuring on the single most-likely path systematically understates expected loss. This is the analytical reason IFRS 9 ¶5.5.17–18/B5.5.42 demands an unbiased, **probability-weighted** evaluation of a range of outcomes; typical practice is three to five named scenarios (base/up/down(s)), in-house or vendor (Moody's S1–S4, Oxford Economics).

> **Worked Example.** | Scenario | $g$ | weight | $Z$ | $PD_{PIT}$ | 1y ECL (€m) |
> | --- | --- | --- | --- | --- | --- |
> | Upside | +3.5% | 0.25 | +1.0 | 0.53% | 0.21 |
> | Base | +2.0% | 0.50 | 0.0 | 1.43% | 0.57 |
> | Downside | −2.5% | 0.25 | −3.0 | 13.97% | 5.59 |

![Fig. 6 — The Jensen gap: the chord average (probability-weighted ECL, ◆) lies above the curve at the mean scenario (■). The downside tail does the work.](img/fig06.png)

*Fig. 6 — The Jensen gap: the chord average (probability-weighted ECL, ◆) lies above the curve at the mean scenario (■). The downside tail does the work.*

**Probability-weighted staging:** SICR itself can be scenario-dependent — the IASB's illustrative two-step approach forms the probability-weighted lifetime PD first, then runs the SICR comparison against the origination benchmark, so an exposure is staged once, on the weighted view.


### 9.3 Post-model adjustments (overlays) — the current supervisory battleground

- **ECB (July 2024 review, 53 banks):** roughly a **quarter of performing-book loan-loss coverage is overlays**, with no downward trend; overlays applied at the *total-ECL level* (bypassing PD and staging) are explicitly discouraged as contrary to IFRS 9 principles; ~44% of banks lacked a clear allocation of tasks/governance for overlays; supervisors warn they can become an earnings-management tool — yet well-governed, methodology-based overlays remain the endorsed answer for *novel* risks the data cannot yet see.
- **PRA Dear CFO letters (2022–24):** challenge the *completeness* of PMAs (e.g. higher-rate affordability and refinance risk), push from broad portfolio-level overlays to targeted account-level adjustments, and flag prolonged reliance on aged, underperforming models.
- **EBA IFRS 9 monitoring:** overlays are now "an integral part of the ECL framework" needing tighter methodology and governance. Disclosure practice (NatWest, Lloyds, Barclays, HSBC) quantifies judgmental PMAs as a share of total ECL — useful benchmarks when sizing your own.

> **Note.** **Interview framing.** A good overlay answer has four parts: trigger (model blind spot, novel risk), quantification basis (sensitivity/benchmark, not a plug), allocation (to stages and segments, so staging still works), and exit criteria (what evidence retires or modelises it).


### 9.4 The forecast horizon, lifetime, and the gross-up factor {#s9-4}

Two horizon questions sit underneath every lifetime ECL — *how far does "lifetime" run*, and *how far can the macro scenarios actually be trusted* — and they have different answers.

> **Definition.** **What "lifetime" means.** IFRS 9 ¶5.5.19 caps the measurement horizon at the **maximum contractual period** (including extension options) over which the entity is exposed to credit risk — and *not* a longer period, even if a longer one matches business practice. So there is no universal "5-year" or "10-year" lifetime: it is the instrument's remaining contractual maturity — months for a personal loan's tail, ~5 years for an auto loan, 20–30 years for a mortgage. Two refinements: assets with an expected life under 12 months use that shorter period (B5.5.43); and the ¶5.5.20 revolver exception (§12) lets **behavioural life** exceed contractual life for cards and overdrafts. Lifetime is bounded by contract (or behaviour for revolvers), never by convenience.

**The reasonable-and-supportable (R&S) horizon is shorter.** IFRS 9 requires forward-looking information only so far as it is *reasonable and supportable*; macro scenarios are credible over a limited window — commonly two to three years, sometimes up to five — beyond which forecast errors compound and the conditioned PD term structure turns unstable. The standard response (explicit in CECL's ASC 326-20-30-9, and the dominant IFRS 9 practice) is to **condition point-in-time over the R&S window, then revert to the long-run / through-the-cycle (TTC) level** across a further "reversion" period, holding TTC out to maturity. The result is a PD term structure that is PIT-shaped early and TTC-flat in the tail (Fig. 7, left; mechanics in §3 and §8).

![Fig. 7 — Left: the conditional hazard is scenario-driven inside the R&S window, then reverts to the long-run TTC level. Right: the cumulative PD this implies, with the lifetime figure obtained by grossing up the reliable-horizon PD.](img/fig07.png)

*Fig. 7 — Left: the conditional hazard is scenario-driven inside the R&S window, then reverts to the long-run TTC level. Right: the cumulative PD this implies, with the lifetime figure obtained by grossing up the reliable-horizon PD.*

> **Definition.** **The gross-up factor.** When a model is trusted only to some horizon $H$ — a 12-month Basel PIT PD, or an ECL reliable to ~60 months — but lifetime is longer, the lifetime figure is recovered by a **gross-up**: $$GU(H\rightarrow\text{life})=\frac{\text{cumulative PD to maturity}}{\text{cumulative PD to }H},\qquad \mathrm{ECL}_{\text{life}}\approx GU\cdot \mathrm{ECL}_{H}.$$ The factor is built two ways: *analytically*, by extending the marginal-PD term structure at the TTC hazard to maturity (the curve in Fig. 7) and taking the ratio; or *empirically*, calibrating $GU$ from completed full-life vintages. Banks holding only 12-month PIT models commonly reach lifetime ECL by exactly this scaling.

> **Worked Example.** | Horizon | Cumulative PD | Gross-up to lifetime | ECL* (EAD 100, LGD 30%) |
> | --- | --- | --- | --- |
> | 12 months | 2.50% | ×4.85 | 0.75 |
> | 36 months (R&S) | 6.46% | ×1.88 | 1.94 |
> | 60 months (reliable) | 9.43% | ×1.29 | 2.83 |
> | Lifetime (84m) | 12.12% | ×1.00 | 3.64 |

> **Pitfall.** **Two cautions.** (1) A single gross-up factor assumes default timing beyond $H$ resembles the calibration vintages — it breaks for back-loaded products (balloon, interest-only) or where the tail is a different regime, so segment the factor and prefer an explicit TTC-extended term structure where the data allows. (2) The reversion speed and the R&S length are judgmental and audited; recent work on anchored / state-space stabilisation of lifetime PDs targets precisely the instability that long-horizon macro forecast error injects.


## 10   LGD Modelling {#s10}


### 10.1 Workout LGD: the measurement definition

> **Definition.** **Workout LGD.** Collect all post-default cash flows — recoveries $R_k$ (payments, collateral sale proceeds, guarantee/insurance claims) and direct workout costs $C_k$ — discount them **at the original EIR** to the default date, and set $$LGD=1-RR=1-\frac{\sum_k PV(R_k)-\sum_k PV(C_k)}{EAD_{\text{default}}}.$$ IFRS 9 LGD must be *unbiased and point-in-time* and discounted at the EIR — three deliberate contrasts with Basel IRB LGD, which is **downturn**-calibrated, carries margins of conservatism and floors, and conventionally accumulates over the full workout period. A fourth, subtler contrast: IFRS 9 references the exposure at the start of the reporting/reference period, not only at default. Net effect: Basel LGD ≥ IFRS 9 LGD almost everywhere, so IRB LGDs must be "de-conservatised" before reuse.

> **Worked Example.** **Worked example — workout LGD** (`compute_ecl.py`). $EAD$ = €100,000 at default, $EIR=7\%$. Recoveries: €30,000 at 12m, €35,000 at 24m, collateral sale €20,000 at 30m. Direct costs: €4,000 at 6m, €3,000 at 24m. $$PV(\text{rec})=\frac{30{,}000}{1.07}+\frac{35{,}000}{1.07^{2}}+\frac{20{,}000}{1.07^{2.5}}=75{,}495,\qquad PV(\text{cost})=6{,}487.$$ $RR=(75{,}495-6{,}487)/100{,}000=69.0\%$, so $LGD=\mathbf{31.0\%}$. Undiscounted, the same cash flows give $LGD=22\%$ — the discounting and cost treatment are not cosmetic.


### 10.2 The distributional reality and model families

![Fig. 8 — Realised LGD is bimodal and bounded on $(0,1)$: a cure spike near zero loss and a write-off hump at high loss. One Gaussian regression cannot describe this; two-stage models can.](img/fig08.png)

*Fig. 8 — Realised LGD is bimodal and bounded on $[0,1]$: a cure spike near zero loss and a write-off hump at high loss. One Gaussian regression cannot describe this; two-stage models can.*

- **Bounded-response regressions:** beta regression (Ferrari–Cribari-Neto) on $(0,1)$, Tobit for the point masses at 0/1, fractional logit (quasi-likelihood, robust default choice). Plain OLS survives as a benchmark, with macro covariates (HPI, unemployment) for the PIT layer.
- **Two-stage (cure) models** — the workhorse: $$\mathbb{E}[LGD]=P(\text{cure})\cdot LGD_{\text{cure}}+\big(1-P(\text{cure})\big)\cdot LGD_{\text{write-off}},$$ a logistic model for the cure/redefault outcome × a bounded regression for severity given write-off; a survival-to-resolution variant handles long workouts. This mirrors the data-generating process and lets macros act on the right margin (cure rates collapse in recessions even when collateral severities move less).
- **Downturn dependence (PD–LGD correlation):** realised LGDs rise exactly when default rates rise (Altman et al.); independent-margins ECL understates losses, so the LGD satellite must share macro drivers with the PD satellite.


### 10.3 Secured, unsecured, corporate

- **Mortgages / secured:** structural formula — expected sale proceeds = indexed collateral value × (1 − forced-sale discount), less selling costs and prior charges, delivered after time-to-repossession; loss = shortfall vs exposure, plus cure overlay. The HPI path from §5's merge drives both current LTV (PD covariate) and severity, making mortgage LGD the most scenario-sensitive parameter in the book.
- **Unsecured retail:** recovery *curves* — cumulative recovery as a function of months-since-default, estimated by vintage and segment (chain-ladder-style completion for open workouts), then discounted.
- **Corporate:** seniority and security dominate (secured bank debt recovers far more than subordinated bonds); debt cushion below the instrument matters; market-based LGD (30-day post-default trading prices) vs ultimate workout recoveries diverge; Moody's LossCalc is the reference vendor architecture.
- **Incomplete workouts:** excluding them biases LGD toward fast, favourable resolutions — include open cases with estimated completion (and validate the completion model itself).


## 11   Realised Losses: Net Credit Loss, the 90-DPD Trigger, and Discounting {#s11}

§10 modelled the LGD *ratio*; this section is about the quantity that ratio is built from — the actually-incurred loss on a defaulted loan — and two things that determine it in practice: **where you put the default boundary** (90 vs 180 days past due) and **how you bring delayed cash flows back to the default date**. The vocabulary and the numbers here come straight from the agency loan-level data of §5, so everything is reproducible.


### 11.1 What is Net Credit Loss (NCL)?

"Net credit loss" is used in two related senses, and interviewers expect you to separate them:

> **Definition.** **Loan-level NCL (the realised / actual loss).** The net loss on a single defaulted loan once its workout is complete — recoveries and proceeds netted against the exposure and the costs of collecting it. This is exactly the numerator of workout LGD: $LGD = NCL/EAD_{\text{default}}$. In Freddie Mac's loan-level dataset this is the *Actual Loss* field, built from the disclosed components $$NCL = \underbrace{\text{Default UPB}}_{\text{exposure at default}} + \text{Delinquent accrued interest} + \text{Expenses} - \text{Net sale proceeds} - \text{MI recoveries} - \text{Non-MI recoveries},$$ where **Expenses** decompose into legal/foreclosure costs, property maintenance & preservation, taxes & insurance, and miscellaneous. Equivalently, loss severity = (UPB + expenses − net sale proceeds − recoveries) ÷ UPB. The same template applies to any portfolio: replace "net sale proceeds" with whatever the recovery source is (collateral, guarantee, restructured cash flows).

> **Definition.** **Portfolio NCL (net charge-offs).** At the book level, NCL = gross charge-offs − recoveries over a period, usually expressed as an annualised **NCL rate** in basis points of average outstanding balances. This is the income-statement realisation that the ECL allowance is meant to anticipate; comparing realised NCL rates against modelled ECL by vintage and stage is a core part of the outcome analysis in §13.

| Component | Effect on loss | Notes |
| --- | --- | --- |
| Default UPB | increases | unpaid principal at the credit event = exposure base |
| Delinquent accrued interest | increases | interest from last paid instalment (DDLPI) onward; agency proxy for lost time value |
| Expenses (legal, maint., T&I, misc.) | increases | costs of foreclosure, holding and disposal |
| Net sale proceeds | decreases | REO/short-sale proceeds net of selling costs (largest offset) |
| MI recoveries | decreases | mortgage-insurance claim proceeds |
| Non-MI recoveries | decreases | T&I refunds, hazard proceeds, escrow, make-wholes |

> **Pitfall.** **Data trap.** Freddie Mac applies a roughly **90-day lag** on loss components after the zero-balance date — for very recent liquidations the proceeds/expenses/recovery fields are blank and only a zero-balance code is shown. The documentation's own advice: drop loans with missing net sale proceeds before computing severity, or your LGD will be biased by half-resolved cases.


### 11.2 The default trigger: 90 DPD vs 180 DPD, and why 90 DPD reporting matters

The same loan can be "in default" at different points depending on the convention:

- **90 DPD** — the **IFRS 9 / Basel** default backstop (CRR Art. 178: more than 90 days past due on a material obligation, plus unlikeliness-to-pay; §2.1). This is also the line behind most "default flags" in accounting and capital models, and aligns with non-accrual practice under CECL.
- **180 DPD (D180)** — the **agency credit-risk-transfer** convention: in Freddie Mac STACR (and Fannie Mae CAS) deals a reference loan becomes a *credit event* at 180+ days delinquent, regardless of any forbearance granted. Agency loss data and CRT severities are therefore anchored on a D180 (or disposition) definition, not 90 DPD.

**Why 90-DPD reporting is needed.** The point of IFRS 9 was earlier, unbiased loss recognition (§1); a 90-DPD trigger recognises trouble roughly three months sooner than D180. It also delivers **comparability** (a common, supervisor-endorsed default definition across accounting, capital and risk — the BCBS d350 alignment expectation), and the 30-/90-DPD backstops are deliberately hard to game. So even when your raw data (e.g. agency files) is built around D180, an IFRS 9 model must define default at 90 DPD + UTP and re-derive the parameters on that basis.

![Fig. 9 — Left: the delinquency ladder with the two trigger points — 90 DPD (IFRS 9/Basel default) and 180 DPD (agency credit event) — and the cure path that sits between them. Right: the §11.3 worked example — recoveries and costs at their actual months, each shrunk to present value by the discount-factor curve DF(t).](img/fig09.png)

*Fig. 9 — Left: the delinquency ladder with the two trigger points — 90 DPD (IFRS 9/Basel default) and 180 DPD (agency credit event) — and the cure path that sits between them. Right: the §11.3 worked example — recoveries and costs at their actual months, each shrunk to present value by the discount-factor curve DF(t).*

**What changes when you move the boundary from 180 DPD to 90 DPD:**

|  | 90-DPD definition | 180-DPD definition (D180) |
| --- | --- | --- |
| Default count / observed PD | **higher** (more loans reach 90 than 180) | lower |
| Cure content of the population | substantial (many 90+ loans self-cure) | small (most D180 loans liquidate) |
| Average LGD per default | **lower** (diluted by near-zero-loss cures) | higher (concentrated in real losses) |
| Timing of recognition | earlier (~3 months) | later |
| Typical use | IFRS 9, Basel, CECL | agency CRT (STACR/CAS), legacy severity studies |

> **Pitfall.** **Consistency rule.** PD, LGD and EAD must all be estimated on the *same* default definition. The most common silent error on agency data is pairing a 90-DPD PD with a D180-based LGD/severity: the product over-states loss because the LGD reflects only the severe, late-stage subset while the PD counts the whole 90-DPD population. Pick one boundary, build a consistent default flag (§5.4), and tie cure/probation rules to it.


### 11.3 Discounting future values

Recoveries and workout costs arrive months or years after default; a euro recovered in two years is worth less than a euro today. IFRS 9 therefore requires post-default cash flows to be **discounted at the original effective interest rate** back to the default date — the same EIR used in the ECL sum of §3, and the discounting already baked into the workout-LGD definition of §10.

> **Theorem.** **Discount factor.** For a cash flow occurring $t$ years after the default date, $DF(t) = (1+EIR)^{-t}$; for a flow at month $m$, $DF = (1+EIR)^{-m/12}$. The present value of the realised loss is $$NCL_{PV} = EAD_{\text{default}} + \sum_k DF(t_k)\,\text{Expense}_k - \sum_j DF(t_j)\,\text{Recovery}_j,\qquad LGD = NCL_{PV}/EAD_{\text{default}} .$$ The exposure at default sits at $t=0$ (undiscounted); everything that comes later is pulled back to $t=0$.

> **Worked Example.** | Component | ± | Month | Amount (€) | $DF$ | PV (€) |
> | --- | --- | --- | --- | --- | --- |
> | Net sale proceeds (REO) | − | 20 | 170,000 | 0.9146 | 155,487 |
> | MI recoveries | − | 22 | 12,000 | 0.9065 | 10,878 |
> | Non-MI recoveries | − | 23 | 2,000 | 0.9025 | 1,805 |
> | Taxes, insurance, maintenance | + | 10 | 5,000 | 0.9564 | 4,782 |
> | Legal / foreclosure | + | 16 | 4,000 | 0.9311 | 3,724 |
> 
> - **Ignore timing** (face values): loss = 200,000 + 9,000 − 184,000 = €25,000 → severity **12.5%**.
> 
> - **EIR-discounted (IFRS 9)**: loss = 200,000 + 8,506 − 168,170 = €40,336 → LGD **20.2%**.

> **Pitfall.** **Agency "Actual Loss" is nominal.** The Freddie Mac field does not discount — it adds a *delinquent accrued interest* term (here ≈€23,833, note rate on UPB over the ~26-month non-performing span) as a coarse stand-in for time value. That gives a nominal NCL of €48,833 → severity **24.4%**, in the same neighbourhood as the properly discounted 20.2% but not equal to it. So when modelling LGD on agency data, prefer to **discount the dated components yourself at the EIR**; if you use the supplied nominal severity instead, document that it embeds a lost-interest proxy rather than IFRS 9 EIR discounting, and that the two diverge with the workout length and rate.


### 11.4 Converting a 180-DPD definition to 90 DPD {#s11-4}

§11.2 set out *why* agency data is built on a 180-DPD (D180) credit event while IFRS 9 needs 90 DPD; this is *how* you move between them. The literature offers two routes, and the EU banking system ran the exercise wholesale when supervisors withdrew the 180-DPD exemption (removing it shifted risk-weighted assets by only ~1.6% on average, so the effect is real but contained).

> **Note.** **Route 1 — re-flag and re-estimate (preferred).** If you hold the monthly delinquency status (agency files do), don't "convert" anything: redefine default at 90 DPD (+ materiality + UTP, §2.1), rebuild the default flag across the whole history, and re-estimate PD, LGD, EAD, the transition matrix and cure rates from scratch — then backtest old- vs new-definition default counts and recalibrate only if they differ materially. This is what EU regulators and model vendors prescribe; it is exact, and on loan-level data it is just a threshold change.

> **Definition.** **Route 2 — the roll-rate bridge.** When you hold only D180-calibrated parameters, bridge them with the delinquency roll rates. Every loan reaching 180 first passed through 90, so D180 defaults are the subset of 90-DPD loans that *roll through* rather than cure. With $R=P(\text{reach }180\mid\text{reached }90)$ the roll-through rate, $$PD_{90}=\frac{PD_{180}}{R},\qquad LGD_{90}=(1-R)\,LGD_{\text{cure}}+R\,LGD_{180}\;\approx\;R\cdot LGD_{180},$$ so the product $PD\times LGD$ — the expected loss — is preserved when cures are loss-free. $R$ comes from a delinquency-bucket transition matrix (§6.3): the eventual roll-forward probability from bucket $b$ is $q_b=\text{fwd}/(\text{fwd}+\text{cure})$, and $R=q_{90}\,q_{120}\,q_{150}$.

| From bucket | monthly roll-forward | monthly cure | eventual roll-forward $q_b$ |
| --- | --- | --- | --- |
| 90 DPD | 0.50 | 0.12 | 0.81 |
| 120 DPD | 0.55 | 0.10 | 0.85 |
| 150 DPD | 0.60 | 0.08 | 0.88 |

> **Worked Example.** |  | D180 | D90 (cure loss 0) | D90 (cure loss 3%) |
> | --- | --- | --- | --- |
> | PD | 2.00% | 3.32% | 3.32% |
> | LGD | 30.0% | 18.1% | 19.3% |
> | EL = PD×LGD | 0.600% | 0.600% | 0.640% |

> **Pitfall.** **Caveats.** "90 DPD" means 90 days past due on a *material* amount plus unlikeliness-to-pay, not calendar days alone; attach cure/probation periods so loans don't oscillate across the boundary; and $R$ is segment- and cycle-dependent (roll-through jumps in downturns), so one factor is fragile — GSE mortgage data implies $R\approx0.8$ (only ~20% cure from 90), unsecured retail far lower. Whenever the loan-level data exists, re-estimating per segment (Route 1) beats a portfolio-wide factor.


## 12   EAD Modelling and Behavioural Life {#s12}


### 12.1 Term loans

For amortising products, EAD is the projected outstanding balance along the contractual schedule, adjusted for expected **prepayment** (full and partial). Prepayment is usually modelled as an SMM/CPR hazard with rate-incentive and seasoning covariates — itself a competing risk in the §6.2 framework. Missing the prepayment adjustment overstates late-horizon EAD and hence lifetime ECL.


### 12.2 Revolvers and the credit-conversion factor

> **Definition.** **CCF.** For facilities with undrawn headroom, $EAD=\text{Drawn}+CCF\times(\text{Limit}-\text{Drawn})$, where the CCF is estimated from defaulted accounts as the share of headroom at the observation point that had been drawn by default. Alternatives: loan-equivalent (LEQ) factors, utilisation-change regressions, momentum models.

> **Worked Example.** **Worked example** (`compute_ecl.py`): drawn €5m, limit €20m, estimated $CCF=60\%$ → $EAD=5+0.6\times15=14.0$ (**€14.0m**) — 2.8× the current drawn balance. The allowance on a lightly-drawn line is dominated by the undrawn commitment, which is why the ECL on loan commitments is recognised as a provision (liability) rather than netted off an asset.

![Fig. 10 — Left: declining term-loan EAD, contractual vs prepayment-adjusted (CPR 8%). Right: the revolver pathology — utilisation drifts up into default; the CCF captures the drawn share of headroom between observation and default.](img/fig10.png)

*Fig. 10 — Left: declining term-loan EAD, contractual vs prepayment-adjusted (CPR 8%). Right: the revolver pathology — utilisation drifts up into default; the CCF captures the drawn share of headroom between observation and default.*

> **Pitfall.** **CCF pitfalls.** Realised CCFs are bimodal (many near 0, many near 1) and unstable when current utilisation is near the limit (denominator → 0); they rise in downturns as distressed borrowers draw lines — a downturn-sensitive PIT CCF or utilisation-path model is better than one long-run average. Censor/floor handling and the choice of observation horizon (fixed 12m vs cohort) materially move the estimate.


### 12.3 Lifetime for revolving facilities: ¶5.5.20 and behavioural life

The general rule (B5.5.38) caps the ECL horizon at the **maximum contractual period** of exposure to credit risk. ¶5.5.20 carves out the exception for products like credit cards and overdrafts — facilities including both a drawn balance and an undrawn commitment, contractually cancellable at short notice but managed on a collective behavioural basis: for these, measure ECL over the **behavioural life**, the period the entity expects to be exposed, even beyond the 1-day contractual notice. B5.5.40's guidance reduces to the *shortest of*: the period over which credit-risk-management actions actually bite (limit cuts, withdrawal), the expected behavioural life, and normal credit-risk-management horizon. In practice banks evidence behavioural lives of roughly 2–4 years (~30 months is a common card answer) from attrition/closure curves — one of the most judgmental and audited numbers in a card book, since lifetime ECL scales almost linearly with it.


## 13   Validation, Backtesting and Staging Effectiveness {#s13}

Validation has three pillars — **discrimination**, **calibration**, **stability** — plus IFRS-9-specific layers: staging effectiveness, scenario reasonableness, and ECL outcome analysis.


### 13.1 Discrimination

$\mathrm{Gini}=2\,\mathrm{AUC}-1$ from the CAP/ROC; KS = maximum distance between cumulative score distributions of goods and bads. Working folklore: retail application Ginis of 40–60% are normal, behavioural higher; monitor the *trend* and segment-level values, not a single point. Discrimination decay is the usual first symptom of population drift.


### 13.2 Calibration backtests

| Component | Statement |
| --- | --- |
| Null $H_0$ | the assigned PD is adequate (true default probability $\le PD$) |
| Alternative $H_1$ | the PD *underestimates* the true default probability |
| Test statistic | observed defaults $d$ in the grade over the horizon |
| Reference distribution | $d\sim\mathrm{Binomial}(n,\,PD)$ under independence |
| Decision rule | reject if $p=P(D\ge d\mid n,PD)\le\alpha$ (one-sided) |

> **Worked Example.** **Worked example — grade-level backtest** (`compute_validation.py`). Grade with $n=1{,}000$, assigned $PD=2\%$, observed $d=28$ defaults. Binomial: $p=P(D\ge 28)=\mathbf{0.0507}$ — narrowly *fails to reject* at $\alpha=5\%$ (the critical count is $d_{crit}=29$). Jeffreys test (Bayesian, posterior $\mathrm{Beta}(d+\tfrac12,\,n-d+\tfrac12)$): $p=P(\pi\le 0.02\mid \text{data})=\mathbf{0.041}$ — *rejects*. A textbook boundary case: conclusions at the edge depend on the test, so policy should fix the test family, the $\alpha$, and a traffic-light buffer in advance, not after seeing the result.

> **Pitfall.** **Correlation caveat.** The binomial test assumes independent defaults; with asset correlation $\rho>0$ the variance of $d$ is far larger, so the naive test over-rejects in bad years and under-rejects in good ones. Remedies: the Basel traffic-light logic, granularity/correlation-adjusted tests (Tasche; BCBS Working Paper 14), or backtesting against the scenario-conditional PD rather than the unconditional one. Multi-year backtests must also handle overlapping cohorts and the cycle.

**Portfolio-level calibration:** Hosmer–Lemeshow $\chi^2$ across deciles (sharp with huge $n$ — pair with absolute-error views), Spiegelhalter test, calibration-in-the-large vs central tendency, and reconciliation of the predicted vs realised default-rate path.


### 13.3 Stability

> **Worked Example.** **Worked example — PSI** (`compute_validation.py`). Five score bands, development shares $[0.10,0.25,0.30,0.25,0.10]$ vs current $[0.06,0.20,0.30,0.28,0.16]$: $$PSI=\sum_i (a_i-e_i)\ln\frac{a_i}{e_i}=0.0204+0.0112+0+0.0034+0.0282=\mathbf{0.0632}.$$ Convention: $<0.10$ stable; $0.10$–$0.25$ monitor/investigate; $>0.25$ material shift — here the book has drifted toward the tails but remains formally stable. Run characteristic-level PSI/CSI to localise drift.


### 13.4 LGD, EAD and ECL-level validation

- **LGD:** predicted vs realised on resolved cases (t-tests / loss-shortfall views), segment-level bias, cure-rate backtests, discrimination via rank correlations; re-perform on completed-only vs completion-adjusted samples to expose incomplete-workout bias.
- **EAD/CCF:** realised vs predicted CCF distributions, utilisation-at-default backtests, downturn sensitivity.
- **Staging effectiveness:** stage flow/migration matrices; share of defaults that passed through Stage 2 first (early-warning hit rate) vs Stage-1→3 "jumps"; Stage-2 size, entry/exit churn and time-in-stage; override and backstop-trigger monitoring (how often does 30DPD, not the model, do the work?).
- **ECL outcome analysis:** ex-post comparison of ECL against realised losses by vintage/stage, attribution of movements (model vs macro vs overlays vs portfolio), scenario-weight reasonableness, and sensitivity disclosures reconciling to IFRS 7.
- **Independent validation:** second-line review with effective challenge, documented scope (data, methodology, implementation, use), and annual revalidation cycles — the SR 11-7 / TRIM expectations carried into accounting models.


## 14   Governance, Disclosure, Capital Interaction, Hot Topics {#s14}


### 14.1 The supervisory rulebook around the accounting standard

- **BCBS d350** (*Guidance on credit risk and accounting for expected credit losses*, 2015): 11 principles — board/senior-management responsibility for the ECL framework; sound, documented methodologies; robust rating/grouping processes; allowance adequacy; model validation; **experienced credit judgment** (the doctrinal home of overlays); common data and systems across risk and finance; disclosure; plus supervisory-evaluation principles. Its sharpest line: cost or operational burden is not a justification for forgoing reasonably available forward-looking information.
- **EBA/GL/2017/06** transposes d350 for EU credit institutions with proportionality; **Fed SR 11-7** (model risk management) supplies the validation/effective-challenge vocabulary; **ECB TRIM/IMI** reviews enforce it for internal models, with IFRS 9 models increasingly in scope of on-site inspections.


### 14.2 IFRS 7 disclosure package

What auditors and analysts expect to reconcile: credit-risk exposure and allowance **by stage** with movement (reconciliation) tables explaining transfers, originations, derecognitions, remeasurement and write-offs; the entity's **SICR criteria and default definition**; write-off policy; the **scenarios, weights and key macro assumptions** with sensitivity of ECL to them; and the significant judgments — ¶5.5.20 behavioural life, overlay quantification — that move the number. UK/EU large-bank reports (NatWest, Lloyds, Barclays, HSBC) are the best free worked examples of mature disclosure.


### 14.3 Capital interaction

- **Day 1 and transition:** the initial ECL uplift hit retained earnings (CET1); transitional arrangements (CRR Art. 473a in the EU) phased the impact over five years with static and dynamic components, with mandatory dual disclosure (transitional vs fully-loaded). The phase-ins have now largely expired, but the mechanism returns whenever the framework changes.
- **IRB books:** accounting provisions are compared with regulatory expected loss — a **shortfall** is deducted from CET1, an excess is recognised in Tier 2 up to 0.6% of credit RWA. Higher IFRS 9 provisions therefore partly "pre-pay" an existing CET1 deduction rather than reducing capital one-for-one.
- **Standardised books:** general provisions count toward Tier 2 up to **1.25% of credit RWA**; specific provisions reduce the exposure base.
- **Stress testing/ICAAP:** post-2018 stress tests are provision-sensitive: the EBA methodology prescribes scenario-conditional staging (with "perfect foresight" of the adverse path), so ECL models are now inside the capital-planning loop, and PIT parameters feed both.


### 14.4 Hot topics to be fluent in (mid-2026)

- **Overlay discipline** (§9.3) — the dominant supervisory theme: quantified, allocated, governed, with exit criteria.
- **Climate and novel risks:** the ECB's reviews show the share of banks reflecting climate risk in provisioning rising from a small minority (~16%) to a majority (~55%) within two years, mostly via overlays for want of data; the PRA observes few *material* climate PMAs yet keeps raising the evidential bar. The methodological frontier is moving climate from overlay to model covariate (transition/physical-risk-adjusted PD/LGD).
- **Procyclicality:** evidence (Behn & Couaillier, ECB WP 2841) that IFRS 9 provisions react earlier and more strongly to shocks than IAS 39 — better early recognition, but cliff effects at stage boundaries persist; expect questions on Stage-2 threshold design as a procyclicality dial.
- **Model ageing & ML adoption:** supervisors flag prolonged reliance on aged models patched by PMAs; ML challengers (GBMs, survival forests) are mainstream as challengers, gated by explainability and governance.


## 15   Learning Path, Tooling, Interview Drill {#s15}


### 15.1 A 12-week build-it-yourself path (all on §5 data)

| Weeks | Goal | Concrete deliverable |
| --- | --- | --- |
| 1–2 | Standard fluency (§§1–4) | one-page staging/ECL memo; framework-comparison table from memory |
| 3–6 | PD end-to-end (§6) | WOE/IV scorecard on Lending Club; discrete-time hazard on the CRA/DCR mortgage panel (Freddie sample as stretch); lifetime PD term structures by segment |
| 7–9 | LGD, EAD, wholesale (§§7, 10, 11) | two-stage LGD with workout discounting on DCR losses; CCF study; Merton DD replication; Pluto–Tasche on an S&P transition study |
| 10–12 | Scenarios + validation (§§8, 9, 12) | Z-recovery + satellite model; ECL engine conditioned on Fed 2026 base/severely-adverse paths with weights; validation pack (Gini, binomial/Jeffreys, PSI, staging flows) and a model-documentation write-up |


### 15.2 Tooling and references

**Python:** `pandas`/`numpy`, `statsmodels` (GLM cloglog, ARDL/ECM), `scikit-learn`, `lifelines` (survival), `scipy.stats`; **R:** `survival`, `glmnet`, `betareg`; SAS remains common in incumbent banks. **Books:** Baesens–Rösch–Scheule, *Credit Risk Analytics* (SAS, with the §5 datasets); Rösch–Scheule, *Deep Credit Risk* (Python, same universe); Bellini, *IFRS 9 and CECL Credit Risk Modelling and Validation* (R/SAS, the most directly on-topic); Siddiqi, *Credit Risk Scorecards*; plus Botha & Verster's open tutorial papers on IFRS 9 PD term-structure modelling (arXiv 2507.15441 and companions).


### 15.3 Interview drill — the twelve questions that recur

- **Why did IFRS 9 replace IAS 39?** Incurred → expected loss; "too little, too late"; provisions from day 1, forward-looking, probability-weighted.
- **Walk through the three stages.** 12-month vs lifetime ECL; gross vs net interest basis; transfers both ways with probation (Fig. 1).
- **What exactly is 12-month ECL?** Lifetime losses from defaults *possible* in the next 12 months — not truncated cash shortfalls, not only-certain defaults.
- **How would you design a SICR test?** Relative lifetime-PD comparison vs origination; doubling convention + absolute add-on, grade-sensitive; qualitative triggers; 30DPD backstop; low-credit-risk exemption; cure/probation; show the Stage-2 size trade-off.
- **IFRS 9 PD vs Basel PD?** PIT vs TTC; unbiased vs conservative/floored; 12m-or-lifetime vs 12m; EIR vs regulatory discounting in LGD; quote a de-conservatism adjustment you'd make (§4).
- **How do you build a lifetime PD term structure?** Discrete-time hazard (cloglog = grouped Cox) on a loan-month panel with time-varying covariates; seasoning baseline; competing prepayment risk; transition matrices/generators for wholesale (§6).
- **Why multiple scenarios — why not the base case?** ECL is convex in the macro state, Jensen's inequality; in the worked example the weighted ECL is ≈1.9× the average-path ECL (§9.2).
- **How does the macro enter the model?** Satellite model on default rates / recovered $Z_t$; ARDL/ECM hygiene; Vasicek conditioning of PDs and migration matrices (§§8–9).
- **Why is LGD modelled in two stages?** Bimodality: P(cure) × severity given write-off; EIR-discounted workout cash flows; HPI-driven collateral severity (§10).
- **EAD for a credit card?** CCF on headroom; ¶5.5.20 behavioural life beyond the 1-day notice; B5.5.40 shortest-of-three; behavioural life as the audited judgment (§12).
- **How do you validate an IFRS 9 suite?** Discrimination/calibration/stability + staging effectiveness + ECL outcome analysis; binomial vs Jeffreys with the correlation caveat; PSI bands; independent effective challenge (§13).
- **When is an overlay acceptable?** Trigger, quantification basis, allocation to stages/segments, exit criteria — and never silently at total-ECL level (§9.3).

> **Summary.** **One-screen cheat sheet.** $\;\mathrm{ECL}=\sum_t S(t{-}1)\lambda_t\cdot LGD_t\cdot EAD_t\cdot(1{+}EIR)^{-t}$ • 12m ECL = first 12 months of that sum • SICR: relative lifetime-PD test, 30DPD backstop, doubling convention • default: 90DPD + UTP, €100/€500 & 1% materiality, 3m/1y probation • $PD_{PIT}(Z)=\Phi[(\Phi^{-1}(PD_{TTC})-\sqrt{\rho}Z)/\sqrt{1-\rho}]$, $\mathbb{E}_Z[PD_{PIT}]=PD_{TTC}$ • weighted-scenario ECL > base-case ECL (Jensen; ≈1.9× in the worked example) • $WOE=\ln(\mathrm{Dist}^G/\mathrm{Dist}^B)$, IV strong ≥ 0.3 • $DD=[\ln(V/D)+(\mu-\tfrac12\sigma^2)T]/\sigma\sqrt{T}$ • Pluto–Tasche zero-default bound $1-(1-\gamma)^{1/n}$ • workout LGD: EIR-discounted recoveries less costs • $EAD=$ drawn $+CCF\times$ headroom; ¶5.5.20 behavioural life • backtests: binomial/Jeffreys (correlation caveat), HL, PSI 0.10/0.25 • data: CRA/DCR panels → Freddie/Fannie + FRED/FHFA/BLS → Fed/EBA scenario paths.


## Figures

### Figure 1 (ifrs9_credit_risk_notes.md ![](img/fig01.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig001.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig01.png)
- context_keywords: etime ECL since initial recognition which can gain Impairment Model Staging Default
- caption: Three-stage IFRS 9 impairment model flowchart: Stage 1 performing (12-month ECL, EIR on gross carrying amount) moves to Stage 2 under-performing on SICR (lifetime ECL, EIR on gross) and to Stage 3 credit-impaired on default (lifetime ECL, EIR on net), with cure/probation arrows back and the backstops noted: 30 DPD rebuttable SICR presumption, 90 DPD default, low-credit-risk exemption.

### Figure 2 (ifrs9_credit_risk_notes.md ![](img/fig02.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig002.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig02.png)
- context_keywords: age discounted-cash-flow approaches equally permissible unbiased probability-weighted forward-looking
- caption: Lifetime PD term structure, two panels over 120 months on book. Left: conditional hazard lambda_t peaking near month 20 at ~0.29%/month (the retail seasoning hump) with the marginal PD S(t-1)*lambda_t just below it. Right: survival S(t) declining to ~84% and cumulative PD F(t)=1-S(t) rising to ~16%.

### Figure 3 (ifrs9_credit_risk_notes.md ![](img/fig03.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig003.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig03.png)
- context_keywords: month panel macro series merged time geography scenario paths entering through conditioning
- caption: End-to-end practice pipeline flowchart: loan-level panels (Freddie SFLLD, Fannie SFLP, CRA/Deep Credit Risk, Lending Club) plus macro time series (FRED/ALFRED, BLS LAUS, FHFA HPI, PMMS) merge into a loan-month panel (lag macros 1-2q, macro-at-origination columns, HPI ratio to updated LTV); scenario paths (Fed DFAST, EBA/ECB, IMF WEO) enter the macro-conditioning layer (satellite ARDL/ECM, Vasicek Z-shift) feeding PD/LGD/EAD models into scenario ECLs and the probability-weighted ECL with lifetime-PD SICR staging.

### Figure 4 (ifrs9_credit_risk_notes.md ![](img/fig04.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig004.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig04.png)
- context_keywords: nerator may not exist empirically estimated annual matrix embedding problem regularisation standard
- caption: Illustrative S&P-style 1-year corporate rating transition matrix heatmap (%, row-stochastic), AAA through D: diagonal-dominant (AAA 90.5, A 91.0, CCC 61.7), monotone default column rising from 0.01 (AAA) to 27.8 (CCC), absorbing D state at 100.

### Figure 5 (ifrs9_credit_risk_notes.md ![](img/fig05.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig005.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig05.png)
- context_keywords: PD_ PIT
- caption: Vasicek conditioning curves PD_PIT(Z) = Phi[(Phi^-1(PD_TTC) - sqrt(rho)Z)/sqrt(1-rho)] at rho=0.12 for TTC anchors 0.5%, 2%, 5%, plotted against systematic factor Z from -3 to +3 with the downturn band Z<-1 shaded. Worked-example points on the 2% curve: PD_PIT = 7.34% at Z=-2, 1.43% at Z=0, 0.17% at Z=+2.

### Figure 6 (ifrs9_credit_risk_notes.md ![](img/fig06.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig006.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig06.png)
- context_keywords: Base Downside
- caption: The Jensen gap exhibit: 1-year ECL as a convex decreasing function of real GDP growth, with three scenario points (downside g=-2.5% w=0.25, base g=2.0% w=0.5, upside g=3.5% w=0.25). Probability-weighted ECL = EUR 1.74m sits ~1.9x above the ECL at the average scenario (EUR 0.90m) — why IFRS 9 requires multiple probability-weighted scenarios.

### Figure 7 (ifrs9_credit_risk_notes.md ![](img/fig07.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig007.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig07.png)
- context_keywords: esult term structure PIT-shaped early TTC-flat tail left mechanics
- caption: Forecast horizon and lifetime gross-up, two panels. Left: annual conditional hazard scenario-conditioned inside the ~36-month reasonable-and-supportable window (2.5% falling to 1.9%) then reverting to the 1.5% long-run TTC level. Right: cumulative PD reaching 9.4% at the 60-month reliable horizon and 12.1% lifetime, giving gross-up factor x1.29.

### Figure 8 (ifrs9_credit_risk_notes.md ![](img/fig08.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig008.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig08.png)
- context_keywords: discounting cost treatment not cosmetic distributional reality model families
- caption: Histogram showing realised LGD is bimodal on [0,1]: a cure/self-cure spike near zero loss and a write-off hump centred around 0.6-0.8, with mean LGD = 0.37 falling in the low-density middle — the argument for two-stage P(cure) x LGD-given-write-off models over single Gaussian regression.

### Figure 9 (ifrs9_credit_risk_notes.md ![](img/fig09.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig009.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig09.png)
- context_keywords: built around D180 IFRS model must define default DPD UTP re-derive parameters
- caption: Default trigger and loss discounting, two panels. Left: delinquency ladder (current, 30, 60, 90, 120, 150, 180+, liquidation) marking 90 DPD as the IFRS 9/Basel default and 180 DPD as the agency credit event, with the cure path between them; counting at 90 DPD gives more defaults with lower average LGD. Right: the worked example discounting recoveries and costs to the default date with the DF(t) curve — face loss 12.5% of UPB becomes 20.2% EIR-discounted.

### Figure 10 (ifrs9_credit_risk_notes.md ![](img/fig10.png))

- asset: `img/ifrs9_credit_risk_notes.md_fig010.png`
- kind: md-img
- anchor: ifrs9_credit_risk_notes.md ![](img/fig10.png)
- context_keywords: which why ECL loan commitments recognised provision liability rather than netted off
- caption: EAD profiles, two panels. Left: term-loan declining EAD, contractual amortisation vs prepayment-adjusted at CPR 8% over 60 months. Right: revolver pathology — drawn balance drifts from 9.6 at observation (12m before default) to 16.5 at default against a limit of 20, giving CCF ~ 0.67 of undrawn headroom.
