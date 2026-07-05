---
title: pageindex-plus Skill
type: entity
status: active
aliases: [pageindex, pageindex-plus]
tags: [skill, knowledge-layer, retrieval]
sources:
  - ../.claude/skills/pageindex-plus/SKILL.md
links:
  relates: [llm-wiki Skill, Knowledge Pipeline]
---

# pageindex-plus Skill

Installed at `.claude/skills/pageindex-plus/`. Vectorless PageIndex RAG over mixed documents
(PDF/PPTX/XLSX/DOCX/HTML/MD) with figure preservation: sources → Markdown corpus with figure
cards → hierarchical heading-tree index → LLM tree-search retrieval with page anchors. No
embeddings, no vector DB, no API calls inside the scripts — all LLM steps are agent hooks.

## Used here for

- The [[Knowledge Pipeline]] (corpus + index + captions) behind Tier-3 citations.
- **`scan_code.py`** — AST call graph + `--fingerprints` NONE/COSMETIC/STRUCTURAL change
  classification; after the Day-2 freeze this is the engine-gate tripwire (any post-gate
  `engine/*.py` edit flips STRUCTURAL and fails the wiki staleness audit).
- The HTML-notes build recipe (`references/html_notes_build.md` + `assets/`) — the export path for
  the final MDD/board-pack, with its recompute-every-number rule.

## Environment caveats

`assets/build_final.py` defaults output to `/mnt/user-data/outputs/` (claude.ai container path) —
always pass explicit output paths. PPTX rasterisation needs LibreOffice `soffice`, `--ocr` needs
tesseract — neither installed in this WSL2; not needed for the committed scope. Python-only call
graph: the Preact UI never appears in `scan_code.py` output.
