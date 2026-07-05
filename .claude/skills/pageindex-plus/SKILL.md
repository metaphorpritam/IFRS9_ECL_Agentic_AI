---
name: pageindex-plus
description: >-
  Build, grow, and query a vectorless PageIndex RAG that captures TEXT and VISUALS
  (images, graphs, plots, flowcharts, charts) from a folder of mixed sources - PDFs,
  PowerPoint, Excel, Word, Markdown, HTML, scanned/handwritten notes — then render
  incrementally-growing HTML study notes from it without reloading sources into context. Use
  whenever the user wants a reusable knowledge base / "second brain" / handoff memory over
  documents; wants Claude (now or in a later Claude Code / API session) to reason over,
  fact-check, or cite long PDFs/decks/workbooks by exact page, slide, or sheet; building
  or topping-up study notes from materials that arrive over time; mentions PageIndex,
  vectorless retrieval, anti-hallucination grounding, or adding more sources to existing
  notes. Especially apt when sources contain figures text-only extraction would lose, or the
  corpus is too large to hold in context. Bundles incremental visual-aware ingest,
  LLM-vision caption hook, code cataloguing, build, query, and an HTML-notes recipe.
---

# PageIndex Plus — visual-aware, incremental RAG → HTML notes

A **vectorless, reasoning-based RAG** (no embeddings, no vector DB) that — unlike plain
text RAG — preserves the **figures** in your sources. A mixed corpus (PDF, PPTX, XLSX,
DOCX, Markdown, HTML) is turned into a hierarchical tree (titles + extractive summaries +
page/slide/sheet anchors) over a per-page text store, **plus** extracted figure assets
(PNG) recorded as anchored "figure cards." Retrieval is an LLM reading the tree and
*reasoning* about which nodes to open — then reading those nodes' text and pulling the
relevant figure files, with traceable citations.

It is built for the way materials actually arrive: **incrementally**. Ingest is
content-hashed and idempotent, so you point it at a growing folder and re-run; only new or
changed files are processed. Then you grow your HTML notes the same way — adding sections
for new sources without rebuilding the whole document.

This skill combines three concerns that are painful to do well separately:
1. **Vectorless indexing** (the PageIndex tree + page store) — small, inspectable, durable.
2. **Visual extraction** (the hard part text RAG skips) — embedded rasters, vector charts,
   flowcharts, slide pictures, Excel charts/images, scanned-page figures.
3. **HTML notes generation** — the downstream consumer that renders grounded, figure-rich,
   numerically-verified notes from the index without re-reading sources.

## When to use

- Build a searchable index / "second brain" / long-running memory over a folder of mixed
  notes — and keep the figures, not just the prose.
- Generate **HTML study notes** from indexed material, and **top them up** as new sources
  (more PDFs, handwritten scans, an Excel file, a PPTX) arrive.
- Keep handoff memory current so a fresh Claude Code session recovers state after
  compaction, and can cite the exact page/slide/sheet + figure for any claim.
- Catalogue a codebase alongside notes (structure, functions, data sources, dependencies).
- Feed a long-lived, topic-organised memory: layer the **llm-wiki** skill on
  top of the corpus (its playbook's "combined pipeline" section is the recipe)
  when you want concept/module pages, decision records, and staleness audits
  in addition to — or instead of — HTML notes.

## The pipeline at a glance

```
sources/  ──ingest_notes.py──▶  corpus/  ──build_pageindex.py──▶  index/
(mixed)      (+ figure PNGs)     (.md + img/)                      (pageindex.json + pages.jsonl)
                  │                                                      │
        caption_figures.py (LLM-vision hook, optional)          pageindex_query.py (tree-search)
                                                                         │
                                                          HTML notes build  (see references/html_notes_build.md)
```

All scripts live in `scripts/` next to this file. Run them with `uv run` — the ingester
declares its dependencies inline, so uv installs them automatically. Replace `SKILL_DIR`
with the path to this skill directory. **LibreOffice (`soffice`) is strongly
recommended for PPTX sources**: slides holding OMML equations, SmartArt,
EMF/WMF metafiles, tables or native charts are auto-rasterised to figure cards
via headless PPTX→PDF→PNG (`--raster-slides auto|all|off`; set `SOFFICE=<path>`
if it's not on PATH — on Windows typically
`C:\Program Files\LibreOffice\program\soffice.exe`). Without it those slides
lose their equations/diagrams and the ingester will *tell you so* on stderr.
Legacy `.xls` is read via xlrd (text/tables only — BIFF images aren't
extractable; re-save as .xlsx to recover them). **`pdftoppm`/`pdfimages`
(poppler) are useful but
not required** — the ingester uses PyMuPDF for PDF visuals; reach for the `pdf-reading`
skill when you need manual visual inspection of a tricky PDF (see step 1).

## Workflow

### 1. (When figures matter) read the source-reading routing first

Before ingesting, skim `references/visual_extraction.md`. It explains *what each format
yields* and the one rule that prevents the most data loss: **vector charts and flowcharts
(matplotlib/Excel/draw.io exports) are invisible to image extraction** — they are page
drawing operators, not image objects — so the ingester rasterises whole pages that look
like vector figures. For a one-off PDF you want to inspect by eye (scanned, garbled fonts,
ambiguous layout), read `/mnt/skills/public/pdf-reading/SKILL.md` and rasterise the page
with `pdftoppm` before deciding how to treat it.

### 2. Build / grow the corpus (incremental)

Point the ingester at your sources folder. Re-run it any time the folder grows — it skips
unchanged files via a content-hash manifest (`corpus/.ingest_manifest.json`).

```bash
# Notes -> one Markdown file per document + extracted figure PNGs under corpus/img/
uv run SKILL_DIR/scripts/ingest_notes.py <sources_dir> <corpus_dir>

# add --ocr to OCR in-figure text (needs tesseract); --prune to drop deleted sources;
# --no-rasterize to skip vector-page rendering; --force to reprocess everything.

# Code (optional) -> a single code_map.md catalogued alongside notes
uv run SKILL_DIR/scripts/scan_code.py --root <repo_dir> --dirs <dir1> <dir2> \
    --out <corpus_dir>/code_map.md
# add --fingerprints <corpus_dir>/code_fp.json to classify each file NONE/COSMETIC/
# STRUCTURAL across runs (signature-based, so comment-only edits are skippable). The map
# also includes a resolved function call graph + reverse "called-by" impact map.
```

Every figure becomes a **figure card** in the corpus Markdown — a `### Figure N (anchor)`
heading carrying the source + page/slide/sheet anchor, nearby-text keywords, optional OCR
text, the relative PNG path, and a caption placeholder. Because it is a heading, the index
turns each figure into its own addressable, citable node.

### 3. (Optional but recommended) caption the figures — the LLM-vision hook

Ingest captions are intentionally offline (keywords + OCR) to stay cheap. To make figures
findable by *what they show*, run the vision hook. This is the clean place to spend an LLM
call (Claude Code looking at the PNGs, or a Claude API vision request):

```bash
# 1. list uncaptioned figures (asset path, anchor, keywords, OCR) as JSON
uv run SKILL_DIR/scripts/caption_figures.py <corpus_dir> --list > figs.json
# 2. View each asset PNG, write a 1-2 sentence caption per figure into captions.json
#    as {"<corpus.md>::Figure N": "caption", ...}  (use the caption_id from --list)
# 3. merge captions back into the cards (idempotent, in place)
uv run SKILL_DIR/scripts/caption_figures.py <corpus_dir> --apply captions.json
```

Then re-run step 4 so the captions fold into the index and become searchable.

### 4. Build the index

```bash
uv run SKILL_DIR/scripts/build_pageindex.py <corpus_dir> <index_dir> --name "My KB"
# -> <index_dir>/pageindex.json (tree)  +  <index_dir>/pages.jsonl (page store)
```

### 5. Query (vectorless retrieval)

```bash
# offline keyword search (no LLM) — also matches figure captions/keywords
uv run SKILL_DIR/scripts/pageindex_query.py <index_dir> --search "topic words"
# dump the whole tree for LLM tree-search
uv run SKILL_DIR/scripts/pageindex_query.py <index_dir> --render
```

**LLM tree-search (the intended path):**
1. `--render` to get the compact tree (node ids, titles, page ranges, summaries, figure cards).
2. Reason over it and pick the `node_id`s relevant to the question (figures included).
3. Pull their full text — which includes figure cards with `asset:` paths — and answer,
   citing page/slide/sheet and figure:
   ```python
   import sys; sys.path.insert(0, "SKILL_DIR/scripts")
   from pageindex_query import load, get_context
   tree, pages = load("<index_dir>")
   context = get_context(["0017", "0018"], tree, pages)   # text + figure asset paths
   ```

### 6. Generate (and grow) HTML notes from the index

This is the payoff: render textbook-quality HTML notes **from the index**, not by reloading
sources. Read `references/html_notes_build.md` for the full recipe. The short version:

- Use tree-search to assemble the sections you want; pull node text + figure cards.
- For each figure card: if it is a `*-native-chart` or its data sits in an adjacent table,
  **regenerate it cleanly in matplotlib** (the data is in the page text); otherwise **embed
  the extracted PNG** (`corpus/img/...`) via base64. This is the html-notes-academic
  philosophy — clean regeneration where data is recoverable, faithful embed otherwise.
- **Recompute every numerical example in Python** before writing it into the notes; never
  hand-type a derived number. Cite the source page/slide/sheet for each.
- Build incrementally with `{{IMG:key}}` placeholders and substitute at the end.

To **top up** existing notes when new sources arrive: re-run ingest (step 2) + build (4),
then `str_replace` new `<h2>` sections into the existing HTML and renumber figures — do not
rebuild the whole document. `references/html_notes_build.md` has the incremental-growth
section.

## Keep it fresh

Re-run ingest + build after sources change. Automate via a git pre-commit hook, a scheduler
(cron / Windows Task Scheduler), or a Claude Code `/schedule` routine. For a codebase,
re-running `scan_code.py` then `build_pageindex.py` is enough.

## Notes

- Page/slide/sheet numbers are 1-based anchors, so every text claim and every figure is
  traceable to its source location.
- Supported note types: `.pdf .html .htm .pptx .xlsx .xls .docx .md .markdown .txt`.
  Unsupported files are reported and skipped.
- Figure kinds you will see in cards: `pdf-raster`, `pdf-vector-page`, `pptx-picture`,
  `pptx-native-chart`, `xlsx-image`, `xlsx-native-chart`, `docx-image`, `html-img`,
  `md-img`. Native-chart cards have no PNG — regenerate them from the adjacent data.
- Summaries are extractive by default. Swap an LLM call into `summarize()` in
  `build_pageindex.py` for abstractive summaries.
- Details, schema, tuning, and troubleshooting are in `references/reference.md`.

## Reference files (load on demand)

- `references/reference.md` — index schema, retrieval protocol, corpus convention, the
  incremental manifest, code cataloguing, tuning, troubleshooting.
- `references/visual_extraction.md` — what each format yields, the vector-figure problem,
  when to fall back to `pdf-reading`, scanned/handwritten notes, OCR, captioning strategy.
- `references/html_notes_build.md` — the full HTML-notes recipe: section assembly from the
  index, figure regenerate-vs-embed decision, numerical verification, incremental growth.
