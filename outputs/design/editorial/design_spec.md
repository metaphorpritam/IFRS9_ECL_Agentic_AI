# The Consulting Deliverable — Editorial Report Direction

Design spec for the IFRS9 ECL Copilot, explored as a direction distinct from the
shipped app. Nothing here has been wired into `app/ui` — this is a static design
artefact under `outputs/design/editorial/`.

**Premise.** A consultant does not hand a client a dashboard; they hand them a
document that happens to be interactive. Serif display heads, a sans body built
for reading, a single restrained ink-blue used only where data or an action
lives, and every chart framed as a numbered, captioned exhibit — the way a
McKinsey/OW deck or a printed research note is built.

**Palette provenance.** Every hex below is either the dataviz skill's own
documented default (`references/palette.md`) unchanged, or a step already
tabulated in that file's sequential ramp (never an invented value). This
matters twice: the six-checks validator only certifies documented values (rule
6), and it means this direction is a *skin* on the app's already-validated
color system, not a second palette to re-certify later if it ships.

---

## 1. Palette

### 1.1 Chrome & ink

| Role | Light | Dark | Note |
|---|---|---|---|
| Page plane | `#f7f5f0` | `#15130f` | warm paper, not neutral gray |
| Panel / card surface | `#fffcf6` | `#1c1a15` | slightly lighter than the page — a sheet laid on the desk |
| Primary ink | `#161512` | `#f3f1ea` | body text, headings, stat values |
| Secondary ink | `#57534a` | `#c9c4b7` | captions, table body, panel subtitles |
| Muted ink | `#8a8579` | `#8a8579` | axis ticks, exhibit source lines *only* — 3.37:1 on light paper, below the 4.5:1 text floor by design; never use for body copy (see §6) |
| Hairline (rule/border/grid) | `#e4e0d5` | `#332f27` | 1px, solid, never dashed |
| Border ring (focus / card edge) | `rgba(22,21,18,.10)` | `rgba(243,241,234,.10)` | |

Validated against these exact surfaces (`node scripts/validate_palette.js … --surface`):
ink-primary 16.76:1 / 16.42:1, secondary 7.03:1 / 10.66:1, muted 3.37:1 / 5.05:1
(light/dark). Muted's light-mode number is a known, accepted WARN‑tier
compromise — it is *never* the only carrier of a value (see §6, Muted-ink rule).

### 1.2 The one accent, two steps

One hue carries every "this is data" and every "act on this" moment. It is
**blue, slot 1 of the app's existing categorical order** (`palette.js`
`CATEGORICAL_LIGHT[0]` / `CATEGORICAL_DARK[0]`) — reused exactly, not
reinvented, so this direction stays a re-skin of the same validated system.

| Role | Light | Dark | Contrast vs its surface |
|---|---|---|---|
| **Accent · UI** (links, primary button fill, active tab rule, focus ring) | `#184f95` | `#3987e5` | 7.44–7.91:1 (light, vs paper/panel) · 4.78–5.10:1 (dark) |
| **Accent · mark** (chart total-bars, single-series emphasis, sparkline "now" dot) | `#2a78d6` | `#3987e5` | 4.31:1 (light, vs panel) · same dark step, ≥3:1 |

Both steps come from the sequential ramp already tabulated in `palette.md`
(`#184f95` is step 600; `#2a78d6`/`#3987e5` are the categorical slot‑1 pair).
In light mode the UI role deepens one step because interactive **text**
needs the 4.5:1 AA floor, which the raw mark hex (4.31:1) just misses; a
chart **mark** only needs 3:1, so it stays at the lighter, exact slot‑1 step
used everywhere else in the app. In dark mode a single hex clears both bars,
so the two roles collapse to one value — the asymmetry is a contrast
correction, not a second color.

**Discipline:** nothing else in the interface is colored. Not a second accent
for "info," not a tint for hover states beyond a wash of this same hue at low
opacity. If a future exhibit needs more than one series identity, reach for
the app's existing 8-hue categorical order (§1.4) rather than inventing a
second accent.

### 1.3 Status (good / bad valence — reserved, fixed, never themed)

Reused verbatim from `palette.md` / `palette.js` `STATUS`. Used **only** where
a color change is a genuine value judgment (the allowance went up = worse
outcome; went down = better) — never for plain series identity (the
collision rule in `color-formula.md`).

| Role | Hex (both modes) | Contrast light panel | Contrast dark panel |
|---|---|---|---|
| Good (allowance released / favorable movement) | `#0ca30c` | 3.28:1 | 5.18:1 |
| Critical (allowance built / unfavorable movement) | `#d03b3b` | 4.69:1 | 3.62:1 |
| Warning · reserved for Policy-tab threshold breaches, not used in this Executive mock | `#fab219` | 1.79:1 | 9.49:1 |
| Serious · reserved, same | `#ec835a` | 2.57:1 | 6.60:1 |

Every status-colored mark ships with an icon (▲/▼ or ⚠) **and** a label —
never color alone, per the skill's status rule. Warning/serious are
documented sub‑3:1 on light by design; if a future exhibit needs them, the
relief channel (visible label / table view) is mandatory, not optional.

### 1.4 Categorical (identity — reserved for future multi-segment exhibits)

Unchanged from the app's existing set — not used in this Executive-tab mock
(nothing here needs more than one series identity) but documented so a future
Model-tab segment breakdown draws from the same fixed order rather than a
new one:

| Slot | Light | Dark |
|---|---|---|
| 1 blue | `#2a78d6` | `#3987e5` |
| 2 aqua | `#1baf7a` | `#199e70` |
| 3 yellow | `#eda100` | `#c98500` |
| 4 green | `#008300` | `#008300` |
| 5 violet | `#4a3aa7` | `#9085e9` |
| 6 red | `#e34948` | `#e66767` |
| 7 magenta | `#e87ba4` | `#d55181` |
| 8 orange | `#eb6834` | `#d95926` |

Validated (light, panel `#fffcf6`): all 8 pass lightness band + chroma floor;
worst adjacent CVD ΔE 9.1; worst normal-vision ΔE 19.6; slots 3/4/5
(yellow/green/violet — reordered here to this app's own sequence) sit below
3:1 and require the relief channel if ever used as large fills. Dark
(panel `#1c1a15`): worst adjacent CVD ΔE 8.4; worst normal-vision ΔE 19.3;
all 8 clear 3:1. *(Full validator transcript in the repo run log below §7.)*

### 1.5 Ordinal ramp — the Up / Base / Down scenario spectrum

Scenario severity is **one hue, ordered**, not three unrelated colors — the
category order (down worse than base worse than up) is the meaning, which is
exactly the ordinal job (`color-formula.md` §"Categorical or ordinal?").
Steps are the same blue family as the accent, taken straight from the
sequential ramp table:

| Step | Light | Dark | Used for |
|---|---|---|---|
| Lightest | `#86b6ef` | `#6da7ec` | Upside scenario |
| Mid | `#2a78d6` | `#3987e5` | Base scenario |
| Darkest | `#104281` | `#184f95` | Downside scenario |

Validated `--ordinal`: monotone lightness ✓, adjacent ΔL ≥ 0.06 ✓, single hue
(spread 3°) ✓, light-end contrast 2.06:1 light / 2.15:1 dark (both clear the
2.0:1 ordinal floor — this is *why* the ramp stops at step 250/600 rather
than going paler/darker).

### 1.6 Diverging pair (documented, reserved — not spent in this mock)

`palette.md`'s own blue↔red pair, kept in reserve for any future exhibit that
needs a true polarity read (e.g., a Model-tab residual chart with no
good/bad valence). Not used on the Executive tab: the one place a bridge
chart appears here (§ waterfall) *does* carry good/bad valence, so it
correctly draws from Status (§1.3), not this pair — see the collision rule.

### 1.7 Surfaces used for every validator run

Light surface `#fffcf6` (panel) / `#f7f5f0` (page); dark surface `#1c1a15`
(panel) / `#15130f` (page). All contrast figures above are against these,
not the skill's own generic default surfaces — re-run the validator against
these exact hexes before trusting a new color choice in this direction.

---

## 2. Type scale

**No runtime font loading — the CSP forbids it.** Every family below is a
local/system stack; the browser's own installed serif/sans/mono is the
worst case, and it still reads as "editorial," not broken.

```css
--font-serif: "Iowan Old Style", "Palatino Linotype", "URW Palladio L", P052,
              Palatino, Georgia, Cambria, "Times New Roman", Times, serif;
--font-sans:  -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
              Ubuntu, Cantarell, "Helvetica Neue", Arial, sans-serif;
--font-mono:  ui-monospace, SFMono-Regular, Menlo, Consolas,
              "Liberation Mono", monospace;
```

Serif is for **display headings and prose only** — report title, section
titles, exhibit titles, panel titles, Copilot prose answers. Every number
(stat-tile values, hero figures, table cells, axis ticks, chart labels) stays
in the sans, per the dataviz skill's own hero-figure rule: a serif hero
number reads as decoration, not data.

| Token | Family | Size / line-height | Weight | Tracking | Case |
|---|---|---|---|---|---|
| `display` (report title) | serif | 2.5rem / 1.15 | 500 | −0.01em | sentence |
| `h1` (section title) | serif | 1.75rem / 1.2 | 500 | −0.005em | sentence |
| `h2` (exhibit / panel title) | serif | 1.25rem / 1.3 | 500 | normal | sentence |
| `h3` (small serif subhead) | serif italic | 1rem / 1.4 | 400 | normal | sentence |
| `kicker` (eyebrow / exhibit number) | sans | 0.75rem / 1 | 600 | 0.08em | UPPERCASE |
| `body` | sans | 1rem / 1.6 | 400 | normal | sentence |
| `body-sm` (secondary / captions) | sans | 0.875rem / 1.55 | 400 | normal | sentence |
| `caption` (source lines, footnotes) | sans | 0.75rem / 1.5 | 400 | 0.01em | sentence |
| `stat-value` | sans | 2.5rem / 1.05 | 700 | −0.01em | — proportional figures, never `tabular-nums` |
| `stat-label` | sans | 0.75rem / 1.2 | 600 | 0.06em | UPPERCASE |
| `table-header` | sans | 0.6875rem / 1.2 | 600 | 0.06em | UPPERCASE |
| `table-cell` | sans | 0.875rem / 1.4 | 400 (600 for the row's key figure) | normal (`tabular-nums` — this is a column, so it's exactly where the skill says to use it) | sentence |
| `nav-tab` | sans | 0.8125rem / 1 | 600 | 0.05em | UPPERCASE |
| `button` | sans | 0.8125rem / 1 | 600 | 0.04em | UPPERCASE (primary/secondary) or sentence (text link) |

---

## 3. Spacing scale

8px base grid, generous by default — whitespace is doing brand work here, not
just tidiness:

```css
--space-1: 4px;   --space-2: 8px;   --space-3: 12px;  --space-4: 16px;
--space-5: 24px;  --space-6: 32px;  --space-7: 48px;  --space-8: 64px;
--space-9: 96px;
```

- Page margin (desktop): `--space-9` (96px) left/right, collapsing to
  `--space-5` under ~900px.
- Panel padding: `--space-6` (32px), `--space-5` (24px) on narrow viewports.
- Gap between KPI tiles: `--space-5` (24px).
- Gap between major sections (KPI row → Exhibit 1 → Exhibit 2): `--space-8` (64px).
- Gap inside a panel between title block and content: `--space-5` (24px).

Radii stay small and print-like — nothing here should read as a mobile-app
pill: `--radius-sm: 2px` (chips, table row hover), `--radius-md: 3px`
(buttons, stat tiles), `--radius-lg: 4px` (panels). No card drop-shadows by
default (a report page doesn't cast one); the one exception is the floating
chat dock (§ Chat dock), which is an overlay and earns a soft elevation cue.

---

## 4. Component specs

### 4.1 Stat tile

Contract (matches the dataviz skill's figure spec exactly):

```
┌─────────────────────────────┐
│ ALLOWANCE (COVERAGE BASIS)   │ ← stat-label: sans, uppercase, muted ink
│                               │
│ $34.0m                       │ ← stat-value: sans bold 2.5rem, PRIMARY ink
│                               │    (proportional figures — never tabular-nums)
│ of gross carrying amount      │ ← body-sm, secondary ink — context, not a
│                               │   fabricated delta (see rationale.md)
└─────────────────────────────┘
```

- Card: panel surface, 1px hairline border, `--radius-md`, padding
  `--space-6`/`--space-5`. No shadow, no gradient, no accent fill — parity
  across all four tiles (this is a KPI row, not a hero figure; per
  `choosing-a-form.md` a "handful of headline numbers" is a KPI row, and a
  KPI row's tiles read as equals).
- Value color is **primary ink**, not the accent — "text never wears the
  data color" extends here too: the accent is reserved for marks and
  actions, and coloring one tile's number would silently promote it above
  its three neighbors.
- Optional `delta` slot (signed, vs a named period, direction × good/bad
  color from §1.3, always with a ▲/▼ glyph) and optional `trend` slot (12pt
  sparkline, de-emphasis gray, current point in Accent·mark) are part of the
  contract for when the pipeline actually supplies a comparison period —
  **this mock ships neither**, because no historical comparison value was
  given for any of the four metrics, and inventing one would violate the
  product's own "never hallucinated numbers" rule.

### 4.2 Panel (the "exhibit" frame)

```
┌───────────────────────────────────────────────────┐
│ EXHIBIT 1                            [✎ explain]  │ ← kicker + AI-explain chip, same row
│ ECL Allowance Bridge, Q2 2026                      │ ← h2, serif
│ Opening to closing allowance, by movement type      │ ← body-sm, secondary ink, subtitle
│                                                     │
│  [ chart / table content ]                         │
│                                                     │
│ ─────────────────────────────────────────────────  │ ← hairline rule
│ Source: IFRS9 ECL Copilot model run · 2026-07-16   │ ← caption, muted ink
└───────────────────────────────────────────────────┘
```

Panel = panel surface, 1px hairline border, `--radius-lg`, padding
`--space-6`. Every chart/table panel is numbered ("EXHIBIT N") — the KPI row
is deliberately *not* numbered (front-page headline stats, not exhibits, in
report convention). Footnote/source line is mandatory on every exhibit: it is
where any data caveat (see the waterfall's scale-break note) lives, so the
chart body stays uncluttered.

### 4.3 Table

Financial-statement convention, not a web-app data-grid: no zebra striping,
no boxed cells. A double rule (2px hairline sitting 2px above a 1px hairline)
under the header row is the one decorative flourish, echoing a printed
statement's ruled header. Numeric columns right-align with `tabular-nums`;
label column left-aligns and does not. Row hover = the Accent hue at 4%
opacity, no border. Every table is itself the "table view" twin the dataviz
skill requires for any chart on the page — the Scenario exhibit in this mock
*is* its own table view (no separate chart form was warranted for 3 values —
see rationale.md and `choosing-a-form.md`'s "a single ratio / a handful of
numbers" guidance).

### 4.4 Tab nav

Five tabs, flat text-based nav (no pill backgrounds — a pill row reads as an
app's tab bar, not a report's section index). `nav-tab` type, muted ink at
rest, primary ink + Accent·UI 2px underline (only under the active label's
own width, not the full cell) when active. One full-width hairline sits under
the whole row; the active underline sits on top of it, in the accent, thicker
(2px vs 1px) so it reads as "this section" rather than a stray rule.

### 4.5 Buttons

| Kind | Fill | Text | Border | Use |
|---|---|---|---|---|
| Primary | Accent·UI solid | paper/panel-light (`#fffcf6`) both modes | none | the one CTA per screen ("Ask the analyst", "Run scenario") |
| Secondary | transparent | primary ink | 1px hairline | "View as table", "Export exhibit" |
| Text link | transparent | Accent·UI | underline on hover only | inline references, footnote links |

`--radius-md` (3px) — deliberately not a pill. Uppercase + 0.04em tracking on
primary/secondary; text links stay sentence case since they sit inside prose.

### 4.6 AI-explain affordance

A small ghost chip in the top-right of a panel's title row: a thin circular
outline (1px hairline) around a minimal inline-SVG "spark/quill" glyph (drawn
in `currentColor` so it themes for free — no icon font, which the CSP
wouldn't allow to load remotely anyway), plus the label "Explain" in
`body-sm`. Rest state: muted ink, invisible border. Hover/focus: border and
glyph turn Accent·UI, background washes to Accent at 6% opacity. This is
deliberately quiet — it should read as a footnote marker (a report
convention), not a chatbot badge.

**Behavior / API convention.** Clicking it does not call a bespoke
"explain this chart" endpoint — it opens the chat dock and pre-fills (and
auto-sends) a structured question through the *same* `POST /api/agent/ask`
every other Copilot question uses, so grounding/refusal governance is never
bypassed for an explain click:

```
question = "Explain " + <exhibit label> + " — " + <exhibit title> + ": "
         + <one-line, code-generated recap of the exact figures the panel
            is showing right now — never free text typed by the affordance
            itself> + "  What should I take from this?"
```

Example, for Exhibit 1 as rendered in this mock:

```
Explain Exhibit 1 — ECL Allowance Bridge: opening allowance $24.5m moved
through FX & macro update +$3.9m, new business +$26.0m, write-offs &
recoveries −$21.2m, and stage transfers & remeasurement +$999.4m, to a
closing allowance of $1,032.6m. What should I take from this?
```

Document this prefix convention in `docs/api_contract.md` if/when this
affordance ships — it is the one integration point this design assumes.

### 4.7 Chat dock (MiniChatDock)

Collapsed state: a slim ribbon fixed bottom-right, panel surface, 1px
hairline border, small soft shadow (`0 4px 16px rgba(0,0,0,.08)` light /
`rgba(0,0,0,.4)` dark — the one place this direction allows elevation,
since it's a floating overlay rather than a page element), serif label "Ask
the analyst" plus the same quill glyph as §4.6, a small Accent·UI dot when
the agent has an unread proactive note. Expanded state: same chrome, grows
upward; input row is a bottom-border-only field (no boxed input — a
signature-line treatment) with the primary button (§4.5) as "Ask"; Copilot's
own prose answers render in the serif body face at `body` size, quoted
figures inline in the sans per the "numbers never wear the display face"
rule.

---

## 5. Chart styling rules (ECharts)

These translate `marks-and-anatomy.md` into concrete ECharts option
fragments. General, mode-aware `chartText()`/`gridLine()`/`surface()`-style
accessors should read the tokens in §1, exactly as `app/ui/src/palette.js`
already does — this direction only changes which hexes those accessors
return, not the accessor pattern itself.

**Global**
- `textStyle.fontFamily`: the sans stack (§2) — never the serif, even inside
  a chart titled in serif HTML above it.
- `grid`: generous — left/right ≥ 48px, top ≥ 24px, bottom ≥ 48px (room for
  rotated category labels without clipping).
- `axisLine`: hairline color, 1px. `axisTick`: hidden or hairline, never
  bolder than the axis line. `splitLine`: hairline color, **`type: 'solid'`**
  (never `'dashed'` — the app's current `WaterfallChart.jsx` uses dashed
  splitLines; this direction intentionally drops that).
- `axisLabel` / `legend.textStyle` / tooltip body: secondary or muted ink,
  never the series color (labels are text, marks are color — §6).
- Legend: bottom-anchored, small square swatch, `body-sm`, present whenever
  ≥ 2 series share a chart; omitted for a single-hue exhibit (the title
  already names it).
- Tooltip: panel surface, 1px hairline border, `--radius-sm`, no drop
  shadow beyond a 1px hairline; crosshair on line/area, per-mark on
  bar/dot; value in `table-cell` tabular figures, label in `body-sm`.

**Bar / waterfall**
- `barMaxWidth: 24` (never let a bar fill its category slot — the spec's
  "cap it, let the leftover be air").
- `itemStyle.borderRadius`: `[4,4,0,0]` for a bar that terminates at its own
  top (a total bar, an increase's upper edge), `[0,0,4,4]` mirrored for one
  that terminates at its bottom (a decrease's lower edge); square at the
  shared baseline either way.
- A 2px surface-color gap between the invisible "base" stack and the visible
  "movement" stack (`itemStyle.borderColor: surface(), borderWidth: 2`) —
  this replaces the current app's 1px border, which reads as an outline
  rather than a spacer; 2px matches the skill's spacer spec exactly.
- Color by role, not by series: **total** bars → Accent·mark; **increase**
  bars → Status·critical; **decrease** bars → Status·good (§1.3 — this is a
  good/bad-valence bridge, so it draws from Status, not the Diverging pair;
  see rationale.md for why this differs from a "neutral" polarity read).
- Every bar is direct-labeled at its tip with its signed value
  (`fmtSignedM`/`fmtMillions`, matching `app/ui/src/format.js` conventions
  exactly) — expected practice for a 5–7-step bridge, not the "number on
  every point" anti-pattern (that warns about dense line/scatter series, not
  a small labeled bridge where every step *is* the story).
- **Scale breaks are opt-in, always labeled.** When one step dwarfs the
  rest by an order of magnitude or more (as in this mock's `+999.4` step —
  see rationale.md for the data-quality flag this raised), split the axis
  into two linear zones at a natural low point in the sequence, mark the
  break with a small zig-zag glyph on the shared baseline, and keep every
  bar's direct label exact regardless of which zone drew it. Never silently
  log/sqrt-scale a bar without both the break glyph and a footnote — an
  unmarked nonlinear axis is indistinguishable from a linear one to the eye
  and misstates every ratio in the chart.

**Ordinal scenario chart / chips**
- One hue, three lightness steps (§1.5), assigned by scenario severity, not
  by chart order or user selection — Down is always the darkest step even if
  the reader has re-sorted the table.
- If rendered as a chart (not just table chips): grounded bars, thin
  (`barMaxWidth: 24`), direct-labeled at the cap, category axis ordered
  Down → Base → Up or Up → Base → Down (either monotone direction is fine;
  never interleaved) so the ramp reads as a visible gradient left-to-right.

**Sparkline (stat tile, when a trend exists)**
- 12 points, 1.5px line, de-emphasis muted-ink hue; the current-period point
  is an 8px marker in Accent·mark with a 2px surface ring. No axis, no grid,
  no fill — a sparkline is a glance, not a chart.

**Every chart ships a table-view twin** (`components.md`'s Tier‑0
requirement) — a "View as table" text-link (§4.5) in the panel's footer row,
next to the source line, toggling a plain `<table>` rendering of the same
series. For the two exhibits in this mock the underlying table view is
almost the whole content already (waterfall: the 6-row bridge table;
scenario: the 3-row scenario table), so the toggle is a formality here but
documented for exhibits that grow more visually dense later (e.g. a Model
tab AUC/PSI trend line).

---

## 6. Cross-cutting rules carried over from the dataviz skill

- **Muted ink is never the only carrier of a value.** It sits under axis
  ticks and source/footnote lines, both of which are secondary reading, not
  the number itself.
- **Text never wears the data color.** Stat-tile values stay primary ink
  even when the metric they represent is colored on a chart elsewhere on the
  same page (e.g., the allowance total is Accent-colored on the waterfall
  bar, but plain ink in its stat tile).
- **A legend is always present for ≥ 2 series, never for 1** — the Executive
  tab's two exhibits are single-hue-family bridges/ramps read through direct
  labels and the panel title, so no legend box is drawn; the moment a future
  exhibit carries 2+ genuinely separate identities, a legend is mandatory,
  not optional.
- **One theme per surface, frozen.** This report never mixes the ordinal
  ramp and the categorical order in the same exhibit.
- **Dark mode is a selected variant**, re-validated against its own surface
  (§1.7), not an automatic filter-flip of the light values.

---

## 7. Validator transcript (this direction's exact tokens)

Run from the dataviz skill's base directory, against **this direction's own
surfaces** (`--surface`), not the skill's generic defaults:

```
$ node scripts/validate_palette.js \
    "#2a78d6,#008300,#e87ba4,#eda100,#1baf7a,#eb6834,#4a3aa7,#e34948" \
    --mode light --surface "#fffcf6"
  [PASS] Lightness band          all 8 inside L 0.43–0.77
  [PASS] Chroma floor            all 8 >= 0.1
  [PASS] CVD separation          worst adjacent ΔE 9.1 (protan)
  [PASS] Normal-vision floor     worst adjacent ΔE 19.6
  [WARN] Contrast vs surface     3 slots below 3:1 — relief required (as documented)

$ node scripts/validate_palette.js \
    "#3987e5,#008300,#d55181,#c98500,#199e70,#d95926,#9085e9,#e66767" \
    --mode dark --surface "#1c1a15"
  [PASS] all five checks

$ node scripts/validate_palette.js "#86b6ef,#2a78d6,#104281" \
    --ordinal --mode light --surface "#fffcf6"
  [PASS] all four ordinal checks (light-end 2.06:1)

$ node scripts/validate_palette.js "#6da7ec,#3987e5,#184f95" \
    --ordinal --mode dark --surface "#1c1a15"
  [PASS] all four ordinal checks (light-end 2.15:1)
```

Plus discrete WCAG contrast checks (via the validator's exported
`contrast()`) for every text/UI-chrome pairing in §1.1–1.3 above. No
invented hex appears anywhere in this document — every value traces to
`palette.md`, `palette.js`, or a tabulated ramp step in one of those two
files.
