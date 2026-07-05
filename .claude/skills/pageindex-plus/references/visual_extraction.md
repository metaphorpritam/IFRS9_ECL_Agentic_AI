# Visual extraction — what each format yields and how to not lose figures

Text-only RAG silently drops every chart, plot, flowchart, and diagram. `ingest_notes.py`
extracts visuals as PNG assets and records them as figure cards. This file explains what to
expect per format, the one failure mode that loses the most content, and when to fall back
to the `pdf-reading` skill for manual inspection.

## The one rule that prevents the most loss: vector figures are invisible to image extraction

Charts and diagrams drawn as **vector graphics** — the normal output of matplotlib, Excel,
R, draw.io, and most slide tools — are *page drawing operators*, not image objects. Tools
that "extract images" (`pdfimages`, `page.get_images()`) return **nothing** for them. The
only way to capture a vector figure as a raster is to **rasterise the whole page**.

`ingest_notes.py` handles this automatically for PDFs: a page that has drawing operators
*and* little text is rendered to PNG as a `pdf-vector-page` figure. The text-vs-figure
discrimination is deliberate — a text-heavy page with a small inline diagram is kept as
text (cheaper, searchable), while a near-blank page that is mostly a chart is captured as a
figure. If you have a PDF where this heuristic misjudges (a dense page that is *also* a key
figure), inspect it by hand (next section) and add it to the notes build explicitly.

## What each format yields

| Format | Text | Visuals extracted | Notes |
|---|---|---|---|
| **PDF** | per-page text (`pypdf`) | embedded rasters (`pdf-raster`) + rasterised vector-figure pages (`pdf-vector-page`) via PyMuPDF | text page vs figure page is auto-discriminated |
| **PPTX** | slide title + body text, table cells (`[TABLE]`), grouped-shape textboxes (recursive), OMML equation runs (`[EQUATION]`) | slide pictures (`pptx-picture`); native charts recorded as `pptx-native-chart` cards (no PNG) | speaker notes are *not* extracted by the ingester — if they matter, read the `pptx` skill |
| **XLSX/XLS** | first 60 rows × 12 cols per sheet as a Markdown table | embedded images (`xlsx-image`); native charts as `xlsx-native-chart` cards (no PNG, data is in the table) | inspect formulas with the `xlsx` skill if values look stale |
| **DOCX** | paragraphs with heading levels | inline images (`docx-image`) | |
| **HTML** | heading-aware text | local `<img>` files that exist on disk (`html-img`); remote/data-URI images skipped | |
| **Markdown/TXT** | verbatim | local `![](path)` images that exist on disk (`md-img`) | |

Native-chart cards (`*-native-chart`) carry no PNG on purpose: the underlying data is right
there in the adjacent table/page text, so at notes time you **regenerate the chart cleanly
in matplotlib** rather than embedding a screenshot. That is strictly better output.

## When to fall back to the `pdf-reading` skill

The ingester is for bulk, hands-off extraction. Reach for
`/mnt/skills/public/pdf-reading/SKILL.md` (read it first) when a *specific* PDF needs human
judgement:

- **Scanned / no text layer** (`pdffonts` shows no fonts): `pypdf` returns nothing.
  Rasterise pages at 150 DPI (`pdftoppm -jpeg -r 150 -f N -l N doc.pdf /tmp/page`) and Read
  them; OCR for bulk text (REFERENCE.md in that skill has a pytesseract example). The
  ingester will still extract page-level figures, but the *text* will be thin — so for a
  scanned source, do the OCR pass, save the text as a `.md` into the sources folder, and
  re-ingest.
- **Garbled text** (non-embedded fonts, Identity-H encoding): rasterise and use vision.
- **A dense page that is also a critical figure**: rasterise that one page and embed it in
  the notes manually; do not rely on the sparse-text heuristic.
- **Embedded attachments** (a spreadsheet inside a report PDF): `pdfdetach -saveall` to pull
  them out, then drop them in the sources folder so they get ingested as first-class files.

The division of labour: **`pdf-reading` is for inspecting and rescuing one tricky PDF;
`ingest_notes.py` is for indexing the whole folder.** They compose — rescue a hard source
into clean text/PNG, put it in the sources folder, re-ingest.

## Handwritten / scanned notes

1. Rasterise pages (via `pdf-reading`) and Read them to transcribe — or OCR them.
2. Save the transcription as Markdown (with `## Page N` headings and `![](scan_pN.png)`
   references to the page rasters) into the sources folder.
3. Re-ingest. The transcribed text is now searchable; the page rasters ride along as
   `md-img` figures so the original handwriting is still one click away and citable.

## OCR (`--ocr`)

`ingest_notes.py --ocr` runs `pytesseract` over each extracted figure and stores up to ~400
chars of in-image text in the card's `ocr_text` line — useful for figures full of labels
(flowcharts, annotated diagrams) so they are findable before a vision caption pass. It is
off by default (needs the `tesseract` binary + `pytesseract`); a missing stack degrades
silently to no OCR.

## Captioning strategy (hybrid)

- **At ingest (offline, free):** nearby-text keywords + optional OCR. Enough to anchor a
  figure to its topic.
- **After ingest (LLM-vision, the good captions):** `caption_figures.py --list` emits the
  uncaptioned figures with their asset paths; view each PNG (Claude Code, or a Claude API
  vision call) and write a 1–2 sentence caption describing *what the figure shows and why
  it matters*; `--apply` merges them back. Rebuild the index to make them searchable.

A good figure caption names the chart type, the variables/axes, and the takeaway — e.g.
"U-shaped EOQ total-cost curve (total annual cost vs order quantity Q); the minimum marks
the optimal order size." That sentence is what lets tree-search surface the figure when a
later question asks about optimal order quantity.


## PPTX: what python-pptx CANNOT read (and the recovery path)

Four content classes are invisible to a flat `slide.shapes` text loop — this was
the single biggest silent-loss bug in real projects (whole worked examples and
derivations dropped with "success" reported):

| Lost content | Why | Recovery in this skill |
|---|---|---|
| Table cells | need `shape.has_table` branch | extracted as `[TABLE]` rows |
| Grouped shapes/textboxes | need recursion into `GROUP` | recursive walk |
| OMML (Office Math) equations | live in raw `m:oMath` XML, not text frames | `[EQUATION]` runs + slide render |
| EMF/WMF metafiles, SmartArt, native charts | rendered vector objects; Pillow can't decode metafiles | **whole-slide rasterisation**: `soffice --headless --convert-to pdf` → PyMuPDF PNG (`--raster-slides`, default `auto`) |

The MuPDF warning `No common ancestor in structure tree` during rasterisation is
harmless — PNGs save fine. If `soffice` is missing, the ingester prints exactly
which slides were NOT recovered; never treat that warning as cosmetic.
