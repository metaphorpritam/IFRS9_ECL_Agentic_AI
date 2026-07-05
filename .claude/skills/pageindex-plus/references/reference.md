# PageIndex Plus — reference

Details behind `SKILL.md`: index schema, retrieval protocol, the corpus + figure
convention, the incremental manifest, code cataloguing, tuning, and troubleshooting.

## What "vectorless / PageIndex" means

The corpus is a hierarchical **table-of-contents tree** (titles + extractive summaries +
page anchors) over a **page-text store**. Retrieval is two LLM steps — reason over the tree
to choose nodes, then read those nodes' pages — instead of embedding similarity. Benefits:
no vector DB, fully inspectable, traceable citations, reasons over structure not surface
similarity. Plus-version: figures are extracted as assets and recorded as tree nodes, so
visual content is retrievable and citable too.

## Index schema

`pageindex.json`:

```json
{
  "doc_name": "My KB",
  "total_pages": 42,
  "sources": ["corpus/lecture.pdf.md", "corpus/code_map.md"],
  "structure": [
    {
      "title": "Section title",
      "node_id": "0007",
      "start_index": 12,
      "end_index": 15,
      "summary": "extractive summary ...",
      "nodes": [ { "title": "Figure 1 (lecture.pdf p2)", "node_id": "0008", ... } ]
    }
  ]
}
```

`pages.jsonl` — one object per line: `{"physical_index": N, "text": "..."}`. `start_index`
/ `end_index` are 1-based page numbers into this store.

## Figure cards (how visuals live in the index)

`ingest_notes.py` writes each extracted visual as a Markdown **figure card** under a
`## Figures` section of the document's `.md`:

```
### Figure 1 (lecture.pdf p2 (page render))

- asset: `img/lecture.pdf_fig001.png`
- kind: pdf-vector-page
- anchor: lecture.pdf p2 (page render)
- context_keywords: EOQ total cost curve
- ocr_text: ...            (only with --ocr)
- caption: <one-to-two sentences, or the placeholder>
```

Because each card is a `###` heading, `build_pageindex.py` makes it its own node. So a
tree-search returns the figure node; `get_context` returns the card (with the `asset:`
path) alongside the surrounding page text. `caption_figures.py` fills the `caption:` line;
once you rebuild, the caption is searchable.

`kind` values and how to treat them at notes-build time:

| kind | has PNG? | treatment |
|---|---|---|
| `pdf-raster`, `pptx-picture`, `xlsx-image`, `docx-image`, `html-img`, `md-img` | yes | embed PNG, or regenerate if it is a chart whose data you have |
| `pdf-vector-page` | yes (rasterised page) | a vector chart/flowchart; regenerate cleanly if data is in the page text, else embed |
| `pptx-native-chart`, `xlsx-native-chart` | no | regenerate from the adjacent data table (it is in the page text) |

## Retrieval protocol (the two PageIndex steps)

1. **Tree search.** `pageindex_query.py <index> --render` prints the compact tree. Give it
   to an LLM with the question and: *"Return the node_ids most relevant to the question,
   including any figure nodes."* This is reasoning, not similarity.
2. **Answer generation.** `get_context(node_ids, tree, pages)` concatenates the full page
   text of the chosen nodes (with page markers and figure cards). Give that + the question
   to an LLM and ask for a grounded answer **with page/slide/sheet + figure citations**.

`search_tree(query, tree)` is an offline keyword fallback (term overlap with titles +
summaries, titles weighted) for when no LLM is available; it matches figure captions and
keywords too once they are in the index.

## Corpus convention

`build_pageindex.py` indexes every `.md` / `.markdown` / `.txt` in the corpus directory,
concatenated. The tree comes from Markdown ATX headings (`#`…`######`); fenced code blocks
are skipped so `# comment` lines are not treated as headings. To get a clean tree:

- Each source document starts with a single `# <relative path>` (top-level node).
  `ingest_notes.py` does this automatically.
- `##` for structural sub-sections (PDF pages, PPTX slides, Excel sheets, DOCX/HTML
  headings) and for the per-document `## Figures` block; `###` for each figure card.
- If a corpus has no headings at all, the whole corpus becomes a single node.

## The incremental manifest

`ingest_notes.py` writes `corpus/.ingest_manifest.json`:

```json
{ "files": { "lecture.pdf": { "hash": "ab12…", "slug": "lecture_pdf",
                              "assets": ["corpus/img/lecture.pdf_fig001.png", ...],
                              "figures": 2 } } }
```

On re-run: unchanged hash → skipped; changed → old assets for that source are deleted and
it is reprocessed; `--prune` drops the `.md` and assets for sources no longer present;
`--force` ignores the manifest and reprocesses everything. This is what makes "point at a
growing folder and re-run" safe and fast — and it is the mechanism behind incremental
notes growth (re-ingest, rebuild, then add only the new sections to the HTML).

## Code cataloguing

`scan_code.py` statically analyses a repo (no execution) and emits `code_map.md` with: the
code directory tree; per file the module docstring, imports (stdlib / third-party / local),
classes + methods, function signatures + one-line docs, and detected data sources; the
local-module dependency hierarchy (imports and reverse imported-by); a resolved **function
call graph** (caller -> callee) plus its reverse **called-by / impact map**; the third-party
library usage map; and (with `--fingerprints`) a per-file **structural fingerprint** with
change classification. Put `code_map.md` in the corpus to catalogue code alongside notes.

**Call graph.** Resolved conservatively from the AST without executing anything: bare calls
`foo()` -> local function `foo`; method calls `self.bar()` -> method `bar` on the enclosing
class; qualified calls `mod.baz()` -> `baz` when `mod` is a known local module. Calls it
cannot attribute (builtins, third-party, calls on arbitrary objects) are omitted, so the
edges shown are trustworthy. The reverse "called-by" map answers *"what breaks if I change
this function?"* — the impact view a plain import graph cannot give.

**Structural fingerprinting & change classification.** With `--fingerprints code_fp.json`,
each file gets a `struct_hash` computed over its *signatures* — function parameter lists,
class method signatures, and import bases — **not** its raw bytes. Comparing against the
previous run's store classifies every file:
- `NONE` — content hash identical, nothing changed.
- `COSMETIC` — bytes changed but `struct_hash` identical (comment/docstring/internal-logic
  edits): the graph topology is unaffected, so a consumer can skip re-indexing it.
- `STRUCTURAL` — signatures or imports changed: re-index this file and, via the called-by
  map, its callers.
- `NEW` / `DELETED` — as named.
This is a strict upgrade over the document ingester's content-hash manifest *for code*,
because it distinguishes edits that matter to the graph from edits that don't. The store is
a small JSON sidecar; omit `--fingerprints` and the script behaves exactly as before (call
graph still included, no fingerprint section).

## Tuning

- `build_pageindex.py --lines-per-page N` (default 30) sets page granularity. Smaller pages
  = finer anchors and more precise `get_context`, at the cost of more pages. If figure
  cards get split across pages during chunking, the `asset:` path and keywords still land
  intact; only a long caption may wrap — increase `--lines-per-page` if that bothers you.
- `ingest_notes.py --rasterize-dpi N` (default 150) — DPI for vector-figure page renders.
  `--max-figures-per-doc N` (default 40) caps runaway extraction. `--no-rasterize` disables
  whole-page rendering (embedded rasters only) when a deck is image-heavy and you only want
  true pictures.
- Summaries are extractive. For abstractive per-node summaries, replace the body of
  `summarize()` in `build_pageindex.py` with an LLM call.
- `render_tree_for_llm(..., max_summary=N)` controls how much summary text the tree shows.

## Troubleshooting

- **`unsupported type` / skipped notes** — only the listed extensions are handled. Convert
  exotic formats to PDF/HTML/Markdown first.
- **Missing dependency** — `ingest_notes.py` declares deps inline; run with `uv run`. Each
  handler imports lazily, so a missing optional package only disables that file type or
  feature (e.g. PyMuPDF missing → PDF text still extracted, visuals skipped with a notice).
- **No figures from a PDF that clearly has charts** — those charts are likely vector, and
  the page had enough text to look "non-sparse." Re-run with a lower text threshold by
  using `--rasterize-dpi` is not it; instead inspect the page via `pdf-reading`
  (`pdftoppm`) and, if needed, treat it as a figure manually in the notes build.
- **`UnicodeEncodeError` on Windows** — tools force UTF-8 stdout and read/write UTF-8; do
  the same if you call the library functions yourself.
- **Empty / wrong tree** — check the corpus actually has Markdown headings; without them
  you get one node. Ensure `ingest_notes.py` produced non-empty `.md` files.
- **Captions not searchable** — you must re-run `build_pageindex.py` after
  `caption_figures.py --apply`; captions live in the corpus and only enter the index on
  rebuild.
