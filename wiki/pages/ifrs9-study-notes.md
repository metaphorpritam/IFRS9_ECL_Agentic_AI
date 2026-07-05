---
title: IFRS9 Study Notes
type: source
status: active
aliases: [the notes, credit risk notes, study notes]
tags: [domain-knowledge, corpus]
sources:
  - ../init_docs/ifrs9_credit_risk_notes.html
  - ../knowledge/sources/ifrs9_credit_risk_notes.md
  - ../knowledge/corpus/ifrs9_credit_risk_notes.md.md
links:
  relates: [Build Plan, Golden Fixtures]
  part-of: [Knowledge Pipeline]
---

# IFRS9 Study Notes

"IFRS 9 Credit Risk Modelling — Complete Study Notes": a self-contained 15-section HTML textbook
(~9,700 words, 10 matplotlib figures, 17 tables, 32 typed boxes), itself generated with the
[[pageindex-plus Skill]] HTML-notes recipe. **The primary domain corpus** — ingested (after
pre-processing by [[Knowledge Pipeline]]) into `../knowledge/index/` (23 pages, 69 nodes, all 10
figures captioned).

## Topic map (section → role in the build)

- **§1–2** standard, staging, default definition (90 DPD + UTP + materiality + probation), SICR —
  the staging-module requirements. **§3** hazard/survival ECL formula + worked 12m-vs-lifetime
  example — the engine spec. **§4** IFRS9 vs Basel IRB vs CECL. **§5** data blueprint (CRA/DCR/
  Freddie panels, FRED, merge recipe, the 90-day loss-lag and D180-vs-D90 traps) — the panel-builder
  spec. **§6–7** PD modelling (WOE/IV, hazards, transition matrices; Merton, Pluto–Tasche).
  **§8** Vasicek PIT/TTC. **§9** scenarios, satellite hygiene, Jensen, gross-up, overlays.
  **§10** two-stage LGD. **§11** realised losses, NCL, roll-rate bridge. **§12** EAD/CCF.
  **§13** validation pack. **§14** governance (BCBS d350, EBA GL/2017/06, SR 11-7, IFRS 7).
  **§15** learning path.

## Numeric ground truth

13 worked examples with verified values → recreated as [[Golden Fixtures]]. Known quirks: stale H3
numbers in §12–15 (fixed during conversion); MathJax CDN dependency; figure alt-text contained `]`
(see [[Knowledge Pipeline]] for the ingestion fix).
