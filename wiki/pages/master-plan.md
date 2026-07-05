---
title: Master Plan
type: source
status: active
aliases: [MASTER_PLAN, execution plan]
tags: [planning]
sources:
  - ../MASTER_PLAN.md
links:
  derived-from: [Build Plan, IFRS9 Study Notes, llm-wiki Skill, pageindex-plus Skill]
  relates: [Bootstrap Decisions]
---

# Master Plan

`../MASTER_PLAN.md` (2026-07-05) is the execution layer over the [[Build Plan]]: it reconciles the
plan with the actual repo state and sequences the work. Synthesized from a parallel deep-read of all
four inputs plus an adversarial cross-check (12 conflicts, 16 gaps, 11 synergies, 12 risks).

## Structure

- **§1** input inventory · **§2** governing principles · **§3 Phase −1** bootstrap & reconciliation
  (git, skill install, uv, fixtures, corpus pre-processing, contradiction resolutions — see
  [[Bootstrap Decisions]]) · **§4 Phase 0** setup + operator checklist (data, keys) ·
  **§5** the 4-day committed path with gates · **§6** knowledge-layer wiring ·
  **§7** decision defaults · **§8** risk register · **§9** immediate next actions.

## Key synthesis findings

- The notes' 13 worked examples double as engine unit-test fixtures ([[Golden Fixtures]]).
- The freeze gate becomes machine-checkable: `scan_code.py --fingerprints` + `wiki_audit.py`
  stale-page errors trip on any post-gate engine edit.
- Tier-3 retrieval is nearly pre-built: `wiki_query.py` and `pageindex_query.py` are importable —
  wrap in-process as `query_model_docs`, no vector DB.
- The wiki pages, maintained update-in-place, ARE the model development document; the formal MDD is
  an export via the pageindex-plus HTML-notes pipeline.
