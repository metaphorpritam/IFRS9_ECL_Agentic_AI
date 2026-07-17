# Freddie Mac SFLLD -- data-quality report

Coverage note: vintages 2011, 2012, 2013, 2017 were never downloaded for this project (not an ingestion failure -- documented gap; see freddie/ingest.py MISSING_VINTAGES).

## Per-vintage row counts and event rates

| vintage | n_loans | n_loan_months (modeled) | d90 rate | prepay rate | other-terminal rate | censored rate | perf. window end |
|---|---|---|---|---|---|---|---|
| 2005 | 50000 | 3588153 | 0.1075 | 0.8721 | 0.0015 | 0.0189 | 2025-09 |
| 2006 | 50000 | 2833990 | 0.1411 | 0.8395 | 0.0033 | 0.0161 | 2025-09 |
| 2007 | 50000 | 2592669 | 0.1626 | 0.8158 | 0.0034 | 0.0182 | 2025-09 |
| 2008 | 50000 | 2224103 | 0.0914 | 0.8885 | 0.0023 | 0.0178 | 2025-09 |
| 2009 | 50000 | 3078747 | 0.0307 | 0.9231 | 0.0028 | 0.0434 | 2025-09 |
| 2010 | 50000 | 3363401 | 0.0316 | 0.9026 | 0.0016 | 0.0643 | 2025-09 |
| 2014 | 50000 | 3265018 | 0.0378 | 0.7921 | 0.0019 | 0.1683 | 2025-09 |
| 2015 | 50000 | 3317071 | 0.0400 | 0.7370 | 0.0007 | 0.2223 | 2025-09 |
| 2016 | 50000 | 3201194 | 0.0466 | 0.6840 | 0.0013 | 0.2681 | 2025-09 |
| 2018 | 50000 | 1901886 | 0.0536 | 0.7636 | 0.0018 | 0.1810 | 2025-09 |
| 2019 | 50000 | 1750978 | 0.0548 | 0.6756 | 0.0020 | 0.2676 | 2025-09 |
| 2020 | 50000 | 2306271 | 0.0208 | 0.3620 | 0.0018 | 0.6155 | 2025-09 |
| 2021 | 50000 | 2272716 | 0.0180 | 0.1709 | 0.0020 | 0.8091 | 2025-09 |
| 2022 | 50000 | 1766601 | 0.0302 | 0.1566 | 0.0041 | 0.8091 | 2025-09 |
| 2023 | 50000 | 1214980 | 0.0185 | 0.1801 | 0.0033 | 0.7981 | 2025-09 |
| 2024 | 50000 | 691421 | 0.0063 | 0.0937 | 0.0028 | 0.8972 | 2025-09 |
| 2025 | 37500 | 153366 | 0.0004 | 0.0179 | 0.0003 | 0.9814 | 2025-09 |

**Totals**: 837,500 loans, 39,522,565 modeled loan-months, overall D90 rate 0.0532, overall prepay rate 0.5893.

## Sentinel / missing-value profile (raw sentinel-code occurrences, pre-NaN-mapping)

Documented sentinel codes (see freddie/ingest.py docstring for the full list; credit_score=9999, dti=999, orig_ltv=999, cltv=999, mi_pct=999, num_units=99, num_borrowers=99, property_type=99, eltv=999, net_sale_proceeds='U', plus the categorical '9'/'7' Not-Available codes) are mapped to NaN on read. Counts below are per vintage, BEFORE mapping.

| vintage | channel | cltv | credit_score | dti | eltv | first_time_homebuyer_flag | loan_purpose | mi_cancellation_indicator | mi_pct | net_sale_proceeds | num_borrowers | num_units | occupancy_status | orig_ltv | property_type | property_valuation_method | special_eligibility_program |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2005 | 0 | 2 | 41 | 1532 | 60362 | 8 | 0 | 50000 | 0 | 0 | 11 | 1 | 0 | 2 | 1 | 50000 | 50000 |
| 2006 | 0 | 9 | 46 | 1069 | 53777 | 13 | 0 | 50000 | 0 | 0 | 19 | 0 | 0 | 9 | 0 | 50000 | 50000 |
| 2007 | 0 | 2 | 38 | 1124 | 60231 | 13 | 0 | 50000 | 0 | 0 | 23 | 0 | 0 | 1 | 0 | 50000 | 50000 |
| 2008 | 0 | 1 | 35 | 1026 | 50834 | 15 | 0 | 50000 | 0 | 0 | 23 | 0 | 0 | 1 | 0 | 50000 | 50000 |
| 2009 | 0 | 2 | 1 | 5462 | 60742 | 4 | 0 | 50000 | 2 | 0 | 8 | 0 | 0 | 2 | 0 | 50000 | 50000 |
| 2010 | 0 | 1 | 3 | 14662 | 80919 | 15 | 0 | 50000 | 1 | 0 | 1 | 0 | 0 | 1 | 0 | 50000 | 50000 |
| 2014 | 0 | 2 | 13 | 7309 | 199329 | 2 | 0 | 50000 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 50000 | 49973 |
| 2015 | 0 | 1 | 0 | 4020 | 228191 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 50000 | 49675 |
| 2016 | 0 | 0 | 0 | 2528 | 249159 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 50000 | 48942 |
| 2018 | 0 | 1 | 14 | 513 | 196910 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 48487 | 44331 |
| 2019 | 0 | 1 | 18 | 31 | 142899 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 44564 | 45317 |
| 2020 | 0 | 1 | 8 | 0 | 106774 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 47991 |
| 2021 | 0 | 0 | 6 | 5 | 109366 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 48191 |
| 2022 | 0 | 0 | 8 | 2 | 117107 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 46815 |
| 2023 | 0 | 0 | 12 | 3 | 99369 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 44122 |
| 2024 | 0 | 0 | 16 | 1 | 59978 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 43772 |
| 2025 | 0 | 0 | 18 | 0 | 20403 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 32229 |

## Validation messages

- 2005: 50 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2006: 38 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2007: 44 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2008: 26 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2009: 6 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2010: 4 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2014: 9 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2015: 13 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2016: 9 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2018: 10 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2019: 6 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2020: 4 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2021: 1 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2022: 4 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
- 2023: 8 loans have first_payment_date outside vintage+/-1 (informational -- expected construction-to-perm/seller-modified mortgages per User Guide footnote 3, within budget)
