---
title: llm-wiki Skill
type: entity
status: active
aliases: [llm-wiki, the wiki skill]
tags: [skill, knowledge-layer]
sources:
  - ../.claude/skills/llm-wiki/SKILL.md
links:
  relates: [pageindex-plus Skill, Knowledge Pipeline]
---

# llm-wiki Skill

Installed at `.claude/skills/llm-wiki/` (project-scoped, committed). Implements
compile-don't-retrieve: this wiki's pages, typed link graph, memory files, and health audit.
Five stdlib-only scripts: `wiki_init` / `wiki_log` / `wiki_graph` / `wiki_query` / `wiki_audit`.

## Roles in this project

1. **Build-time memory** — session ritual: compile pages → `wiki_graph.py wiki` →
   `wiki_log.py` → `wiki_audit.py wiki --strict` clean. Recovery: `index.md` → last 3 log
   entries → audit counts.
2. **The model development document** — pages maintained update-in-place with provenance ARE the
   MDD; export at the end is mechanical.
3. **Run-time Tier 3** — `wiki_query.py`'s deterministic lexical + k-hop retrieval becomes
   `query_model_docs` (import in-process; cache the graph object — it rebuilds per call).

## Conventions adopted here

- Stub pages (`status: draft`) for forward links, same session — keeps the audit clean while
  draft pages still mark work remaining, as the playbook's "link anyway" rule intends.
- Single writer: `wiki_log.py` rewrites whole files without locking — one session/agent writes at
  a time.
- Lexical retrieval needs curated `aliases:` — seed every concept page with domain synonyms
  (SICR ⟷ significant increase in credit risk, allowance ⟷ provision, …).
