# Requirement 11 — Exhaustive App Guide (user-mandated, binding for the app-guidebook chapter)

The app chapter is NOT a tour — it is a complete reference: **every page, every section,
every image**. Coverage must be provably exhaustive, not narrative.

## Mechanical completeness law

The chapter author MUST derive the coverage checklist from the code, then document every
item on it — and the reviewer MUST re-derive the same list and diff it against the chapter:

1. Enumerate tabs from `app/ui/src/app.jsx` (TABS array — 6 tabs incl. Real Data).
2. Enumerate every panel per tab: grep `Panel`/`PanelHeading`/`<h2>`/EXHIBIT kickers in
   each `app/ui/src/tabs/*.jsx` + shared components (WaterfallChart, CreditCycleChart,
   StatTile rows, SearchableTable, WeightsBarChart, StageGuide, AgentTrace, ChatPanel,
   MiniChatDock, SelectionExplain, ExplainButton/ExplainStrip).
3. Enumerate every image/exhibit: `/api/exhibits/list`, `/api/freddie/exhibits`, plus
   static PNGs referenced by the UI; MDD link in header.

## Per-item documentation (each tab / panel / image gets all of these)

- **What it shows**: the exact data source (endpoint + contract fields + the outputs/*
  file behind it) and the meaning of every number/axis/color.
- **How to read it**: interpretation in plain language + one concrete example reading
  using the real live values.
- **How to use it**: every control (sliders, dropdowns, buttons, text inputs), what
  changes when you use it, and what does NOT change (e.g. scenario controls vs the
  historical waterfall — the recorded user confusion).
- **AI affordances**: the ✨ explain icon behavior on that heading, the selection-explain
  chip, the chat dock status states (GROUNDED / REASONED / THINKING / OUT OF SCOPE) and
  what each means about answer trustworthiness.
- **Screenshot or rendered image** of the panel (captured from the live Space or a local
  run; image-QA'd like every other figure).
- **Gotchas** specific to that panel (empty states, API-offline behavior, refusal cases).

## Also required

- A "60-second orientation" quick-start path through the app.
- The full endpoint→panel wiring table (which API call feeds which panel, with contract
  field names).
- Docker/deployment linkage: which image layers serve which static assets.
- Quiz: "where would you look to answer X" questions.
