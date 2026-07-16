# Rationale — The Consulting Deliverable

## Why this direction serves the north star

**The operator's complaint was never about missing features — it was about
the thing not looking like something worth sending.** Two "underwhelming"
verdicts on a functionally complete, 509/509-green app point at aesthetic
confidence, not capability. This direction makes the single biggest bet
available: stop looking like an internal analytics dashboard and start
looking like the deliverable a consulting engagement actually produces —
a document a partner signs their name to, that happens to be interactive.
Concretely:

- **Numbered exhibits make every number traceable, which is the same promise
  as "never hallucinated numbers," expressed visually.** Exhibit 1 and
  Exhibit 2 each carry a source line and a caption; nothing floats
  unattributed. A client reading this can point at a figure and ask "where
  did this come from" and the page already answers structurally, before the
  Copilot says a word.
- **The AI-explain chip reuses `POST /api/agent/ask` with a structured,
  code-generated prefix (design_spec.md §4.6) — never a bespoke
  "explain-chart" endpoint.** That was a deliberate seam choice: every
  explanation, whether typed by a user or triggered by clicking an exhibit,
  passes through the same tool-routing/Tier-2/Tier-3/refusal governance. The
  visual affordance is new; the trust boundary is not.
- **The report puts the agent in the margin, not the center of the page** —
  a quiet footnote-style chip per exhibit plus a collapsed dock, rather than
  a chat window competing with the numbers for primary attention. This
  matches the north star's own framing: *pre-generated analysis* is the
  headline; the agent is the annotation layer that interprets it on demand.
  A chat-first layout would have inverted that hierarchy.
- **The KPI row is deliberately unnumbered while the charts are Exhibit 1/2.**
  That distinction (front-page headline stats vs. numbered supporting
  exhibits) is a real report convention, and it does product work here too:
  it separates "the four things everyone needs at a glance" from "the
  analysis that explains them," which is exactly the pre-generated-analysis
  /  self-serve-lab split the product is built around — this Executive tab
  is the deliverable; Scenario Lab is where a client goes to poke at it
  themselves.
- **Every color decision traces to the dataviz skill's six checks, not
  taste** (design_spec.md §1, §7 has the validator transcript). That's not
  incidental to "looks like a consulting report" — real consulting decks get
  printed, projected, and read by colorblind stakeholders, and a palette
  that only works on one calibrated monitor doesn't survive that. Reusing
  the app's *existing* validated hues (rather than a new invented palette)
  also means this direction could be adopted incrementally: it changes
  chrome, type, and spacing, not the underlying color contract
  `app/ui/src/palette.js` already ships.
- **Serif is reserved for prose and titles; every number stays in the sans,
  always proportional, never tabular except in aligned columns** — a small
  rule with an outsized trust effect: the reader's eye learns, within one
  scroll, that "serif = someone wrote this" and "sans, bold, large = the
  model computed this." That's a visual contract for "never hallucinated
  numbers" as much as a typographic one.
- **The CSP constraint became a feature, not a compromise.** No remote font
  request means no FOUT/FOIT, no failed-fetch fallback flash, no dependency
  on a CDN being reachable when a client opens the link. The serif stack
  (`Iowan Old Style → Palatino → Georgia → Cambria → Times → serif`)
  degrades gracefully to *some* legitimate serif on every platform the app
  actually runs on.

## Where it risks failing

- **This is a stronger stylistic bet than the shipped app's neutral palette,
  and it will not read as "obviously more modern" to everyone.** Warm paper
  and a serif headline can land as "considered and expensive" or as
  "old-fashioned / PDF-like," depending on the viewer's prior. If the primary
  audience is technical operators expecting an "AI-native" product feel
  rather than a credit-committee readership, this direction should be
  A/B'd against a cleaner sans-only variant before committing — it is a
  taste bet, not a neutral improvement, and the brief's own instruction to
  explore multiple directions in parallel suggests that comparison is
  already the plan.
- **The waterfall's two-zone, marked axis break is a legitimate technique
  (used deliberately here, not to hide anything — see the in-page
  data-quality flag) but it is real engineering, not a free upgrade over a
  single-scale ECharts waterfall.** Getting a clean break in production
  ECharts means either two `grid`/`xAxis` pairs stitched together or manual
  pixel-space bar placement (closer to what this static mock does by hand)
  — meaningfully more surface area than the app's current single-scale
  `buildOption`, and a rushed port could get zone continuity subtly wrong in
  a way a screenshot won't catch (only checking that consecutive running
  totals actually agree, as this mock's numbers do, will catch it).
- **The waterfall's own numbers do not reconcile.** Opening `$24.5m` walking
  to a closing `$1,032.6m` sits nowhere near the `$34.0m` headline allowance
  stat tile on the same page. The mock renders the figures exactly as
  supplied and flags the mismatch directly under the chart (in-page,
  not buried in this file) rather than quietly "fixing" or omitting it —
  but a design direction can only *frame* a data problem honestly, not
  resolve it. This looks adjacent to the already-diagnosed
  `WaterfallChart.jsx` historical-payload bug (raw `components` shape fed to
  a `{start,steps,end}`-shaped `buildOption`); whoever wires real numbers
  into this frame needs to confirm the reconciliation before a client sees
  it, or the visual promise of "every exhibit foots" is broken by the first
  chart in the deck.
- **One accent, two contexts (data-mark vs. UI) is intentionally minimal —
  and minimal runs out.** The moment a Model-tab exhibit needs true
  multi-series identity (PD by vintage cohort, five segments on one chart),
  this direction has to reach back into the full 8-hue categorical order
  (documented in reserve, §1.4) for the first time. That's a planned, not
  improvised, expansion — but this pass never actually exercises it, so the
  "does the restrained system still feel like one system once it's not
  restrained anymore" question is untested.
- **Hairline-only separation between page and panel is a deliberate,
  quiet choice (`#f7f5f0` vs `#fffcf6` is intentionally close — a sheet on
  a desk, not a card floating above it) but it is close: under a
  non-calibrated display, `forced-colors` mode, or a printed black-and-white
  export, that boundary can all but disappear.** A `forced-colors`/
  `prefers-contrast: more` fallback (a slightly heavier border or a hairline
  shadow) is worth adding before this ships past a mock.
- **The AI-explain chip is the one rounded shape in an otherwise
  square-cornered, print-like system** (design_spec.md §4.6 calls this out
  as deliberate — a footnote-marker metaphor, not a UI inconsistency). That
  reading needs to actually land with users; it's the kind of small
  deliberate-exception decision that either reads as "of course, that's the
  interactive one" or as a stray inconsistency, and only usage will tell
  which.
- **Status colors encode a value judgment (allowance up = critical/red,
  allowance down = good/green) that is true from a P&L lens but may not sit
  well with every audience** — a credit-risk committee can reasonably view
  "the model correctly built more provisions this quarter" as prudent, not
  bad news. The reserved neutral Diverging pair (§1.6, documented but unused
  here) is the fallback if that framing doesn't land with real stakeholders
  — swapping it in is a one-line color change, not a redesign, because the
  bar geometry and layout don't depend on which pair is doing the coloring.

## What was intentionally left alone

Per the task brief, nothing under `app/ui` was touched, read for editing, or
assumed to change as a side effect of this exploration. The known
`WaterfallChart.jsx` historical-mode bug is referenced above only because
this mock's own numbers brushed up against the same shape of problem
(raw component payload vs. the chart's expected contract) — this design
pass does not fix it, and doesn't need to: fixing it is a code change to a
file this task explicitly excludes.
