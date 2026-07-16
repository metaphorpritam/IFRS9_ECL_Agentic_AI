# Design direction: THE PRECISION INSTRUMENT

Regulatory/quant terminal. The book is read the way a model-validation desk
reads a model: hairline rules, tabular figures that line up in columns,
every panel stamped with the endpoint it came from, nothing on the canvas
that isn't a number, a label, or the rule that separates two numbers. Equal
seriousness in light and dark — this is a desk instrument, not a marketing
surface, and it must look identical in intent under either OS theme.

This is one candidate direction for the App v2 Executive tab (and, by
extension, the other four tabs). It does **not** modify `app/ui/` — it is a
static design exploration under `outputs/design/terminal/` per instructions.

---

## 1. Palette (validated)

The categorical palette is the dataviz-skill default hue set. **Slot order
matters and is re-derived here, not assumed**: the app's current
`app/ui/src/palette.js` orders the eight hues as
`blue, aqua, yellow, green, violet, red, magenta, orange`, which **fails**
the hard normal-vision floor (worst adjacent pair `#eb6834`↔`#e87ba4` ΔE 12.9,
below the 15 floor — confirmed by running `validate_palette.js` against that
exact order). This design uses the **documented reference order** from the
skill's `palette.md` instead, which passes every hard gate in both modes.
See `rationale.md` for the flag on the discrepancy — it's an app bug worth a
follow-up ticket, not something this exploration should quietly inherit.

### Categorical — fixed order (identity, never rank)

| Slot | Hue | Light | Dark |
|---|---|---|---|
| 1 | blue | `#2a78d6` | `#3987e5` |
| 2 | green | `#008300` | `#008300` |
| 3 | magenta | `#e87ba4` | `#d55181` |
| 4 | yellow | `#eda100` | `#c98500` |
| 5 | aqua | `#1baf7a` | `#199e70` |
| 6 | orange | `#eb6834` | `#d95926` |
| 7 | violet | `#4a3aa7` | `#9085e9` |
| 8 | red | `#e34948` | `#e66767` |

**Validator results, this order** (`node scripts/validate_palette.js "<hexes>" --mode <light|dark>`):

```
LIGHT — Lightness band PASS · Chroma floor PASS
        CVD separation PASS  worst adjacent #1baf7a↔#eda100 ΔE 9.1 (protan)
        Normal-vision floor PASS  worst adjacent #eda100↔#e87ba4 ΔE 19.6
        Contrast vs surface WARN  sub-3:1: magenta 2.62, yellow 2.11, aqua 2.74
        → ALL CHECKS PASS (contrast WARN requires the relief rule below)

DARK  — Lightness band PASS · Chroma floor PASS
        CVD separation PASS  worst adjacent #199e70↔#c98500 ΔE 8.4 (protan)
        Normal-vision floor PASS  worst adjacent #c98500↔#d55181 ΔE 19.3
        Contrast vs surface PASS  all 8 ≥ 3:1
        → ALL CHECKS PASS
```

**Relief rule in force** (this is a hard obligation, not decoration): magenta,
yellow, and aqua sit below 3:1 on the light surface. Every place this
instrument uses those three hues as a fill or mark, it *also* ships a direct
value label or the table-view toggle — never a bare colored dot/segment
relying on hue alone to be read. This governs the stage-mix bar and the
scenario-table row markers below.

**All-pairs cap** (scatter/bubble/small-multiples only — not used on the
Executive tab, noted for Model/Scenario Lab): only the first four slots
(blue, green, magenta, yellow) clear `--pairs all` in both modes; past four,
fold to "Other," facet, or direct-label.

### Status (fixed, never themed, never reused for series identity)

| Role | Hex | Light contrast | Dark contrast |
|---|---|---|---|
| good | `#0ca30c` | 3.27 | 5.19 |
| warning | `#fab219` | 1.79 | 9.49 |
| serious | `#ec835a` | 2.57 | 6.60 |
| critical | `#d03b3b` | 4.68 | 3.62 |

Warning/serious sit below 3:1 on light by design — icon + label is the
mitigation, always, never color alone.

### Diverging pair (waterfall deltas, shock deltas)

Blue `#2a78d6` (light) / `#3987e5` (dark) = increase. Red `#e34948` / `#e66767`
= decrease. Neutral midpoint / level bars: gray, not a hue — see chrome table.

### Chrome & ink (shared across all direction candidates, from `palette.md`)

| Role | Light | Dark |
|---|---|---|
| Chart/panel surface | `#fcfcfb` | `#1a1a19` |
| Page plane | `#f9f9f7` | `#0d0d0d` |
| Primary ink | `#0b0b0b` | `#ffffff` |
| Secondary ink | `#52514e` | `#c3c2b7` |
| Muted (axis/labels/micro-labels) | `#898781` | `#898781` |
| Gridline / hairline rule | `#e1e0d9` | `#2c2c2a` |
| Baseline / axis / level-bar fill | `#c3c2b7` | `#383835` |
| Delta ↑ good (success text) | `#006300` | `#0ca30c` |
| Border (hairline ring, general) | `rgba(11,11,11,.10)` | `rgba(255,255,255,.10)` |

**Instrument-specific addition** — a second, stronger hairline for structural
rules (panel/table/nav dividers, as opposed to chart gridlines, which stay on
the softer `--gridline` token):

| Role | Light | Dark |
|---|---|---|
| Structural hairline (`--rule`) | `rgba(11,11,11,.16)` | `rgba(255,255,255,.16)` |
| Structural hairline, strong (`--rule-strong`, header underlines, active tab) | `rgba(11,11,11,.32)` | `rgba(255,255,255,.32)` |

No new hues are introduced. Every color in this direction is a slot from the
tables above — the "precision" comes from restraint (one accent, reserved
status four, everything else is ink/gray/hairline), not from a bigger palette.

---

## 2. Type

**No external fonts** — strict CSP, everything is a local/system stack.

| Token | Stack |
|---|---|
| `--font-sans` | `system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif` |
| `--font-mono` | `ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Consolas, "Liberation Mono", monospace` |

Sans carries prose, labels, nav, and buttons. Mono carries **every number and
every unit annotation** — this is the one deliberate, named deviation from
the dataviz skill's default figure guidance (see callout below).

### Type scale

| Token | Size / weight / spacing | Family | Used for |
|---|---|---|---|
| `--fs-micro` | 10px / 600 / `+0.08em`, uppercase | sans | tile labels, column headers, tab index row, unit chips |
| `--fs-caption` | 11px / 400 / normal | sans | hints, footnotes, provenance stamps |
| `--fs-body` | 13px / 400 / normal | sans | prose, narrative panel, table text cells |
| `--fs-data-sm` | 13px / 500, `tabular-nums` | mono | table numeric cells, axis ticks |
| `--fs-data-md` | 15px / 600, `tabular-nums` | mono | table totals, secondary readouts |
| `--fs-data-lg` | 32px / 600, `tabular-nums` | mono | stat-tile value |
| `--fs-heading` | 13px / 600 / `+0.04em`, uppercase | sans | panel headers |
| `--fs-page-title` | 20px / 600 / normal | sans | page/tab title (`h1`) |

Line height: 1.15 for anything ≥15px, 1.4 for body/caption prose.

> **Deliberate deviation, flagged.** The dataviz skill's figure guidance
> (`marks-and-anatomy.md`) specifies *proportional* figures for a standalone
> hero/stat-tile value and reserves `tabular-nums` for columns that must
> align vertically — because tabular spacing makes a lone big number ("121")
> look loose. The Precision Instrument brief calls for tabular numerals
> **everywhere**, which is the direction's whole visual thesis: every figure
> on the screen — tile, table, tooltip, waterfall label — sits on the same
> monospaced grid, so a reader's eye can align a coverage ratio in a stat
> tile against the same ratio three rows down in a table without the digits
> re-flowing. That consistency is worth the small looseness cost on the
> 3–4 digit stat-tile values used here ($34.0m, 2.03%, 1.035×, 7,849). Two
> guardrails keep the cost from compounding: (1) stat-tile values stay short
> (≤7 characters incl. unit suffix) so looseness never becomes visible
> ragging, and (2) the unit suffix is *always* set in `--fs-caption` sans,
> never mono, so it doesn't inherit the tabular box-width and doesn't read
> as part of the digit string. If a future tile needs a long free-form
> number, drop to proportional there rather than stretching this rule.

---

## 3. Spacing, radius, elevation

4px base unit — an instrument grid, not a "friendly" 8px card grid:

| Token | Value |
|---|---|
| `--sp-1` | 4px |
| `--sp-2` | 8px |
| `--sp-3` | 12px |
| `--sp-4` | 16px |
| `--sp-5` | 24px |
| `--sp-6` | 32px |
| `--sp-7` | 48px |
| `--sp-8` | 64px |

- **Radius**: `--radius: 2px` everywhere a corner exists (tiles, panels,
  buttons, chips, tooltip). Never 0 (perceptibly a rendering artifact on
  some engines) and never > 2px (anything softer reads as "app," not
  "instrument"). Circles stay circles (status dots, swatches).
- **Elevation**: **no drop shadows, anywhere.** Every separation is a 1px
  hairline (`--rule`) or a change of plane (`--surface` panel vs `--page`
  background). This is the single biggest structural difference from the
  current app v2 CSS (`--shadow` tokens in `styles.css`) — this direction
  deletes shadow as a concept.
- **Motion**: 100–120ms linear opacity/border-color transitions only, on
  hover/focus/active. No easing curves that overshoot, no slide-ins, no
  skeleton shimmer. State changes are instant reads, like a needle
  snapping — not an animated reveal.

---

## 4. Components

### Stat tile

```
┌───────────────────────────────────────────┐
│ SCENARIO-WEIGHTED ALLOWANCE      [ USD m ]│  ← fs-micro label + unit chip
│ ─────────────────────────────────────────┤  ← 1px --rule, full width
│ 34.0                                      │  ← fs-data-lg, mono, tabular
│ ─────────────────────────────────────────┤  ← 1px --rule (footnote rule)
│ 7,849 loans · $1,673.7m balance           │  ← fs-caption, ink-muted
└───────────────────────────────────────────┘
```
- Border: 1px `--rule`, radius `--radius`, background `--surface`, no shadow.
- Label row: `--fs-micro` left, a unit chip right (hairline-bordered pill,
  `--fs-micro`, the unit only — `USD m`, `%`, `×`, `loans`) so the value
  itself never carries a unit suffix inline — the chip is the single source
  of "what scale is this," read once per tile.
- Value: `--fs-data-lg` mono. A signed delta (when present) sits inline
  after the value in `--fs-data-md`, colored by direction × whether-up-is-good
  as **text color** (delta good/bad tokens), never by a categorical hue —
  this is a status/meaning use, not identity. None of today's four Executive
  tiles carry a delta (they're point-in-time reads, not period-over-period
  movements) — the slot is specified here for the tiles on Model/Scenario
  Lab that do.
- Footer: a second hairline rule, then a caption line — this is the
  "footnote" register: context that explains the number without competing
  with it. Never more than one caption line; overflow goes to the panel's
  provenance stamp, not the tile.
- **No sparkline on these four tiles** (allowance/coverage/Jensen/reporting
  date are point-in-time headline reads, not trends) — the `trend` slot in
  the stat-tile figure contract stays empty here; it's used on Model/Scenario
  tiles that report a rate over time.

### Panel

```
STAGE MIX OF ALLOWANCE                    SOURCE · /api/ecl/summary
Part-to-whole share by IFRS 9 stage.
──────────────────────────────────────────────────────────────────
[ body ]
```
- Border 1px `--rule`, radius `--radius`, background `--surface`, no shadow.
- Header row: `--fs-heading` title (left) + a **provenance stamp** (right,
  `--fs-micro` mono, ink-muted): `SOURCE · /api/ecl/summary` or
  `SOURCE · /api/ecl/waterfall?t0=20&t1=40`. This is the instrument's
  signature move — every reported panel is stamped with the exact endpoint
  it read, visible at all times, not tucked into a tooltip. It's the visual
  expression of "never a hallucinated number": the reader can see, at a
  glance, that this panel is a live read of a named contract endpoint.
- Optional one-line subtitle under the title, `--fs-body` ink-muted, before
  the header rule.
- Header rule: `--rule-strong` (2px logical weight via `border-bottom: 2px`
  — the one place this direction uses a heavier-than-hairline rule, marking
  "this is a section boundary," same device as a table's header rule).
- Body padding `--sp-5` (24px) all sides; panels stack with `--sp-5` gap.

### Table

- Row height 40px (36px in dense/compact contexts — Model tab regression
  tables). Header row: `--fs-micro` uppercase, ink-muted, bottom border
  `--rule-strong`. Body rows: bottom border `--rule` (hairline), **no zebra
  fill** — stripes are a decoration this direction spends nothing on;
  scannability comes from the rule + right-aligned tabular columns instead.
- Numeric columns: right-aligned, `--fs-data-sm` mono tabular. Text columns
  (scenario name, component name): left-aligned `--fs-body` sans.
- Units live in the column header, in parentheses, `--fs-micro`:
  `Allowance (USD m)`, `Coverage (%)` — never repeated per cell.
- The **adopted/base row** (or any row the narrative calls out) gets a 2px
  left border in `--accent` (blue, slot 1) plus a 4%-opacity accent wash
  on that row only — a status-style callout, not a new identity color.
- Row hover: background steps to `--page` (a one-step-off-surface wash),
  120ms linear, no other affordance — this is a read-only ledger, not a
  clickable grid, unless a row is explicitly wired to drill down (Scenario
  Lab), in which case the hover also gets a right-edge caret glyph `›` in
  ink-muted.

### Tab nav

```
01 EXECUTIVE   02 MODEL   03 SCENARIO LAB   04 POLICY   05 COPILOT
━━━━━━━━━━━━
```
- Full-width strip, bottom border `--rule` for the whole nav.
- Each tab: `--fs-micro` mono index (`01`…`05`) + `--fs-heading` sans label,
  `--sp-2` gap between them, `--sp-5` gap between tabs.
- Inactive: index and label both ink-muted. Hover: label steps to primary
  ink, no rule yet (a "considering" state, not a commit).
- Active: label in primary ink, index number switches to `--accent`
  (the *only* place in the nav chrome that takes a hue — a live-channel
  marker, not decoration), and a 2px `--rule-strong`-colored underline sits
  under the active tab only, flush with the strip's bottom border so it
  reads as a "closed circuit" on that one tab.
- Keyboard focus: 2px accent outline, `2px` offset, on the tab button —
  same token as every other focus ring in this system.

### Chat dock (Copilot / MiniChatDock)

```
┌ COPILOT ● GROUNDED ──────────────────── — ┐
│ ⟨AI⟩ Coverage is 2.03% — allowance $34.0m │
│      against $1,673.7m balance across      │
│      7,849 loans.                          │
│      SOURCE · /api/ecl/summary · tc-000123 │
│                                             │
│                    what's driving Stage 2? │
│ ─────────────────────────────────────────  │
│ Ask about the book…                 [ ⏎ ] │
└─────────────────────────────────────────────┘
```
- Docked panel, same hairline/no-shadow chrome as every other panel.
- Header: `COPILOT` micro-label + a status dot — solid `--status-good` 6px
  circle + `GROUNDED` micro-label when the last answer cited a live
  endpoint, amber pulsing dot + `THINKING` while a request is in flight,
  and (per the north-star refusal path) a `--status-warning` dot +
  `OUT OF SCOPE` label when `/api/agent/ask` returns a refusal — the
  dock's own chrome tells the reader which governance state they're in
  before they read a word of the answer.
- Agent messages: left-aligned, prefixed by a small filled square swatch
  (6px, `--accent`) rather than colored text — text stays ink, per the
  "text never wears the series/accent color" rule; the swatch alone carries
  "this is the agent speaking." User messages: right-aligned, plain ink,
  no swatch (identity is positional).
- Every agent message that reports a number ends with a hairline-separated
  provenance line, `--fs-micro` mono ink-muted:
  `SOURCE · <endpoint> · <tool_call_id>` — reusing the same stamp device as
  the panel header, so the dock and the dashboard speak one visual
  language for "this number is grounded."
- Input row: hairline top border, **mono font** for the input itself (the
  one input field in the whole system set in `--font-mono` — it's the
  "command line" moment), a bracketed send affordance `[ ⏎ ]` instead of a
  filled button, disabled/dimmed while a request is in flight (no spinner
  animation — the amber dot in the header already carries that state).

### Buttons

- Rectangular, radius `--radius` (2px), 1px hairline border, **no shadow,
  no gradient fill**. Label: `--fs-heading` (13px/600/uppercase/+0.04em).
- **Primary**: filled `--ink` background, `--surface` text — reserved for
  the one committing action per view (e.g. "Run scenario," "Apply shock").
  Accent blue is *not* a button-fill color in this direction — it's reserved
  for live/data/focus signaling, so a filled-blue button never competes
  with an actual data mark for the reader's "this is live" attention.
- **Secondary** (default): `--surface` fill, 1px `--rule` border, `--ink`
  text. This is the workhorse — most controls are secondary.
- **Ghost/tertiary**: no border, `--ink-muted` text, underline on hover.
  Used for dismissive/low-commitment actions ("Reset," "Cancel").
- Heights: 32px default, 26px compact (inline table/row actions).
- Disabled: `--ink-muted` text and border, 50% opacity, no pointer.
- Focus ring: 2px `--accent` outline, 2px offset — identical token
  everywhere (tabs, buttons, inputs, AI-explain chip) so keyboard focus is
  one learned signal across the whole instrument.

### AI-explain affordance

Brief calls for a specific treatment; this direction's answer is a
**bracketed probe tag**, not an icon-button — it reads as an instrument
control (like a CLI flag or a lab probe), not a decorative sparkle:

```
STAGE MIX OF ALLOWANCE                    ⟨ ASK AI ⟩ ●   SOURCE · /api/ecl/summary
```

- A hairline-bordered chip, `--fs-micro` uppercase, literal angle brackets
  around the label (`⟨ ASK AI ⟩`), sitting between the panel title and the
  provenance stamp — deliberately adjacent to the stamp, because the
  affordance and the grounding proof are the same idea: "ask the agent" and
  "here's where the number came from" are two sides of one governance
  story, so they live in the same header rail. Default state: `--ink-muted`
  border + text. Hover/focus: border and text step to `--ink`, plus a
  6px `--accent` dot appears after the label (the same "live" dot vocabulary
  as the chat dock header) to signal "this will hit the agent, not a canned
  string." Reduced-motion-safe (a 100ms border-color/color transition only).
- Click behavior: expands a bordered strip directly under the panel's
  header rule (`--fs-body`, `--surface` background, `--rule` top border) —
  never a modal, never a popover that occludes the panel it's explaining —
  containing the agent's answer plus the same `SOURCE · <endpoint> ·
  <tool_call_id>` footer used in the chat dock. **Implementation note for
  whoever builds this**: this reuses `POST /api/agent/ask` with a
  structured question prefix (per the shared convention — e.g.
  `"[explain:stage_mix] "` + a templated question) rather than a bespoke
  endpoint, so the refusal/grounding governance of `/ask` covers this
  surface for free; if that prefix convention gets standardized, it belongs
  in `docs/api_contract.md`.
- The chip never appears without the provenance stamp beside it — asking
  the agent to interpret a number is only ever offered next to the receipt
  for that number.

---

## 5. Chart styling rules (ECharts)

All mark specs are the dataviz-skill defaults, restated here as the
concrete ECharts option values this direction expects an implementer to set:

- **Bars**: `barMaxWidth: 24`, `itemStyle.borderRadius: [4,4,0,0]` (vertical)
  or `[0,4,4,0]` (horizontal) — rounded only at the data end, square at the
  baseline. `barGap`/`barCategoryGap` tuned so touching bars keep a 2px
  surface-color gap (never a stroke drawn to separate them).
- **Lines**: `lineStyle.width: 2`, `cap: 'round'`, `join: 'round'`.
  Markers `symbolSize: 8` minimum, `itemStyle.borderColor: <surface>`,
  `borderWidth: 2` (the surface ring).
  Area fill (if used): series color at 10% opacity, never a gradient.
- **Axes**: `axisLine` hairline (`--rule` 1px), `splitLine` hairline
  (`--gridline`, solid, never `type: 'dashed'`), `axisLabel` in
  `--font-mono` for numeric axes / `--font-sans` uppercase for category
  axes, both at `--fs-micro` size, `--ink-muted` color. Round tick values
  to clean numbers, thousands-comma'd.
- **Tooltip**: `--surface` background, 1px `--rule` border, `--radius`
  corners, **no box-shadow** (`extraCssText: 'box-shadow: none'` if the
  ECharts theme injects one by default). Header row = period/category in
  `--fs-micro` uppercase ink-muted with a hairline rule beneath; each series
  row = a 6px square swatch + `--fs-body` label + `--fs-data-sm` mono value,
  right-aligned in a mono column so multi-series tooltips line up like a
  ledger.
- **Legend**: present for every ≥2-series chart, swatches only (no chart
  border around the legend itself), `--fs-micro` labels; omitted entirely
  for single-series charts (the panel title already names the series).
- **Labels**: selective, never one per point. Bars/columns → value at the
  tip in `--fs-data-sm` mono. Lines → value at the last point only, with a
  leader line if the end collides with another series' label.
- **Waterfall — explicit scale rule** (this book's real components span
  ~2.6 orders of magnitude: derecognitions ‑$21.2m vs new loans +$999.4m):
  render bars on a **true linear scale** — never a log axis, never a break
  that silently re-proportions the story — but apply a **minimum visible
  height floor** (6px) to any bar whose true height would render under that
  floor, and label every segment directly regardless of rendered height.
  Add a one-line `--fs-caption` footnote under the chart whenever the floor
  is engaged: *"bars floored at 6px for legibility above/below this height;
  labeled values are exact."* An instrument is not allowed to lie about
  scale to make small numbers look punchier — if the honest read is "one
  component dwarfs the others," the chart says that, out loud, in the
  footnote, rather than hiding it behind a fake axis.
  - **Fill**: level bars (opening, closing) = `--baseline` gray (a level,
    not a movement, and not a hue). Delta bars = `--accent` blue for
    positive components, status/diverging red for negative — the polarity
    job from the color formula, not identity.

---

## 6. Accessibility summary

- Every categorical use in this direction passes the six-checks validator
  in the documented order (§1); the three sub-3:1 hues (magenta, yellow,
  aqua) always ship with a direct label or table view alongside — never a
  bare fill.
- Status colors always carry an icon/dot + label, never color alone
  (chat-dock grounding state, delta direction, AI-explain "live" dot).
- Focus rings are one consistent token (`2px --accent`, `2px` offset)
  across tabs, buttons, inputs, and the AI-explain chip.
- Text never inherits a series/accent hue — every label, value, and legend
  entry stays in an ink token; identity rides beside the text (a swatch, a
  dot, a rule color), never inside it.
- Dark mode is a selected, separately-validated set of steps (§1), not an
  automatic filter-flip — both themes carry equal information density and
  equal contrast guarantees.
