# The Modern Risk Platform — design spec

Direction: crisp fintech dashboard. Dense but breathable cards, strong
typographic hierarchy in a single grotesque family, one saturated accent +
semantic up/down colors, subtle borders/elevation instead of boxes-in-boxes,
dark-first with a clean light variant.

This spec targets the existing IFRS9 ECL Copilot app (Preact + ECharts, 5
tabs, hash router) but lives at `outputs/design/fintech/` only — nothing here
touches `app/ui`. Every color decision below was run through the dataviz
skill's validator (`scripts/validate_palette.js`); the numbers quoted are
real, not eyeballed. Every number *shown* on the Executive tab in
`preview.html` is a real, already-published figure (`docs/api_contract.md`
worked examples / `GET /api/ecl/summary` / `GET /api/ecl/waterfall?t0=20&t1=40`)
— nothing invented, per the product's own north star of never hallucinating
numbers.

---

## 1. Palette

### 1.1 How it's structured

Two layers, both validated:

1. **Chart/data layer** — reused verbatim from `app/ui/src/palette.js` /
   the dataviz reference palette (`references/palette.md`). Categorical,
   sequential, diverging, status. Unchanged, because it already passes
   every check and re-deriving it would just be reinventing a validated
   wheel.
2. **UI chrome layer** — page/panel surfaces, ink, borders, radii — new for
   this direction, built as *extensions* of the same tokens (same hue
   family, same surfaces) so chart and chrome read as one system, not two
   palettes glued together.

### 1.2 Chart/data layer (validated, unchanged from the app)

**Categorical — fixed order, both modes pass all six checks:**

| Slot | Hue | Light | Dark |
|---|---|---|---|
| 1 | blue (= the UI accent, see 1.3) | `#2a78d6` | `#3987e5` |
| 2 | green | `#008300` | `#008300` |
| 3 | magenta | `#e87ba4` | `#d55181` |
| 4 | yellow | `#eda100` | `#c98500` |
| 5 | aqua | `#1baf7a` | `#199e70` |
| 6 | orange | `#eb6834` | `#d95926` |
| 7 | violet | `#4a3aa7` | `#9085e9` |
| 8 | red (= the "decrease" hue, see 1.4) | `#e34948` | `#e66767` |

Re-validated for this spec:

```
$ node scripts/validate_palette.js "#2a78d6,#008300,#e87ba4,#eda100,#1baf7a,#eb6834,#4a3aa7,#e34948" --mode light
[PASS] Lightness band        all 8 inside L 0.43–0.77
[PASS] Chroma floor          all 8 >= 0.1
[PASS] CVD separation        worst adjacent ΔE 9.1 (protan)
[PASS] Normal-vision floor   worst adjacent ΔE 19.6
[WARN] Contrast vs surface   magenta/yellow/aqua < 3:1 → relief required (direct labels / table view — see §6)

$ node scripts/validate_palette.js "#3987e5,#008300,#d55181,#c98500,#199e70,#d95926,#9085e9,#e66767" --mode dark --surface "#1a1a19"
[PASS] all five checks, worst adjacent ΔE 8.4 (protan) / 19.3 (normal)
```

First 4 slots only for scatter/bubble/small-multiples (`--pairs all`); past 4,
fold to "Other" or facet — see `references/color-formula.md`.

**Status (fixed, never themed):** good `#0ca30c` · warning `#fab219` ·
serious `#ec835a` · critical `#d03b3b`. Always icon + label, never color
alone (warning/serious sit below 3:1 on the light surface by design).

**Diverging pair:** blue `#2a78d6`/`#3987e5` ↔ red `#e34948`/`#e66767`,
neutral gray midpoint. This is the polarity job — "which side of a
baseline" — and it is what the waterfall chart uses for
increase-vs-decrease (§5.2). It is *not* the status good/bad job: an
allowance **increase** is not "good news" for the bank, so it must never be
painted with the status-good green. Blue/red here means "adds to / reduces
the balance," full stop — see the risk flagged in `rationale.md`.

### 1.3 UI chrome layer (new — the fintech shell)

```css
:root, :root[data-theme="dark"] {
  color-scheme: dark;
  --page:            #0d0d0d;   /* app shell background */
  --panel:           #1a1a19;   /* card / row surface */
  --panel-2:         #232322;   /* hover wash, input fill, elevated dock */
  --border:          rgba(255,255,255,0.10);
  --border-strong:   rgba(255,255,255,0.16);
  --ink:             #ffffff;   /* primary text */
  --ink-2:           #c3c2b7;   /* secondary text */
  --ink-3:           #898781;   /* muted / axis / eyebrow */
  --grid:            #2c2c2a;   /* gridline hairline */
  --baseline:        #383835;   /* axis / reference line */

  --accent:          #3987e5;   /* icons, focus ring, active tab, chart mark */
  --accent-solid:    #3987e5;   /* solid button fill (dark theme) */
  --accent-on-solid: #0b0b0b;   /* label on --accent-solid (5.41:1) */
  --accent-text:     #3987e5;   /* readable link/text accent (4.79:1) */

  --increase:        var(--accent);   /* waterfall: adds to allowance */
  --decrease:        #e66767;         /* waterfall: reduces allowance */
  --level-fill:      #c3c2b7;         /* waterfall: opening/closing totals */
  --level-on-fill:   #0b0b0b;         /* label inside --level-fill (10.99:1) */

  --good:            #0ca30c;   /* status dot/icon, fixed */
  --good-text:       #0ca30c;   /* readable good text, dark (5.19:1) */
  --critical:        #d03b3b;   /* status dot/icon, fixed */
  --critical-text:   #e66767;   /* readable critical text, dark (5.39:1) */
  --warning:         #fab219;
  --serious:         #ec835a;
}
@media (prefers-color-scheme: light) {
  :root:where(:not([data-theme="dark"])) {
    color-scheme: light;
    --page:            #f9f9f7;
    --panel:           #fcfcfb;
    --panel-2:         #ffffff;
    --border:          rgba(11,11,11,0.10);
    --border-strong:   rgba(11,11,11,0.16);
    --ink:             #0b0b0b;
    --ink-2:           #52514e;
    --ink-3:           #898781;
    --grid:            #e1e0d9;
    --baseline:        #c3c2b7;

    --accent:          #2a78d6;
    --accent-solid:    #1c5cab;   /* deeper step of the SAME hue — see 1.3.1 */
    --accent-on-solid: #ffffff;   /* 6.63:1 */
    --accent-text:     #1c5cab;   /* 6.29:1 — #2a78d6 alone is 4.30:1, short of 4.5 */

    --increase:        var(--accent);
    --decrease:        #e34948;
    --level-fill:      #52514e;
    --level-on-fill:   #ffffff;   /* 7.94:1 */

    --good:            #0ca30c;
    --good-text:       #006300;   /* 7.35:1 — #0ca30c alone is 3.27:1 on light */
    --critical:        #d03b3b;
    --critical-text:   #d03b3b;   /* 4.68:1 */
    --warning:         #fab219;
    --serious:         #ec835a;
  }
}
:root[data-theme="light"] { /* mirror of the light block above, wins over OS setting */ }
:root[data-theme="dark"]  { /* mirror of the dark block above, wins over OS setting */ }
```

`preview.html` implements the full dark+light pair (see its `<style>` block);
the tokens above are the source of truth this spec's component rules
reference by name.

#### 1.3.1 Why the button fill isn't just `--accent`

This is the one place the "one saturated accent" rule gets a second look,
backed by numbers (`node --input-type=module -e "import{contrast}from
'./scripts/validate_palette.js'; …"`):

| Pair | Ratio | Verdict |
|---|---|---|
| white text on `#2a78d6` (light accent) | 4.42:1 | short of 4.5:1 for normal-weight text |
| white text on `#3987e5` (dark accent) | 3.64:1 | fails |
| white text on `#1c5cab` (sequential step 550) | 6.63:1 | pass, comfortably |
| `#0b0b0b` ink on `#3987e5` (dark accent) | 5.41:1 | pass |
| `#1c5cab` vs dark panel (component edge) | 2.63:1 | fails the 3:1 non-text floor |
| `#3987e5` vs dark page (component edge) | 5.34:1 | pass |

Resolution, still one hue, still one documented palette (`#1c5cab` is
sequential-ramp step 550 from `references/palette.md`, not an invented
color): **light-theme buttons fill with the deeper step (`#1c5cab`) and
carry white text; dark-theme buttons fill with the accent itself
(`#3987e5`) and carry near-black text.** Same blue, calibrated per surface —
exactly the "one saturated accent" the direction asks for, just not
naively copy-pasted across both themes.

### 1.4 Semantic up/down — where it's used and where it's deliberately NOT

| Context | Treatment | Why |
|---|---|---|
| Waterfall bar fill | blue = adds, red = reduces, gray = level/total | Polarity job (diverging pair), not a value judgement |
| Scenario table status dot | `up` = good green, `down` = critical, `base` = neutral ink dot | Here the series genuinely *means* better/worse economic outcome — the status-color collision rule explicitly allows this |
| Scenario Δ-vs-base pill | text in `--good-text` / `--critical-text` on a 10%-opacity wash of the same hue | icon(dot)+label+color, never color alone |
| Stat-tile value | **never** tinted — stays `--ink`, full stop | A headline figure is a fact, not a verdict; see `marks-and-anatomy.md` "text never wears the data color" |
| Model tab metrics (AUC, PSI, KS) *(future tab, noted for consistency)* | same status-dot pattern as scenario table when a metric has a pass/warn/fail band | keeps the semantic vocabulary consistent app-wide |

---

## 2. Type scale

**Single grotesque family, CSP-safe (local/system only — no `@font-face`,
no network fetch, ever):**

```css
--font-sans: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial,
             system-ui, sans-serif;
--font-mono: ui-monospace, "SFMono-Regular", Consolas,
             "Liberation Mono", Menlo, monospace; /* tool-call ids, citation chips only */
```

`-apple-system`/San Francisco, Segoe UI, Roboto and Helvetica Neue are all
neo-grotesque — whichever the OS resolves to, the "crisp fintech" character
holds without ever touching a font CDN.

| Token | Size | Weight | Line-height | Use |
|---|---|---|---|---|
| `--text-2xs` | 11px | 600, +0.04em tracking, uppercase | 1.3 | eyebrow labels, badges, table headers |
| `--text-xs` | 12px | 500 | 1.4 | captions, axis ticks, timestamps, citation chips |
| `--text-sm` | 13px | 400 | 1.45 | secondary body, table cells, tile subtitle |
| `--text-base` | 14px | 400 (500 for nav/buttons) | 1.5 | body copy, nav labels, buttons |
| `--text-md` | 16px | 600 | 1.35 | panel titles |
| `--text-lg` | 20px | 600 | 1.3 | section headers |
| `--text-xl` | 24px | 700 | 1.2 | page title |
| `--text-2xl` | 32px | 600 | 1.1 | **stat-tile value** |
| `--text-3xl` | 40px | 700 | 1.05 | reserved: a true hero figure, ≥48px in practice — not used on the Executive tab (it's a KPI row of 4 equal tiles, not a single headline number; see `choosing-a-form.md`) |

**Figures:** proportional (default) on every large standalone number — hero
figure, stat-tile value. `font-variant-numeric: tabular-nums` is reserved
for columns that must align vertically: the scenario table's Allowance/
Coverage columns and any axis-tick label.

---

## 3. Spacing, radius, elevation

```css
--sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px;
--sp-5: 20px; --sp-6: 24px; --sp-8: 32px; --sp-10: 40px;
--sp-12: 48px; --sp-16: 64px;

--radius-sm: 6px;   /* buttons, inputs, icon buttons */
--radius-md: 10px;  /* panels, stat tiles, table container */
--radius-pill: 999px; /* badges, status dots' hit area, chat input */
```

**Elevation is borders, not stacked boxes.** The whole point of "subtle
borders/elevation instead of boxes-in-boxes" is that a panel sitting on the
page gets **one** hairline (`--border`) + a whisper of shadow — never a
card containing another bordered card containing the value. Concretely:

| Tier | Used for | Treatment |
|---|---|---|
| E0 | page background | none |
| E1 | stat tile, panel, table container | 1px `--border`, `--radius-md`, `0 1px 2px rgba(0,0,0,.36)` dark / `rgba(11,11,11,.06)` light |
| E2 | tooltip, dropdown, expanded chat dock | 1px `--border-strong`, `--radius-md`, `0 8px 24px rgba(0,0,0,.5)` dark / `rgba(11,11,11,.12)` light |
| E3 | modal (if ever needed) | E2 + backdrop scrim |

Inside an E1 panel, sub-sections are separated by a **hairline divider**
(`border-top: 1px solid var(--border)`) or plain spacing — never a nested
E1 box. A stat tile is itself one E1 box; it does not contain a second
bordered box around its value.

---

## 4. Components

### 4.1 Stat tile

```
┌ panel (E1, radius-md, padding sp-5) ──────────────┐
│ EYEBROW LABEL                    [ ✦ ai-explain ] │  text-2xs, --ink-3, uppercase
│ $34.0M                                            │  text-2xl, 600, --ink, proportional
│ weighted · 25/50/25 scenario mix                  │  text-sm, --ink-2
│ (optional) ▲ 2.1% vs prior qtr    ⟋‾\_ sparkline   │  delta pill + 12-pt sparkline
└────────────────────────────────────────────────────┘
```

Contract (mirrors `marks-and-anatomy.md`'s figure contract exactly):

- `label` — sentence case in the design language, rendered uppercase via
  `--text-2xs` + tracking (no trailing colon).
- `value` — `--text-2xl`, weight 600, proportional figures, auto-compact
  (`$34.0M`, `2.03%`, `1.035x`, `7,849`).
- `subtitle` — one line, `--text-sm`, `--ink-2`; states the grounding
  context (scenario weights, as-of period, "of $1.67bn gross book") so the
  tile is self-explanatory without a tooltip.
- `delta` *(optional — not populated on the Executive tab today; the
  summary endpoint has no prior-period comparison field)* — signed,
  colored by direction × whether up is good for that metric, using
  `--good-text`/`--critical-text`, never the raw status hex on text.
- `trend` *(optional)* — 12-point sparkline, `--ink-3` line, current
  point in `--accent`.
- **AI-explain icon** top-right, see §4.7.

Four tiles sit in a `grid-template-columns: repeat(4, 1fr)` row, each its
own E1 box with `--sp-4` gutters — a KPI row, not a single hero figure
(the Executive tab has four co-equal headline numbers, so `choosing-a-form.md`'s
"handful of headline numbers → KPI row" applies, not the one-hero-per-view rule).

### 4.2 Panel

- Header row: title (`--text-md` or `--text-lg`), optional subtitle/caption
  (`--text-xs`, `--ink-3`), right-aligned action cluster: table-view toggle
  → AI-explain icon, in that order (secondary action first, the agent
  affordance closest to the edge as the "final word").
- `border-bottom: 1px solid var(--border)` under the header only if the
  body is dense (chart/table); omit for a single paragraph.
- Body: chart, table, or prose.
- Footer *(optional)*: source/caption line, `--text-2xs`, `--ink-3` — e.g.
  "Source: `GET /api/ecl/waterfall?t0=20&t1=40`".

### 4.3 Table (scenario table and general data tables)

- Row height 44px. **No zebra striping** — flat rows, hairline
  `border-top: 1px solid var(--border)` between rows only (crisp, not busy).
- Header row: `--text-2xs` uppercase `--ink-3`, `border-bottom: 1px solid
  var(--border-strong)`, sticky if the table scrolls.
- Hover: row background → `--panel-2`, no other movement.
- Numeric columns right-aligned, `tabular-nums`; identity columns
  (scenario name) left-aligned with a leading status dot (10px, `border-
  radius: 999px`) — never color-only, the scenario name is the label.
- A Δ-vs-base (or vs-baseline) column renders as a pill: `--radius-pill`,
  10% hue wash background, `--good-text`/`--critical-text` label, a small
  ▲/▼ glyph *inside the same text run* (not a separate colored icon) so
  screen readers get one coherent string ("▼ 9.1% vs base").

### 4.4 Tab nav (Executive / Model / Scenario Lab / Policy / Copilot)

Underline-indicator style, not boxed pill buttons — keeps the "no
boxes-in-boxes" discipline at the top of the page too:

- Row: flex, `gap: var(--sp-6)`, sits directly on `--page`, no card
  around it.
- Inactive tab: `--text-base`, 500, `--ink-2`, transparent 2px
  bottom-border.
- Active tab: `--ink`, 600, 2px bottom-border in `--accent`.
- Hover (inactive): `--ink` text, border stays transparent (no color
  flash — the underline is reserved for "selected," never "hovered").
- Optional 16px leading glyph per tab (outline icon, `currentColor`).
- Keyboard: `role="tablist"`/`role="tab"`, arrow-key roving tabindex,
  visible focus ring (`box-shadow: 0 0 0 2px var(--page), 0 0 0 4px
  var(--accent)`).

### 4.5 Chat dock (MiniChatDock)

- **Collapsed (default):** a slim bar pinned to the viewport bottom (or
  bottom-right on wide screens), E2 elevation, one-line input + accent
  send button + a small live "agent" status dot. Height ~52px. Always
  visible — the agent is front-and-centre per the north star, not a
  drawer the user has to discover.
- **Expanded:** grows upward into a message log (E2, max-height ~60vh,
  internal scroll), input pinned at the bottom of the dock.
- Message rows:
  - User: right-aligned, background = `--accent` at ~8% opacity wash,
    `--ink` text.
  - Agent: left-aligned, `--panel-2` background, `--ink` text. Every
    number the agent states is wrapped in a `tabular-nums` span in
    `--ink` (not accent-colored — see §1.4) so grounded figures are
    visually distinct from prose without implying "this is a status."
  - **Citation chip** under an agent message: `--text-2xs`, `--font-mono`
    for the tool/id part, pill shape, `border: 1px solid var(--border)`,
    e.g. `⚙ decompose_waterfall(t0=20, t1=40)`. This is the visual promise
    behind "never hallucinated" — every claim names its tool call.
  - **Refusal state**: not red/error-styled — refusing out-of-scope
    questions is correct behavior, not a failure. Render as a neutral
    `--panel-2` row with an `--ink-3` "outside scope" tag (`--text-2xs`,
    hairline pill), same as a normal agent message otherwise.

### 4.6 Buttons

| Variant | Fill | Text | Border | Use |
|---|---|---|---|---|
| Primary | `--accent-solid` | `--accent-on-solid` | none | one per view/panel — the single confident CTA (e.g. "Run scenario") |
| Secondary | transparent | `--ink` | 1px `--border` | most actions |
| Ghost / icon | transparent | `--ink-2`, `--accent` on hover | none | table-view toggle, export, AI-explain |
| Tertiary / link | transparent | `--accent-text` | none, underline on hover | inline "view details" |

All: `--radius-sm`, height 36px (40px for primary CTA), `--text-base`
weight 500 (600 for primary), horizontal padding `--sp-4`. Hover = darken
fill 6% (primary) or `--panel-2` wash (secondary/ghost). Focus ring as in
§4.4. Disabled: 45% opacity, no hover.

### 4.7 The AI-explain affordance

The single most important new component in this direction — it's the
visual promise that the agent is reading *this exact panel*, not a
generic chatbot bolted on the side.

- **Icon**: a 4-point spark/sparkle, single SVG `<path fill="currentColor">`,
  16px, no external icon font (CSP-safe).
- **Hit area**: 28×28px, `--radius-sm` (or circular — pick one and hold it
  app-wide; this spec uses circular to visually distinguish it from the
  square table-toggle icon next to it).
- **Default**: `color: var(--ink-3)`, transparent background.
- **Hover/focus**: `color: var(--accent)`, background `--panel-2`,
  tooltip "Ask Copilot to explain this" (`--text-xs`, E2 mini-panel).
- **Active/loading**: a 2px `--accent` ring, animated only if
  `prefers-reduced-motion` allows; otherwise a static ring + a single
  pulsing dot.
- **Placement**: top-right of the panel header, right of the table-view
  toggle — the last thing the eye hits before leaving the panel, by
  design ("everything in this panel, plus one more question").
- **Interaction contract (proposed convention — not yet wired into
  `docs/api_contract.md`; flagging here so whoever implements it can
  promote it)**: reuse `POST /api/agent/ask` (never a new endpoint) with a
  structured prefix identifying the panel and its live parameters, e.g.

  ```
  POST /api/agent/ask
  {"question": "[explain:waterfall t0=20 t1=40] Why did the allowance move
                from $24.5m to $1,032.6m over this window?"}
  ```

  This keeps every explain-click inside the existing Tier-1/Tier-2/Tier-3/
  refusal router — an AI-explain click can be refused exactly like a typed
  question, and that refusal renders in the normal neutral refusal style
  (§4.5), not as an error. The answer streams into an inline "agent
  answer" card directly under the panel (not a modal — it belongs to the
  panel it explains) with the same citation-chip treatment as the chat
  dock.

---

## 5. Chart styling rules (ECharts)

Global, applied via one theme object per mode (never a second option-builder):

- **One y-axis, always.** No dual-axis, ever — see `anti-patterns.md`. Two
  differently-scaled measures are two charts or an indexed-to-100 line.
- `backgroundColor: 'transparent'` — the panel surface shows through;
  charts never paint their own surface color.
- Font: `--font-sans`, `--text-xs`/`--text-sm` for axis/legend, `--ink-2`
  for axis labels, `--ink-3` for gridlines-adjacent ticks.
- Axis line: hidden except the baseline (`--baseline` token, 1px, solid).
  Tick marks hidden. Split line: `--grid`, 1px, **solid, never dashed**.
- `containLabel: true`, generous grid padding (`sp-4`–`sp-6`) on every side.
- Y-axis ticks round to clean numbers, thousands-comma'd.
- **Bar/column**: `barMaxWidth: 24`, `itemStyle.borderRadius` rounds only
  the data-end (`[4,4,0,0]` for columns growing up, `[0,0,4,4]` for ones
  growing down from a running total — see waterfall below), square at the
  baseline it grows from. Adjacent bars separated by a 2px `--panel` gap
  (`barGap` tuned so the rendered gap is exactly 2px at the chart's typical
  width, not "some barGap value" — check it at build width).
- **Line**: width 2, round cap/join. Marker ≥8px (r≥4) with a 2px `--panel`
  ring (`itemStyle.borderColor: 'var(--panel)', borderWidth: 2`).
- **Area**: series hue at 10% opacity, never a saturated block.
- **Legend**: only rendered for ≥2 series (a single-series chart's title
  already says what's plotted); icon `roundRect` for bar/area, a short
  line-stroke icon for line series; text `--ink-2`; toggled-off series
  fades to `--ink-3` with a faded swatch, never disappears from the
  legend row (so re-enabling doesn't require memory of where it was).
- **Tooltip**: custom HTML tooltip, not the ECharts default box —
  E2-styled (`--panel-2`, `--radius-md`, `--border-strong`, the box-shadow
  from §3), value **first** in `--text-base` 600 tabular-nums, series name
  second in `--ink-2` (`interaction.md`: "values lead, labels follow").
  Line-key swatches (a short stroke of the series color), never filled
  boxes, at tooltip density. Crosshair (`axisPointer: {type: 'line'}`,
  color `--baseline`, solid) on line/area; per-mark hover + lift
  (`emphasis.itemStyle` opacity bump) on bar/scatter/heatmap, no crosshair.
- **Table-view toggle**: every chart panel ships the icon-button twin from
  §4.6 (ghost variant) that swaps the plot region for an accessible
  `<table>` built from the same series array — never a second, separately
  maintained dataset.
- **Category order**: exactly the order the API returns (`components[]`,
  scenario `[up, base, down]`) — never re-sorted by value, so "color
  follows the entity" holds when a filter changes what's visible.
- **Reduced motion**: `animationDuration: prefersReducedMotion ? 0 : 300`
  (and no hover-transform if reduced-motion is set).

### 5.2 Waterfall-specific rules

The waterfall is a **floating column / bridge chart** — an invisible
"base" stacked series plus a visible "value" series per ECharts' standard
waterfall recipe, not a special chart type.

- Column order is the API's `components[]` order — never resorted:
  opening → stage_migration → remeasurement → derecognitions → new_loans
  → closing.
- Fill by **kind**, not by magnitude: `kind: "level"` (opening, closing) →
  `--level-fill`; `kind: "delta"` with `amount > 0` → `--increase`;
  `amount < 0` → `--decrease`. This is the diverging-pair polarity job
  from §1.4 — never the status-good/critical hues.
- Value label **outside** every column (above the higher end of its
  span), `--ink` (never inside the colored fill — sidesteps needing a
  per-fill contrast check entirely, and matches `marks-and-anatomy.md`'s
  "columns → value on the cap"), signed (`+$3.9m`, `−$21.2m`), tabular-nums.
- **Minimum visible segment height.** When one component dominates by two
  orders of magnitude (here: `new_loans` at +$999.4m against a
  `stage_migration` of +$3.9m on the *same* axis), a true-to-scale render
  makes the small bars sub-pixel. Floor every rendered segment to a
  minimum ~3% of plot height, and **disclose it** in a panel caption
  ("components under ~3% of range shown at a minimum visible height for
  legibility — exact figures are labelled on every bar and in the table
  view"). The floor changes pixels, never the label — the number shown is
  always the real one. This is a chart-honesty tradeoff, not a shortcut;
  see `rationale.md` for when it's the wrong call (a narrower, less
  skewed window needs no floor at all).
- A thin solid reference line (`--baseline`, 1px) may mark the opening and
  closing levels across the full plot width — an annotation, not a
  gridline, and solid per the no-dashed rule.
- Legend: 3 swatches — "Adds to allowance" (`--increase`), "Reduces
  allowance" (`--decrease`), "Running total" (`--level-fill`) — always
  shown (3 identities on one chart, well over the 1-series no-legend
  exception).

---

## 6. Accessibility checklist (roll-up)

- Table view exists for every chart (§5, §5.2).
- Every categorical/status pairing that WARNs on contrast (magenta/
  yellow/aqua on light, warning/serious status on light) ships with
  visible direct labels or lives inside the table view — never bare fill.
- Focus rings are visible everywhere interactive (`--accent`, 2px, 2px
  offset) — tabs, buttons, icon buttons, table rows if row-actionable.
- Labels are untrusted data: any name coming from the API (scenario
  names, component names) is inserted via `textContent`, never
  `innerHTML` string-built — applies to tooltip, legend, and the
  AI-explain citation chip.
- `prefers-reduced-motion` disables chart animation and the AI-explain
  active-state pulse; both fall back to an instant/static equivalent, not
  "no state at all."
- Refusal is not an error state (§4.5) — it never borrows `--critical`.
