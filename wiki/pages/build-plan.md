---
title: Build Plan
type: source
status: active
aliases: [copilot plan, ifrs9_ecl_copilot_plan]
tags: [planning, methodology]
sources:
  - ../init_docs/ifrs9_ecl_copilot_plan.md
links:
  relates: [Master Plan, IFRS9 Study Notes]
---

# Build Plan

`../init_docs/ifrs9_ecl_copilot_plan.md` — the 600-line master build plan generated on web Claude
(mid-2026). The methodology reference; its pinned decisions stay pinned.

## Contents map

- **§0** operating instructions (surface prerequisites; ask-don't-assume; secrets hygiene; WSL2/9P
  environment facts) — **§1** architecture principles — **§2** data foundation (mortgage panel
  ladder CRA → DCR → Freddie SFLLD; 90 DPD re-flag; macro merge rules; DFAST/WEO/SPF scenarios) —
  **§3** EDA-as-verification (every chart has an expected shape) — **§4** classical engine (cloglog
  hazard + competing-risk prepayment, two-stage LGD, EAD/CCF, relative SICR + 30 DPD backstop, APC
  caveat, double trigger) — **§5** DL challenger (challenger-never-champion) — **§6** Vasicek/Z +
  satellite + Jensen (≈1.9×) — **§7** three-tier agent + refusal-as-a-feature — **§8** llm-wiki
  three roles — **§9** stack (LangGraph, FastAPI, Preact/Vite, provider matrix) — **§10** repo
  skeleton — **§11** 4-day schedule + stretch backlog — **§12–13** interview mapping, CV bullets —
  **§14** source directory (all URLs).

## Deviations recorded

Actual repo is `/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI` (plan assumed `/mnt/c/.../ecl-copilot`);
internal contradictions resolved in [[Bootstrap Decisions]]. Provider pricing/quota facts are dated
mid-2026 and must be re-verified in each console before demo day.
