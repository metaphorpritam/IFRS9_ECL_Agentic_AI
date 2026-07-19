# Notes conventions — template, widgets, QA gate, data pack

This is the campaign's shared rulebook: how a chapter author uses the four
scaffolding deliverables in `notes/assets/`, the image-QA checklist, and the
recompute-every-number law. Read this before writing a chapter; it does not
change per-chapter, so it is written once here rather than repeated in every
chapter's own comments.

Companion recipe files (read these too, they are the law for the HTML build
itself): `.claude/skills/pageindex-plus/references/html_notes_build.md` and
`.claude/skills/pageindex-plus/references/visual_extraction.md`.

**Campaign plan (read before writing the first chapter):** `notes/plan/chapters.md`
(the 13-chapter outline — learning goals, source anchors, fixture walkthroughs,
derivations to expand, planned widgets/diagrams, per chapter), `notes/plan/topic_map.md`
/ `topic_map.json` (46 concepts, machine-readable backbone tracing every concept to its
theory anchor / fixtures / exhibits / reports / wiki / code touchpoints),
`notes/plan/derivation_backlog.md` (every derivation flagged for full step-by-step
expansion, with the exact fixture values to substitute), and
`notes/plan/requirement_11_app_guide.md` (binding coverage law for the app-guidebook
chapter). Those four files are chapter-content planning; this file is the
infrastructure/mechanics layer they build on top of.

## Layout

```
notes/
  assets/
    template.html                    the shell for the ONE growing notes HTML file
    check_notes.py                   the QA gate (uv run, PEP-723)
    widget_demo.html                 worked reference example for widgets.js
    js/
      widgets.js                     the interactivity mini-library
    data/
      build_data_pack.py             regenerates the four xlsx files below
      fixtures_all.xlsx
      dcr_coefficients.xlsx
      sflld_coefficients.xlsx
      scenario_weights_calibration.xlsx
    img/                             regenerated/embedded PNGs land here, per chapter
  chapters/                          the compendium HTML lives here (not built yet by
                                      this phase — see notes/plan/chapters.md for the
                                      13-chapter outline that will fill it)
  corpus/, index/                    reserved for a notes-specific PageIndex, if the
                                      campaign ever needs to top itself up incrementally
  plan/
    conventions.md                   this file
    chapters.md, topic_map.{md,json}, derivation_backlog.md,
    requirement_11_app_guide.md      chapter-content planning (pre-existing)
```

**One file, not one-per-chapter.** Per `html_notes_build.md`'s "Incremental
growth" pattern and `notes/plan/chapters.md`'s explicit build order, the
13-chapter compendium is **a single growing HTML file**
(e.g. `notes/chapters/ifrs9_ecl_study_notes.html`) — each of the 13 planned
chapters is one `<h2 id="sN">` section appended to that one file, in
chapter-number order, never 13 separate files. `template.html`'s
`<h1>`/TOC/closing-`<hr>` skeleton is written once at the top of that file;
every chapter after the first is added by `str_replace`-ing the closing
`</body></html>` with the new `<h2>` section plus fresh closing tags (exactly
the recipe's step 6). Figure numbers, once a later chapter is appended, may
need the renumbering pass the recipe describes — EXHIBIT numbers are
chapter-scoped (§3 below) so only figures *within* an edited chapter ever
need renumbering, not the whole file.

## 1. Starting the compendium from `template.html`

1. Copy `notes/assets/template.html` to
   `notes/chapters/ifrs9_ecl_study_notes.html` (once — this becomes the one
   growing file; do not re-copy the template for chapter 2 onward).
2. Fill `{{TITLE}}`, `{{SUBTITLE}}`, `{{META}}` (a one-line "compiled from
   X on Y" style credit), `{{SOURCE}}`, `{{DATE}}`.
3. Build the table of contents as chapters are appended, one `<li>` per
   `<h2 id="sN">` (`notes/plan/chapters.md` gives the 13 chapter titles and
   order up front, so the full TOC skeleton can be written before the first
   chapter's prose) — keep `id`s stable once a chapter is public, since
   later chapters cross-link earlier ones (`href="#s3"`).
4. Every section follows the pattern already commented into the template:
   intro paragraph with an inline source citation → sub-sections → boxes →
   figures → interpretation → gotcha → quiz. Do not skip the interpretation
   or gotcha steps; see "Binding rendering rules" below.
5. Pull theory text/figures from the existing textbook PageIndex — do not
   re-read the raw HTML textbook:
   ```bash
   uv run --no-sync .claude/skills/pageindex-plus/scripts/pageindex_query.py knowledge/index --render
   uv run --no-sync .claude/skills/pageindex-plus/scripts/pageindex_query.py knowledge/index --search "vasicek conditioning"
   ```
6. Build incrementally: draft the skeleton (head + empty TOC), then grow
   chapter by chapter with `str_replace`-style edits against the closing
   `</body></html>`. This survives interruption — a half-built file with N
   of 13 chapters is still a valid, checkable file; run `check_notes.py`
   after every chapter append, not just at the end.

## 2. Box vocabulary — pick deliberately

| Class | Colour | Use for |
|---|---|---|
| `.defn` | blue | A term is defined here, first use. |
| `.thm` | purple | A stated result/proposition (no derivation shown here). |
| `.derivation` | violet | Step-by-step algebra. **No skipped steps** — one `<div class="step">` per algebraic move, each with a `<span class="stepno">`. |
| `.ex` | green | A fully worked numerical example (paste numbers from `tests/fixtures/`, never hand-type). |
| `.interpretation` | teal | "What this means" reasoning. **Required after every derivation/result**, not optional. |
| `.gotcha` | amber | A common misreading or pitfall. **Required once per topic.** |
| `.warn` | red | A correctness-critical caution — validity conditions, sign conventions, "do not use this formula outside X". Distinct from `.gotcha`: `.warn` is about correctness, `.gotcha` is about intuition traps. |
| `.note` | yellow | A general aside / intuition pump — optional, use freely. |
| `.quiz` | dashed | "Check yourself", 2-4 questions. **Required after every topic** (paired with `.gotcha`). |

Incomplete derivations in the source notes must be **expanded**, not copied
verbatim — worked examples in this campaign's material that need this
treatment: cloglog link derived from the continuous-time hazard, Vasicek
conditioning derived from the one-factor Gaussian model, WESML consistency,
Jensen's inequality applied to scenario-weighted ECL. Each becomes a
`.derivation` box with every substitution shown, including intermediate
numeric values in LaTeX.

### Quiz box — the exact shape the QA gate checks for

```html
<div class="quiz">
<b>Check yourself.</b>
<ol>
  <li>Question 1 text?
    <details><summary>Answer</summary>
    <div class="answer">The answer, with reasoning.</div></details>
  </li>
  <!-- 2-4 <li> total; EVERY <li> needs its own <details><summary>Answer</summary> -->
</ol>
</div>
```

`check_notes.py` counts `<li>` vs `<details>` inside every `.quiz` block and
fails if fewer than 2 or more than 4 questions, or if any question lacks its
answer reveal.

## 3. Figure numbering — EXHIBIT style

Every figure caption carries an explicit label, chapter-scoped:

```html
<img class="fig" src="data:image/png;base64,{{IMG:03_pd_pit_curve}}" alt="…">
<div class="figcap"><b>Exhibit 3.2</b> — PD_PIT(Z) at rho=0.12 (knowledge/corpus/… §8).</div>
```

- `<chapter number>.<figure number within chapter>`, both 1-indexed,
  restarting the figure counter at 1 for each chapter (not a running total
  across the whole notes set).
- Number consecutively as figures appear top-to-bottom in the chapter; when
  a chapter grows incrementally (see the recipe's "Incremental growth"
  section), re-scan and renumber before shipping.
- The `{{IMG:key}}` naming convention: `<figure-number>_<slug>`, e.g.
  `02_hazard_ratio_forest`. Keys are chapter-local; two chapters may reuse
  the same key safely since each chapter is built/encoded independently.

## 4. Figure decision — regenerate vs embed

Per `visual_extraction.md`'s figure-card `kind`:

- `*-native-chart` (pptx/xlsx cards, no PNG) → **always regenerate** in
  matplotlib from the adjacent data table.
- `pdf-vector-page` → regenerate if the underlying data is recoverable from
  nearby text/tables; embed the PNG if it's a conceptual diagram/flowchart
  with no data.
- `pdf-raster`, real pictures/scans → **embed** the PNG unless it is plainly
  a chart whose data you have.
- **Flowcharts are never embedded unchecked** — if a flowchart needs to
  exist and isn't already a clean source figure, build it as a matplotlib
  box-arrow diagram (`ax.annotate` with `arrowprops`, or `FancyBboxPatch` +
  `FancyArrowPatch`) and save it as a regenerated PNG like any other figure.

Start every regenerated figure from
`.claude/skills/pageindex-plus/assets/matplotlib_setup.py`
(`apply_textbook_style()` — serif, light dashed grid, no top/right spines;
the `COLORS` dict is tuned to match this template's CSS variables:
`accent #1f3a5f`, `warn #c0392b`, `good #27ae60`, `purple #8e44ad`,
`orange #e67e22`).

### Image QA checklist (mandatory, per figure, before it ships)

1. **View the PNG with the Read tool.** Structural checks (file exists,
   right dimensions) cannot see: overlapping titles/legends, clipped axis
   labels, illegible small text, arrows pointing the wrong way, boxes in
   the wrong place on a flowchart. Every generated image gets a human
   (agent) look, no exceptions.
2. Title, axis labels, and legend all present and non-overlapping at the
   figure's actual saved size (view at 100%, not scaled up).
3. Colours match the palette above (consistency across a chapter's figures).
4. For flowcharts specifically: every arrow points the direction the prose
   claims; every box is where the prose says it is; no crossed/ambiguous
   arrows without a legend note.
5. Caption states chapter figure number, what's plotted, and the source
   anchor — see EXHIBIT numbering above.
6. File landed in `notes/assets/img/` (or the chapter's local `img/` during
   drafting) under the exact `{{IMG:key}}` name before running
   `encode_imgs.py` / `build_final.py`
   (`.claude/skills/pageindex-plus/assets/`).

## 5. Recompute every number — the law, no exceptions

**Never hand-type a number that appears in a derivation, formula, worked
example, or table.** For every numeric claim:

1. Check whether `tests/fixtures/compute_*.py` already derives it —
   `RESULTS` holds the derived value, `TARGETS` holds the value as printed
   in the source notes. This campaign has 133 such golden values, gated by
   `tests/test_fixtures.py` (664/664 in the shared suite — do not touch that
   suite; notes work is additive only).
2. If it does: paste `RESULTS[key]` (formatted to the same
   `_DISPLAY_DECIMALS` the fixture module records) into the chapter's `.ex`
   or `.derivation` box. Cite the fixture: "(see
   `tests/fixtures/compute_ecl.py`, `ECL_12M`)" or similar, so a reader can
   verify.
3. If it doesn't yet (a new worked example a chapter needs): write a small
   `compute_<topic>.py` under `tests/fixtures/` (or a scratch script if it's
   not going to be gated) that derives every claimed output from the stated
   inputs, print + compare against the source's printed value, and only
   then paste the computed value into the chapter. If a value differs from
   the source at the last displayed decimal, stop and investigate — it is
   usually a mistyped input, not a formula bug.
4. `fixtures_all.xlsx` (see §7) is the browsable version of the same 133
   values for anyone who wants to check a number without reading Python.

This mirrors the DCR/SFLLD report numbers too: every metric quoted from
`outputs/**/*.md` or `outputs/**/*.csv` in a chapter must cite that file —
never retype a number from memory of having read it earlier in the session.

## 6. Widgets

`notes/assets/js/widgets.js` (vanilla JS, no external libraries beyond
MathJax for the surrounding prose) exposes `window.Widgets`:

- `Widgets.makeSlider(container, {label, min, max, step, value, format(v), onInput(v)})`
  → appends a labeled `<input type="range">` + live value readout to
  `container`; returns `{el, value, setValue(v)}`.
- `Widgets.makeNumberInput(container, {...})` → same shape, `<input type="number">`.
- `Widgets.makeLinePlot(container, {width, height, xDomain, yDomain, xLabel, yLabel, title, series})`
  → a dependency-free SVG line plot with "nice" ticks, axis labels, and an
  optional legend. Returns `{svg, update(series, newYDomain?, newXDomain?)}` —
  `update` clears and redraws so axes stay correct even when a slider
  changes the domain (e.g. rho stretching the y-range).
- `Widgets.makeLiveTable(container, {columns:[{key,label,format(v,row)}], rows})`
  → a plain `<table>` with `update(rows)` to refresh the body.

### The interaction pattern (see `widget_demo.html` for the full worked copy)

```html
<div class="widget">
  <h4>Live widget — drag the sliders</h4>
  <div class="widget-controls" id="controls"></div>
  <div id="plot"></div>
  <div id="table"></div>
</div>
<script src="js/widgets.js"></script>
<script>
  var state = { pdTtc: 0.02, rho: 0.12 };
  var controls = document.getElementById('controls');
  Widgets.makeSlider(controls, { label: 'PD_TTC', min: 0.005, max: 0.10, step: 0.001,
    value: state.pdTtc, format: v => (v*100).toFixed(1)+'%',
    onInput: v => { state.pdTtc = v; redraw(); } });
  // ...second slider for rho, same shape...
  var plot = Widgets.makeLinePlot(document.getElementById('plot'), { /* ...axes... */ });
  var table = Widgets.makeLiveTable(document.getElementById('table'), { /* ...columns... */ });
  function redraw() { /* recompute the REAL formula, call plot.update()/table.update() */ }
  redraw();
</script>
```

Golden rule: the widget must call the **real** formula (e.g. the Vasicek
`PD_PIT(Z,rho)` closed form, re-implemented in JS from the same equation the
Python fixture uses — see `widget_demo.html`'s `erf`/`normPpf`
implementation), not a canned lookup table. Where feasible, seed the
widget's default slider values so the live table reproduces a golden value
from `tests/fixtures/` exactly — that is a live, reader-visible correctness
check, not just a demo.

Candidate widgets for the chapters this scaffolding will support: Vasicek
`PD_PIT` vs `Z` and `rho` (built already, `widget_demo.html`); ECL vs
LGD/EIR; staging SICR threshold vs resulting stage-1/2/3 shares.

### Inlined vs relative `widgets.js` — pick one per chapter, document which

- **Relative** (`<script src="../assets/js/widgets.js"></script>` from
  `notes/chapters/`, or `<script src="js/widgets.js"></script>` from
  `notes/assets/`): smaller chapter files, one script to fix bugs in. Use
  this for chapters that will only ever be viewed from inside the repo /
  served together.
- **Inlined** (copy the full contents of `widgets.js` into a `<script>`
  block in the chapter): use when a chapter must be a single
  self-contained artifact shipped outside the repo (e.g. exported as a
  standalone deliverable, pasted into an Artifact). `check_notes.py`'s
  "widget JS parses" check only inspects `<script src="...">` references —
  an inlined copy is checked as part of ordinary tag-balance/well-formed
  HTML, so no extra step is needed either way.

State your choice in the chapter's own top HTML comment so a later editor
doesn't accidentally maintain two diverging copies.

## 7. Data pack (`notes/assets/data/`)

Four Excel workbooks, each sheet titled (row 1) with a frozen header row
(`freeze_panes`, row below the title/header), built by
`notes/assets/data/build_data_pack.py`:

| File | Sheets | Source |
|---|---|---|
| `fixtures_all.xlsx` | `fixtures_all` (133 rows: id, fixture_module, description, inputs, computed_value, notes_printed_value, displayed_decimals, matches_notes, source_anchor) | `tests/fixtures/compute_*.py` `RESULTS`/`TARGETS` |
| `dcr_coefficients.xlsx` | `default_hazard`, `prepayment_hazard` | `outputs/hazard/hazard_ratios.md` |
| `sflld_coefficients.xlsx` | `hazard_coefficients`, `cure_coefficients`, `severity_coefficients` | `outputs/freddie/{hazard,lgd}/*.csv` |
| `scenario_weights_calibration.xlsx` | `dfast_scenario_weights`, `macro_anchors`, `satellite_model_coefs`, `satellite_model_fit`, `scenario_ecl_summary` | `outputs/scenarios/scenarios_report.md`, `outputs/satellite/satellite_report.md`, `outputs/scenario_ecl/scenario_ecl_summary.csv` |

Regenerate after any change to `tests/fixtures/*.py` or the source `outputs/`
reports:

```bash
cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
uv run --no-project notes/assets/data/build_data_pack.py
```

`--no-project` is deliberate: the script's own PEP-723 header declares
`pandas`, `numpy`, `scipy`, `openpyxl` and `uv` resolves them into an
isolated ephemeral environment, so the build never has to add `openpyxl` (a
notes-only dependency) to the project's own `--no-sync` venv. The script
asserts every `fixtures_all` row's `computed_value` matches
`notes_printed_value` at the source's displayed precision before writing —
if `tests/test_fixtures.py` passes, this assertion passes too; they check
the same 133 values from the same modules.

A chapter author who wants the DataFrame instead of the xlsx: `pandas.read_excel(path, sheet_name=..., skiprows=2)` (the title row + one
blank row precede the header).

## 8. QA gate — `check_notes.py`

```bash
cd /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI
uv run --no-sync python notes/assets/check_notes.py notes/chapters/*.html
uv run --no-sync python notes/assets/check_notes.py notes/assets/widget_demo.html
```

No extra dependencies (stdlib only: `html.parser`, `re`), so it runs fine
inside the project's `--no-sync` venv. Exit code `0` iff every file passes
every check; otherwise `1`. Six checks per HTML file:

1. **HTML tag balance** — every non-void opening tag has a matching close
   (browser-style tolerant matching against the last few open tags, so one
   typo doesn't cascade into hundreds of false positives).
2. **Every `<img>` resolves** — `data:` URIs must be non-trivially long
   (catches an empty/truncated placeholder substitution); relative `src`
   must exist on disk relative to the HTML file.
3. **MathJax delimiter parity** — total unescaped `$` count is even (covers
   both inline `$…$` and display `$$…$$`, since `$$` is just two `$`
   characters); `\[`/`\]` counts match; `\(`/`\)` counts match.
4. **No leftover `{{...}}` placeholders** — catches an unsubstituted
   `{{IMG:key}}` (or any other `{{FIELD}}` template token) that should have
   been replaced by `build_final.py`.
5. **Every `.quiz` has answers** — see §2's exact shape; 2-4 `<li>`
   questions, one `<details>` answer reveal each.
6. **Widget JS parses** — every local `<script src="....js">` the chapter
   references (resolved relative to the chapter file) is checked with
   `node --check` if Node is on `PATH`, else a comment/string-stripping
   brace/paren/bracket balance check (a heuristic — flags gross syntax
   breakage, not full JS-grammar validity; good enough for widget-sized
   files written by hand).

`check_notes.py` also accepts a bare `.js` file as an argument (it runs
check 6 standalone on that file) — useful for gating `widgets.js` itself
after an edit:

```bash
uv run --no-sync python notes/assets/check_notes.py notes/assets/js/widgets.js
```

**Every chapter ends green through this script before it ships.** Run it
after every substantive edit, not just once at the end — cheap and fast
(no external calls, pure text/DOM parsing).

## 9. Theming and print

- Light palette lives in `:root`; dark override applies two ways —
  `@media (prefers-color-scheme: dark)` (follows the OS/browser) and
  `:root[data-theme="dark"]` / `:root[data-theme="light"]` (the explicit
  override, which always wins in either direction). The theme-toggle button
  (`#theme-toggle`, top-right, sun/moon glyph) stamps `data-theme` on
  `<html>` and persists the choice in `localStorage` under
  `ifrs9-notes-theme`.
- Print CSS (`@media print`) drops the page shadow/shell background, forces
  a page break before each `<h2>`, and marks figures/tables/boxes
  `break-inside: avoid` so a box or figure never splits across a page
  boundary. The theme-toggle button is hidden on print.
- Every box class, the widget panel, figures, and tables carry
  `page-break-inside: avoid` (or the `break-inside` print-media equivalent)
  for the same reason.

## 10. Known simplifications (carried forward, update if resolved)

- `widgets.js` is ~290 lines, a little over the "~200 lines" steer in the
  brief — the SVG line-plot helper (nice-tick generation, axis labels,
  legend) is the bulk of the overage. Split further only if a future
  widget needs functionality the current four helpers don't cover.
- `check_notes.py`'s MathJax delimiter check counts characters, not full
  MathJax grammar — it cannot catch a `$` that is semantically mismatched
  but numerically balanced (e.g. two separate unrelated inline maths that
  happen to close correctly). It catches the common failure mode
  (unsubstituted currency `$`, a missing closing `$`), not every possible
  LaTeX error; visually reviewing the rendered chapter remains necessary.
- `check_notes.py`'s widget-JS check falls back to a comment/string-stripped
  brace-balance heuristic when Node isn't on `PATH` — it will not catch
  every category of JS syntax error (e.g. a stray comma in valid-looking
  brace nesting), only gross unbalanced-delimiter breakage. Node was not
  available in the environment this scaffolding was built in, so the
  fallback path is what actually ran during development (verified against
  `widgets.js` and a deliberately-broken test file to confirm it does
  reject real breakage, not just rubber-stamp).
- `fixtures_all.xlsx`'s `inputs` column lists every top-level literal
  assignment in a fixture module (best-effort `ast.literal_eval` scan up to
  the `RESULTS` assignment), not a per-row mapping of exactly which inputs
  feed which output — several worked examples share one module (e.g.
  `compute_ecl.py` covers three separate worked examples: the amortising
  loan, the workout LGD, and the revolver CCF), so a given row's `inputs`
  cell may include constants from a different worked example in the same
  file. The `source_anchor` and `id` (module::key) columns are exact; the
  breadth of `inputs` is the tradeoff documented here.
- `dcr_coefficients.xlsx` and `scenario_weights_calibration.xlsx` are
  scraped from Markdown report tables via a small regex-based parser
  (`_parse_markdown_table`), not a structured export from the fitting code
  — if a report's Markdown table format changes (column additions,
  reordering), re-run `build_data_pack.py` and spot-check the sheet; the
  parser does not validate column semantics, only pipe-table syntax.
- No `notes/corpus/` or `notes/index/` content yet — those directories are
  reserved (per the campaign's directory map) for a notes-specific
  PageIndex if a later phase needs to top up the notes incrementally from
  new sources; this phase only builds the shared scaffolding.
