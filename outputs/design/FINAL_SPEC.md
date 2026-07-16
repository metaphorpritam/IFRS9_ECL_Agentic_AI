# FINAL DESIGN SPEC — IFRS9 ECL Copilot App v2 UI (binding)

**Winner: `fintech` — "The Modern Risk Platform", with five grafts from the losing
directions.** This document supersedes the three candidate specs. An implementer
works from THIS file only; the candidate files under `outputs/design/<key>/` are
history. Where this spec and a candidate preview disagree, this spec wins.

Decision summary (full scoring in the judge's report):

| Criterion (1–10) | editorial | **fintech** | terminal |
|---|---|---|---|
| North-star fit | 8 | **9** | 7 |
| Information hierarchy | 9 | **8** | 7 |
| Data-ink discipline | 8 | **7** | 8 |
| Dark+light parity | 7 | **9** | 8 |
| Implementability (Preact/ECharts, no framework change) | 5 | **9** | 9 |
| **Total** | 37 | **42** | 39 |

Grafts adopted into this spec (detailed in the sections below):

1. **Editorial → exhibit apparatus**: numbered `EXHIBIT N` kickers on chart/table
   panels + a mandatory source/caption footer line; the KPI row stays unnumbered.
2. **Terminal → grounding vocabulary**: the chat dock's `GROUNDED / THINKING /
   OUT OF SCOPE` status word + dot, tied to real `/api/agent/ask` states.
3. **Terminal → adopted-row treatment + units-in-header**: 2px accent left
   border, 6% accent wash, `ADOPTED` tag on the base-scenario row; units live in
   column headers (`Allowance ($m)`), never repeated per cell.
4. **Editorial → the explain-question figure recap**: the `/api/agent/ask`
   explain prefix carries a code-generated recap of the exact figures the panel
   shows (merged with fintech's `[explain:<panel> <params>]` tag — §7.5).
5. **Terminal → dock scroll reserve**: the fixed chat dock is collapsed-first on
   small viewports and every tab's scroll container reserves ≥160px of bottom
   padding so the dock never sits over the last table row.

---

## 0. Prerequisites (do these FIRST — both verified by the judge with the dataviz validator)

1. **Fix the categorical slot order in `app/ui/src/palette.js` and
   `app/ui/src/styles.css`.** The shipped order
   (`blue, aqua, yellow, green, violet, red, magenta, orange`) **FAILS** the
   validator's hard normal-vision floor: worst adjacent pair
   `#eb6834↔#e87ba4` ΔE 12.9 (< 15). Replace with the documented reference
   order, which passes all checks in both modes (validator output reproduced
   in §1.2). This is a data-correctness fix, not taste.
2. **Fix the `WaterfallChart.jsx` historical-mode bug** (operator-reported,
   already diagnosed): historical mode sets `hist` to the RAW
   `/api/ecl/waterfall` payload (`{components,...}`) but `buildOption` expects
   `{start,steps,end}` — the default view renders EMPTY. Wrap it:
   `adaptWaterfallRows(d.components, 'Opening allowance', 'Closing allowance')`,
   keep `period_t0`/`period_t1` for the subtitle, and add the regression check
   (a node script run during build verification that feeds a captured payload
   through the adapter + `buildOption` and asserts non-empty series data). The
   restyle in §8.2 touches this file anyway — fix the bug in the same pass,
   before restyling, so the restyle is verifiable against a rendering chart.
3. Keep the suite green: 509/509, `tests/test_contract.py` guards the seam,
   `docs/api_contract.md` is law. This spec adds one contract-documentation
   item (§7.5) and changes no endpoint.

---

## 1. Palette — complete, both themes

Two layers. The **chart/data layer** is the validated dataviz reference set
(already mostly shipped — only the slot ORDER changes, per §0.1). The **UI
chrome layer** replaces the current styles.css chrome tokens with the fintech
shell. Every hex below is either the dataviz reference palette verbatim or a
tabulated step of its sequential ramp; nothing is invented.

### 1.1 UI chrome tokens (source of truth — put these in `styles.css` `:root`)

Light is the OS-default; dark mirrors via `prefers-color-scheme: dark`. If a
manual theme toggle is ever added, it stamps `data-theme` on `<html>` and the
`[data-theme]` blocks must win over the media query (the fintech preview shows
the exact CSS pattern).

| Token | Light | Dark | Role |
|---|---|---|---|
| `--page` | `#f9f9f7` | `#0d0d0d` | app shell background |
| `--panel` | `#fcfcfb` | `#1a1a19` | card / panel / tile surface (replaces current `--surface`/`--panel` pair — ONE panel plane) |
| `--panel-2` | `#ffffff` | `#232322` | hover wash, input fill, tooltip, expanded dock |
| `--border` | `rgba(11,11,11,0.10)` | `rgba(255,255,255,0.10)` | 1px hairline on every panel/tile |
| `--border-strong` | `rgba(11,11,11,0.16)` | `rgba(255,255,255,0.16)` | table header rule, tooltip edge, dock edge |
| `--ink` | `#0b0b0b` | `#ffffff` | primary text, stat values |
| `--ink-2` | `#52514e` | `#c3c2b7` | secondary text, table cells, axis labels |
| `--ink-3` | `#898781` | `#898781` | muted: eyebrows, captions, provenance, ticks |
| `--grid` | `#e1e0d9` | `#2c2c2a` | chart gridlines (solid, never dashed) |
| `--baseline` | `#c3c2b7` | `#383835` | chart axis/reference lines |
| `--accent` | `#2a78d6` | `#3987e5` | icons, focus ring, active tab, chart mark (= categorical slot 1) |
| `--accent-solid` | `#1c5cab` | `#3987e5` | primary button FILL (see contrast note) |
| `--accent-on-solid` | `#ffffff` (6.63:1) | `#0b0b0b` (5.41:1) | text on `--accent-solid` |
| `--accent-text` | `#1c5cab` (6.29:1) | `#3987e5` (4.79:1) | link/text accent — raw `#2a78d6` is only 4.31:1 on light, short of 4.5 |
| `--accent-wash` | `rgba(42,120,214,0.08)` | `rgba(57,135,229,0.10)` | active-state wash, adopted-row wash base |
| `--increase` | `var(--accent)` | `var(--accent)` | waterfall: adds to allowance |
| `--decrease` | `#e34948` | `#e66767` | waterfall: reduces allowance |
| `--level-fill` | `#52514e` | `#c3c2b7` | waterfall opening/closing totals |
| `--good` | `#0ca30c` | `#0ca30c` | status dot/icon fill (fixed, never themed) |
| `--good-text` | `#006300` (7.35:1) | `#0ca30c` (5.19:1) | readable "good" TEXT — never use raw `#0ca30c` as light-mode text (3.27:1) |
| `--critical` | `#d03b3b` | `#d03b3b` | status dot/icon fill |
| `--critical-text` | `#d03b3b` (4.68:1) | `#e66767` (5.39:1) | readable "critical" TEXT |
| `--warning` / `--serious` | `#fab219` / `#ec835a` | same | reserved (Policy thresholds); icon+label ALWAYS (1.79:1 / 2.57:1 on light) |
| `--good-wash` | `rgba(0,99,0,0.10)` | `rgba(12,163,12,0.14)` | delta-pill background |
| `--critical-wash` | `rgba(208,59,59,0.10)` | `rgba(230,103,103,0.14)` | delta-pill background |
| `--shadow-e1` | `0 1px 2px rgba(11,11,11,.06)` | `0 1px 2px rgba(0,0,0,.36)` | panel/tile |
| `--shadow-e2` | `0 8px 24px rgba(11,11,11,.12)` | `0 8px 24px rgba(0,0,0,.5)` | tooltip, dropdown, dock |

All quoted ratios were re-computed by the judge with the validator's exported
`contrast()` against the exact surfaces above. When a NEW text/fill pairing is
introduced, run that same check for that pairing — the discipline generalizes,
the numbers don't. Retire the current `--amber-bg`/`--amber-ink` tokens in
favor of the status system (warning wash = `--warning` at 12% + `--ink` text +
⚠ icon).

### 1.2 Chart/data layer (categorical — FIXED reference order, both modes)

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

Judge-verified validator runs:

```
light  (surface #fcfcfb): PASS band · PASS chroma · PASS CVD (worst 9.1 protan)
       PASS normal floor (worst 19.6) · WARN contrast: magenta 2.62, yellow 2.11,
       aqua 2.74 < 3:1 → relief REQUIRED (direct labels or table view) wherever used
dark   (surface #1a1a19): ALL FIVE PASS (worst CVD 8.4, worst normal 19.3)
```

Rules: assign in fixed order, never cycled; slot follows the ENTITY, never its
rank; past 4 series fold to "Other" or facet; only slots 1–4 for
scatter/bubble/small-multiples. Status hues are never series colors.
Diverging pair = slot-1 blue ↔ slot-8 red with a neutral gray midpoint — this
is the waterfall's polarity job ("adds to / reduces the balance"), NOT the
good/bad status job: an allowance increase is not painted "bad".

### 1.3 Where up/down color is used — and deliberately not

| Context | Treatment |
|---|---|
| Waterfall bar fill | `--increase` blue / `--decrease` red / `--level-fill` gray. Legend words: "Adds to allowance / Reduces allowance / Running total" — never "good/bad" |
| Scenario table status dot | up = `--good`, down = `--critical`, base = `--ink-3` dot; the scenario NAME is the label, dot is secondary |
| Δ-vs-base pill | `--good-text`/`--critical-text` on the matching wash, ▲/▼ glyph INSIDE the same text run |
| Stat-tile value | NEVER tinted — always `--ink` |
| Chart value labels | ALWAYS `--ink` (binding — overrides both losing previews, which colored them; "text wears text tokens, never the series color") |

---

## 2. Type

**Single grotesque family. No `@font-face`, no network fetch, ever (CSP).**

```css
--sans: -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, system-ui, sans-serif;
--mono: ui-monospace, "SFMono-Regular", "Cascadia Code", Consolas, "Liberation Mono", Menlo, monospace;
```

Mono is used ONLY for: provenance stamps, citation chips, tool-call ids. Not
for stat values, not for table numerals (those use `tabular-nums` on the sans).

| Token | Size / weight / lh | Use |
|---|---|---|
| `--text-2xs` | 11px / 600 / 1.3, +0.04em, UPPERCASE | eyebrows, exhibit kickers, badges, table headers |
| `--text-xs` | 12px / 500 / 1.4 | captions, axis ticks, timestamps, citation chips (chips in `--mono` at 10.5px) |
| `--text-sm` | 13px / 400 / 1.45 | secondary body, table cells, tile subtitle |
| `--text-base` | 14px / 400 / 1.5 (500 nav/buttons) | body, nav labels, buttons |
| `--text-md` | 16px / 600 / 1.35 | panel titles |
| `--text-lg` | 20px / 600 / 1.3 | section headers |
| `--text-xl` | 24px / 700 / 1.2 | page title |
| `--text-2xl` | 32px / 600 / 1.1, −0.01em | stat-tile value |

**Figures:** stat-tile values are PROPORTIONAL (the default — never
`tabular-nums` on a lone big number). `font-variant-numeric: tabular-nums` is
MANDATORY on: every numeric table column, every axis tick, every chart value
label, every delta pill, and numbers quoted inline in agent answers (wrap in a
`.num` span). Numeric columns right-align; identity columns left-align.

---

## 3. Spacing, radius, elevation

```css
--sp-1: 4px;  --sp-2: 8px;  --sp-3: 12px; --sp-4: 16px; --sp-5: 20px;
--sp-6: 24px; --sp-8: 32px; --sp-10: 40px; --sp-12: 48px; --sp-16: 64px;
--radius-sm: 6px;    /* buttons, inputs, icon-button (square variant), tooltips */
--radius-md: 10px;   /* panels, stat tiles, table containers */
--radius-pill: 999px;/* badges, delta pills, chat dock bar, AI-explain hit area */
```

**Elevation is borders, not boxes-in-boxes.** Tiers:

- **E0** page: nothing.
- **E1** panel / stat tile / table container: 1px `--border`, `--radius-md`,
  `--shadow-e1`. Inside an E1 box, subdivide with a hairline
  (`border-top: 1px solid var(--border)`) or spacing — NEVER a nested bordered
  card. A stat tile is one E1 box; its value is not boxed again.
- **E2** tooltip / dropdown / expanded dock: 1px `--border-strong`,
  `--radius-md`, `--shadow-e2`.
- **E3** modal (avoid; only if unavoidable): E2 + scrim.

Shell: `max-width: 1180px; margin: 0 auto; padding: 24px 24px 160px` — the
160px bottom reserve is graft 5 (dock never occludes the last row). Panels
stack with 20px gaps; KPI grid gap 16px.

---

## 4. App shell, header, tab nav

### 4.1 Topbar (`DecisionHeader.jsx` / `app.jsx` header)

Left → right: brand mark (26px rounded-7px square, `--accent` fill,
`--accent-on-solid` glyph), product name (`--text-md` 600), **grounded badge**
(pill, 1px `--border`, `--text-2xs` `--ink-3`, 6px `--good` dot + text
"every figure cites its source"), then `margin-left:auto` meta line
(`--text-xs` `--ink-3` `tabular-nums`: as-of period · loan count · book size),
then the theme toggle if present. Header background `--page` (not a card),
`border-bottom: 1px solid var(--border)`, may stay sticky.

### 4.2 Tab nav (5 tabs, hash router — unchanged routing)

Underline-indicator style, sits directly on `--page`, no card:

- Row: `display:flex; gap:24px; border-bottom:1px solid var(--border)`.
- Inactive: `--text-base` 500 `--ink-2`, transparent 2px bottom border.
- Hover (inactive): text → `--ink`; underline stays transparent (underline
  means SELECTED, never hovered).
- Active: `--ink` 600, 2px bottom border `--accent`.
- A11y: `role="tablist"/"tab"`, arrow-key roving tabindex, focus ring
  `box-shadow: 0 0 0 2px var(--page), 0 0 0 4px var(--accent)`.
- No pill backgrounds, no boxed tabs, no mono index numbers.

---

## 5. Components

### 5.1 Stat tile (`StatTile.jsx` — keep classnames, restyle)

```
┌ E1 tile, radius-md, padding 18px 18px 16px ────────┐
│ EYEBROW LABEL                        [✦ explain]   │  --text-2xs, --ink-3, uppercase
│ $34.0M                                             │  --text-2xl 600 --ink, PROPORTIONAL
│ 25/50/25 scenario mix                              │  --text-sm, --ink-2 (grounding context)
│ ── (only when open) ──────────────────────────────│  hairline divider
│ agent answer strip (§7.6)                          │
└────────────────────────────────────────────────────┘
```

- `label`: no trailing colon; uppercase via CSS, sentence case in source.
- `value`: auto-compact (`$34.0M`, `2.03%`, `1.035x`, `7,849`) via
  `format.js`; color `--ink` always (even if the same metric is colored in a
  chart elsewhere).
- `subtitle` (maps to current `tile-hint`): one line stating grounding
  context; the tile must be self-explanatory without a tooltip.
- `delta` slot (optional, ONLY when the API supplies a prior-period value —
  never fabricate): signed, ▲/▼ glyph in the same text run,
  `--good-text`/`--critical-text` by direction × whether-up-is-good.
- `trend` slot (optional): 12-pt sparkline, `--ink-3` 1.5px line, current
  point 8px `--accent` marker with 2px `--panel` ring; no axis/grid/fill.
- AI-explain icon-button top-right (§7). Four tiles:
  `grid-template-columns: repeat(4,1fr)` → 2 → 1 at 900/620px.
- Retire `tile-${tone}` accent tinting — tone is carried by delta/status
  affordances, not tile chrome.

### 5.2 Panel — the exhibit frame (all chart/table panels, all tabs)

```
┌ E1 panel ──────────────────────────────────────────────┐
│ EXHIBIT 1                       [⊞ table] [✦ explain]  │ ← kicker row + action cluster
│ Allowance bridge                                        │ ← --text-md 600
│ 2015Q1 → 2015Q1 (t=59 → t=60)                           │ ← --text-xs --ink-3 tabular
│ ────────────────────────────────────────────────────── │ ← 1px --border under header
│  [ body: chart | table | prose ]                        │ padding 20px
│ ────────────────────────────────────────────────────── │
│ Source: GET /api/ecl/waterfall?t0=59&t1=60 · run 2026-07-16 │ ← footer, --text-2xs --mono --ink-3
└─────────────────────────────────────────────────────────┘
```

- **Graft 1 (editorial):** every chart/table panel carries a numbered kicker
  `EXHIBIT N` (`--text-2xs` 700, +0.1em, `--accent-text`), numbered top-to-
  bottom PER TAB. The KPI row is deliberately unnumbered (headline stats, not
  exhibits). Every exhibit's footer line is MANDATORY: `Source:` + the exact
  endpoint (mono) + run date; data caveats live here, not in the chart body.
- Header action cluster order (left→right): table-view toggle, then
  AI-explain — the agent affordance is the last thing the eye hits.
- `border-bottom` under the header only when the body is dense (chart/table);
  omit for a single paragraph.

### 5.3 Tables (`SearchableTable.jsx`, scenario table, waterfall table twin)

- Row height 44px; NO zebra striping; hairline `border-top: 1px solid
  var(--border)` between rows.
- Header: `--text-2xs` uppercase `--ink-3`, `border-bottom: 1px solid
  var(--border-strong)`, sticky when the table scrolls.
- Numeric columns right-aligned `tabular-nums`; identity columns left-aligned.
- **Graft 3 (terminal):** units in the column header, parenthesized —
  `Allowance ($m)`, `Coverage (%)` — never per cell. The adopted/base row
  gets a 2px `--accent` left border + `--accent-wash` background + an
  `ADOPTED` tag (`--text-2xs` 700 `--accent-text`, 8px left margin) after the
  scenario name.
- Scenario rows: leading 9px status dot (`--good`/`--ink-3`/`--critical`);
  Δ-vs-base column renders as a pill (`--radius-pill`, wash background,
  `--good-text`/`--critical-text`, ▲/▼ inside the text run — one coherent
  string for screen readers: "▼ 9.1% vs base").
- Hover: row background → `--panel-2`, nothing moves. Every table sits in an
  `overflow-x: auto` wrapper.
- All API-sourced strings inserted via `textContent`, never string-built HTML.

### 5.4 Buttons

| Variant | Fill | Text | Border | Use |
|---|---|---|---|---|
| Primary | `--accent-solid` | `--accent-on-solid` | none | ONE per view — the committing CTA ("Run scenario") |
| Secondary | transparent | `--ink` | 1px `--border` | most actions |
| Ghost/icon | transparent | `--ink-2` → `--accent` on hover | none | table toggle, export, AI-explain |
| Link | transparent | `--accent-text` | underline on hover | inline "view details" |

Heights 36px (primary CTA 40px), `--radius-sm`, `--text-base` 500 (primary
600), padding-x 16px. Hover: primary darkens ~6%; others wash `--panel-2`.
Focus ring as §4.2. Disabled: 45% opacity, no hover. Never fill a button with
raw `--accent` in light mode (white text on `#2a78d6` = 4.42:1, fails).

### 5.5 MiniChatDock (`MiniChatDock.jsx`)

- **Collapsed (default):** a pill bar fixed bottom-right
  (`right:24px; bottom:20px; width:min(420px, 100vw − 48px)`), E2,
  `--radius-pill`, containing: status dot (§ below), one-line input
  (transparent, `--text-sm`, placeholder `--ink-3`), and a 34px round
  `--accent-solid` send button. Always visible — the agent is
  front-and-centre, not a drawer to discover.
- **Expanded:** grows upward into a message log (E2, `--radius-md`,
  max-height 60vh, internal scroll), input pinned at bottom.
- **Graft 2 (terminal):** the dock's status dot + word reflect the REAL
  agent state: `--good` dot + `GROUNDED` after an answer that cites a tool/
  endpoint; `--warning` dot + `THINKING` while a request is in flight
  (pulse only if `prefers-reduced-motion` allows; static otherwise);
  `--ink-3` dot + `OUT OF SCOPE` after a refusal. Word in `--text-2xs`
  uppercase `--ink-3`.
- Messages — user: right-aligned, `--accent` 8% wash, `--ink` text. Agent:
  left-aligned, `--panel-2`, `--ink` text; every number in a
  `tabular-nums` `--ink` span (never accent-colored).
- **Citation chip** under any agent message that reports figures: pill, 1px
  `--border`, `--text-2xs`, `--mono` for the call part —
  `⚙ decompose_waterfall(t0=59, t1=60)`. This chip is the product's
  anti-hallucination promise made visible; it is not optional.
- **Refusal is not an error:** neutral `--panel-2` row + hairline
  "outside scope" pill in `--ink-3`. Never `--critical`, never red.
- **Graft 5 (terminal):** with the 160px shell bottom reserve (§3), the
  collapsed dock must never overlap the final table row at max scroll; on
  viewports < 620px the dock collapses to an icon pill.

---

## 6. Not adopted (binding rejections — do not resurrect)

- **Serif display faces, warm-paper surfaces (editorial):** a taste bet the
  editorial rationale itself says needs A/B evidence; costs a full chrome
  re-skin and forks from the shipped token values. Rejected.
- **Broken/two-zone axis waterfall (editorial):** real ECharts engineering
  (two stitched grids or manual pixel placement) with a subtle-wrongness
  failure mode; rejected in favor of §8.2's floored linear scale + disclosure.
- **Mono/tabular numerals on stat-tile values (terminal):** the dataviz
  figure rule stands — proportional for lone big numbers, tabular in columns.
- **All-caps micro-label density + raw endpoint stamps in every header
  (terminal):** legibility cost for non-quant client readers; provenance
  lives in the exhibit FOOTER (§5.2) in mono, headers stay sentence-case.
- **Status green/red painted on waterfall movements (editorial):** the bridge
  is a polarity read (diverging pair), not a value judgment; a credit
  committee may read "built provisions" as prudent, not bad.

---

## 7. The AI-explain affordance (every stat tile + every exhibit panel)

The signature component: proof the agent reads THIS panel.

### 7.1 Icon
A 4-point spark, one inline SVG path in `currentColor`, 16px — no icon font:

```html
<svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
  <path d="M8,0 L10,6 L16,8 L10,10 L8,16 L6,10 L0,8 L6,6 Z"/>
</svg>
```

### 7.2 Hit area & states
- 28×28px, circular (`--radius-pill`) — visually distinct from the SQUARE
  (`--radius-sm`) table-view toggle beside it. Hold this pairing app-wide.
- Rest: `color: var(--ink-3)`, transparent bg.
- Hover/focus: `color: var(--accent)`, bg `--panel-2`; tooltip "Ask Copilot
  to explain this" (`--text-xs`, E2 mini-panel, `attr(data-tip)` is fine).
- Active/open: `color: var(--accent)`, bg `--accent-wash`,
  `aria-expanded="true"`.
- Loading: 2px `--accent` ring; pulse only without `prefers-reduced-motion`.
- Accessible name: `aria-label="Ask Copilot to explain <panel title>"`.

### 7.3 Placement
Top-right of the tile/panel header, RIGHT of the table-view toggle — the last
element before the eye leaves the panel.

### 7.4 Response surface
The answer renders INLINE under the panel/tile it explains (never a modal): a
`--panel-2` strip, 1px `--border`, `--radius-sm`(8px ok), 14px padding, with a
22px round `--accent-wash`/`--accent` spark avatar, `--text-sm` `--ink-2`
prose, quoted figures in `--ink` `tabular-nums` spans, and a **citation chip**
(§5.5). While in flight, show the strip with a "THINKING" status word rather
than a spinner. A refusal renders in the neutral refusal style — an explain
click can be refused exactly like a typed question.

### 7.5 API convention (document in `docs/api_contract.md` when shipped)
REUSE `POST /api/agent/ask` — never a bespoke explain endpoint — so every
explain click passes the same tools/Tier-2/Tier-3/refusal governance. Merged
convention (fintech tag + editorial figure recap, graft 4):

```
question = "[explain:<panel_id> <live params>] <Exhibit label> — <panel title>: "
         + <one-line CODE-GENERATED recap of the exact figures the panel is
            rendering right now — built from the same payload the chart drew,
            never free text>
         + " What should I take from this?"
```

Example:

```
[explain:waterfall t0=59 t1=60] Exhibit 1 — Allowance bridge: opening $X.Xm,
stage migration +$X.Xm, remeasurement +$X.Xm, derecognitions −$X.Xm, new
loans +$X.Xm, closing $X.Xm. What should I take from this?
```

The recap makes the answer verifiably about the rendered numbers;
`POST /api/agent/interpret {tool, result}` remains available for structured
tool-result interpretation, but the explain affordance goes through `/ask`.

---

## 8. Chart restyle rules (ECharts — one theme accessor, both modes)

Keep the `palette.js` live-accessor pattern (`tokens()`, `colors()`,
`chartText()`, read inside option builders per render + `useThemeVersion`).
Update `tokens()` to return the §1.1 values; update the categorical arrays to
§1.2 order.

### 8.1 Global (every chart)
- `backgroundColor: 'transparent'` — the panel paints the surface.
- **One y-axis, always.** Two differently-scaled measures = two charts or an
  indexed line. No exceptions.
- Text: `--sans`; axis labels 12px `--ink-2`; ticks/units `--ink-3`;
  `tabular-nums` on numeric axis labels. Chart text NEVER wears a series hue.
- `axisLine`: hidden except the baseline (`--baseline`, 1px, solid);
  `axisTick`: hidden; `splitLine`: `--grid`, 1px, **solid — never dashed**
  (the current `WaterfallChart.jsx` dashed splitLine goes away).
- `grid: { containLabel: true }`, padding ≥16px each side, ≥48px bottom when
  category labels rotate.
- Ticks round to clean numbers, thousands-comma'd.
- Bars: `barMaxWidth: 24`; `itemStyle.borderRadius` `[4,4,0,0]` growing up /
  `[0,0,4,4]` growing down — rounded ONLY at the data end, square at the
  baseline; 2px `--panel` gap between adjacent/stacked fills
  (`itemStyle.borderColor: surface(), borderWidth: 2` on stacks; check the
  rendered gap ≈2px at build width).
- Lines: width 2, round cap/join; markers ≥8px with 2px `--panel` ring.
- Area: series hue at 10% opacity, never saturated.
- Legend: rendered ONLY for ≥2 series (single series: the title names it);
  `--ink-2` text; toggled-off series fades, never disappears from the row.
- Tooltip: E2 panel (`--panel-2`, `--border-strong`, `--radius-md`,
  `--shadow-e2`); value FIRST (`--text-base` 600 tabular), series name second
  (`--ink-2`); crosshair (`axisPointer: 'line'`, `--baseline`, solid) on
  line/area; per-mark emphasis on bar/scatter, no crosshair.
- Direct labels: selective — bars at the cap in `--ink`; lines at last point
  only. Never a number on every point of a dense series.
- Category order = API order (`components[]`, `[up, base, down]`) — never
  re-sorted by value.
- `animationDuration: prefersReducedMotion ? 0 : 300`.
- **Table-view twin:** every chart panel ships the square ghost icon-button
  that swaps the plot for a `<table>` built from the SAME series array.

### 8.2 Waterfall (`WaterfallChart.jsx`)
- Standard ECharts bridge recipe (invisible base stack + visible series) on a
  **true linear scale** — no log axis, no axis break.
- Fill by KIND: `level` → `--level-fill`; positive delta → `--increase`;
  negative delta → `--decrease`. Legend (3 identities, always shown):
  "Running total / Adds to allowance / Reduces allowance".
- Value label OUTSIDE every column, above the higher end of its span, in
  `--ink` (never inside a fill, never in the series color), signed
  (`+$3.9m`, `−$21.2m`) via `format.js`, tabular.
- **Minimum visible height:** floor any rendered segment below ~3% of plot
  height to that floor, and disclose in the panel caption: "components under
  ~3% of range shown at a minimum visible height — labeled values are exact."
  The floor changes pixels, never labels.
- **Default window = the latest single quarter** (t=59→t=60), where the floor
  rarely triggers; long cumulative windows (e.g. t=20→t=40, whose 250:1 skew
  makes small bars sub-pixel) are an explicit user drill-down, clearly
  subtitled — never the executive default.
- Optional thin solid `--baseline` reference lines at opening/closing levels.
- Historical mode: fixed per §0.2 (adapter + regression check) before restyle.

### 8.3 Stage mix (`StageMixBar.jsx`)
Stage 1/2/3 use STATUS colors (good/warning/critical) — a genuine risk-state
read, the one sanctioned status-on-chart use. Because warning is 1.79:1 on
light, the legend MUST carry value labels ("Stage 2 (SICR) · 1.4% · 3 loans")
and segments get the 2px `--panel` gap; never color-alone.

### 8.4 Scenario charts (`WeightsBarChart.jsx`, Scenario Lab)
Grounded thin bars, direct-labeled at the cap in `--ink`; Down/Base/Up in
monotone order (never interleaved). If scenario severity is colored as a ramp,
use one blue family light→dark (Up `#86b6ef`/`#6da7ec`, Base
`#2a78d6`/`#3987e5`, Down `#104281`/`#184f95` — judge-validated ordinal,
passes all four checks both modes); otherwise plain `--accent` with the status
dot carried by the adjacent table.

### 8.5 Line/time-series (`CreditCycleChart.jsx`)
Series colors from §1.2 slots in fixed order; ≤4 series also direct-labeled at
line ends; legend always present at ≥2 series; crosshair tooltip per §8.1.

---

## 9. Accessibility roll-up (ship gates)

1. Table view exists for every chart; sub-3:1 categorical hues (magenta,
   yellow, aqua on light) and warning/serious status never appear without a
   visible label or table twin.
2. Focus ring everywhere interactive: `0 0 0 2px <surface>, 0 0 0 4px
   var(--accent)`.
3. Status always dot/icon + word, never color alone (incl. dock states §5.5).
4. API strings via `textContent` only (tooltips, legends, citation chips).
5. `prefers-reduced-motion` kills chart animation and all pulses — static
   fallback states, not missing states.
6. Refusal never borrows `--critical`.
7. Dark mode is a SELECTED variant (own validated steps per §1) — never an
   automatic inversion. Any new text/fill pairing gets a `contrast()` check
   against its actual surface before merge.
