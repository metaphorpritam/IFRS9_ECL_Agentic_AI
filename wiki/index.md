---
title: IFRS9 ECL Copilot Wiki Index
type: concept
status: active
tags: [index]
---

# IFRS9 ECL Copilot Wiki — wiki index

The catalog of the wiki, and the FIRST thing read both by a fresh session and at query time.
Session ritual: this file → last 3 entries of `memory/log.md` → `.wiki/audit.json` counts.
Never re-orient by re-reading raw sources. Every page gets one line here.

## Concepts

- [[Project Overview]] — what this capstone is, the governing principles, where everything lives.

## Sources

- [[Master Plan]] — the execution plan (`MASTER_PLAN.md`): phases, gates, risks, accepted defaults.
- [[Build Plan]] — the 600-line methodology reference generated on web Claude; its decisions stay pinned.
- [[IFRS9 Study Notes]] — the 15-section textbook corpus; topic map and the numeric ground truth.

## Modules

- [[Agent Layer]] — LangGraph copilot + Tier-1 tools, LIVE public HF Space; refusal path; coherent-shock convention.
- [[Scenario Layer]] — Vasicek ρ=0.0227, DFAST paths, satellite, Jensen 1.035×, challenger scorecard; Day-3 gate PASS.
- [[Golden Fixtures]] — the 8 recreated `compute_*.py` scripts; 133/133 golden values pass; the engine freeze gate.
- [[Knowledge Pipeline]] — preprocess → ingest → index → caption chain; hard-won ingestion lessons.
- [[LGD Model]] — two-stage cure × severity on resolved workouts; excess-loss loading +0.0255, never clipped.
- [[EAD Model]] — contractual amortisation profiles + revolver CCF (€14.0m fixture); the double-counting rule.
- [[Staging Model]] — relative SICR verified to 1e-10; Stage 2 empty in calm / 75.8% in stress; threshold sensitivity exhibit.
- [[ECL Engine]] — the sum + movement decomposition; GATE PASSED 187/187, engine frozen 2026-07-05.
- [[Loan Panel]] — DCR → 621,736-row eligible loan-quarter panel; itemized waterfall; verified lags; train/OOT split.
- [[Hazard Model]] — cloglog competing-risk PD engine; AUC 0.748/0.661; seasoning hump reproduced; timing convention.

## Entities

- [[llm-wiki Skill]] — this wiki's engine; session ritual and conventions adopted here.
- [[pageindex-plus Skill]] — corpus ingestion, code fingerprints (freeze-gate tripwire), MDD export path.

## Concepts (contd.)

- [[Variable Dictionary]] — every variable: source → transformation → window → rationale → expected vs fitted sign.

## Decisions & open questions

- [[Bootstrap Decisions]] — Phase −1 contradiction resolutions + accepted §7 defaults.

Registers in `memory/decisions.md` and `memory/questions.md` (append via `wiki_log.py`; memory
files sit outside the graph by design).
