---
title: Project Overview
type: concept
status: active
aliases: [ifrs9 ecl copilot, the project]
tags: [hub, orientation]
sources:
  - ../MASTER_PLAN.md
links:
  relates: [Master Plan, Build Plan, IFRS9 Study Notes, Bootstrap Decisions]
  uses: [Knowledge Pipeline, llm-wiki Skill, pageindex-plus Skill]
---

# Project Overview

A placement-grade capstone: a classical **IFRS 9 ECL engine** (loan-month panel → PD → LGD → EAD →
staging → discounting → ECL), a deep-learning challenger, a **Vasicek/Z scenario layer**, and an
**agentic natural-language interface** (LangGraph, three tiers), deployed as a Preact + FastAPI app
in one Docker image on HF Spaces.

## Governing principles

1. Deterministic engine first, frozen behind a gate (end of Day 2) — no agentic code before the
   engine reproduces the [[Golden Fixtures]].
2. The LLM never does arithmetic — it routes, parameterises, narrates.
3. The wiki serves knowledge, never numbers.
4. Every scope cut is a documented simplification in `memory/decisions.md`.

## Where things are

- [[Master Plan]] — execution plan (`../MASTER_PLAN.md`); [[Build Plan]] — methodology reference.
- [[IFRS9 Study Notes]] — the domain corpus, indexed at `../knowledge/index/` via [[Knowledge Pipeline]].
- [[Golden Fixtures]] — `../tests/fixtures/compute_*.py`, the engine's acceptance tests.
- Committed 4-day scope: data rungs 1–2 (CRA + DCR), Tier-1 agent + refusal path only.

## Session recovery ritual

Read `index.md` → last 3 entries of `memory/log.md` → audit counts. Never re-orient by re-reading
raw sources.
