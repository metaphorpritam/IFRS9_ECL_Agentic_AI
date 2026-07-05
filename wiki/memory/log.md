# Session log

Append-only. One entry per working session — what was read, what changed, what's next. Newest at the bottom.

## 2026-07-05 05:49 UTC — tags: bootstrap, session

Phase -1 complete: git repo + hygiene + gitleaks 8.30.1 hook; skills installed to .claude/skills/ and verified; uv project (Python 3.13.13, pandas 3.0.3); notes HTML preprocessed (10 figs extracted, H3 renumbering, alt-text bracket fix after fig08 silently dropped); corpus ingested + indexed (23 pages/69 nodes) + 10 captions applied; retrieval smoke-tested. Fixtures: 8 compute_*.py recreated by 8 author + 8 adversarial-review agents, all clean, pytest 133/133 green. Wiki initialized with 9 pages. NEXT: user downloads (CRA mortgage.csv, DCR, DFAST/WEO) + API keys; then Day-1 PM panel load + EDA suite + first hazard model.

## 2026-07-05 05:53 UTC — tags: data, session

Data auto-fetch: CRA mortgage.csv extracted from mortgage_csv.rar via static 7zz (622,490 loan-month rows, macro pre-merged: hpi/gdp/uer_time) + lgd.csv + ratings.csv + hmeq.csv -> data/raw/. Fed DFAST 2026 Final Domestic CSVs (Historic 201 rows, Baseline + Severely Adverse 13 quarters 2026Q1-2029Q1) -> data/scenarios/. Deep Credit Risk now behind free Moodle login - operator action. Rung-1 PD modelling is unblocked.

## 2026-07-05 06:36 UTC — tags: secrets, keys, data

Operator pasted real API keys into .env.example (committed file) - moved to gitignored .env (chmod 600) before any commit, placeholders restored; keys never entered git history (gitleaks hook would also have blocked). All 4 keys validated live: OpenRouter (paid tier), Google AI Studio (50 models visible), FRED, HF (write, user Preetomsorkar). GROQ left empty - optional. DCR data validated: dcr_full.csv = 622,489 rows / 50k loans / 28 cols incl. res_time, payoff_time, lgd_time, recovery_res, state_orig_time, hpi_orig_time; dcr.csv = 62k-row sample. Docker Desktop installed via winget (UAC accepted) and launched; WSL integration pending first-run agreement.

## 2026-07-05 07:06 UTC — tags: day1, engine

Day 1 PM complete (6-agent workflow, all reviews clean/fixed): panel builder -> 621,736-row parquet with itemized 753-row waterfall (review: clean, zero defects); EDA suite 5 PASS/0 FAIL/1 INFO (seasoning hump age 10, worst vintages = HPI-peak cohorts 2.4x median, LGD bimodal, 9.8% LGD>1 kept raw); cloglog hazard engine (train AUC 0.748, OOT 0.661 on stress window, signs sane, net UER shock HR 1.28/pp, timing convention documented after review). Docker Desktop live in WSL. NEXT: Day 2 - engine/lgd.py (cure x severity), engine/ead.py, engine/staging.py (relative SICR; 30DPD backstop inert - no delinquency ladder), engine/ecl.py + movement decomposition, then GATE freeze (pytest + scan_code fingerprints).
