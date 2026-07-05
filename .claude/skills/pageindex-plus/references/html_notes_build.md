# HTML notes build — from the index, grown incrementally

The payoff of the index: render textbook-quality HTML study notes **from the index**, never
re-loading the source PDFs/decks/workbooks into context, and **top them up** as new sources
arrive. This is the `html-notes-academic` workflow, fed by PageIndex retrieval instead of
raw source reading. The proven scaffolding lives in this skill's `assets/`.

## Why drive notes from the index (not the raw sources)

- **Context economy.** A 300-slide course never fits in context. The tree + targeted
  `get_context` pulls only the nodes a section needs.
- **Grounding.** Every section cites a page/slide/sheet; every figure cites its anchor.
- **Incremental growth.** New sources → re-ingest + rebuild → add only new sections. The
  notes grow with the course instead of being regenerated each time.

## Assets (start here, do not rewrite from scratch)

- `assets/template.html` — base HTML scaffold: MathJax SVG renderer, page CSS, and box
  styles (`.defn` blue, `.thm` purple, `.ex` green, `.warn` red, `.note` yellow,
  `.summary` beige), serif typography. **Always start phase 3 from this.**
- `assets/matplotlib_setup.py` — textbook `rcParams` (serif, light grid, tight layout).
  **Always start figure regeneration from this.**
- `assets/encode_imgs.py` — PNG → base64 dict.
- `assets/build_final.py` — substitutes `{{IMG:key}}` placeholders, asserts none remain,
  writes the final file.

## Phase 1 — Assemble sections from the index

1. `pageindex_query.py <index> --render` to see the tree.
2. Decide the section outline (8–12 sections for a course module). Map each section to the
   `node_id`s that cover it — include figure nodes.
3. For each section, `get_context([...node_ids...], tree, pages)` to pull text + figure
   cards. Record, per section: the source anchors (for citations), the equations/tables
   (verbatim for LaTeX), and the figure cards (asset path + kind + caption).

## Phase 2 — Recompute every numerical example in Python

The rule from `html-notes-academic`: **never hand-type a number that appears in a
derivation, formula, or table.** For each worked example, write `compute_<topic>.py` that
re-derives every claimed output from the inputs found in the page text, print + `json.dump`
the results, and cross-check against the source. If a value differs by more than the last
decimal, stop and investigate (usually a wrong input). The HTML pulls exact values from the
JSON.

For XLSX-sourced examples, the sheet table is already in the page text — mirror its logic in
pandas/numpy. (If you need to re-open the workbook for formulas vs cached values, read the
`xlsx` skill.)

## Phase 3 — Figures: regenerate where data is recoverable, embed otherwise

This is the figure decision, made per card using its `kind`:

- **`*-native-chart`** (pptx/xlsx) — **regenerate in matplotlib.** No PNG exists, but the
  data is in the adjacent table in the page text. This yields a clean, themed, fixable
  figure. Start from `assets/matplotlib_setup.py`.
- **`pdf-vector-page`** — a vector chart/flowchart rasterised at ingest. If the underlying
  data is in the page text (e.g. a plotted series you can read off a nearby table),
  **regenerate** it. If it is a conceptual diagram/flowchart with no data, **embed the PNG**
  (`corpus/img/...`).
- **`pdf-raster`, `pptx-picture`, `xlsx-image`, `docx-image`, `html-img`, `md-img`** —
  real pictures/photos/scanned diagrams. **Embed the PNG.** Only regenerate if it is plainly
  a chart whose data you have.

Embedding an extracted PNG: copy it into the notes `img/` dir (or read directly from
`corpus/img/`), and reference it with a placeholder — never paste base64 into the HTML you
author:

```html
<img class="fig" src="data:image/png;base64,{{IMG:01_eoq_curve}}" alt="EOQ total-cost curve">
<div class="figcap">Fig. 1 — EOQ total-cost curve (lecture.pdf p2).</div>
```

For regenerated figures, save the matplotlib PNG into the notes `img/` dir under the same
`{{IMG:key}}` naming. **View every PNG after generating** — overlapping titles, clipped
legends, and illegible labels are invisible to structural checks.

## Phase 4 — Build the HTML with placeholders, then substitute

1. Start from `assets/template.html`. Each section: `<h2 id="sN">`, sub-sections `<h3>`.
2. Use the box classes deliberately (`.defn/.thm/.ex/.warn/.note/.summary`).
3. Math: inline `$ … $`, display `$$ … $$`; write `<`/`>` as `&lt;`/`&gt;` inside HTML.
4. For hypothesis tests, build an explicit H₀/H₁ table (Component | Statement rows:
   Null, Alternative, Test statistic, Reference distribution, Decision rule).
5. Cite sources inline: a small "(lecture.pdf p2)" after the claim or in the figure caption.
6. Build incrementally: write head + skeleton, then `str_replace` the closing
   `</body></html>` with new sections + fresh closing tags — robust to interruption.
7. Run `assets/build_final.py` (copy into the working dir first): it loads base64 from
   `img/*.png` via `encode_imgs.py`, replaces every `{{IMG:key}}`, asserts none remain,
   writes the final file to `/mnt/user-data/outputs/<topic>_notes.html`.

## Phase 5 — Validate

- `<h2>` tags balanced; figure numbers consecutive from 1; zero `{{IMG:…}}` left; MathJax
  `tex-svg.js` present; every `<p>` closes.
- Visually spot-check ≥3 figures by viewing the PNG.
- For each numerical example, the matching `compute_*.py` output exists.
- File size plausible (~0.5–3 MB for 10–20 figures). One file out; only external dep is the
  MathJax CDN. Present with `present_files`.

## Incremental growth — the recurring case

New material arrives (more PDFs, a scan, an Excel file, a deck). Do **not** regenerate the
whole notes document. Instead:

1. Drop the new files into the sources folder.
2. Re-ingest (`ingest_notes.py` — only new/changed files are processed) and rebuild the
   index (`build_pageindex.py`). Optionally caption new figures.
3. Tree-search the **new** node_ids; assemble only the new section(s).
4. Recompute any new numericals; regenerate/embed only the new figures.
5. `str_replace` the new `<h2>` section(s) into the existing HTML, then **renumber
   figures** (subsequent figure numbers shifted): re-scan `Fig. N`/`{{IMG:..}}` in order and
   reassign. Re-run `build_final.py`.
6. Re-validate (phase 5) and re-present.

This keeps a single growing notes file that tracks the course as it unfolds, with every
addition grounded in a cited source and its figures preserved.

## Common feedback patterns

- *"Figure X has a bug"* — regenerate that one PNG, view it, re-encode, rebuild. Touch
  nothing else.
- *"Add a section on Y"* — see incremental growth above.
- *"This number looks off"* — re-open the `compute_*.py`, check the inputs against the cited
  page; the source value, not your transcription, is usually right.
- *"Where did this come from?"* — every section already carries its page/slide/sheet anchor
  from the index; surface it in the prose or caption.
