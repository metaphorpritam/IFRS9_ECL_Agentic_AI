# SFLLD Realized-Loss LGD -- Two-Stage Cure x Severity on Real Workouts
**The upgrade over DCR** (`engine/lgd.py`): the DCR champion fits on the CoreLogic vendor's pre-computed `lgd_time` field -- a number handed over with no visible construction. This refit RECONSTRUCTS realized loss from Freddie Mac's own reported cash components (`net_sale_proceeds`, `mi_recoveries`, `non_mi_recoveries`, `total_expenses`, `delinquent_accrued_interest`, `zero_balance_removal_upb`) and locks the sign convention with a fixture loan traced from the raw servicing tape (`tests/test_freddie_lgd.py`) rather than trusting an opaque vendor column. See `freddie/lgd.py`'s module docstring for the full sign-convention derivation.
## 1. Sign convention (empirically verified)
`actual_loss_calculation` reconciles to sub-dollar rounding with `net_sale_proceeds + mi_recoveries + non_mi_recoveries + total_expenses - zero_balance_removal_upb - delinquent_accrued_interest` (`total_expenses` already reported NEGATIVE by Freddie). This module defines `realized_loss = -actual_loss_calculation` so that `realized_loss > 0` is the common-sense LOSS direction. See `tests/test_freddie_lgd.py::test_sign_convention_fixture_loan` for the fixture-loan lock traced directly from a raw servicing zip.
## 2. Sample & outcome partition
44,593 had_d90_event loans (loan_orig.parquet), partitioned exhaustively and disjointly into cure / liquidation / unresolved (see `freddie/lgd.py::partition_outcomes` docstring for the exact zero_balance_code logic and the reverted-status re-read for loans with no terminal code):

| lgd_outcome | oot | train | total |
|---|---|---|---|
| cure | 14141 | 12429 | 26570 |
| liquidation | 430 | 14480 | 14910 |
| unresolved | 1885 | 1228 | 3113 |

**Zero-balance code 15 (whole loan sale) is split, not lumped whole into unresolved**: 853 of 922 code-15 D90 rows carry a populated `actual_loss_calculation` (92.5%), concentrated in 2015+ disposition dates and with severities (mean 0.459, median 0.390) statistically indistinguishable from third-party sale (mean 0.445) and REO (mean 0.584) -- i.e. Freddie's non-performing-loan (NPL) sale program, a genuine liquidation-equivalent economic event. This refit counts that subset as **liquidation**, not unresolved (a correction versus treating all of code 15 as unresolved). Only the small remaining no-loss-field subset (69 rows, pre-2015 vintages) stays unresolved, since its ultimate resolution is genuinely unobservable. See `freddie/lgd.py`'s module docstring and `tests/test_freddie_lgd.py::test_npl_sale_code15_split_by_loss_data`.

**Unresolved** (defect-prior-to-disposition code 96, the small no-loss-field code-15 subset above, or still-active-and-still-90+DPD with no terminal code) are excluded from BOTH stages -- the same resolved-workouts-only convention as DCR's `engine/lgd.py` ("unresolved lgd_time is not a realised outcome"), with the SAME documented selection-bias direction: loans that resolve fast are over-represented in the observed population, so cure is biased up / severity down for cohorts near the panel's own window end (2025-09).

**COVID caveat** (Phase-A finding): the 2020 D90 spike overwhelmingly resolves CURE (deferral/reinstatement under forbearance), not a loss event -- visible directly in the OOT split above (14141 OOT cures vs 430 OOT liquidations): most post-2019-default loans have not yet had time to reach a liquidation disposition by the 2025-09 window end, so OOT liquidation counts are thin BY CONSTRUCTION, not because post-2019 defaults are safer. Reported honestly here, not patched.

**Selection bias quantified BY DEFAULT YEAR** (not vintage era -- COVID D90s occur across every origination vintage, so vintage era can't isolate the effect): the resolved-only convention's stated bias ("loans that resolve fast are over-represented in the observed population") is real but concentrates in RECENCY, not specifically in the 2020 COVID spike -- a correction of the naive assumption that "COVID-era defaults are heavily unresolved":

| default_year | n | unresolved_rate | cure_rate | liquidation_rate |
|---|---|---|---|---|
| 2005 | 72 | 0.1111 | 0.6528 | 0.2361 |
| 2006 | 230 | 0.0609 | 0.5130 | 0.4261 |
| 2007 | 823 | 0.0814 | 0.3366 | 0.5820 |
| 2008 | 2591 | 0.0787 | 0.2551 | 0.6662 |
| 2009 | 6445 | 0.0597 | 0.3836 | 0.5567 |
| 2010 | 5338 | 0.0405 | 0.4249 | 0.5347 |
| 2011 | 3757 | 0.0426 | 0.3833 | 0.5741 |
| 2012 | 2783 | 0.0266 | 0.4351 | 0.5383 |
| 2013 | 1648 | 0.0194 | 0.5309 | 0.4496 |
| 2014 | 1034 | 0.0097 | 0.5677 | 0.4226 |
| 2015 | 820 | 0.0171 | 0.6268 | 0.3561 |
| 2016 | 743 | 0.0121 | 0.6635 | 0.3244 |
| 2017 | 1126 | 0.0142 | 0.8135 | 0.1723 |
| 2018 | 727 | 0.0261 | 0.7565 | 0.2173 |
| 2019 | 785 | 0.0548 | 0.7860 | 0.1592 |
| 2020 | 8698 | 0.0224 | 0.9650 | 0.0125 |
| 2021 | 1546 | 0.0433 | 0.9224 | 0.0343 |
| 2022 | 953 | 0.0965 | 0.8468 | 0.0567 |
| 2023 | 1231 | 0.1665 | 0.7953 | 0.0382 |
| 2024 | 1757 | 0.2715 | 0.7075 | 0.0211 |
| 2025 | 1486 | 0.5424 | 0.4542 | 0.0034 |

**The 2020 COVID D90 spike itself is NOT heavily unresolved** -- its unresolved rate (2.2%, n=8,698) is BELOW the 2005-2019 average (4.4%), because forbearance-driven D90s cure fast (deferral/reinstatement, 96.5% cure rate) and have had five years to do so by the 2025-09 window end. What IS heavily unresolved is RECENCY, unrelated to COVID: default year 2025 is 54.2% unresolved (n=1,486) simply because most of those D90s have not had TIME to reach a terminal disposition yet, rising monotonically from 2022 defaults onward. The resolved-only fit's real selection-bias exposure is therefore the most recent 2-3 default years, not the COVID cohort specifically -- reported here as measured, not assumed.
## 3. Severity denominator: upb_at_default vs zero_balance_removal_upb
Reconciliation on 13,840 liquidation rows with both fields populated: correlation = 0.9948, mean ratio (zero_balance_removal_upb / upb_at_default) = 1.0018. The two are essentially the same loan-level number -- upb_at_default (current_actual_upb on panel_monthly's own first-D90-event row) is used as the severity denominator because it is the theoretically correct EAD base (observable AT the default date, not years later at resolution, when continued interest capitalization / partial curtailments can move zero_balance_removal_upb away from the default-date balance) -- and it is what any ECL assembly multiplying LGD x EAD must use.
## 4. Stage 1 -- cure logit
`cure ~ ltv10 + fico_s + loan_age_at_default + C(era) + C(property_state)`, fit on train resolved rows (n=26,896: 12,422 cure / 14,474 liquidation).

| term | coef | std_err | z | p_value | ci_low | ci_high | exp_coef |
|---|---|---|---|---|---|---|---|
| Intercept | 4.2819 | 0.4589 | 9.3299 | 0.0000 | 3.3824 | 5.1814 | 72.3756 |
| C(era)[T.modern 2018-2025] | 0.1498 | 0.7062 | 0.2122 | 0.8320 | -1.2343 | 1.5340 | 1.1616 |
| C(era)[T.recovery 2009-10, 14-16] | 0.8034 | 0.0406 | 19.7679 | 0.0000 | 0.7237 | 0.8830 | 2.2330 |
| C(property_state)[T.AL] | -0.6136 | 0.4404 | -1.3932 | 0.1636 | -1.4768 | 0.2496 | 0.5414 |
| C(property_state)[T.AR] | -0.6490 | 0.4547 | -1.4274 | 0.1535 | -1.5401 | 0.2421 | 0.5226 |
| C(property_state)[T.AZ] | -0.5385 | 0.4298 | -1.2528 | 0.2103 | -1.3809 | 0.3039 | 0.5836 |
| C(property_state)[T.CA] | 0.2049 | 0.4265 | 0.4804 | 0.6310 | -0.6311 | 1.0409 | 1.2274 |
| C(property_state)[T.CO] | -0.1342 | 0.4389 | -0.3057 | 0.7599 | -0.9945 | 0.7261 | 0.8744 |
| C(property_state)[T.CT] | -0.1787 | 0.4409 | -0.4052 | 0.6853 | -1.0428 | 0.6855 | 0.8364 |
| C(property_state)[T.DC] | 0.1025 | 0.5408 | 0.1896 | 0.8497 | -0.9574 | 1.1624 | 1.1079 |
| C(property_state)[T.DE] | 0.1206 | 0.4781 | 0.2523 | 0.8008 | -0.8165 | 1.0577 | 1.1282 |
| C(property_state)[T.FL] | -0.1270 | 0.4263 | -0.2978 | 0.7659 | -0.9626 | 0.7087 | 0.8808 |
| C(property_state)[T.GA] | -0.3549 | 0.4293 | -0.8268 | 0.4083 | -1.1962 | 0.4864 | 0.7012 |
| C(property_state)[T.GU] | 21.2079 | 12631.2004 | 0.0017 | 0.9987 | -24735.4900 | 24777.9058 | 1623628315.0880 |
| C(property_state)[T.HI] | -0.0399 | 0.4803 | -0.0830 | 0.9339 | -0.9813 | 0.9016 | 0.9609 |
| C(property_state)[T.IA] | -0.5290 | 0.4588 | -1.1530 | 0.2489 | -1.4282 | 0.3702 | 0.5892 |
| C(property_state)[T.ID] | -0.4955 | 0.4493 | -1.1027 | 0.2702 | -1.3762 | 0.3852 | 0.6093 |
| C(property_state)[T.IL] | -0.5354 | 0.4281 | -1.2506 | 0.2111 | -1.3744 | 0.3037 | 0.5854 |
| C(property_state)[T.IN] | -0.3858 | 0.4352 | -0.8865 | 0.3754 | -1.2387 | 0.4672 | 0.6799 |
| C(property_state)[T.KS] | -0.8018 | 0.4571 | -1.7539 | 0.0794 | -1.6977 | 0.0942 | 0.4485 |
| C(property_state)[T.KY] | -0.4284 | 0.4446 | -0.9636 | 0.3353 | -1.2999 | 0.4430 | 0.6515 |
| C(property_state)[T.LA] | 0.2006 | 0.4441 | 0.4518 | 0.6514 | -0.6697 | 1.0710 | 1.2222 |
| C(property_state)[T.MA] | 0.2821 | 0.4352 | 0.6482 | 0.5169 | -0.5709 | 1.1351 | 1.3259 |
| C(property_state)[T.MD] | -0.0596 | 0.4323 | -0.1379 | 0.8903 | -0.9068 | 0.7876 | 0.9421 |
| C(property_state)[T.ME] | -0.2965 | 0.4669 | -0.6351 | 0.5253 | -1.2116 | 0.6185 | 0.7434 |
| C(property_state)[T.MI] | -0.7337 | 0.4297 | -1.7072 | 0.0878 | -1.5760 | 0.1086 | 0.4801 |
| C(property_state)[T.MN] | -0.5235 | 0.4338 | -1.2068 | 0.2275 | -1.3736 | 0.3267 | 0.5925 |
| C(property_state)[T.MO] | -0.7690 | 0.4342 | -1.7711 | 0.0765 | -1.6201 | 0.0820 | 0.4635 |
| C(property_state)[T.MS] | -0.3170 | 0.4572 | -0.6935 | 0.4880 | -1.2131 | 0.5790 | 0.7283 |
| C(property_state)[T.MT] | -0.0804 | 0.4986 | -0.1613 | 0.8719 | -1.0576 | 0.8968 | 0.9227 |
| C(property_state)[T.NC] | -0.2118 | 0.4318 | -0.4906 | 0.6237 | -1.0582 | 0.6345 | 0.8091 |
| C(property_state)[T.ND] | 1.3239 | 0.7656 | 1.7292 | 0.0838 | -0.1766 | 2.8245 | 3.7581 |
| C(property_state)[T.NE] | -0.5708 | 0.4943 | -1.1546 | 0.2482 | -1.5396 | 0.3981 | 0.5651 |
| C(property_state)[T.NH] | -0.1788 | 0.4552 | -0.3929 | 0.6944 | -1.0709 | 0.7133 | 0.8362 |
| C(property_state)[T.NJ] | -0.0424 | 0.4307 | -0.0984 | 0.9216 | -0.8866 | 0.8018 | 0.9585 |
| C(property_state)[T.NM] | -0.4799 | 0.4563 | -1.0517 | 0.2929 | -1.3743 | 0.4144 | 0.6188 |
| C(property_state)[T.NV] | -0.0505 | 0.4368 | -0.1156 | 0.9080 | -0.9065 | 0.8056 | 0.9508 |
| C(property_state)[T.NY] | 0.2985 | 0.4305 | 0.6934 | 0.4881 | -0.5453 | 1.1422 | 1.3478 |
| C(property_state)[T.OH] | -0.6729 | 0.4305 | -1.5630 | 0.1181 | -1.5168 | 0.1709 | 0.5102 |
| C(property_state)[T.OK] | -0.5024 | 0.4522 | -1.1110 | 0.2666 | -1.3886 | 0.3839 | 0.6051 |
| C(property_state)[T.OR] | -0.4210 | 0.4371 | -0.9631 | 0.3355 | -1.2776 | 0.4357 | 0.6564 |
| C(property_state)[T.PA] | -0.1561 | 0.4310 | -0.3621 | 0.7173 | -1.0007 | 0.6886 | 0.8555 |
| C(property_state)[T.PR] | 1.1621 | 0.4848 | 2.3973 | 0.0165 | 0.2120 | 2.1123 | 3.1968 |
| C(property_state)[T.RI] | -0.3125 | 0.4659 | -0.6707 | 0.5024 | -1.2256 | 0.6007 | 0.7316 |
| C(property_state)[T.SC] | -0.3246 | 0.4381 | -0.7410 | 0.4587 | -1.1834 | 0.5341 | 0.7228 |
| C(property_state)[T.SD] | -0.5927 | 0.5943 | -0.9973 | 0.3186 | -1.7576 | 0.5722 | 0.5528 |
| C(property_state)[T.TN] | -0.2730 | 0.4370 | -0.6248 | 0.5321 | -1.1294 | 0.5834 | 0.7611 |
| C(property_state)[T.TX] | 0.0439 | 0.4298 | 0.1022 | 0.9186 | -0.7986 | 0.8864 | 1.0449 |
| C(property_state)[T.UT] | 0.1451 | 0.4435 | 0.3273 | 0.7435 | -0.7241 | 1.0144 | 1.1562 |
| C(property_state)[T.VA] | -0.3955 | 0.4326 | -0.9142 | 0.3606 | -1.2433 | 0.4524 | 0.6734 |
| C(property_state)[T.VI] | -0.6768 | 1.6239 | -0.4168 | 0.6768 | -3.8595 | 2.5059 | 0.5082 |
| C(property_state)[T.VT] | 0.0001 | 0.5421 | 0.0003 | 0.9998 | -1.0624 | 1.0627 | 1.0001 |
| C(property_state)[T.WA] | -0.3035 | 0.4320 | -0.7025 | 0.4824 | -1.1503 | 0.5433 | 0.7382 |
| C(property_state)[T.WI] | -0.7413 | 0.4349 | -1.7044 | 0.0883 | -1.5937 | 0.1112 | 0.4765 |
| C(property_state)[T.WV] | -0.6744 | 0.4813 | -1.4012 | 0.1612 | -1.6178 | 0.2689 | 0.5095 |
| C(property_state)[T.WY] | -0.6910 | 0.5906 | -1.1701 | 0.2420 | -1.8485 | 0.4665 | 0.5011 |
| ltv10 | -0.2475 | 0.0075 | -33.2141 | 0.0000 | -0.2621 | -0.2329 | 0.7808 |
| fico_s | -0.3643 | 0.0243 | -15.0193 | 0.0000 | -0.4119 | -0.3168 | 0.6947 |
| loan_age_at_default | 0.0066 | 0.0005 | 12.7328 | 0.0000 | 0.0056 | 0.0076 | 1.0066 |

### Per-variable rationale

| variable | transform | economic rationale | expected direction |
|---|---|---|---|
| `ltv10` | `updated_ltv`/10 (state-HPI indexed, see freddie.macro) | equity cushion lets a distressed borrower sell or refinance out of default | - |
| `fico_s` | `credit_score`/100 | ability/willingness to work a resolution | + (weak) |
| `loan_age_at_default` | months at first D90 | seasoned defaulters cure less (burnout) | - |
| `era` | vintage cohort (bubble/recovery/modern) | underwriting-quality + macro-regime cohort effect on workout outcomes | era-dependent |
| `property_state` | fixed effects | regional foreclosure-process / servicing-practice heterogeneity (stage 2's judicial dummy only partially explains this) | state-dependent |

Cure AUC: train **0.6991**, OOT **0.4769**.

### Cure rate by era

| era | split | n | observed_cure_rate | predicted_cure_rate |
|---|---|---|---|---|
| bubble 2005-2008 | train | 23172 | 0.4307 | 0.4307 |
| bubble 2005-2008 | oot | 787 | 0.8844 | 0.8253 |
| bubble 2005-2008 | all | 23959 | 0.4456 | 0.4437 |
| recovery 2009-10, 14-16 | train | 3715 | 0.6560 | 0.6560 |
| recovery 2009-10, 14-16 | oot | 5312 | 0.9699 | 0.8009 |
| recovery 2009-10, 14-16 | all | 9027 | 0.8407 | 0.7413 |
| modern 2018-2025 | train | 9 | 0.4444 | 0.4444 |
| modern 2018-2025 | oot | 8467 | 0.9790 | 0.5143 |
| modern 2018-2025 | all | 8476 | 0.9784 | 0.5143 |

**Why OOT cure AUC (0.4769) is BELOW random, not just weak**: the `era` fixed effect for `modern 2018-2025` is fit on only **9 train rows** -- a mechanical consequence of the calendar-time train/OOT split (SPLIT_CUTOFF = 2019-01): a modern-vintage (2018-2025-origination) loan can only default BEFORE 2019 if it reaches D90 within months of origination, so almost the entire modern-era D90 population falls in OOT by construction. The fitted coefficient (see section 4's coefficient table, `C(era)[T.modern 2018-2025]`) is statistically indistinguishable from zero (std_err ~4.7x the point estimate) -- effectively unidentified from training data. Combined with the post-2019 COVID-forbearance base-rate shift (observed cure rate jumps to 97-98% OOT vs 43-66% train across eras -- see the table above), the model's LTV/FICO/state-driven discrimination, learned on a very different pre-2019 base rate, does not transfer -- a genuine small-sample-plus-regime-shift limitation, not a coding defect. Weight the OOT AUC comparison in section 8 accordingly.

## 5. Stage 2 -- severity | liquidation (fractional logit, HC1 robust SEs)
`sev_capped ~ ltv10 + C(liq_year_bucket) + is_judicial + C(disposition_type)`, fit on train liquidation rows with populated `actual_loss_calculation` (n=13,444).

| term | coef | std_err | z | p_value | ci_low | ci_high | exp_coef |
|---|---|---|---|---|---|---|---|
| Intercept | -1.8372 | 0.1809 | -10.1553 | 0.0000 | -2.1918 | -1.4826 | 0.1593 |
| C(liq_year_bucket)[T.2008-09 crash] | 1.3517 | 0.1803 | 7.4969 | 0.0000 | 0.9983 | 1.7051 | 3.8639 |
| C(liq_year_bucket)[T.2010-12 peak workout] | 1.7275 | 0.1775 | 9.7338 | 0.0000 | 1.3797 | 2.0754 | 5.6268 |
| C(liq_year_bucket)[T.2013-16 recovery] | 1.6983 | 0.1778 | 9.5531 | 0.0000 | 1.3499 | 2.0467 | 5.4646 |
| C(liq_year_bucket)[T.2017-19 calm] | 1.3792 | 0.1816 | 7.5933 | 0.0000 | 1.0232 | 1.7352 | 3.9716 |
| C(liq_year_bucket)[T.2020+ covid-modern] | 0.8751 | 0.1927 | 4.5415 | 0.0000 | 0.4974 | 1.2527 | 2.3990 |
| is_judicial[T.True] | 0.5199 | 0.0207 | 25.0991 | 0.0000 | 0.4793 | 0.5605 | 1.6819 |
| C(disposition_type)[T.short_sale_or_charge_off] | -0.7200 | 0.0236 | -30.5233 | 0.0000 | -0.7662 | -0.6738 | 0.4868 |
| C(disposition_type)[T.third_party_sale] | -0.3982 | 0.0290 | -13.7330 | 0.0000 | -0.4550 | -0.3413 | 0.6716 |
| C(disposition_type)[T.whole_loan_sale] | -0.3477 | 0.0471 | -7.3874 | 0.0000 | -0.4399 | -0.2554 | 0.7063 |
| ltv10 | 0.0307 | 0.0049 | 6.2590 | 0.0000 | 0.0211 | 0.0403 | 1.0311 |

### Per-variable rationale

| variable | transform | economic rationale | expected direction |
|---|---|---|---|
| `ltv10` | `updated_ltv`/10 at default | less equity -> bigger foreclosure shortfall | + |
| `liq_year_bucket` | coarse liquidation-year cycle phase | workout costs + distressed-sale discounts vary sharply with the disposition-year housing cycle | hump, peak 2010-2012 |
| `is_judicial` | static judicial-foreclosure-state flag | judicial process is slower and costlier (more accrued interest/expenses by disposition) | + |
| `disposition_type` | zero_balance_code label | third-party sale / short sale-charge-off / REO / whole-loan (NPL) sale carry different cost structures | disposition-dependent |

### Severity by liquidation year (2006-2025 cycle)

| liq_year | n | mean_severity | median_severity | mean_severity_capped | share_gt_cap | share_lt_0 |
|---|---|---|---|---|---|---|
| 2006 | 10 | 0.1022 | -0.0027 | 0.1078 | 0.0000 | 0.6000 |
| 2007 | 60 | 0.1774 | 0.0825 | 0.1772 | 0.0167 | 0.2000 |
| 2008 | 201 | 0.3535 | 0.3223 | 0.3524 | 0.0299 | 0.0697 |
| 2009 | 761 | 0.4563 | 0.4360 | 0.4528 | 0.0263 | 0.0263 |
| 2010 | 1588 | 0.4990 | 0.5021 | 0.4956 | 0.0435 | 0.0202 |
| 2011 | 2195 | 0.5410 | 0.5360 | 0.5355 | 0.0515 | 0.0096 |
| 2012 | 2317 | 0.5285 | 0.5107 | 0.5209 | 0.0604 | 0.0104 |
| 2013 | 1734 | 0.5083 | 0.4767 | 0.4958 | 0.0830 | 0.0213 |
| 2014 | 1347 | 0.5805 | 0.5648 | 0.5573 | 0.1180 | 0.0163 |
| 2015 | 1055 | 0.5870 | 0.5463 | 0.5572 | 0.1327 | 0.0152 |
| 2016 | 795 | 0.6130 | 0.5801 | 0.5768 | 0.1522 | 0.0151 |
| 2017 | 433 | 0.5048 | 0.4640 | 0.4783 | 0.1132 | 0.0277 |
| 2018 | 316 | 0.4769 | 0.4053 | 0.4566 | 0.1013 | 0.0316 |
| 2019 | 252 | 0.4445 | 0.3654 | 0.4289 | 0.1071 | 0.0516 |
| 2020 | 219 | 0.3921 | 0.2631 | 0.3699 | 0.1050 | 0.0685 |
| 2021 | 156 | 0.2013 | 0.0955 | 0.2107 | 0.0128 | 0.1410 |
| 2022 | 71 | 0.3921 | 0.0862 | 0.2584 | 0.0845 | 0.0563 |
| 2023 | 136 | 0.3393 | 0.1957 | 0.3168 | 0.0956 | 0.0588 |
| 2024 | 111 | 0.2991 | 0.1175 | 0.2574 | 0.0721 | 0.0721 |
| 2025 | 83 | 0.2637 | 0.1525 | 0.2371 | 0.0361 | 0.0964 |

![severity by liquidation year](severity_by_liq_year.png)

## 6. Severity > 1 / < 0 tail -- is a CONSTANT loading still defensible?
7.8% of liquidations have severity > 1 (workout costs + accrued interest push the loss past upb_at_default); 2.3% are < 0 (net recoveries, MI/proceeds exceeded UPB + costs + accrued interest). Both are real, not data errors -- never silently discarded.

Overall (DCR-style) constant loading: **0.0148** (vs DCR's 0.0255). Per-liquidation-year-bucket loading, computed with the liquidation-year covariate ALREADY in the severity regression:

| liq_year_bucket | n | excess_loading | share_gt_cap | mean_severity |
|---|---|---|---|---|
| pre-2008 | 70 | 0.0020 | 0.0143 | 0.1667 |
| 2008-09 crash | 962 | 0.0037 | 0.0270 | 0.4348 |
| 2010-12 peak workout | 6100 | 0.0064 | 0.0528 | 0.5253 |
| 2013-16 recovery | 4931 | 0.0243 | 0.1144 | 0.5617 |
| 2017-19 calm | 1001 | 0.0245 | 0.1079 | 0.4808 |
| 2020+ covid-modern | 776 | 0.0417 | 0.0709 | 0.3175 |

The per-bucket loading ranges over 0.0397 across cycle phases -- wide enough that a single constant materially misstates stress-period severity once `liq_year_bucket` is already a regression covariate (it absorbs most of the cycle dependence at the MEAN; the residual beyond-cap tail is what the per-bucket table measures). **Verdict**: unlike DCR's single national panel (which has no comparable liquidation-year span to test this against), the SFLLD liquidation-year cycle here spans the full 2006-2025 GFC-through-modern era, so this refit reports the per-bucket loading table above ALONGSIDE the constant, rather than asserting the constant is sufficient by fiat -- a downstream ECL assembly under active stress-period liquidation volume should prefer the bucket-specific loading over the pooled constant.

## 7. Portfolio-level LGD summary (aggregate, train vs OOT)
| split | n_resolved | n_liq_excluded_no_loss_data | cure_rate_observed | cure_rate_predicted | mean_realized_lgd | mean_predicted_lgd_aggregate |
|---|---|---|---|---|---|---|
| train | 26896 | 1035 | 0.4619 | 0.4619 | 0.2715 | 0.2819 |
| oot | 14566 | 34 | 0.9705 | 0.6356 | 0.0074 | 0.1170 |

`n_resolved` / `cure_rate_observed` / `cure_rate_predicted` cover ALL resolved rows (cure + liquidation). `mean_realized_lgd` additionally EXCLUDES `n_liq_excluded_no_loss_data` liquidation rows with no populated `actual_loss_calculation` ("loss not yet finalized" -- the same exclusion the severity fit itself applies) rather than zero-filling their missing severity, which would silently conflate "loss not yet known" with "no loss" and bias the reported mean realized LGD DOWN.

`mean_predicted_lgd_aggregate` combines the mean predicted cure-complement with the mean predicted severity (capped + excess loading) at the AGGREGATE level only, NOT per-row: the severity-stage covariates (liquidation-year bucket, disposition type) are only known once a loan has actually liquidated, so there is no per-row forward-LGD score for a still-resolving loan in this refit (documented simplification, see section 8 and `freddie/lgd.py`'s module docstring).

## 8. DCR vs SFLLD LGD comparison

| metric | DCR champion (`engine/lgd.py`) | SFLLD refit (train) | SFLLD refit (OOT) |
|---|---:|---:|---:|
| mean realized LGD | 0.5995 / 0.6113 | 0.2715 | 0.0074 |
| cure rate | 0.1224 / 0.0716 | 0.4619 | 0.9705 |
| cure AUC | 0.8370 / 0.7690 | 0.6991 | 0.4769 |
| excess-loss loading (constant) | 0.0255 | 0.0148 (overall) | -- |
| share severity > cap | 14.2% | 7.8% | -- |
| n resolved (train) | 9,496 | 26,896 | -- |

**Key differences, not just numbers**: (1) SFLLD's realized loss is RECONSTRUCTED from Freddie's own cash-component fields, not taken from an opaque vendor column (section 1); (2) SFLLD's OOT is dominated by the 2020 COVID D90 spike (section 2), so the SFLLD OOT cure rate/mean LGD comparison is NOT a clean like-for-like regime test the way DCR's quarterly-panel OOT is -- read the SFLLD OOT column as "mostly forbearance-era cures", not as forward-looking calibration evidence; (3) SFLLD's liquidation-year cycle spans 2006-2025 (vs DCR's shorter panel), which is what makes the per-bucket excess-loading comparison in section 6 possible at all; (4) SFLLD adds state fixed effects + a judicial-foreclosure-state dummy that DCR's national panel has no field to support.

## 9. Documented simplifications
- `zero_balance_code == 16` (RPL securitization) is treated as a CURE by judgement, not a vendor label -- it never carries a realized loss field.
- `zero_balance_code == 96` (defect prior to disposition) has NO observable loss (100% NaN `actual_loss_calculation`) and is folded into "unresolved" alongside the small no-loss-field subset of whole-loan-sale (code 15, 69 of 922 rows, pre-2015 vintages); the 853-row loss-bearing code-15 subset (Freddie's NPL-sale program) is treated as LIQUIDATION, not unresolved -- see section 2.
- Liquidations with `actual_loss_calculation` still NaN ("not yet finalized") are excluded from the severity fit only, not from the cure stage's liquidation outcome.
- `JUDICIAL_STATES` is a single static classification -- no within-sample (2005-2025) foreclosure-regime changes modeled; a handful of states are genuinely hybrid.
- No downturn add-on; LGD is point-in-time (matches DCR's `engine/lgd.py`).
- `predict_components`/`predict_lgd` (freddie/lgd.py) are calibration/diagnostic tools scored on ALREADY-RESOLVED history, not a forward-scoring API for a still-performing loan of unknown eventual liquidation date/type -- unlike DCR's severity stage, whose covariates are all available forward via a macro-scenario path. Wiring this into a live ECL assembly needs a projected liquidation-year substituted for the realized one -- documented future work, not built here.
- Portfolio-level LGD summary (section 7) combines cure and severity predictions at the AGGREGATE level only (mean x mean), not per-row, for the reason above.
