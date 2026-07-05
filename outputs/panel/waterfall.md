# Panel eligibility waterfall — dcr_full.csv -> panel.parquet

Generated 2026-07-05T06:31:56+00:00 by `data/panel/build_panel.py`. Raw: **622,489 rows / 50,000 loans / 15,158 default rows / 26,589 payoff rows**.

| # | Step | Rows in | Rows dropped | Defaults lost | Payoffs lost | Rows out | Loans out | Reason |
|---|------|--------:|-------------:|--------------:|-------------:|---------:|----------:|--------|
| 1 | exact_duplicate_rows | 622,489 | 305 | 3 | 0 | 622,184 | 50,000 | Verbatim copies of an existing row (all 28 columns identical), incl. the doubled terminal default rows of ids 37067/37130/37792; dropped copies are duplicates of retained rows, so no information is lost. |
| 2 | id_collision_loans | 622,184 | 108 | 3 | 2 | 622,076 | 49,995 | 5 ids each contain two interleaved distinct loans (same-(id,time) rows with conflicting covariates, e.g. two different balance_orig/FICO tracks under id 3014, both defaulting); rows cannot be attributed to either loan, so the whole id is excluded. |
| 3 | same_quarter_status_conflict | 622,076 | 7 | 0 | 0 | 622,069 | 49,995 | Same-(id,time) pairs identical on every covariate but with one status-0 row shadowing a terminal row (e.g. id 37528 at t=51): the terminal row is kept so the event is preserved; the shadow is dropped. |
| 4 | post_terminal_truncation | 622,069 | 0 | 0 | 0 | 622,069 | 49,995 | Generic guard: any row after a loan's FIRST terminal event (default or payoff) is truncated — a loan leaves the at-risk set at its event. Expected 0 after steps 1-3 resolved the 4-loan anomaly; recorded to prove the check ran. |
| 5 | nonpositive_origination_balance_loans | 622,069 | 270 | 5 | 7 | 621,799 | 49,977 | 18 loans with balance_orig_time missing-coded as 0 (a static origination defect): original property value = balance_orig / (LTV_orig/100) = 0, so updated LTV and the double-trigger interaction are incomputable for every row of the loan; these are exactly the rows where the vendor's own LTV_time is NaN. |
| 6 | zero_balance_live_rows | 621,799 | 38 | 0 | 0 | 621,761 | 49,976 | Non-terminal (status 0) rows with balance_time <= 0: zero exposure on a live row is a missing-coded balance, not a real state — the history continues or the loan is censored at the prior quarter. Terminal payoff rows with balance 0 are KEPT (the zero balance IS the payoff; the row carries the competing-risk event). |
| 7 | nonpositive_current_note_rate_rows | 621,761 | 25 | 0 | 0 | 621,736 | 49,974 | Rows with interest_rate_time missing-coded as 0: the prepayment incentive (note rate - market rate) is incomputable; all such rows are status 0, so no events are lost. |

**Final panel:** 621,736 rows / 49,974 loans / 15,147 defaults / 26,580 payoffs (8,247 loans right-censored; train 421,761 rows, OOT 199,975 rows).

Note on step 1: the 3 'defaults lost' there are verbatim duplicate copies of retained default rows (ids 37067/37130/37792), not lost events. Steps 2 and 5 lose real events, counted above and reconciled in the self-checks. The raw file's documented '4 loans with rows after their default event' are exactly those three ids plus collision id 3014.

## Counted but retained (flagged, not dropped)

| Flag | Rows | Disposition |
|------|-----:|-------------|
| state_orig_time_missing | 2,829 | kept — state unused at this rung (national macros only; no state-level merge in scope) |
| orig_rate_missing_coded_zero | 89,730 | kept + flag orig_rate_missing — origination-rate snapshot missing-coded 0; current note rate is populated and drives the prepayment incentive |
| lag_warmup_rows_time_le_5 | 3,343 | kept + flag lag_warmup — uer_chg4_lag1 needs uer(t-5), undefined before t=6; excluded from no-NaN guarantee |
| within_loan_time_gaps | 1,257 | kept — non-consecutive quarter steps inside loans; macro lags repaired from the panel-internal time map so lag distance is always exact |

## Lag construction audit

Macro lags built inside the panel: `groupby(id).shift` on consecutive rows (agreement asserted to 1e-9), completed from the panel-internal time->macro map on loan first rows and within-loan gaps (1,257 gap steps). No lookahead: only t-k (k>=1) values are referenced.

| Lag column | Rows via groupby-shift | Completed from time map | NaN (warm-up) |
|------------|----------------------:|------------------------:|--------------:|
| uer_lag1 | 570,505 | 50,948 | 283 |
| uer_lag2 | 523,413 | 97,511 | 812 |
| gdp_lag1 | 570,505 | 50,948 | 283 |

Warm-up rows (time <= 5, `lag_warmup=1`): 3,343 — retained, excluded from the no-NaN guarantee on model columns.
