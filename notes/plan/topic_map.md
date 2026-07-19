# Master topic map — IFRS9 ECL study-notes compendium

Generated 2026-07-19. 46 concepts mapped. Human-readable index over `topic_map.json` (the machine-readable backbone used to drive chapter assembly). Every row traces a concept to its theory anchor, fixtures, exhibits, reports, wiki pages, code and app/docker touchpoints.

## Sources swept

- knowledge/index (pageindex tree, --render, 69 nodes over 23 pages)
- tests/fixtures/compute_{ecl,pd,vasicek,scenarios,grossup,ncl,rollrate,validation}.py (8 files, 133 golden RESULTS values per tests/test_fixtures.py)
- outputs/**/*.md (34 report files across panel/eda/hazard/lgd/ead/staging/ecl/gate/vasicek/scenarios/satellite/scenario_ecl/challenger/design/mdd/mcp + outputs/freddie/**)
- outputs/**/*.png (36 project exhibits + 10 textbook figure cards in knowledge/corpus/img/)
- wiki/index.md + all 20 pages in wiki/pages/
- agent/*.py (graph.py, tools_tier1.py, tools_tier2.py, tier3_retrieval.py, mcp_server.py)
- app/api/main.py (24 endpoints), app/ui/src/**, docs/api_contract.md (886 lines)
- Dockerfile, .dockerignore, requirements.docker.txt
- engine/*.py, analysis/*.py, freddie/*.py (module references only — READ-ONLY, not modified)

## Part A — IFRS 9 theory (knowledge/corpus, 15 sections)

## Part B — DCR (synthetic Data Consortium) modelling pipeline

## Part C — Freddie Mac SFLLD rung-3 build

## Part D — Agent, App, Deployment layers

(Table of contents above; detail follows below, grouped by part.)

---

## Part A — IFRS 9 theory (knowledge/corpus, 15 sections)

### A1 — IFRS 9 standard: origins, scope, classification

**Topics:** IAS39->IFRS9, scope of ECL, business model test, SPPI test, simplified approach, POCI

**Theory anchor:** s1 (1, 1.1, 1.2, 1.3)  (node ids: 0003, 0004, 0005, 0006)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/mdd/MDD.md`

**Wiki pages:** `wiki/pages/project-overview.md`, `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Foundational/definitional; no fixture (no worked numeric example in source).

### A2 — Staging, default definition, SICR

**Topics:** 3-stage model, 12m vs lifetime ECL trigger, default (90 DPD/UTP), SICR relative test, backstops, low-credit-risk exemption

**Theory anchor:** s2 (2, 2.1, 2.2); Fig. 1 (node 0060)  (node ids: 0007, 0008, 0009)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/staging/stage2_sensitivity.png`
- `outputs/staging/stage_distribution.png`
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig001.png`

**Reports:** `outputs/staging/staging_report.md`

**Wiki pages:** `wiki/pages/staging-model.md`

**Code:** `engine/staging.py`, `analysis/staging_exhibits.py`

**App surface:** tab = Policy; endpoint = /api/policy/staging_sensitivity

**Notes:** Project verified relative-SICR test to 1e-10; Stage 2 empty in calm regime vs 75.8% in stress (staging_report.md).

### A3 — ECL mechanics: formula, term structure, worked example

**Topics:** ECL = sum PV(hazard x survival x LGD x EAD), discrete-time decomposition, 12m vs lifetime ECL, worked 5-year amortising loan example

**Theory anchor:** s3  (node ids: 0010)

**Fixtures:**
- `tests/fixtures/compute_ecl.py` — keys: ecl_12m_eur, ecl_lifetime_eur, lifetime_over_12m_ratio, cumulative_pd_5y_pct, workout_pv_recoveries_eur, workout_pv_costs_eur, workout_recovery_rate_pct, workout_lgd_pct, workout_lgd_undiscounted_pct, revolver_ead_eur_m, revolver_ead_over_drawn

**Exhibits:**
- `outputs/ecl/ecl_waterfall.png`
- `outputs/ecl/allowance_by_stage.png`
- `outputs/ecl/coverage_by_stage.png`

**Reports:** `outputs/ecl/ecl_report.md`, `outputs/gate/gate_report.md`, `outputs/gate/day3_gate_report.md`, `outputs/gate/day4_gate_report.md`

**Wiki pages:** `wiki/pages/ecl-engine.md`, `wiki/pages/golden-fixtures.md`

**Code:** `engine/ecl.py`, `analysis/run_ecl.py`

**App surface:** tab = Model / Executive Overview; endpoint = /api/ecl/summary, /api/ecl/waterfall

**Notes:** Core theorem chapter; ECL decomposition THEOREM box must be expanded step-by-step (hazard->survival->PV chain). Engine frozen 2026-07-05, gate 187/187.

### A4 — IFRS 9 vs Basel IRB vs CECL

**Topics:** PIT vs TTC parameters, downturn LGD vs neutral LGD, 12m floor, day-1 loss recognition (CECL) vs staged (IFRS9)

**Theory anchor:** s4  (node ids: 0011)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Comparison table topic; candidate for a 'Gotchas' box on re-using Basel PD/LGD unmodified.

### A5 — Data foundations: public datasets, macro series, scenarios, variable dictionary

**Topics:** Freddie Mac SFLLD, FRED/ALFRED, left truncation/right censoring, modelling-variable dictionary

**Theory anchor:** s5 (5.1-5.5)  (node ids: 0012, 0013, 0014, 0015, 0016, 0017)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/variable_dictionary.md`

**Wiki pages:** `wiki/pages/variable-dictionary.md`, `wiki/pages/knowledge-pipeline.md`

**Code:** `freddie/ingest.py`, `freddie/macro.py`, `freddie/build_panel.py`

**App surface:** tab = Real Data; endpoint = /api/model/variable_dictionary

### A6 — Retail scorecards: WOE, IV, logistic regression

**Topics:** weight of evidence, information value, coarse classing, logistic scorecard

**Theory anchor:** s6.1  (node ids: 0019)

**Fixtures:**
- `tests/fixtures/compute_pd.py` — keys: bad_rate_pct_ltv_le_60, dist_good_ltv_le_60, dist_bad_ltv_le_60, woe_ltv_le_60, iv_contrib_ltv_le_60, bad_rate_pct_ltv_60_80, dist_good_ltv_60_80, dist_bad_ltv_60_80, woe_ltv_60_80, iv_contrib_ltv_60_80, bad_rate_pct_ltv_80_90, dist_good_ltv_80_90, dist_bad_ltv_80_90, woe_ltv_80_90, iv_contrib_ltv_80_90, bad_rate_pct_ltv_gt_90, dist_good_ltv_gt_90, dist_bad_ltv_gt_90, woe_ltv_gt_90, iv_contrib_ltv_gt_90, iv_total_ltv

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** 4-bin LTV example, IV total = 0.4403 target; every bin's WOE/IV contribution must show the log-odds substitution step-by-step.

### A7 — Lifetime PD via discrete-time survival analysis (hazard/cloglog)

**Topics:** discrete-time hazard, logit vs cloglog link, competing risks, survival function, continuous-time hazard -> cloglog derivation

**Theory anchor:** s6.2  (node ids: 0020)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/hazard/age_baseline.png`
- `outputs/hazard/pd_term_structure.png`
- `outputs/eda/hazard_by_loan_age.png`

**Reports:** `outputs/hazard/fit_stats.md`, `outputs/hazard/hazard_ratios.md`

**Wiki pages:** `wiki/pages/hazard-model.md`

**Code:** `engine/hazard.py`, `analysis/fit_hazard.py`

**App surface:** tab = Model; endpoint = /api/model/coefficients

**Notes:** DERIVATION TO EXPAND (flagged by user): cloglog link from the continuous-time proportional-hazards assumption P(T=t|T>=t) = 1 - exp(-exp(x'beta)) is asserted, not derived, in the source notes. DCR hazard AUC 0.748/0.661 (engine); Freddie hazard AUC in outputs/freddie/hazard/hazard_report.md.

### A8 — Transition matrices (Markov chains) for wholesale/rating books

**Topics:** cohort method, duration/generator method, intensity matrix Q, embedding problem

**Theory anchor:** s6.3  (node ids: 0021)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** No project fixture/code — theory-only topic (wholesale not modelled in this retail-mortgage capstone); flag as scope note in chapter.

### A9 — Corporate & low-default PD: Merton, shadow ratings, Pluto-Tasche

**Topics:** Merton structural model (equity as call option), distance to default, shadow rating masterscale, Pluto-Tasche most-prudent-estimation, Bayesian LDP calibration

**Theory anchor:** s7 (7.1-7.3)  (node ids: 0022, 0023, 0024, 0025)

**Fixtures:**
- `tests/fixtures/compute_pd.py` — keys: merton_dd, merton_pd_pct

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** DERIVATION TO EXPAND: Merton PD = Phi(-DD) from V_T<D under GBM asset dynamics — the Ito/log-normal step from asset SDE to the distance-to-default formula is compressed in the source and must be shown in full.

### A10 — PIT vs TTC: the Vasicek one-factor framework

**Topics:** one-factor Gaussian copula, asset-value latent factor, systematic factor Z, PD_PIT(Z) conditioning formula, correlation rho, law of total probability check

**Theory anchor:** s8; Fig. 5 (node 0064)  (node ids: 0026)

**Fixtures:**
- `tests/fixtures/compute_vasicek.py` — keys: default_threshold_ppf_002, pd_pit_pct_z_plus_2_0, pd_pit_pct_z_plus_1_0, pd_pit_pct_z_0_0, pd_pit_pct_z_minus_1_0, pd_pit_pct_z_minus_2_0, pd_pit_pct_z_minus_2_5, expected_pd_pit_gauss_hermite, expected_pd_pit_fine_grid

**Exhibits:**
- `outputs/vasicek/credit_cycle.png`
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig005.png`

**Reports:** `outputs/vasicek/vasicek_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `engine/vasicek.py`, `analysis/fit_vasicek.py`

**App surface:** tab = Scenario Lab; endpoint = /api/exhibits/credit_cycle, /api/tools/shock_macro

**Notes:** DERIVATION TO EXPAND: full one-factor Gaussian copula derivation from asset value A_i = sqrt(rho)Z + sqrt(1-rho)eps_i to PD_PIT(Z)=Phi[(Phi^-1(PD_TTC) - sqrt(rho)Z)/sqrt(1-rho)]. Project-calibrated rho=0.0227 (wiki scenario-layer.md) vs the textbook's illustrative rho=0.12 — chapter must reconcile both. INTERACTIVE WIDGET: PD_PIT vs Z and rho slider.

### A11 — Forward-looking scenarios: satellite (macro-link) models

**Topics:** credit-index ~ macro drivers regression, GDP/unemployment/HPI drivers, reasonable and supportable information (IFRS9 5.5.17c)

**Theory anchor:** s9.1  (node ids: 0028)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/satellite/satellite_fit.png`

**Reports:** `outputs/satellite/satellite_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `engine/satellite.py`

**App surface:** tab = Scenario Lab; endpoint = —

### A12 — Multiple probability-weighted scenarios; Jensen's inequality

**Topics:** convexity of ECL in the macro state, Jensen's inequality applied to ECL, probability-weighted vs single-scenario understatement

**Theory anchor:** s9.2; Fig. 6 (node 0065)  (node ids: 0029)

**Fixtures:**
- `tests/fixtures/compute_scenarios.py` — keys: upside_z, upside_pd_pit_pct, upside_ecl_eurm, base_z, base_pd_pit_pct, base_ecl_eurm, downside_z, downside_pd_pit_pct, downside_ecl_eurm, weighted_pd_pct, weighted_ecl_eurm, avg_gdp_growth_pct, avg_path_pd_pct, avg_path_ecl_eurm, understatement_pct, weighted_over_single_ratio

**Exhibits:**
- `outputs/scenario_ecl/jensen_gap.png`
- `outputs/scenario_ecl/scenario_ecl_bars.png`
- `outputs/scenario_ecl/z_paths.png`
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig006.png`

**Reports:** `outputs/scenario_ecl/scenario_ecl_report.md`, `outputs/scenarios/scenarios_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `engine/scenarios.py`, `analysis/run_scenarios.py`, `analysis/scenario_exhibits.py`

**App surface:** tab = Scenario Lab; endpoint = /api/tools/reweight_scenarios

**Notes:** DERIVATION TO EXPAND: full Jensen's-inequality proof (convex f => E[f(X)] >= f(E[X])) applied to the PD_PIT(Z) convexity in Z, then to ECL; project measured 1.035x uplift (wiki scenario-layer.md) vs the textbook's illustrative understatement_pct. INTERACTIVE WIDGET: 3-scenario weight sliders -> live weighted ECL vs single-path ECL bar chart, exposing the Jensen gap.

### A13 — Post-model adjustments (overlays)

**Topics:** overlay governance, ECB thematic review findings, quarter of coverage from overlays, exit criteria for overlays

**Theory anchor:** s9.3  (node ids: 0030)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`, `wiki/pages/master-plan.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Narrative/governance topic, folds into the Governance & MDD chapter.

### A14 — Forecast horizon, lifetime, and the gross-up factor

**Topics:** reasonable and supportable window, TTC reversion tail, gross-up factor = cum PD lifetime / cum PD short-horizon

**Theory anchor:** s9.4  (node ids: 0031)

**Fixtures:**
- `tests/fixtures/compute_grossup.py` — keys: cum_pd_12m_pct, gross_up_12m_to_life, ecl_12m, cum_pd_36m_pct, gross_up_36m_to_life, ecl_36m, cum_pd_60m_pct, gross_up_60m_to_life, ecl_60m, cum_pd_84m_pct, gross_up_84m_to_life, ecl_84m

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Ties directly to A3 (ECL mechanics) and A12 (scenario horizon); 7-year loan, PIT-elevated hazard for 3-year R&S window reverting to 1.5% TTC.

### A15 — LGD: workout definition and discounting

**Topics:** workout LGD measurement, recoveries R_k, workout costs C_k, discount at original EIR, NOT the reporting-date discount rate

**Theory anchor:** s10.1  (node ids: 0033)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/lgd-model.md`

**Code:** none

**App surface:** tab = —; endpoint = —

### A16 — LGD distributional reality and model families

**Topics:** bimodal LGD (cure spike + write-off hump), beta regression, two-stage cure x severity models

**Theory anchor:** s10.2; Fig. 8 (node 0067)  (node ids: 0034)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/eda/lgd_realised_bimodal.png`
- `outputs/lgd/lgd_distribution.png`
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig008.png`

**Reports:** none

**Wiki pages:** `wiki/pages/lgd-model.md`

**Code:** none

**App surface:** tab = —; endpoint = —

### A17 — LGD: secured/unsecured/corporate structural formula

**Topics:** indexed collateral value, forced-sale discount, time-to-repossession, loss = shortfall vs indexed collateral

**Theory anchor:** s10.3  (node ids: 0035)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/lgd/calibration_ltv.png`
- `outputs/lgd/cure_by_ltv.png`

**Reports:** `outputs/lgd/lgd_report.md`

**Wiki pages:** `wiki/pages/lgd-model.md`

**Code:** `engine/lgd.py`, `analysis/fit_lgd.py`

**App surface:** tab = Model; endpoint = /api/model/lgd

**Notes:** Project two-stage cure x severity model; excess-loss loading +0.0255, never clipped (wiki lgd-model.md).

### A18 — Net Credit Loss (NCL): loan-level vs portfolio-level; discounting worked example

**Topics:** loan-level NCL definition, portfolio NCL rate, PV of recoveries and expenses at EIR, discounted vs nominal severity

**Theory anchor:** s11 (11.1, 11.3)  (node ids: 0036, 0037, 0039)

**Fixtures:**
- `tests/fixtures/compute_ncl.py` — keys: df_reo_m20, pv_reo_m20, df_mi_m22, pv_mi_m22, df_non_mi_m23, pv_non_mi_m23, df_taxes_m10, pv_taxes_m10, df_legal_m16, pv_legal_m16, face_recoveries_eur, pv_recoveries_eur, pv_expenses_eur, face_loss_eur, face_severity_pct, discounted_loss_ncl_pv_eur, discounted_lgd_pct, accrued_interest_eur, nominal_ncl_agency_eur, nominal_severity_pct

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/lgd-model.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** DERIVATION TO EXPAND: each cash flow's DF(m)=(1+EIR)^(-m/12) shown individually before summing (currently a compressed table in the source notes).

### A19 — The 90-DPD vs 180-DPD default trigger; roll-rate bridge

**Topics:** 90 DPD IFRS9/Basel backstop, 180 DPD agency convention, roll-rate bridge (route 2), eventual roll-forward q_b, roll-through rate R

**Theory anchor:** s11.2, s11.4; Fig. 9 (node 0068)  (node ids: 0038, 0040)

**Fixtures:**
- `tests/fixtures/compute_rollrate.py` — keys: q_eventual_rollforward_90dpd, q_eventual_rollforward_120dpd, q_eventual_rollforward_150dpd, roll_through_rate_R, pd_90_pct, lgd_90_cure_loss_free_pct, lgd_90_cure_loss_3pct_pct, el_180_pct, el_90_cure_loss_free_pct, el_90_cure_loss_3pct_pct

**Exhibits:**
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig009.png`

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** DERIVATION TO EXPAND: q_b = fwd/(fwd+cure) per bucket, R = q90*q120*q150 = 0.60, then EL_90 = EL_180 / R style rescaling — every multiplication shown.

### A20 — EAD: term loans, revolver CCF, behavioural life

**Topics:** contractual amortisation profile, prepayment SMM/CPR, credit conversion factor (CCF), IFRS9 5.5.20 behavioural life exception for revolvers

**Theory anchor:** s12 (12.1-12.3); Fig. 10 (node 0069)  (node ids: 0042, 0043, 0044)

**Fixtures:**
- `tests/fixtures/compute_ecl.py` — keys: revolver_ead_eur_m, revolver_ead_over_drawn

**Exhibits:**
- `outputs/ead/ead_profiles.png`
- `knowledge/corpus/img/ifrs9_credit_risk_notes.md_fig010.png`

**Reports:** `outputs/ead/ead_report.md`

**Wiki pages:** `wiki/pages/ead-model.md`

**Code:** `engine/ead.py`, `analysis/ead_exhibits.py`

**App surface:** tab = Model; endpoint = —

**Notes:** Project's 'double-counting rule' for combining amortisation + CCF (wiki ead-model.md) is a GOTCHA to surface explicitly. EAD fixture: EUR 14.0m revolver worked example.

### A21 — Validation: discrimination, calibration backtests, stability (PSI)

**Topics:** Gini/AUC/KS, binomial backtest, Jeffreys test, PSI worked example, LGD/EAD/ECL-level validation

**Theory anchor:** s13 (13.1-13.4)  (node ids: 0045, 0046, 0047, 0048, 0049)

**Fixtures:**
- `tests/fixtures/compute_validation.py` — keys: binomial_backtest_p_value, binomial_rejects_at_5pct, binomial_critical_count, jeffreys_p_value, jeffreys_rejects_at_5pct, psi_term_band1, psi_term_band2, psi_term_band3, psi_term_band4, psi_term_band5, psi_total, psi_is_stable

**Exhibits:**
- `outputs/challenger/reliability.png`
- `outputs/challenger/psi_scores.png`
- `outputs/challenger/perm_importance.png`
- `outputs/challenger/pdp_grid.png`
- `outputs/challenger/pdp_double_trigger.png`
- `outputs/challenger/staging_swap.png`

**Reports:** `outputs/challenger/scorecard.md`

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`, `wiki/pages/golden-fixtures.md`

**Code:** `analysis/fit_challenger.py`

**App surface:** tab = Model; endpoint = —

**Notes:** DERIVATION TO EXPAND: binomial exact test statistic (1-CDF), Jeffreys prior-posterior interval, and the full PSI sum-of-bands formula with each band's term shown.

### A22 — Governance, disclosure, capital interaction, hot topics

**Topics:** BCBS d350 11 principles, IFRS7 disclosure package (staged reconciliation tables), CRR Art. 473a transitional arrangements, overlay discipline, climate risk in ECL

**Theory anchor:** s14 (14.1-14.4)  (node ids: 0050, 0051, 0052, 0053, 0054)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/mdd/MDD.md`

**Wiki pages:** `wiki/pages/project-overview.md`, `wiki/pages/master-plan.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Governance chapter anchor; MDD.md is the project's own model documentation deliverable and should be walked through structurally as a worked example of this section's disclosure requirements.

### A23 — Learning path, tooling, interview drill (meta/appendix)

**Topics:** 12-week build path, python/R tooling, 12 interview questions

**Theory anchor:** s15  (node ids: 0055, 0056, 0057, 0058)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** none

**Wiki pages:** `wiki/pages/ifrs9-study-notes.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Not a standalone chapter; fold key interview-drill Qs into a closing appendix / per-chapter 'Check yourself' bank.

---

## Part B — DCR (synthetic Data Consortium) modelling pipeline

### B1 — DCR loan-quarter panel construction & waterfall

**Topics:** eligible loan-quarter panel, 621,736 rows, itemized exclusion waterfall, train/OOT split, lag verification

**Theory anchor:** supports s5/s6  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/panel/waterfall.md`

**Wiki pages:** `wiki/pages/loan-panel.md`

**Code:** `engine/staging.py (upstream panel build referenced by analysis/*)`

**App surface:** tab = Model; endpoint = —

**Notes:** No PNGs in outputs/panel/ — the waterfall table itself is the exhibit (render as styled HTML table).

### B2 — DCR EDA: default rates, hazard by age, LGD, origination quality, prepay

**Topics:** default rate vs macro overlay, hazard-by-loan-age seasoning hump, LGD bimodality, origination quality trends, prepay vs rate incentive, vintage cumulative default curves

**Theory anchor:** supports s6.2/s10.2  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/eda/default_rate_vs_macro.png`
- `outputs/eda/hazard_by_loan_age.png`
- `outputs/eda/lgd_realised_bimodal.png`
- `outputs/eda/origination_quality.png`
- `outputs/eda/prepay_vs_rate_incentive.png`
- `outputs/eda/vintage_cumulative_default.png`

**Reports:** `outputs/eda/eda_report.md`

**Wiki pages:** `wiki/pages/loan-panel.md`

**Code:** `analysis/eda_suite.py`

**App surface:** tab = Model / Real Data; endpoint = —

### B3 — DCR hazard model (cloglog competing-risk PD engine)

**Topics:** cloglog GLM fit, AUC 0.748/0.661, seasoning hump reproduced, hazard ratios

**Theory anchor:** extends s6.2  (node ids: 0020)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/hazard/age_baseline.png`
- `outputs/hazard/pd_term_structure.png`

**Reports:** `outputs/hazard/fit_stats.md`, `outputs/hazard/hazard_ratios.md`

**Wiki pages:** `wiki/pages/hazard-model.md`

**Code:** `engine/hazard.py`, `analysis/fit_hazard.py`

**App surface:** tab = Model; endpoint = /api/model/coefficients

### B4 — DCR LGD model (two-stage cure x severity)

**Topics:** cure probability stage, severity | not-cured stage, excess-loss loading

**Theory anchor:** extends s10  (node ids: 0034, 0035)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/lgd/calibration_ltv.png`
- `outputs/lgd/cure_by_ltv.png`
- `outputs/lgd/lgd_distribution.png`

**Reports:** `outputs/lgd/lgd_report.md`

**Wiki pages:** `wiki/pages/lgd-model.md`

**Code:** `engine/lgd.py`, `analysis/fit_lgd.py`

**App surface:** tab = Model; endpoint = /api/model/lgd

**Notes:** Same as A17; cross-referenced from LGD theory chapter.

### B5 — DCR EAD model

**Topics:** amortisation + CCF combination, double-counting rule

**Theory anchor:** extends s12  (node ids: 0042, 0043)

**Fixtures:**
- `tests/fixtures/compute_ecl.py` — keys: revolver_ead_eur_m, revolver_ead_over_drawn

**Exhibits:**
- `outputs/ead/ead_profiles.png`

**Reports:** `outputs/ead/ead_report.md`

**Wiki pages:** `wiki/pages/ead-model.md`

**Code:** `engine/ead.py`, `analysis/ead_exhibits.py`

**App surface:** tab = Model; endpoint = —

**Notes:** Same underlying model as A20; separate entry for the build-report walkthrough.

### B6 — DCR staging model & threshold sensitivity

**Topics:** relative SICR verified to 1e-10, Stage 2 share: 0% calm / 75.8% stress, threshold sensitivity sweep

**Theory anchor:** extends s2  (node ids: 0007, 0008, 0009)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/staging/stage2_sensitivity.png`
- `outputs/staging/stage_distribution.png`

**Reports:** `outputs/staging/staging_report.md`

**Wiki pages:** `wiki/pages/staging-model.md`

**Code:** `engine/staging.py`, `analysis/staging_exhibits.py`

**App surface:** tab = Policy; endpoint = /api/policy/staging_sensitivity

**Notes:** INTERACTIVE WIDGET: staging threshold slider -> live stage-share recompute (per campaign brief example list).

### B7 — DCR ECL engine, gates & golden fixtures

**Topics:** ECL sum + movement decomposition, gate 187/187, engine freeze 2026-07-05, 8 golden compute_*.py fixtures, 133 values

**Theory anchor:** extends s3  (node ids: 0010)

**Fixtures:**
- `tests/fixtures/compute_ecl.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_pd.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_vasicek.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_scenarios.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_grossup.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_ncl.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_rollrate.py` (full file — see Part B7 golden-fixtures roll-up)
- `tests/fixtures/compute_validation.py` (full file — see Part B7 golden-fixtures roll-up)

**Exhibits:**
- `outputs/ecl/allowance_by_stage.png`
- `outputs/ecl/coverage_by_stage.png`
- `outputs/ecl/ecl_waterfall.png`

**Reports:** `outputs/ecl/ecl_report.md`, `outputs/gate/gate_report.md`, `outputs/gate/day3_gate_report.md`, `outputs/gate/day4_gate_report.md`

**Wiki pages:** `wiki/pages/ecl-engine.md`, `wiki/pages/golden-fixtures.md`

**Code:** `engine/ecl.py`, `analysis/run_ecl.py`, `tests/test_fixtures.py`

**App surface:** tab = Executive Overview; endpoint = /api/ecl/summary, /api/ecl/waterfall

**Notes:** The fixtures/gates chapter — meta-level walkthrough of how every number in the notes is verified (tests/test_fixtures.py maps all 133 golden values).

### B8 — Vasicek calibration on the project panel

**Topics:** calibrated rho=0.0227, credit-cycle Z-path, PIT PD conditioning applied to DCR book

**Theory anchor:** extends s8  (node ids: 0026)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/vasicek/credit_cycle.png`

**Reports:** `outputs/vasicek/vasicek_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `engine/vasicek.py`, `analysis/fit_vasicek.py`

**App surface:** tab = Scenario Lab; endpoint = /api/exhibits/credit_cycle

**Notes:** Cross-ref A10.

### B9 — DFAST macro scenario paths & satellite fit

**Topics:** DFAST severely-adverse/adverse/base paths, UER and HPI fan charts, satellite regression fit

**Theory anchor:** extends s9.1  (node ids: 0028)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/scenarios/fan_hpi_growth.png`
- `outputs/scenarios/fan_uer.png`
- `outputs/satellite/satellite_fit.png`

**Reports:** `outputs/scenarios/scenarios_report.md`, `outputs/satellite/satellite_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `engine/scenarios.py`, `engine/satellite.py`, `analysis/run_scenarios.py`

**App surface:** tab = Scenario Lab; endpoint = —

### B10 — Scenario ECL & the project's Jensen-gap exhibit

**Topics:** probability-weighted ECL vs single-path, 1.035x uplift measured on DCR book

**Theory anchor:** extends s9.2  (node ids: 0029)

**Fixtures:**
- `tests/fixtures/compute_scenarios.py` (full file — see Part B7 golden-fixtures roll-up)

**Exhibits:**
- `outputs/scenario_ecl/jensen_gap.png`
- `outputs/scenario_ecl/scenario_ecl_bars.png`
- `outputs/scenario_ecl/z_paths.png`

**Reports:** `outputs/scenario_ecl/scenario_ecl_report.md`

**Wiki pages:** `wiki/pages/scenario-layer.md`

**Code:** `analysis/scenario_exhibits.py`

**App surface:** tab = Scenario Lab; endpoint = /api/tools/reweight_scenarios

**Notes:** Cross-ref A12.

### B11 — Challenger scorecard: benchmarking & explainability

**Topics:** reliability diagram, PSI scores across time, permutation importance, PDP grid + double-trigger PDP, staging swap-set analysis

**Theory anchor:** extends s13  (node ids: 0046, 0047, 0048)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/challenger/reliability.png`
- `outputs/challenger/psi_scores.png`
- `outputs/challenger/perm_importance.png`
- `outputs/challenger/pdp_grid.png`
- `outputs/challenger/pdp_double_trigger.png`
- `outputs/challenger/staging_swap.png`

**Reports:** `outputs/challenger/scorecard.md`

**Wiki pages:** `wiki/pages/golden-fixtures.md`

**Code:** `analysis/fit_challenger.py`

**App surface:** tab = Model; endpoint = —

---

## Part C — Freddie Mac SFLLD rung-3 build

### C1 — SFLLD ingest & data-quality (Phase A)

**Topics:** 837k-loan panel, 17 vintages, real dates/states/losses, D90 absorbing state, 54-state macro merge, COVID-regime EDA

**Theory anchor:** extends s5.2/s5.4  (node ids: 0014)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/freddie/ingest/dq_report.md`, `outputs/freddie/gate_phaseA.md`

**Wiki pages:** `wiki/pages/sflld-panel.md`

**Code:** `freddie/ingest.py`, `freddie/build_panel.py`, `freddie/macro.py`

**App surface:** tab = Real Data; endpoint = /api/freddie/summary

**Notes:** Phase-A gate PASS.

### C2 — SFLLD EDA: vintage curves, roll-rates, state heterogeneity, COVID regime

**Topics:** vintage cumulative-default curves, roll-rate transition matrices, calendar-time series, state-level heterogeneity, realized LGD distribution

**Theory anchor:** extends s5  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/freddie/eda/exhibit1_vintage_curves.png`
- `outputs/freddie/eda/exhibit2_roll_rate_matrices.png`
- `outputs/freddie/eda/exhibit3_calendar_time_series.png`
- `outputs/freddie/eda/exhibit4_state_heterogeneity.png`
- `outputs/freddie/eda/exhibit5_realized_lgd.png`
- `outputs/freddie/macro/state_hpi_growth_2000_2025.png`
- `outputs/freddie/macro/state_uer_2000_2025.png`

**Reports:** `outputs/freddie/eda/eda_report.md`

**Wiki pages:** `wiki/pages/sflld-panel.md`

**Code:** `freddie/eda.py`

**App surface:** tab = Real Data; endpoint = —

### C3 — SFLLD hazard model (Phase B) & COVID-regime decision

**Topics:** hazard AUC 0.854/0.685, COVID=exclude decision (review overturn), seasoning curve, state UER effect, calibration by year

**Theory anchor:** extends s6.2  (node ids: 0020)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/freddie/hazard/calibration_by_year.png`
- `outputs/freddie/hazard/covid_calibration_comparison.png`
- `outputs/freddie/hazard/seasoning_curve.png`
- `outputs/freddie/hazard/state_uer_effect.png`

**Reports:** `outputs/freddie/hazard/hazard_report.md`, `outputs/freddie/gate_phaseB.md`

**Wiki pages:** `wiki/pages/sflld-models.md`

**Code:** `freddie/fit_hazard.py`, `tests/test_freddie_hazard.py`

**App surface:** tab = Real Data; endpoint = /api/freddie/hazard

**Notes:** The COVID-exclude decision was a review overturn — a Gotcha-box candidate about macro-regime handling.

### C4 — SFLLD LGD (realized) model

**Topics:** realized LGD on resolved workouts, severity by liquidation year

**Theory anchor:** extends s10  (node ids: 0034, 0035)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/freddie/lgd/severity_by_liq_year.png`

**Reports:** `outputs/freddie/lgd/lgd_report.md`

**Wiki pages:** `wiki/pages/sflld-models.md`

**Code:** `freddie/fit_lgd.py`, `freddie/lgd.py`, `tests/test_freddie_lgd.py`

**App surface:** tab = Real Data; endpoint = —

### C5 — SFLLD backtest: the 9.42x honesty exhibit

**Topics:** predicted vs realized default rate by vintage-quarter, 9.42x backtest ratio, out-of-time validation across 5 snapshot dates

**Theory anchor:** extends s13  (node ids: 0045, 0047)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/freddie/backtest/predicted_vs_realized_200712.png`
- `outputs/freddie/backtest/predicted_vs_realized_200912.png`
- `outputs/freddie/backtest/predicted_vs_realized_201512.png`
- `outputs/freddie/backtest/predicted_vs_realized_201912.png`
- `outputs/freddie/backtest/predicted_vs_realized_202112.png`

**Reports:** `outputs/freddie/backtest/backtest_report.md`

**Wiki pages:** `wiki/pages/sflld-models.md`

**Code:** `freddie/backtest.py`

**App surface:** tab = Real Data; endpoint = /api/freddie/backtest

**Notes:** The 9.42x figure (200912 GFC snapshot, presumably) is the single most striking honesty exhibit in the project — deserves a dedicated worked walkthrough of why backtest ratios blow up at a crisis vintage.

### C6 — SFLLD LSTM challenger & lift decomposition

**Topics:** sequence model on loan-month panel, lift over cloglog hazard baseline, calibration comparison, lift-split decomposition

**Theory anchor:** extends s6.2 (ML challenger)  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:**
- `outputs/freddie/lstm/calibration_comparison.png`
- `outputs/freddie/lstm/lift_split.png`

**Reports:** `outputs/freddie/lstm/lstm_report.md`

**Wiki pages:** `wiki/pages/sflld-models.md`

**Code:** `freddie/fit_lstm.py`, `freddie/lstm.py`

**App surface:** tab = Real Data; endpoint = —

**Notes:** Gate: 659/659 (Freddie Phase B gate).

---

## Part D — Agent, App, Deployment layers

### D1 — Agent layer: LangGraph router + Tier-1 deterministic tools

**Topics:** route decision (docs/analyze/reasoned/refusal), shock_macro, reweight_scenarios, rerun_ecl, decompose_waterfall, coherent-shock convention, number-guarded narration

**Theory anchor:** n/a (applied system)  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/mcp/README_section.md`

**Wiki pages:** `wiki/pages/agent-layer.md`

**Code:** `agent/graph.py`, `agent/tools_tier1.py`, `agent/mcp_server.py`

**App surface:** tab = Copilot; endpoint = /api/agent/ask, /api/agent/stream, /api/tools/*

**Notes:** narration_numbers_ok/_allowed_numbers in agent/graph.py implement the 'no hallucinated numbers' guardrail — worth a code-reading callout in the Agent chapter.

### D2 — Agent Tier-2 sandbox & Tier-3 retrieval

**Topics:** restricted-AST sandboxed code execution, child-process hardening, wiki/index Graph-RAG retrieval, REASONED route: labeled interpretation for conceptual Qs

**Theory anchor:** n/a  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/gate/reasoned_route_gate.md`

**Wiki pages:** `wiki/pages/agent-layer.md`, `wiki/pages/llm-wiki-skill.md`, `wiki/pages/pageindex-plus-skill.md`

**Code:** `agent/tools_tier2.py`, `agent/tier3_retrieval.py`

**App surface:** tab = Copilot; endpoint = /api/agent/interpret

**Notes:** SandboxViolation / _validate_ast / _harden_child in tools_tier2.py — the security model for LLM-written analysis code is itself a notable design pattern to document.

### D3 — App: FastAPI backend surface

**Topics:** /api/health, /api/ecl/summary, /api/ecl/waterfall, /api/exhibits/credit_cycle, /api/model/*, /api/policy/*, /api/freddie/*, /api/tools/*, /api/agent/*

**Theory anchor:** n/a  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `docs/api_contract.md`, `outputs/gate/appv2_gate_report.md`

**Wiki pages:** `wiki/pages/agent-layer.md`

**Code:** `app/api/main.py`

**App surface:** tab = all tabs; endpoint = see docs/api_contract.md (886 lines, full contract)

**Notes:** 886-line api_contract.md is the ground truth for every request/response shape used across tabs — the App chapter should render it as a navigable endpoint table, not reproduce verbatim.

### D4 — App: React UI (6 tabs) & design system

**Topics:** Executive Overview, The Model, Scenario Lab, Policy, Real Data (Freddie), Copilot, fintech design direction (judged redesign), waterfall fix

**Theory anchor:** n/a  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/design/FINAL_SPEC.md`, `outputs/design/fintech/design_spec.md`, `outputs/design/fintech/rationale.md`, `outputs/design/editorial/design_spec.md`, `outputs/design/editorial/rationale.md`, `outputs/design/terminal/design_spec.md`, `outputs/design/terminal/rationale.md`, `outputs/gate/uiv3_gate_report.md`

**Wiki pages:** `wiki/pages/project-overview.md`

**Code:** `app/ui/src/app.jsx`, `app/ui/src/tabs/ExecutiveTab.jsx`, `app/ui/src/tabs/ModelTab.jsx`, `app/ui/src/tabs/ScenarioLabTab.jsx`, `app/ui/src/tabs/PolicyTab.jsx`, `app/ui/src/tabs/FreddieTab.jsx`, `app/ui/src/tabs/CopilotTab.jsx`, `app/ui/src/api.js`, `app/ui/src/format.js`, `app/ui/src/numText.jsx`, `app/ui/src/palette.js`

**App surface:** tab = all 6 tabs; endpoint = —

**Notes:** 3 design directions were explored (fintech/editorial/terminal) before FINAL_SPEC.md; App guidebook chapter should show the judged comparison, not just the winner.

### D5 — Docker & deployment

**Topics:** multi-stage build (node:22-alpine UI -> python:3.13-slim runtime), non-root appuser, COPY whitelist strategy, .dockerignore lesson, HF Spaces port 7860

**Theory anchor:** n/a  (node ids: —)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/gate/mdd_freddie_gate.md`

**Wiki pages:** `wiki/pages/project-overview.md`

**Code:** `Dockerfile`, `.dockerignore`, `requirements.docker.txt`

**App surface:** tab = —; endpoint = —

**Docker touchpoints:** `Dockerfile`, `.dockerignore`, `requirements.docker.txt`

**Notes:** The dockerignore whitelist lesson (explicit COPY allowlist rather than broad copy + .dockerignore exclude, per git log + mdd_freddie_gate.md) is the key deployment Gotcha to reproduce with before/after.

### D6 — Model Documentation Deliverable (MDD) & governance close-out

**Topics:** structured model documentation, governance sign-off narrative, capital/disclosure alignment

**Theory anchor:** extends s14  (node ids: 0050, 0051, 0052, 0053)

**Fixtures:** none (theory-only / no worked numeric example)

**Exhibits:** none

**Reports:** `outputs/mdd/MDD.md`

**Wiki pages:** `wiki/pages/project-overview.md`, `wiki/pages/master-plan.md`, `wiki/pages/bootstrap-decisions.md`

**Code:** none

**App surface:** tab = —; endpoint = —

**Notes:** Closing chapter: walks MDD.md structurally as the worked instance of the governance/disclosure theory (A22).

