---
title: Knowledge Pipeline
type: module
status: active
aliases: [corpus pipeline, ingestion pipeline]
tags: [knowledge-layer, retrieval]
sources:
  - ../.claude/skills/pageindex-plus/SKILL.md
  - ../knowledge/code_map.md
code:
  - ../knowledge/preprocess_notes.py
links:
  uses: [pageindex-plus Skill]
  relates: [IFRS9 Study Notes, llm-wiki Skill]
---

# Knowledge Pipeline

The chain that turns `init_docs/ifrs9_credit_risk_notes.html` into the citable Tier-3 corpus:

1. **`knowledge/preprocess_notes.py`** (custom, one per-source pass) — extracts the 10 base64 PNG
   figures to `knowledge/sources/img/`, converts the 1.17 MB / 689-line HTML into structured
   Markdown (399 lines, one heading per line, stable anchors s1–s15), renumbers the stale §12–15
   H3s, and emits the worked-example boxes for fixture work.
2. **`ingest_notes.py`** (skill) → `knowledge/corpus/` with 10 figure cards; content-hash manifest
   makes re-runs incremental.
3. **`build_pageindex.py`** (skill) → `knowledge/index/` (23 pages, 69 nodes, every figure card a
   citable node).
4. **`caption_figures.py --apply knowledge/captions.json`** — 10 vision-written captions (agent
   view, no API key), kept in git so re-ingest can re-apply them; then rebuild the index.

## Hard-won lessons (do not rediscover)

- **`]` inside image alt text silently kills the figure card** (fig08's caption contained
  `$[0,1]$`): the md-image regex stops at the first `]`. `preprocess_notes.py` sanitizes brackets
  in alt text; full captions live in the italic line under each image. After ANY re-ingest, verify
  `grep -c '^### Figure' knowledge/corpus/*.md` returns 10.
- Naive ingestion of the raw HTML would collapse the textbook into a handful of 30-line synthetic
  pages — the pre-processing pass is mandatory, not cosmetic.
- Re-ingest discards applied captions (caption IDs depend on figure order) — always re-apply
  `knowledge/captions.json` and rebuild after re-ingesting.

Query: `pageindex_query.py knowledge/index --search "..."` (offline) or `--render` + `get_context`
for LLM tree-search; the module is importable in-process for the future `query_model_docs` tool.
