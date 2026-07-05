---
title: Bootstrap Decisions
type: decision
status: active
aliases: [phase minus one decisions, reconciliation decisions]
tags: [decisions, bootstrap]
sources:
  - ../MASTER_PLAN.md
links:
  relates: [Master Plan, Build Plan]
---

# Bootstrap Decisions

Recorded 2026-07-05 (Phase −1). Rationale in `MASTER_PLAN.md` §3.6/§7; register entries in
`memory/decisions.md`. User accepted the §7 defaults with the right to flag changes — any change
gets a superseding entry.

## Contradiction resolutions (build plan internal)

1. **uv + Python 3.13 everywhere** — deploy image `python:3.13-slim` + `uv.lock`, not the §9
   sketch's 3.12/requirements.txt. (Resolved to 3.13.13 on this machine.)
2. **Tier-1 router = Gemma 4 31B (OpenRouter, paid)**; DeepSeek V4 Flash is the demo-day fallback
   in the failover chain, not a second default.
3. **Repo root = `/mnt/d/Python-UV/IFRS9_ECL_Agentic_AI`** — same 9P mitigations as the plan's
   assumed `/mnt/c` location.
4. **Wiki link hygiene**: stub pages (`status: draft`) instead of dangling links.
5. **Skill container paths**: always pass explicit output paths; claude.ai-only verbs unavailable.

## Accepted defaults (§7)

Freddie Mac SFLLD (rung-3 stretch) · HF Spaces Docker SDK (deploy) · Apache ECharts (charts) ·
LiteLLM (failover router) · scenario weights 50/25/25 with SPF anchoring documented · PD tail
level-off at last observed hazard · HPI forward-fill (rung 3) · MathJax CDN kept for standalone
notes only.

## Session decisions (2026-07-05)

- PyTorch deferred until the challenger phase (cu126 index; keeps bootstrap light).
- Corpus layout: `knowledge/{sources,corpus,index}` + `knowledge/captions.json` in git.
- Fixture precision rule: match within one unit of the notes' last displayed digit
  (notes truncate as well as round).
- gitleaks binary in `~/.local/bin` + grep fallback in the pre-commit hook.
