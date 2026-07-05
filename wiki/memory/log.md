# Session log

Append-only. One entry per working session — what was read, what changed, what's next. Newest at the bottom.

## 2026-07-05 05:49 UTC — tags: bootstrap, session

Phase -1 complete: git repo + hygiene + gitleaks 8.30.1 hook; skills installed to .claude/skills/ and verified; uv project (Python 3.13.13, pandas 3.0.3); notes HTML preprocessed (10 figs extracted, H3 renumbering, alt-text bracket fix after fig08 silently dropped); corpus ingested + indexed (23 pages/69 nodes) + 10 captions applied; retrieval smoke-tested. Fixtures: 8 compute_*.py recreated by 8 author + 8 adversarial-review agents, all clean, pytest 133/133 green. Wiki initialized with 9 pages. NEXT: user downloads (CRA mortgage.csv, DCR, DFAST/WEO) + API keys; then Day-1 PM panel load + EDA suite + first hazard model.

## 2026-07-05 05:53 UTC — tags: data, session

Data auto-fetch: CRA mortgage.csv extracted from mortgage_csv.rar via static 7zz (622,490 loan-month rows, macro pre-merged: hpi/gdp/uer_time) + lgd.csv + ratings.csv + hmeq.csv -> data/raw/. Fed DFAST 2026 Final Domestic CSVs (Historic 201 rows, Baseline + Severely Adverse 13 quarters 2026Q1-2029Q1) -> data/scenarios/. Deep Credit Risk now behind free Moodle login - operator action. Rung-1 PD modelling is unblocked.
