# ch09_app_guide.html

Ch.9 — The App: A Guidebook | IFRS9 ECL Study Notes

☼

# Chapter 9 — The App: A Guidebook

A mechanically-exhaustive reference to every tab, every panel, every image the IFRS 9 ECL Copilot ships — derived from the code, not a tour

IFRS9 ECL Study-Notes Compendium — Chapter 9 of 13. Compiled from 
app/ui/src/app.jsx
, every file under 
app/ui/src/tabs/
 and 
app/ui/src/components/
, 
docs/api_contract.md
, 
app/api/main.py
, 
Dockerfile
, 
outputs/design/FINAL_SPEC.md
 and the three candidate 
rationale.md
 files, plus live calls against a local 
uv run --no-sync uvicorn app.api.main:app --port 7861
 instance (engine warm, live LangGraph agent) captured 2026-07-19 — every quoted number is a real response from that session, not retyped from the contract doc's own examples.

Contents.

9.1 The 60-second orientation

9.2 Architecture at a glance

9.3 Tab 1 — Executive Overview

9.4 Tab 2 — The Model

9.5 Tab 3 — Scenario Lab

9.6 Tab 4 — Policy

9.7 Tab 5 — Real Data (Freddie SFLLD)

9.8 Tab 6 — Copilot

9.9 AI affordances, in full

9.10 The endpoint → panel wiring table

9.11 Docker & deployment linkage

9.12 Three design directions → the shipped spec

9.13 Closing quiz bank — "where would you look to answer X"

## 9  The App: A Guidebook

Chapters 1–7 built and validated the frozen IFRS 9 ECL engine; Chapter 8 opened up the
LangGraph agent that answers questions about it. This chapter is the third leg: the actual product a bank
risk analyst opens in a browser. Per 
notes/plan/requirement_11_app_guide.md
 (binding, supersedes
the lighter "tour" framing this chapter might otherwise have taken), the law here is

mechanical completeness, not narrative
 — the coverage checklist below was derived FROM THE
CODE this session (the 
TABS
 array in 
app/ui/src/app.jsx
; every

Panel
/heading/EXHIBIT kicker in the six 
app/ui/src/tabs/*.jsx
 files and the shared
components they compose; every image enumerated via 
/api/exhibits/list
,

/api/freddie/exhibits
, the two consultant-curated exhibit lists, plus the MDD static mount) and a
reviewer is expected to re-derive the same list independently and diff it against what follows. Every panel
below gets the same six-part treatment requirement 11 mandates: what it shows, how to read it, how to use
it (including what does 
not
 change), its AI affordances, a rendered visual, and its gotchas.

### 9.1 The 60-second orientation

Before the exhaustive walk, the fast path — what a first-time visitor should actually do, in order, to
understand what this app is:

60 seconds, six steps.

Land on Executive Overview
 (the default tab, 
tabFromHash()
 falls back to

'executive'
). Read the four KPI tiles top-left to right: allowance, coverage, Jensen ratio,
reporting date. This is the headline number a credit committee asks for first.

Read the "Consultant's read" panel.
 It is template prose (explicitly 
not
 an LLM call —
the component's own top comment says so), every number filled in from the same

GET /api/ecl/summary
 payload that drove the tiles above it — a sanity-checked narrative, not a
second, independently-fallible source.

Click the ✦ spark icon on any tile or panel heading.
 This is the AI-explain affordance (full
mechanics in §9.9) — it fires a real 
POST /api/agent/ask
 call with a code-generated recap of the
exact numbers that panel is showing, and answers GROUNDED (cited to a tool) or REASONED (cited interpretation,
no fresh number) inline, never a modal.

Switch to Scenario Lab
 (tab 3) and move a slider — reweight the up/base/down scenario mix or apply
a macro shock. Watch the Result card and the Allowance bridge chart update live; nothing else on the page
moves (the historical waterfall on the Executive tab is a 
separate, fixed exhibit
 — see the
scenario-controls-vs-historical-waterfall gotcha in §9.3/§9.5, the single most consistently mis-read distinction
in this app per the recorded user-confusion note requirement 11 flags explicitly).

Open Copilot
 (tab 6) and ask a free-text question, or click one of the three suggestion chips.
Watch the Agent trace panel stream the router's decision, the tool call, and the narration in real time over
SSE — the same three-tier architecture Chapter 8 documented, now visible as it happens.

Open the MDD link
 in the header (top-left, next to the brand mark) for the full Model Development
Document — the governance artifact this whole app is a live demonstration of (bridges to Chapter 13).

Interpretation.
 That ordering is deliberate, not arbitrary: it walks the same "pre-generated analysis
is the headline, the lab is where you poke at it, the agent is the annotation layer, not the centerpiece"
hierarchy the shipped design spec argues for (§9.12) — Executive Overview is the deliverable a client reads
passively; Scenario Lab is where they touch it; Copilot is where they interrogate it in free text; the MDD
link is the paper trail underneath all three.

### 9.2 Architecture at a glance

One FastAPI process (
app/api/main.py
) serves both the JSON API and the built Preact/ECharts SPA
from a single origin — 
docs/api_contract.md
's very first convention is "no CORS anywhere" because
there is only ever one origin to begin with. Three route groups, registered in an order that matters
(Starlette matches in registration order, so the more specific static mounts must win before the catch-all
SPA mount):

Route group
Serves
Guard

/api/*
 (22 endpoints)
JSON — engine reads, Tier-1 tool calls, agent ask/stream,
The Model / Policy / Real Data / auto-interpret endpoints
always registered first

/static/exhibits/*
, 
/static/freddie/*
, 
/static/mdd/*

read-only PNG/HTML mounts over 
outputs/
, 
outputs/freddie/
,

outputs/mdd/
each 
if <dir>.exists()
 guarded — a missing directory
404s harmlessly rather than crashing app boot

/
 (catch-all)
the built SPA, 
app/ui/dist
, mounted LAST with

html=True
 so client-side hash routing works on refresh
falls back to a plain "not built
yet" HTML response if 
dist/index.html
 is missing

The SPA itself is a hash router with no routing library (
app.jsx
's own comment: "Simple hash
router — no router library, per the north-star build spec"): 
TABS
 is a 6-element array
(
executive
, 
model
, 
scenario
, 
policy
, 
freddie
,

copilot
), 
location.hash
 drives 
tabId
, and Left/Right arrow keys cycle
tabs when a tab button has focus (
onTabKeyDown
). Two floating elements sit OUTSIDE the six
per-tab bodies and are shared app-wide: 
SelectionExplain
 (any tab, highlight text anywhere in

.app-main
) and 
MiniChatDock
 — rendered on every tab EXCEPT Copilot
(
{tabId !== 'copilot' && <MiniChatDock />}
, i.e. Executive, Model, Scenario, Policy
AND Real Data — five tabs, not "tabs 1-4" as the component's own top comment claims; a small
code/self-documentation drift, harmless but worth knowing if you go looking for it, noted again as a
component-level gotcha in §9.9).

Gotcha — the header's book stats and the tab content can be from two different calls.
 The header's

meta
 state (
{meta.as_of.period} · {n_loans} loans · {balance} book
) is fetched ONCE
at app mount via its own 
getSummary()
 call in 
App()
, independently of whatever the
active tab fetches. In practice both calls hit the same frozen 
GET /api/ecl/summary
 endpoint and
so always agree (the engine is frozen, not live-changing), but architecturally they are two separate HTTP
round-trips, not one shared cache — worth knowing if you are ever debugging a stale-header report.

### 9.3 Tab 1 — Executive Overview

app/ui/src/tabs/ExecutiveTab.jsx
 — "the consultant's headline read of the book as reported."
Six panels/panel-groups, all fed by a single 
GET /api/ecl/summary
 call except the two chart
panels at the bottom which fetch their own endpoints.

Exhibit 9.1
 — Executive Overview, tab layout (header + 4 KPI tiles + Exhibit 1 stage
mix + Exhibit 2 scenario table; Exhibit 3 Allowance bridge and Exhibit 4 Credit cycle render below this and get
their own detailed figures, Exhibits 9.2/9.3) — rendered from a live 
GET /api/ecl/summary

call, 2026-07-19.

#### Panel group — 4 KPI tiles (
StatTile.jsx
, unnumbered)

##### Scenario-weighted allowance / Coverage / Jensen ratio / Reporting date

unnumbered

Shows
Four headline stats read directly off 
GET /api/ecl/summary
:

weighted_allowance
 (raw USD, UI divides by 1e6), 
coverage
 (a ratio, UI multiplies by
100), 
jensen_ratio
 (a ratio, shown as "×"), and 
as_of.period
/
as_of.t
.

How to read it
Live capture: allowance 
$34.0m
 across 7,849 loans, $1,673.7m balance;
coverage 
2.03%
 (allowance / balance); Jensen ratio 
1.0353×
 (weighted allowance $34.0m vs $32.9m
at the single weighted-average macro path — the scenario-weighted number runs 
above
 the
single-path number, the convexity signature Chapter 6 derives); reporting date 
2015Q1
 (t=60 of
60).

Controls
None — these four tiles are read-only. They do NOT move when you later visit Scenario Lab
and run a control there; Scenario Lab's controls act on its own separate result card and waterfall, never on
this tab's tiles (see the scenario-controls-vs-historical-waterfall gotcha below).

AI affordances
Each tile carries its own ✦ explain icon (top-right of the tile, per

StatTile.jsx
) with a panel-specific recap — e.g. the Jensen-ratio tile's question recaps
"Jensen ratio is 1.0353× — scenario-weighted allowance $34.0m vs allowance at the averaged macro path
$32.9m." Full mechanics in §9.9.

Gotchas
The Jensen-ratio tile's hint text ("weighted ECL vs avg-path ECL") is easy to misread as
"weighted ECL vs a SINGLE scenario's ECL" — it is specifically the ECL at the PROBABILITY-WEIGHTED AVERAGE
macro path, not any one of the three named scenarios (Chapter 6's Jensen's-inequality construction).

#### Panel — Stage mix of allowance (
StageMixBar.jsx
)

##### Stage mix of allowance

Exhibit 1

Shows
A single stacked horizontal bar, part-to-whole share of the reported allowance by IFRS 9
stage. Endpoint: 
GET /api/ecl/summary
, fields

stage_mix.{stage1,stage2,stage3}.{n_loans,allowance,allowance_pct_of_total}
 —

allowance_pct_of_total
 is already 0–100 scale, never re-multiplied.

How to read it
Live capture: Stage 1 (green, performing) 
80.74%
 of allowance across
7,803 loans; Stage 2 (amber, SICR) 
1.43%
 across just 3 loans; Stage 3 (red, impaired)

17.83%
 across 43 loans. Segments under 6% (Stage 2 here) skip their inline percentage label to
avoid collision — the legend below the bar still names every segment with its exact share and loan count.

Controls
None — a static read of the current reporting date's stage mix. The colours are STATUS
semantics (green=good/performing, amber=warning/SICR, red=critical/impaired), not arbitrary categorical
identity, and are never reused for a different meaning elsewhere in the app.

AI affordances
Standard explain icon (§9.9); its recap states all three stages'
percentage-of-total and loan counts in one sentence, so an "explain this" question always has the exact
current numbers in front of the router even if the reader never looked at the legend.

Gotchas
Stage 2 at 3 loans / 1.43% of allowance looks negligible in a calm-quarter book — this
is 2015Q1 specifically (a calm reporting date per Chapter 1); the Policy tab's staging-sensitivity exhibit
(§9.6, Exhibit 1) shows the SAME threshold convention pushes Stage 2 to 75.76% of the book in a
STRESS quarter (t=40, 2010Q1) — this tile is a snapshot, not a claim that Stage 2 is always small.

#### Panel — Consultant's read (unnumbered, template narrative)

##### Consultant's read

unnumbered

Shows
A full paragraph of prose, every number substituted from the same 
GET
/api/ecl/summary
 payload as the tiles/bar above it. The component's own top comment is explicit:
"Template narrative — NOT an LLM call... this is consultant prose with blanks filled in, per the north-star
spec ('template, not LLM')." This is the one panel in the app that is guaranteed never to hallucinate anything,
by construction — it cannot invent a number because it has no generative step at all.

How to read it
The narrative states the same headline figures as the tiles in sentence form, plus
one derived observation the tiles don't spell out directly: "the reported number is set almost entirely by
12-month ECL" (because this calm-quarter book is 80.7% Stage 1) — "and therefore is exactly where
scenario weights and macro shocks act (see Scenario Lab)," an explicit pointer to where a reader should go
next if they want to stress this number.

Controls
None — read-only, regenerated fresh on every page load from the live summary payload
(never a static/cached string), so it always agrees with the tiles above it.

AI affordances
Standard explain icon; its recap is the entire narrative paragraph itself (the

buildExplainQuestion
 passes 
recap: narrative(summary)
 verbatim) — clicking ✦ here
effectively asks the agent "does this paragraph hold up," a genuine cross-check of the template prose against
the agent's own independently-grounded read.

Gotchas
Because this is template text, not an LLM call, it can never explain a number that ISN'T
already in the summary payload — if a reader wants a number this paragraph doesn't cover (a segment cut, a
specific loan), that is exactly the job Copilot's 
analyze_data
 (Tier-2, Chapter 8) is for,
not this panel.

#### Panel — Scenario table (
ScenarioTable
, inline component)

##### Scenario table

Exhibit 2

Shows
One row per named scenario (up/base/down) from 
GET /api/ecl/summary
's

scenarios[]
 array: weight, allowance ($m), coverage (%), UER peak (pp). A leading coloured dot
per row (FINAL_SPEC §5.3/§1.3 convention) — up=good, base=neutral, down=critical — carries STATUS semantics,
same discipline as the stage-mix bar.

How to read it
Live capture: 
up
 25% weight, $27.7m allowance, 1.65% coverage, UER peak
6.4pp; 
base
 50% weight, $30.5m allowance, 1.82% coverage, UER peak 6.4pp (up and base share the same
UER peak by construction — the DFAST base and the project's "upside" macro path do not diverge on this one
driver); 
down
 25% weight, $47.6m allowance, 2.84% coverage, UER peak 11.2pp — nearly 4pp higher
unemployment stress than the other two scenarios, which is most of why its allowance nearly doubles the base
case.

Controls
None on THIS panel — it is the adopted 25/50/25 basis, read-only. The panel's own caveat
box states the coherent-shock convention explicitly: the satellite behind these numbers has NO unemployment
term (Z = f(hpi_growth_lag1, gdp_growth_lag2)), a fact worth knowing before assuming UER peak alone explains
the allowance gap.

AI affordances
Standard explain icon; recap lists all three rows' weight/allowance/coverage in one
semicolon-joined sentence.

Gotchas
This table is NOT interactive.
 A reader who wants to see what a DIFFERENT weighting
(say 15/35/50) does must go to Scenario Lab's "Reweight scenarios" control (§9.5) or the Policy tab's
scenario-weight sensitivity table (§9.6, Exhibit 2, which shows exactly that alternative pre-computed) —
this Executive-tab table always shows the single adopted 25/50/25 basis.

#### Panel — Allowance bridge (
WaterfallChart.jsx
, shared component)

##### Allowance bridge

Exhibit 3

Shows
An ECharts waterfall of the movement decomposition between two reporting snapshots.
On the Executive tab specifically, 
WaterfallChart
 is invoked with fixed props

t0={59} t1={60} action={null}
 — the LATEST single quarter, per the component's own comment
("Default window = the latest single quarter (FINAL_SPEC §8.2) — long cumulative windows... are a Scenario
Lab drill-down, never the executive default"). Endpoint: 
GET
/api/ecl/waterfall?t0=59&t1=60
, six components (opening/stage_migration/remeasurement/
derecognitions/new_loans/closing) that sum exactly (
identity_gap ≈ 0
).

How to read it
Live capture, t=59 (2014Q4) → t=60 (2015Q1): opening 
$18.8m
, stage migration

+$0.9m
 (43 loans), remeasurement 
+$4.7m
 (7,804 loans — nearly the whole live book re-measured),
derecognitions 
−$8.9m
 (269 loans paid off/wrote off), new loans 
+$0.1m
 (45 loans), closing

$15.5m
. Identity gap: 5.6×10⁻⁹ (floating-point noise, not a reconciliation failure).

How to use it
A 
⊞
 icon top-right toggles chart↔table view (same six rows, tabular).
No sliders here — this is a FIXED historical exhibit.

AI affordances
Standard explain icon; recap states opening, every step delta, and closing in one
sentence, built from the SAME adapted row data the chart renders (
recapFor(wf)
), never
hand-typed.

Gotchas — THE recorded user confusion, requirement 11 flags this explicitly.

This waterfall is fixed history — it answers "what happened to the allowance between two ACTUAL past
reporting dates." It is easy to conflate with Scenario Lab's version of the SAME component (§9.5), which
instead shows a HYPOTHETICAL shock/decomposition result on demand. Concretely: moving a Scenario Lab slider
does 
not
 change this Executive-tab chart's six numbers — they are t=59→t=60 history, always. The
subtitle text says so directly ("fixed exhibit — scenario controls act on the reported allowance above, not
on this history") specifically because this confusion was observed and named in the design brief.

Exhibit 9.2
 — Allowance bridge, t=59 (2014Q4) → t=60 (2015Q1) — rendered from a
live 
GET /api/ecl/waterfall?t0=59&t1=60
 call, 2026-07-19.

#### Panel — Credit cycle, PIT vs TTC (
CreditCycleChart.jsx
)

##### Credit cycle — PIT vs TTC

Exhibit 4

Shows
A three-line time series over all 60 panel quarters: observed default rate, TTC PD, PIT PD.
Endpoint: 
GET /api/exhibits/credit_cycle
, fields 
rho
 and 
points[].{calendar,
z, observed_dr, ttc_pd, pit_pd}
, all rate fields ratios (UI multiplies by 100).

How to read it
Live capture: ρ = 
0.0227
 (the project's own fitted asset correlation, well
below the Basel illustrative 0.12 — Chapter 5's calibration). The PIT PD line hugs the observed default
rate through the 2008–2009 GFC hump (both peak near 5% quarterly) while the TTC PD line stays comparatively
flat (~1.7–2.3%) throughout — exactly the PIT-vs-TTC philosophical distinction Chapter 5 derives: PIT
conditions on the current point in the credit cycle, TTC averages over it.

How to use it
Same 
⊞
 chart↔table toggle as the waterfall. No sliders — a static
60-quarter exhibit (the LIVE version of this same curve, with adjustable Z and ρ sliders, is a widget in
Chapter 5's notes, not in this app).

AI affordances
Standard explain icon; recap states ρ and the latest quarter's three values.

Gotchas
The subtitle names the recovery method explicitly ("Z recovered by Belkin inversion") —
Z here is not a directly observed series, it is INFERRED from the observed default rate via the Vasicek
model's inverse mapping (Chapter 5); reading it as a raw macro input would be a category error.

Exhibit 9.3
 — Credit cycle, PIT vs TTC (ρ = 0.0227) — rendered from a live

GET /api/exhibits/credit_cycle
 call, 2026-07-19.

### 9.4 Tab 2 — The Model

app/ui/src/tabs/ModelTab.jsx
 — "Coefficients, fit statistics, and the variable dictionary —
with the honest caveats." One intro panel plus six numbered exhibits, all Requirement 12 additions
(interpretation fields, macro glossary, FRED badges) layered onto the original coefficient tables.

Exhibit 9.4
 — The Model tab, hazard-ratio coefficients (default hazard, n=418,418) —
rendered from a live 
GET /api/model/coefficients
 call, 2026-07-19.

#### Panel — How to read these coefficients (
HowToReadCoefficients.jsx
, shared with Real Data)

##### How to read these coefficients

unnumbered

Shows
A collapsed 
<details>
 intro panel (no engine numbers, no explain
question needed beyond its own title) stating four rules once so neither this tab nor Real Data has to
re-derive them: (1) every model here is a discrete-time CLOGLOG hazard, so 
exp(coef)
 is a
genuine hazard ratio — Chapter 3's link derivation, referenced not repeated; (2) "1 unit" is not always
"1" (FICO is /100, LTV is /10 — read the row's own 
Unit
 line); (3) the 0.01-vs-1pp gotcha for
log-growth macro rows (table HR is scaled to a full 1.0 log-unit ≈ 100% quarterly growth, never observed —
the 
Per-unit HR
 column fixes this, computed as 
hazard_ratio ** 0.01
); (4) only
GENUINELY FRED-pulled rows (state-level, Real Data tab) carry a FRED badge — the national DCR rows are a
vendor-premerged series on the panel's own anonymized clock, calendar-verified against FRED UNRATE
(corr 0.996) but not a live pull.

Controls
Native 
<details>
/
<summary>
 expand/collapse, no JS.

AI affordances
None — plain prose panel, no 
buildExplainQuestion
 prop passed (the
one deliberate exception across this tab; the component's own comment states why: "no engine numbers -- so it
needs no explain-question recap beyond the panel's own title").

Gotchas
This panel is collapsed by default — a reader who skips it and goes straight to the
coefficient table risks the exact 0.01-vs-1pp misread it exists to prevent on the two HPI-growth rows.

#### Panel — Hazard-ratio coefficients (
CoefficientsTable
, inline component)

##### Hazard-ratio coefficients

Exhibit 1

Shows
The full fitted coefficient table for whichever of the two hazard models is selected
(default/prepay), grouped by family (baseline, borrower, collateral, macro, incentive) with a one-line family
"story" row. Endpoint: 
GET /api/model/coefficients
, fields

models.{default,prepay}.coefficients[].{variable, family, hazard_ratio, ci, p, p_display, story}

plus the Requirement 12 interpretation fields (
unit_meaning, transformation, lag, fred_series,
economic_channel, hazard_ratio_per_unit, worked_example
).

How to read it
Live capture, default hazard (n=418,418, McFadden R²=0.0761): Intercept HR

0.2658
; FICO at orig. (per 100 pts) HR 
0.6314
 (p<1e-16 — cleaner credit at origination lowers
the hazard 36.9%); Updated LTV (per 10pp) HR 
1.2250
 (+22.5% per 10pp); Unemployment level (lag 1)
HR 
0.6930
 in isolation (the level-vs-momentum decomposition, see the fit-stats caveat below — the NET
effect is risk-increasing); HPI growth (lag 1) table HR 
0.0318
 but Per-unit HR 
0.9661
 (the
0.01-vs-1pp correction in action — reading 0.0318 as "per 1% growth" would overstate the effect by orders of
magnitude); the DOUBLE TRIGGER interaction term HR 
0.9940
 (p=0.0375, significant but small,
Per-unit HR deliberately 
null
 — a product term has no single legible per-unit reading, see the
worked example instead).

How to use it
A segmented control ("Default hazard" / "Prepayment hazard") in the panel's

actions
 slot swaps the whole table's data source — clicking a row's ▸ toggle expands an

InterpretationRow
 beneath it (Unit, Transformation, Economic channel, Worked example, plus a FRED
badge if genuinely FRED-sourced — none are, on this DCR tab). Each row's toggle state is independent
(
useExpandableRows
, a per-table 
Set
).

AI affordances
Standard explain icon; recap states n, coefficient count, McFadden R², and the
single largest-magnitude hazard ratio (by absolute log), computed fresh from whichever model is currently
selected.

Gotchas
Cell shading is green for HR>1 (risk-increasing), red/pink for HR<1
(risk-reducing) — this is a magnitude-blind binary split, NOT a statistical-significance indicator; the
Condo row (HR 1.0649, p=0.141 — not significant at 5%) shades the same green as the FICO row (HR 0.6314,
p<1e-16 — overwhelmingly significant). Always check the 
p
 column separately.

#### Panel — Fit statistics (
FitStats
, inline component)

##### Fit statistics

Exhibit 2

Shows
A 2-row table (default/prepay) of n, events, train/OOT AUC, McFadden R², plus three
narrative caveat paragraphs read straight off 
fit_stats.{net_uer_effect_note, double_trigger_note,
seasoning_peak}
.

How to read it
Live capture: default hazard train AUC 
0.7476
, OOT AUC 
0.6609
,
McFadden R² 0.0761; prepayment hazard train AUC 
0.6839
, OOT AUC 
0.5841
, McFadden R² 0.0503. The
OOT-caveat box states plainly: OOT (t=41–60, 2010Q2–2015Q1) is the GFC stress AFTERMATH, not a random holdout
— the AUC drop is expected, not evidence of overfitting by itself. The net-UER-effect note resolves the
apparent sign puzzle from Exhibit 1 above: β(uer_lag1) + β(uer_chg4_lag1) = −0.3668 + 0.6135 = 
+0.2467

(hazard ratio 1.280 per pp) — PD genuinely RISES in unemployment once level and momentum are combined; the
negative level coefficient alone is a collinearity artifact (0.94 collinearity between the two terms), not an
economic sign reversal. Seasoning peak: fitted at quarter 12, empirical at quarter 10 (plausible
window 4–18).

Controls
None — read-only, same data source as Exhibit 1 (
GET
/api/model/coefficients
), no model-switch control of its own (it always shows both rows at once).

AI affordances
Standard explain icon; recap states both models' train/OOT AUC in one sentence.

Gotchas
Reading Exhibit 1's "Unemployment level" row (HR 0.693, apparently risk-REDUCING) in
isolation without reading this panel's net-UER-effect caveat is the single most likely misreading on this
whole tab — the two rows must be combined, per the note, to get the economically correct sign.

#### Panel — Seasoning & term-structure exhibits (image grid)

##### Seasoning & term-structure exhibits

Exhibit 3

Shows
An 
exhibit-grid
 of every consultant-curated PNG whose id starts with

hazard_
, filtered client-side from 
GET /api/exhibits/list
's 17-row payload:

hazard_age_baseline
 ("Fitted natural-cubic-spline age baseline of the default hazard") and

hazard_pd_term_structure
 ("Lifetime PD term structure implied by the fitted hazards").

How to read it
These are regenerated PNGs served at

/static/exhibits/hazard/age_baseline.png
 and 
/static/exhibits/hazard/
pd_term_structure.png
 — the same seasoning-hump curve Chapter 3's notes derive in full and the
same PD term-structure Chapter 2's ECL formula sums over.

Controls
None — a static image grid; 
ExhibitImage.jsx
 lazy-loads each PNG and
swaps to a "exhibit unavailable" placeholder on a 404 (never a broken-image icon).

AI affordances
Standard explain icon; recap lists how many exhibits rendered and their titles.

Gotchas
This is exactly 2 of the 17 total curated exhibits (filtered by id prefix). Tracing every
caller of 
GET /api/exhibits/list
 in the codebase (it is called from exactly one file,

ModelTab.jsx
) shows only ONE other id-filtered grid is ever built from it — the 3

lgd_
 rows, this tab's own Exhibit 6. The 
staging_stage2_sensitivity
 row's PNG
IS shown elsewhere (Policy's Exhibit 1, §9.6) but reached via a wholly separate endpoint
(
GET /api/policy/staging_sensitivity
's own 
image_url
 field, which happens to point at
the identical 
staging/stage2_sensitivity.png
) — not via this catalog. That leaves 11 of the 17
rows — 
staging_stage_distribution
 and all 3 
scenario_*
/1 
vasicek_*
/6

eda_*
 rows — with 
no UI consumer anywhere in the shipped app
 (verified by
grepping every id and PNG path across 
app/ui/src/
 and 
app/api/main.py
: no other hit).
They are real, servable catalog entries — 
/api/exhibits/list
 returns all 17 correctly and every
PNG resolves under 
/static/exhibits/
 — but orphaned in the current product, not merely
under-documented by this chapter.

#### Panel — Variable dictionary (
SearchableTable
)

##### Variable dictionary

Exhibit 4

Shows
Every one of 13 modelled variables, one row each: source/transformation, lag/window, economic
rationale, expected sign, fitted/verified checkmark, consumed-by, and a FRED badge column. Endpoint:

GET /api/model/variable_dictionary
, a preamble string plus 
rows[]
 (raw
markdown-lite source cells, rendered as-is — backtick-quoted variable names, ✓/⚡/↑/↓ glyphs included
verbatim).

How to read it
Live capture, row 1: 
fico_s
 = 
FICO_orig_time / 100
, lag
"static (origination)", rationale "Ability/willingness to pay", expected sign "PD ↓", fitted/verified
"✓ negative", consumed by "default hazard; LGD cure." Row 2: 
ltv10
 ⚡ (the lightning-bolt flags a
documented CURRENT-quarter exception to the lag convention — collateral value is a real-time state, not a
forecast), = 
updated_ltv/10
, rationale "Equity cushion / strategic-default trigger," expected
sign "PD ↑, severity ↑, cure ↓," fitted/verified "✓ all three." The preamble states the data window in full:
t=1..60 ≙ 2000Q2–2015Q1 (calendar-anchoring verified vs FRED UNRATE, corr 0.996), train=t≤40, OOT=t=41–60.

Controls
A free-text search box (
SearchableTable
) filters rows by substring match
across every column — try "uer" or "ltv"; a live row-count readout ("N / 13 rows") confirms the filter took
effect.

AI affordances
Standard explain icon; recap states the row count and the five family names spanned.

Gotchas
Five rows carry NO hazard ratio at all
(
loan_age
 — a spline basis, not individually interpretable; 
gdp_lag1
 /

gdp_growth_lag2
 — a single dictionary row conflating two different lags feeding two different
models (the DCR hazard's own GDP-growth row DOES carry a real per-unit HR, §9.4 Exhibit 1 — it is this
merged dictionary row specifically that declines to pick one); 
lgd_time (target)
 — an
LGD target, not a regressor; 
Z_t (recovered)
 — the satellite's dependent variable;

Scenario paths
 — a set of forward paths) — their 
hazard_ratio_per_unit
 and

worked_example
 fields are both explicitly 
null
, not a data-loading bug. (A sixth row,

dt_ltv_uer
, has a null 
hazard_ratio_per_unit
 too but — unlike these five — still
carries a prose 
worked_example
 pointing at the fit-stats double-trigger decomposition instead.)

#### Panel — Macro data glossary (
details
 + 
SearchableTable
)

##### Macro data glossary

Exhibit 5

Shows
The Requirement 12 centrepiece: every macro series used ANYWHERE in the app — DCR
(national), SFLLD (state, Real Data tab), and the satellite Z regression — one row per (series, model)
pairing, endpoint 
GET /api/model/macro_glossary
, 10 rows.

How to read it
Live capture — three representative rows: 
dcr_uer_level
 ("National
UER — level"), FRED ID 
null
, geography "US national," lag "1 quarter," lag rationale states plainly
this is "NOT a live FRED pull — a vendor-premerged national series on the DCR panel's own ANONYMIZED quarterly
clock; only the clock's CALENDAR alignment... was verified, via correlation against FRED UNRATE (corr 0.996)
— an anchoring check, not a sourcing claim." Contrast 
sflld_uer_level
 ("State UER — level"),
FRED ID 
{POSTAL}UR
 (a literal template — one series per state postal code), lag "1 month" (the SFLLD
panel's native monthly clock vs DCR's quarterly), which used_by "SFLLD champion hazard" only. The tenth row,

coherent_shock_convention
, carries no series-level facts at all (geography/frequency/lag all
"n/a") — it documents the 
shock_macro
 tool's own co-moving-shock convention (Chapter 8,
§8.2) as a glossary entry in its own right, because the satellite has no unemployment term to shock directly.

Controls
Collapsed 
<details>
 (default closed, "Macro data glossary (10
series)" summary) + the same free-text search box pattern as the variable dictionary.

AI affordances
Standard explain icon; recap lists all 10 series labels.

Gotchas
THE central FRED-honesty distinction this whole endpoint exists to enforce: 
every

dcr_*
 row and 
satellite_hpi_growth
 carry 
fred_series: null
 — the
DCR/national panel is NOT a live FRED pull, only calendar-anchored against one. Only the three SFLLD/state rows
(
sflld_uer_level
, 
sflld_uer_momentum
, 
sflld_hpi_growth
) and their FRED
IDs are genuinely live-pulled by 
freddie/macro.py
. Reading a `null` FRED badge as "missing data"
rather than "genuinely not a FRED
pull" is exactly the misread this row-level honesty labeling exists to prevent.

#### Panel — LGD, two-stage workout model (
LgdSection
)

##### LGD — two-stage workout model

Exhibit 6

Shows
Three summary tiles (cure rate, cure AUC, excess-loss loading), an OOT-calibration table (8
metrics × train/OOT), two 
SearchableTable
s (cure-stage logit coefficients, severity-stage OLS/HC1
coefficients, 5 rows each), and a 3-image exhibit grid. Endpoint: 
GET /api/model/lgd
.

How to read it
Live capture: cure rate 
12.2%
, cure AUC train/OOT 
0.837 / 0.769
,
excess-loss loading 
2.55%
. OOT calibration shows real drift: mean realised LGD train 59.95% vs OOT
61.13%, mean PREDICTED LGD train 59.90% vs OOT 65.83% — a +4.71pp OOT over-prediction gap
(
gap_pred_minus_real.oot
), vs essentially zero gap in-sample (−0.05pp) — the model over-states
severity in the GFC-aftermath OOT window. Cure-stage coefficients: 
ltv10
 coef −0.764 (odds ratio
0.4658, p≈0 — higher LTV sharply lowers the odds of curing, matching the equity-cushion story). Severity-stage:

ltv10
 coef +0.1074 (p≈0 — higher LTV raises severity conditional on non-cure).

Controls
Independent search boxes on each of the two coefficient tables; the image grid is
static, filtered client-side to exhibit ids starting 
lgd_

(
lgd_calibration_ltv
, 
lgd_cure_by_ltv
, 
lgd_distribution
 — the bimodal
realised-LGD histogram motivating the two-stage model in the first place).

AI affordances
Standard explain icon; recap states cure rate, cure AUC train/OOT, and excess-loss
loading.

Gotchas
The severity coefficient table's SE column is labeled "SE (HC1)" specifically —
heteroskedasticity-consistent standard errors, not the ordinary OLS SEs the cure-stage table's own SE column
uses; the two tables are NOT directly comparable on SE magnitude for that reason, only on sign/significance.

### 9.5 Tab 3 — Scenario Lab

app/ui/src/tabs/ScenarioLabTab.jsx
 — "Parameterise the four Tier-1 engine tools — every
number is computed by the frozen engine; the agent only routes, validates and narrates." Four control panels
on the left, a result/interpretation card and a reactive waterfall on the right.

Exhibit 9.5
 — Scenario Lab, tab layout: (a) Result & interpretation card and
(b) Allowance bridge in shock_macro mode, after running 
shock_macro("UER", 2.0, "parallel")
 live
— rendered from a live 
POST /api/tools/shock_macro
 call, 2026-07-19.

#### Control panel — Reweight scenarios

##### Reweight scenarios

unnumbered (control)

Shows
Three sliders (up/base/down, 0–100 step 5) whose raw values are normalised client-side to
sum to 1 before the call (
norm
), live-labeled with the normalised percentage next to each
slider.

How to use it
Drag any slider, then click "Run reweight" — this calls 
POST
/api/tools/reweight_scenarios
 with the three normalised weights (body must sum to 1 within 1e-6; the
UI's own normalisation guarantees this). Nothing else on the page changes until you click Run — the sliders
themselves are inert previews of what WILL be sent.

AI affordances
Standard explain icon on the control panel itself, recapping the CURRENT (not yet
run) slider setting — e.g. "Control currently set to 30%/40%/30% up/base/down" — distinct from the
Result-card explain question below, which recaps the LAST RUN result.

Gotchas
If all three sliders are dragged to 0 the Run button disables (
sum === 0

guard) — there is no "0/0/0" degenerate call possible from the UI, though the underlying tool would reject it
with 422 (weights must sum to 1) if it somehow reached the API.

#### Control panel — Macro shock

##### Macro shock

unnumbered (control)

Shows
A variable select (UER/HPI growth/GDP growth), a shape select (parallel/peak_revert), and a
shock-size slider whose bounds change per variable (
SHOCK_BOUNDS
: UER ±10pp, HPI/GDP ±5pp/q — the
same pydantic bounds Chapter 8's 
ShockMacroArgs
 enforces server-side, mirrored client-side so
an invalid drag is never even possible). A caveat box states the coherent-shock convention inline, every time.

How to use it
Pick a variable, shape, and size; click "Run shock" → 
POST
/api/tools/shock_macro
. Live capture, UER +2.0pp parallel: baseline allowance $30.5m → shocked $31.7m
(delta 
+$1.24m, +4.07%
), coverage 1.82% → 1.89%. The co-moving deltas applied alongside the named UER
shock: HPI growth −0.826pp/q, GDP growth −0.109pp/q (both negative — a rising-unemployment shock coherently
drags house-price and GDP growth down too, the DFAST severe scenario's own direction).

AI affordances
Standard explain icon on the control, recapping the CURRENT (unrun) selection
AND restating the coherent-shock convention inline in the recap text itself, so an "explain" click before
ever running the shock still surfaces the no-unemployment-term caveat.

Gotchas — the always-100%-remeasurement gotcha (Chapter 8, §8.2).

Look at Exhibit 9.5b: the stage_migration, derecognitions and new_loans bars are all exactly zero —
staging is frozen at the t=60 reporting date and scenario-invariant, so a macro shock can only ever move the
ECL AMOUNT, never which stage a loan sits in. The entire visible delta lands in remeasurement, by
construction, not because the other three components happen to be small this time.

#### Control panel — Rerun by segment

##### Rerun by segment

unnumbered (control)

Shows
A single select over the 6 valid segments: 
all, stage1, stage2, stage3, investor,
high_ltv
 (current updated LTV > 80).

How to use it
Pick a segment, click "Run segment" → 
POST /api/tools/rerun_ecl
. This
is a pure FILTER-AND-SUM over already-computed per-loan scenario ECL — no re-run of the hazard/LGD/EAD models,
despite the tool's name.

AI affordances
Standard explain icon; recap states the currently-selected segment string.

Gotchas
"Rerun" in the tool's name is a slight misnomer worth flagging — nothing is refit; it is a
decomposition of the CURRENT reporting date's already-computed book, same discipline as

decompose_waterfall
 below.

#### Control panel — Decompose waterfall

##### Decompose waterfall

unnumbered (control)

Shows
Two number inputs, t0 and t1 (bounds 1–59 / 2–60 respectively in the HTML, server-side
bound 1≤t0<t1≤60), defaulting to 20/40 — the exact worked example

docs/api_contract.md
 itself publishes.

How to use it
Set t0/t1, click "Run decomposition" (disabled while t0≥t1) → 
POST
/api/tools/decompose_waterfall
. This reruns the movement-decomposition identity between ANY two panel
snapshots, not just the default t=59→60 the Executive tab shows.

AI affordances
Standard explain icon; recap states the current t0/t1 selection.

Gotchas
An out-of-range or inverted t0/t1 pair (e.g. t1=90, beyond T_SNAP=60) fails pydantic
validation server-side with a 422 BEFORE any engine code runs — Chapter 8's 
DecomposeWaterfallArgs

bound, reachable here too since this UI control posts to the same endpoint the agent's Tier-1 tool calls.

#### Panel — Result & interpretation (
ResultCard
 + 
Interpretation.jsx
)

##### Result & interpretation

Exhibit 1

Shows
Before any control has run: an empty-state note ("Run a control on the left..."). After a
run: the tool's own 
headline
 string, a metrics strip (allowance, coverage, Jensen ratio,
delta-vs-baseline — whichever fields the specific tool's result carries), and an auto-interpretation card
fed by 
POST /api/agent/interpret
.

How to read it
Live capture after running the UER +2pp shock: headline "UER +2pp (parallel)
coherent shock of the base scenario: reported allowance $30.5m -> $31.7m (delta +1.2m, +4.1%), shocked
coverage 1.89%"; metrics strip shows 
$31.7m
 allowance, 
1.89%
 coverage, 
+4.1%
 vs
baseline. The auto-interpretation card, called live: 
interpretation
 = "UER +2pp (parallel)
coherent shock of the base scenario: reported allowance $30.5m -> $31.7m (delta +1.2m, +4.1%), shocked
coverage 1.89%. The shocked allowance is 31694012.25." with 
grounded: true, mode: "llm"
 —
badged "AI interpretation" (not the "Engine summary" fallback badge, since the LLM's own narration passed
the number-verbatim check this time).

Controls
None on this card itself — it is a pure reflection of whichever control panel was last
run.

AI affordances
The panel's OWN explain icon recaps the last headline (a second, independent way to
ask about the same result); the auto-interpretation card below it is a SEPARATE, automatic call — it fires
without any click, on every new 
{tool, result}
 pair, and shows a loading spinner ("interpreting
the run…") while in flight. If the interpret call itself errors, the card falls back to the tool's own

headline
 text rather than ever going blank or showing a raw error (
Interpretation.jsx
's
own catch block).

Gotchas
The "AI interpretation" vs "Engine summary" badge is the honest signal for whether the
LLM's own prose passed the verbatim-number/citation check — an "Engine summary" badge is a NORMAL, EXPECTED
outcome under the project's anti-hallucination governance (the LLM's narration either erred or invented a
number), not a bug to be alarmed by; docs/api_contract.md is explicit about this.

#### Panel — Allowance bridge, action-aware (
WaterfallChart.jsx
, 3 modes)

##### Allowance bridge (Scenario Lab instance)

Exhibit 2

Shows
The SAME shared component as the Executive tab's Exhibit 3, but here 
action

is live — the chart resolves one of THREE modes: 
shock_macro
 mode
(
result.waterfall_vs_baseline
, baseline vs shocked), 
decompose_waterfall
 mode
(
result.components
, the custom t0/t1 window just run), or — for 
reweight_scenarios
,

rerun_ecl
, or before any control has run — falls back to the SAME fixed historical t0/t1 window
(props default 20/40 on this tab) as any other instance of this component.

How to read it
See Exhibit 9.5b above (the shock_macro-mode reading: opening $30.5m,
remeasurement +$1.2m only, closing $31.7m — the always-100%-remeasurement pattern visualised directly).

Controls
Same 
⊞
 chart↔table toggle; the chart's own subtitle text changes per mode
so a reader always knows which of the three modes they are looking at ("Effect of ... vs the baseline
scenario," "Movement decomposition ... — every bar is an engine number," or the fixed-history phrasing).

AI affordances
Standard explain icon; recap is built via 
recapFor(wf)
 from whichever
mode's adapted row data is currently showing — always the CURRENT chart, never stale.

Gotchas
Running "reweight_scenarios" or "rerun_ecl" does NOT change this chart at all — those two
tools have no waterfall shape of their own, so the chart silently falls back to the fixed historical window.
A reader who reweights scenarios and expects the bridge below to visualise the reweight is the SAME confusion
requirement 11 names for the Executive tab, now inverted: here the historical default can look like it
"didn't respond" to a control that was never wired to drive it in the first place.

### 9.6 Tab 4 — Policy

app/ui/src/tabs/PolicyTab.jsx
 — "Every exhibit below is paired with the governance decision it
informs — the dials a credit-risk committee actually turns." Four panels, each opening with a

DecisionHeader
 stating the governance question before the numbers.

Exhibit 9.6
 — Policy tab: (a) Stage-2 share vs SICR threshold and (b)
Scenario-weight sensitivity — rendered from live 
GET /api/policy/staging_sensitivity
 and

GET /api/policy/weights_table
 calls, 2026-07-19.

#### Panel — Stage-2 share vs SICR threshold

##### Stage-2 share vs SICR threshold

Exhibit 1

Shows
A 
DecisionHeader
 naming the governance question ("Where would you set the SICR
ratio threshold that triggers Stage 2?"), a static exhibit image, and a table of Stage-2 allowance share at
two reporting dates across four candidate thresholds. Endpoint: 
GET
/api/policy/staging_sensitivity
.

How to read it
Live capture — add-on held at 0.5pp across every threshold shown. At t=20
(2005Q1, calm): Stage-2 share is 
0.0%
 at EVERY threshold (1.5×/2.0×/3.0×/4.0×) — deterioration since
origination simply has not happened yet. At t=40 (2010Q1, stress): 1.5× → 
85.10%
, 2.0× (the adopted
convention) → 
75.76%
, 3.0× → 
30.25%
, 4.0× → 
3.32%
 — the choice between 2.0× and 4.0×
alone swings Stage-2's share of the book by over 72 percentage points.

Controls
None interactive — a fixed sensitivity table over 4 pre-computed thresholds, not a live
slider (the threshold itself is a modelling/governance parameter baked into the frozen staging engine, not an
app-level control).

AI affordances
Standard explain icon; recap states all four thresholds and the report's own
"reading" sentence verbatim.

Gotchas
The report's own reading line calls this out directly: "the threshold is the single
loudest governance dial in the impairment estimate" — a reader who treats the 2.0× convention as an
objectively "correct" number rather than a judgment call is missing this panel's entire point.

#### Panel — Scenario-weight sensitivity

##### Scenario-weight sensitivity

Exhibit 2

Shows
A 
DecisionHeader
 ("which probability weighting... best reflects 'reasonable
and supportable' information?"), a bar chart, and a table of 3 canned weight sets with a Δ-vs-adopted pill
per row. Endpoint: 
GET /api/policy/weights_table
 — 
calling this endpoint appends THREE lines
to the audit trail
 (one per weight set), a deliberate governance choice so every reweighting this app has
ever shown a user is logged, even from this read-only convenience view.

How to read it
Live capture: 
Adopted (25/50/25)
 — $34.0m, coverage 2.034%, Jensen ratio
1.0353×, Δ 0% (the reported basis, tagged "ADOPTED," accent-highlighted bar and a 2px accent-border row).

Equal-thirds (33/33/33)
 — $35.2m, coverage 2.106%, Jensen 1.0437×, 
+3.52%
 vs adopted.

Downside-tilted (15/35/50)
 — $38.6m, coverage 2.307%, Jensen 1.0426×, 
+13.39%
 vs adopted — over
$4.5m more provision than the adopted basis from weight alone, no macro assumption changed.

Controls
None interactive from the UI's perspective — the three weight sets are fixed
illustrative alternatives (not user-adjustable sliders; that live-adjustable version of the SAME question is
Scenario Lab's "Reweight scenarios" control, §9.5).

AI affordances
Standard explain icon; recap lists all three sets' weight/allowance/delta.

Gotchas
The colour convention here (red/bad pill for allowance ABOVE the adopted basis, green/good
for below) encodes a P&L-volatility judgment, not a policy endorsement — the panel's own governance note
and this book's prose both flag it: a policy reviewer could reasonably read "more provision" as prudent
rather than bad, and the visual pill is describing dispersion around the adopted basis, not recommending a
direction.

#### Panel — Stage → ECL horizon guide (
StageGuide.jsx
, shared)

##### Stage → ECL horizon guide

unnumbered

Shows
A collapsed 
<details>
 explainer (shared verbatim with the waterfall
panel's own footer, wherever 
WaterfallChart
 renders): Stage 1 = 12-month ECL (Σ over t≤4
quarters), Stage 2 = the SAME sum over the FULL remaining contractual life (up to 40 quarters), Stage 3
= LGD × current exposure (scenario-invariant by construction).

How to read it
The engine always computes BOTH 12-month and lifetime ECL for every loan and
reports the one the stage prescribes — this calm-quarter book (2015Q1) is 7,803 Stage 1 loans, 3
Stage 2, 43 Stage 3, so the reported allowance is dominated by 12-month ECL, "which is exactly where
scenario weights and macro shocks act" — the same sentence the Executive tab's narrative panel uses,
deliberately consistent across the app.

Controls
Native expand/collapse only.

AI affordances
Standard explain icon; recap states the three stage/horizon definitions in one
sentence.

Gotchas
None specific beyond what §9.3's waterfall gotcha already covers — this panel is the SAME
component reused, not a new one.

#### Panel — When judgment overrides the model, the overlay question

##### When judgment overrides the model — the overlay question

unnumbered

Shows
Pure governance prose (no engine numbers) laying out the post-model-adjustment (overlay)
concept: the 2020 COVID-19 shock as the textbook case (default-rate models trained pre-pandemic could not see
furlough schemes or payment holidays), citing that roughly a quarter of performing-book coverage is still held
as overlay at some institutions per recent supervisory reviews (ECB 2024 thematic review, PRA Dear-CFO
letters), with an explicit warning that overlays applied at the total-ECL level (bypassing PD/staging) are
contrary to IFRS 9 principles.

How to read it
A defensible overlay needs four parts, stated explicitly: a named TRIGGER (a
genuine model blind spot, not "the number looked wrong"), a QUANTIFICATION BASIS tied to evidence, ALLOCATION
to the specific stages/segments affected, and EXIT CRITERIA for retiring it. The panel's closing line points a
reader toward the model-native way to explore this: "The Scenario Lab's shock and reweight tools are the
model-native way to explore 'what would an overlay-sized stress look like' before reaching for a judgmental
add-on" — a direct cross-reference to §9.5.

Controls
None — static prose.

AI affordances
Standard explain icon; recap is a one-sentence summary of the four-part overlay
discipline.

Gotchas
This app reports a model-driven allowance ONLY — there is no overlay-entry control
anywhere in the product; this panel is a governance explainer, not a feature. A reader looking for "where do I
add an overlay in this tool" will not find one — that is a deliberate scope boundary, not a missing feature.

### 9.7 Tab 5 — Real Data (Freddie SFLLD)

app/ui/src/tabs/FreddieTab.jsx
 — the largest tab by panel count. "The DCR engine above runs on
a synthetic panel. This tab surfaces a second, real pipeline built on the actual Freddie Mac Single-Family
Loan-Level Dataset (SFLLD)... read-only, for comparison against the reported engine." One shared
how-to-read panel, six hero tiles, and eight numbered exhibits, none of which touch or mutate engine state
(every number here is parsed straight from 
outputs/freddie/**
's already-written
reports/CSVs/JSON — Chapter 11/12's territory, re-surfaced here as an app tab).

#### Panel group — 6 hero tiles

##### SFLLD panel scale / Hazard OOT AUC / COVID regime / Backtest miss ratio / LSTM AUC / LGD loading

unnumbered

Shows
Six 
StatTile
s, all from 
GET /api/freddie/summary
: panel scale,
hazard OOT AUC (SFLLD vs DCR side by side), COVID regime treatment verdict, backtest worst miss ratio, LSTM
challenger OOT AUC vs champion, LGD excess-loss loading (SFLLD vs DCR).

How to read it
Live capture: 
837,500 loans
, 39,522,565 loan-months, 17 vintages (overall
D90 rate 5.32%, overall prepay rate 58.93%) — vs the DCR synthetic panel's 621,736 rows (Chapter 11), a
scale contrast the tile's own hint text states directly. 
Hazard OOT AUC 0.6847 / 0.6609
 (SFLLD /
DCR) — the real-data champion modestly OUT-discriminates the synthetic-panel champion out-of-time, train AUC
0.8536 vs 0.7476. 
COVID regime: EXCLUDE
 (window 2020-04..2021-09) — the reviewed verdict; the naive/
additive/exclude OOT2 AUC spread (0.7553/0.7547/0.7509) is too small to override the structural argument for
exclude (only exclude keeps every macro coefficient economically signed). 
Backtest worst miss ratio
9.42×
 at 2007-12 — flagged "underpredicted the GFC" (bad direction badge, by design — an underprediction
is the honest finding, not a good one). 
LSTM OOT AUC 0.9925
 vs champion 0.6847 — a striking headline
number the panel's OWN detail exhibit (Exhibit 8) immediately qualifies (see below — this tile alone
would badly overstate the finding). 
LGD excess-loss loading 1.48% (SFLLD) vs 2.55% (DCR)
, mean realised
LGD train 27.15%.

Controls
None — six read-only tiles, same as the Executive tab's four.

AI affordances
Each tile carries its own explain icon with a tile-specific recap — e.g. the LSTM
tile's recap states the FULL split (overall, prior-delinquency, clean-history AUCs) even though the tile
itself only displays the headline number, so an "explain" click never under-informs the router relative to
what Exhibit 8 shows in full.

Gotchas
The COVID-verdict tile's hint text says "window ... -- review overturn" — a terse pointer
to a real modelling-governance event: an earlier "additive dummy" recommendation was OVERTURNED on review
because its own coefficient table showed the dummy failing to repair the sign-flipped structural macro terms
(
delta_uer_lag1
's sign flip persisted) — "the dummy is doing its job" was contradicted by the
fit itself. This is documented, not smoothed over.

#### Panel — Vintage curves

##### Vintage curves — the pre-crisis-vintage hump

Exhibit 1

Shows
A single tall 
ExhibitImage
, id 
freddie_vintage_curves
, endpoint

GET /api/freddie/exhibits
, served at

/static/freddie/eda/exhibit1_vintage_curves.png
.

How to read it
Caption verbatim: "2007 vintage reaches 16.26% cumulative D90 by month 225 vs
14.11% (2006) and 9.14% (2008) — the pre-crisis-vintage hump; every 2018-2025 modern vintage tops out below
5.48%." The 2007 vintage is the worst-performing origination cohort in the whole panel by a wide margin.

Controls
None — a static image.

AI affordances
Standard explain icon; recap is the exhibit's own caption verbatim.

Gotchas
None specific — but see the shared gotcha below Exhibit 7 on tall exhibits generally.

#### Panel — The COVID roll-rate anomaly

##### The COVID roll-rate anomaly

Exhibit 2

Shows
Two side-by-side 
ExhibitImage
s: 
freddie_roll_rate_matrices
 ("Roll-rate
matrices -- GFC vs calm vs COVID") and 
freddie_calendar_time_series
 ("Calendar-time D90-entry
rate"), plus a net-read paragraph.

How to read it
The subtitle states the anomaly directly: "A naive D90-entry read makes COVID look
like the worse credit event; the roll-rate breakdown shows the opposite." The net-read paragraph resolves it:
COVID's 60→90+ roll / D90-entry rate looks worse than the GFC by a naive count, but the 90+→liquidation
transition collapses over 10× in the same window — a forbearance-ACCOUNTING artifact (loans parked in
delinquency status rather than progressing to liquidation), not genuine credit deterioration.

Controls
None — static image pair.

AI affordances
Standard explain icon; recap concatenates both images' captions.

Gotchas
THE central interpretive trap this exhibit exists to catch: reading the D90-entry rate
alone during 2020-21 as "COVID was worse than the GFC for credit" is exactly backwards once the roll-rate
breakdown is examined — this is precisely why the panel pairs the naive series with the matrix breakdown
rather than showing either alone.

#### Panel — The backtest honesty panel (centrepiece)

##### The backtest honesty panel — model risk, historicised

Exhibit 3

Shows
A callout stat, an 8-column table (5 rows, one per pseudo-reporting date), and two narrative
paragraphs. Endpoint: 
GET /api/freddie/backtest
. Styled with a distinct 
freddie-centerpiece

CSS class — the tab's own visual signal that this is the single most important exhibit on the page.

How to read it
Live capture, full 5-row table: 
2007-12
 (n=86,188 fit / 610 events, 124,235
active loans) realized cum. D90 
8.75%
 vs predicted-frozen 
0.93%
 → miss ratio (frozen)

9.42×
, predicted-hindsight 4.61% → miss ratio (hindsight) 1.90×. 
2009-12
: miss (frozen)
1.18×, (hindsight) 1.41×. 
2015-12
: miss (frozen) 0.75×, (hindsight) 0.75× (near-perfect agreement — the
"saturation" reference case). 
2019-12
: miss (frozen) 5.00×, (hindsight) 
0.06×
 — the mirror
failure: fed the real April-2020 unemployment print, the linear hazard extrapolates ~20 SDs outside its
training support and OVER-predicts by 16×. 
2021-12
: miss (frozen) 0.67×, (hindsight) 0.94×. The
callout states the 2007-12 finding in one sentence: a model refit through that date with macro frozen predicted
0.928% 36-month D90 against a realized 8.750% — 
9.42× underprediction of the GFC, as expected.

Controls
None — a fixed 5-date historical backtest, not a parameterised control.

AI affordances
Standard explain icon; recap states the central honesty note plus the 2019-12
hindsight miss ratio.

Gotchas
"Miss ratio >1" means underprediction, "<1" means overprediction —

miss_ratio = realized / predicted
, easy to invert by mis-remembering. The 2007-12 finding is
explicitly framed as "the model was never wrong about its own coefficients, it simply never saw the crisis
coming because nothing in a frozen macro path could show it one" — this argues FOR scenario overlays
(IFRS 9 para 5.5.17), it is not a defect being confessed.

Exhibit 9.7
 — Real Data tab, backtest honesty panel: miss ratio (frozen vs
hindsight macro) across all 5 pseudo-reporting dates — rendered from a live 
GET
/api/freddie/backtest
 call, 2026-07-19.

#### Panel — Realized severity cycle

##### Realized severity — a lagging, not coincident, indicator

Exhibit 4

Shows
A single tall 
ExhibitImage
, id 
freddie_severity_cycle
.

How to read it
The title states the finding directly: realized severity LAGS the credit cycle
rather than moving coincidentally with it — liquidation timing and forced-sale dynamics take time to catch up
to a default event.

Controls
None — static image.

AI affordances
Standard explain icon; recap is the exhibit's own caption.

Gotchas
None specific.

#### Panel — SFLLD hazard coefficients

##### SFLLD hazard coefficients

Exhibit 5

Shows
The full fitted coefficient table — 19 terms (vs the DCR tab's 13), same
click-to-expand 
InterpretationRow
 pattern as Exhibit 9.4. Endpoint: 
GET
/api/freddie/hazard
.

How to read it
Live capture, selected rows: Intercept HR 
0.0272
 (reference-row baseline,
not a marginal effect); 
fico_s
 HR 
0.3963
; 
ltv10
 HR 
1.3806
;

uer_lag1
 HR 
1.0996
 — carries a live FRED badge (
{POSTAL}UR
), the genuinely
FRED-pulled state series Exhibit 9.4's national rows never carry; 
delta_uer_lag1
 HR

1.9485
; 
hpi_growth_lag1
 table HR 
0.0353
 but Per-unit HR 
0.9671
 (the SAME
0.01-vs-1pp correction, computed here from the RAW 
coef
 column since this endpoint publishes coef
directly, unlike the DCR endpoint which only ever publishes 
HR=exp(coef)
). Five loan-age spline
terms, seven occupancy/purpose/channel categorical dummies, and 
dti_s
 (DTI, no DCR counterpart —
see Exhibit 6 below) round out the 19.

Controls
Same per-row expand toggle as the Model tab's table; no model-switch segmented control
here (SFLLD ships one champion hazard model, not a default/prepay pair).

AI affordances
Standard explain icon; recap states term count, train/OOT AUC, and the state
UER-level and HPI-growth hazard ratios.

Gotchas
Three categorical rows are EXPLICITLY STATED MISSES against the DCR sign prior
(
occupancy_status[T.S]
, 
loan_purpose[T.N]
, 
channel[T.C]
 — see their own

economic_channel
 text, verbatim from the report's "Fitted signs vs the priors" paragraph) — these
are documented honestly, not hidden by omitting the row.

#### Panel — Champion hazard vs DCR priors, and the COVID verdict

##### Champion hazard vs the DCR priors, and the COVID regime verdict

Exhibit 6

Shows
A 7-row sign-comparison table (SFLLD term vs its DCR counterpart vs the DCR-expected sign),
a COVID caveat paragraph, and a 4-image exhibit grid (calibration-by-year, seasoning curve, state-UER effect,
COVID-calibration comparison).

How to read it
Live capture, sign comparison: 
fico_s
 ↔ DCR 
fico_s
,
expected "−" (matches); 
dti_s
 ↔ 
null
 DCR variable, "n/a (DCR has no DTI field at this
rung)" — an honest scope gap, not a missing-data bug; 
uer_lag1
 ↔ DCR 
uer_lag1
,
expected "+ (net, level+momentum)" — the SAME net-effect caveat as Exhibit 9.4's fit-stats panel applies
here too; 
cr(loan_age, df=5)
 ↔ DCR's spline, expected "hump (DCR peak ~12 quarters ~= 36
months)." The COVID caveat restates the reviewed exclude verdict verbatim.

Controls
None — a static comparison table plus static images.

AI affordances
Standard explain icon; recap states the COVID verdict and its recommendation
text.

Gotchas
The sign-comparison table covers ONLY the 7 continuous/structural terms — the 7
categorical occupancy/purpose/channel dummies have no DCR counterpart at all (DCR carries no such fields at
this rung) and are correctly absent from this table, not an oversight.

#### Panel — State heterogeneity

##### State heterogeneity — the collateral channel, in real geography

Exhibit 7

Shows
A single tall 
ExhibitImage
, id 
freddie_state_heterogeneity
,
title states its content: "2006-07 vintage default vs HPI drawdown" by state.

How to read it
The real-geography counterpart to the collateral/negative-equity channel documented
in the variable dictionary (§9.4) — the SAME 
ltv10
 mechanism, shown here as cross-state
variation rather than a single pooled coefficient.

Controls
None — static image.

AI affordances
Standard explain icon; recap is the exhibit's own caption.

Gotchas
The tall 
ExhibitImage
 variant (this exhibit, plus Exhibits 1 and 4) is
a taller aspect-ratio CSS treatment for exhibits with more vertical detail (a state map, a long vintage-curve
family) — a purely presentational difference from the standard 
ExhibitImage
, not a different data
source or contract.

#### Panel — LSTM path-dependence challenger, lift decomposition

##### LSTM path-dependence challenger — lift decomposition

Exhibit 8

Shows
A 3-row table (Overall OOT / Clean history / Prior delinquency spell, champion vs LSTM AUC
and the delta), a caveat paragraph, and a 2-image grid (lift-split, calibration-by-year). Endpoint: 
GET
/api/freddie/summary
 (the 
lstm
 object, reused — not a separate endpoint).

How to read it
Live capture: 
Overall OOT
 champion 0.6847 → LSTM 0.9925 (Δ +0.3078);

Clean history
 champion 0.5386 → LSTM 0.5287 (Δ 
−0.0098
, essentially zero, slightly negative);

Prior delinquency spell
 champion 0.5698 → LSTM 0.9570 (Δ 
+0.3872
). The lift concentrates almost
ENTIRELY on loans with a prior delinquency spell — direct evidence for the path-dependence hypothesis: a
borrower's delinquency HISTORY (not just their current state) carries real predictive signal the
current-state-only champion cannot see.

Controls
None — a static comparison table.

AI affordances
Standard explain icon; recap states all three groups' champion→LSTM deltas.

Gotchas
The subtitle states the governance boundary explicitly: "Challenger-never-champion: a
discrimination-only scorecard... not integrated into the reported allowance." The overall 0.9925 AUC headline
(also shown on the hero tile) is dramatically inflated by the clean-history/prior-delinquency SPLIT — reading
the headline number alone, without this exhibit's breakdown, would badly overstate what the LSTM actually adds
for a typical (clean-history) loan. The caveat also flags an UNRESOLVED caveat, not smoothed over: "A
forbearance-era delinquency-ladder distortion may inflate part of the 2020-21 window's contribution —
flagged, not resolved, in the calibration chart's shaded window."

### 9.8 Tab 6 — Copilot

app/ui/src/tabs/CopilotTab.jsx
 — the one tab where the agent IS the interface, not an
annotation layer on top of one. Three panels: the full chat panel, a live SSE trace feed, and a session-only
audit log. This is the only tab where 
MiniChatDock
 is deliberately absent (per §9.2 — it has its
own full-page chat instead).

Exhibit 9.8
 — Copilot chat-dock status states, three LIVE recorded exchanges
(
POST /api/agent/ask
, live LangGraph agent, 2026-07-19) — one per governed outcome this app
surfaces to a user.

#### Panel — Ask the copilot (
ChatPanel.jsx
, mode="full")

##### Ask the copilot

unnumbered

Shows
A free-text chat log + input form + (when empty) three suggestion chips. Endpoint:

POST /api/agent/ask
, body 
{"question": "..."}
 (1–2000 chars), response

{answer, route, mode, trace}
.

How to read it
Full worked GROUNDED example, live: question "What is the reported allowance under
the downside scenario?" → route 
reweight_scenarios
, mode 
grounded
, answer: "The
weighted allowance is $47.6m, representing a +39.8% increase versus the adopted 25/50/25 weight of $34.0m. The
Jensen ratio is 1.000x compared to $47.6m at the averaged path. This result is based on weights up/base/down =
0.00/0.00/1.00." — the router correctly interpreted "the downside scenario" as a 0/0/1 reweight, not a lookup
of the existing scenario-table row. REASONED example: question "Why does the double-trigger LTV × UER
coefficient come out negative?" → route 
REASONED
, mode 
reasoned
, answer prefixed
"[REASONED — interpretation, not engine output]" then a cited, number-disciplined interpretation drawing on
6 documentation passages plus the baseline engine snapshot — no new engine number is stated. REFUSAL example:
question "What is the price of Bitcoin today?" → route 
REFUSE
, mode 
refusal
, a fixed
refusal message enumerating all 6 validated tool families as the alternative.

Controls
A text input + Ask button (disabled while a request is in flight — the API itself
enforces single-flight with a 429 on overlap, a single-worker demo limit); 3 suggestion chips pre-fill and
send a canned question on click. An optional 
contextLabel
 prop (unused on this full-page
instance, used by 
MiniChatDock
's per-tab instances) would prefix the wire question with

[TabLabel]
.

AI affordances
This panel carries its OWN explain icon too (operator request #3's "no heading is
ever missed" rule applied even to the chat panel itself) — its recap states the session's own question count
and most recent route, distinct from anything a user has typed into the chat log.

Gotchas
The REASONED prefix marker is BOTH stripped for display (the UI's own reasoned-tag badge
already communicates the same fact visually) AND present in the raw wire string as a redundant machine-readable
signal — branch on 
mode === 'reasoned'
, never string-match the prefix, is the documented
convention (
docs/api_contract.md
).

#### Panel — Agent trace (
AgentTrace.jsx
)

##### Agent trace

unnumbered

Shows
A live-scrolling event log over Server-Sent Events. Endpoint: 
GET
/api/agent/stream
 (
text/event-stream
), replays the most recent 
/ask
 trace on
connect then streams new events as they happen; a connection-status badge (connecting/live/reconnecting) sits
in the panel's action slot.

How to read it
Each event is a dict keyed by 
node
 — 
router
 (chosen
route + validated args), a tool-name node (
shock_macro
, 
query_model_docs
,

analyze_data
, ...; execution outcome + headline), 
narrator
 (grounding-check outcome,

number_check_passed
), 
REASONED
, or 
refusal
. A badge per row
(ROUTER/TOOL/NARRATION/REASONED/REFUSAL/ERROR) colour-codes the node type at a glance.

Controls
None — a pure read-only firehose, capped at the last 200 events client-side
(
MAX_EVENTS
), auto-scrolled to bottom on new events.

AI affordances
Standard explain icon; recap states the current event count and the most recent
event's text.

Gotchas
No event field is EVER parsed back into a number by the UI — every field rendered here is
display-only text, the same discipline as every other agent-touched surface in the app. The per-event

mode
/
number_check_passed
 on a 
narrator
 event is a DIFFERENT, per-event
diagnostic from the top-level response's own 
mode
 field (§9.9) — easy to conflate since both are
named 
mode
.

#### Panel — Session audit log (
AuditLog
, inline component)

##### Session audit log

unnumbered

Shows
A client-side-only log of every question asked THIS BROWSER SESSION, most recent first —
built entirely from 
ChatPanel
's own 
onResult
 callback, not a server-side history
endpoint. Each row is collapsed by default; clicking expands the full answer text plus the raw trace JSON.

How to read it
A route badge per row (error-red for refusal, purple for reasoned, the standard
tool badge otherwise) lets a reader scan the session's route mix at a glance without expanding every row.

Controls
Click any row to expand/collapse; no filtering or search (unlike the coefficient tables
elsewhere in the app — this log is expected to stay short, one session's worth of questions).

AI affordances
Standard explain icon; recap states the entry count and the most recent route.

Gotchas
This log resets on page reload
 — there is no server-side 
GET
 history
endpoint for past 
/ask
 calls (the component's own comment states this explicitly); the PERSISTENT
audit trail a governance reviewer would actually rely on is the server-side

outputs/agent_log/tool_calls.jsonl
 file Chapter 8 documents, not this UI panel — this panel
is a convenience view of the current session only, not the system of record.

### 9.9 AI affordances, in full

Every panel doc block above says "standard explain icon" or similar — this section is where "standard"
is actually defined once, in full, so it is never re-derived per panel. Three affordances, all layered on top
of the SAME single endpoint, 
POST /api/agent/ask
 — requirement 11's own framing: "zero new
endpoints... every explanation... passes through the same tool-routing/Tier-2/Tier-3/refusal governance."

#### 1. The ✦ explain icon (
ExplainButton.jsx
, 
useExplain
 hook)

Mechanics.
 Every 
Panel
 heading and every 
StatTile
 carries a small circular
spark-icon button in its action cluster. Clicking it toggles an inline "answer strip" that renders UNDER the
panel body (never a modal, never squeezed into the header row — FINAL_SPEC §7.4). On click, it calls

buildQuestion()
 FRESH (so the question always reflects the panel's CURRENT payload, not a stale
snapshot from when the component first mounted), then 
askAgent(question)
. The composed question
follows a fixed wire-text convention (
app/ui/src/api.js
's 
explainPanelQuestion
):

[explain:<panel_id> <live params>] <Exhibit label> — <panel title>: <CODE-GENERATED
recap of the exact figures the panel is showing right now> What should I take from this?

panel_id
 is a short STABLE slug (e.g. 
waterfall
, 
hazard_coefficients
,

kpi_jensen_ratio
) — the same value every render, never free text; live params (when present) are

key=value
 pairs reflecting the panel's current control state (e.g. 
t0=59 t1=60
). The
recap sentence is built from the SAME payload object that rendered the panel — never hand-typed prose — so the
router always has the rendered numbers directly in front of it.

Live worked example — clicking ✦ on the Jensen-ratio tile.
 Composed question (built exactly as the
convention above specifies, from the live summary payload):

[explain:kpi_jensen_ratio] Jensen ratio: Jensen ratio is 1.0353x — scenario-weighted allowance
$34.0m vs allowance at the averaged macro path $32.9m. What should I take from this?

This is a real, reproducible question string — posting it to 
POST /api/agent/ask
 live this
session routed to 
REASONED
 (a conceptual "what should I take from this" question, no fixed tool
computes a fresh number for it) and returned a cited interpretation grounded in the recap's own numbers.

The answer strip itself renders one of four states, matching a small state machine in 
useExplain
:

loading
 ("THINKING," a warm-coloured status dot), 
done
 + refusal route ("OUT OF
SCOPE," muted dot, the refusal text shown), 
done
 + non-refusal route ("GROUNDED," good-coloured
dot, the answer text plus a 
⚙ <route>
 citation chip), or 
network-error
 ("OUT
OF SCOPE — request failed (...)," muted dot — a network failure is deliberately shown in the SAME visual
register as a genuine refusal, never a scary red error state, so a flaky connection never looks like the
model did something wrong).

#### 2. The selection-explain chip (
SelectionExplain.jsx
)

Mechanics.
 Highlighting ANY text anywhere inside 
.app-main
 (i.e. any of the six tab
bodies, but explicitly NOT inside an input/textarea/select/contenteditable, NOT inside either chat surface,
and NOT inside an already-open explain popover — 
inExcludedZone
's exact exclusion list) shows a
small floating "Explain with AI" chip near the selection, after a 220ms debounce. Clicking it composes:

Explain, in the context of the <tab label> tab: "<selected text, trimmed, <=300 chars>"

<tab label>
 is one of the six tab display names; the selected text is quoted VERBATIM
(truncated at 300 chars, never paraphrased) so the router sees exactly what the user highlighted, with the
active tab as routing context.

Gotcha — this is a genuinely global affordance, not per-panel.
 Unlike the ✦ icon (which only exists on
panels that explicitly pass a 
buildExplainQuestion
 prop), selection-explain works on ANY visible
text in the main area — a stray sentence in a caption, a table cell, even the "Consultant's read" narrative
paragraph — which makes it the one AI affordance that requires no per-panel wiring at all to reach every
panel's prose.

#### 3. The chat-dock status states — GROUNDED / REASONED / THINKING / OUT OF SCOPE

Both 
MiniChatDock
 (present on 5 of 6 tabs, collapsed-first, per §9.2) and the Copilot tab's
own 
ChatPanel
 render every agent reply through the SAME 4-state vocabulary — the "grounding
vocabulary" graft the shipped design spec pulled from the losing 
terminal
 direction (§9.12):

State
When
What it implies about trustworthiness

THINKING
request in flight
(
status === 'thinking'
/
'loading'
)
no answer yet — nothing to trust or
distrust

GROUNDED
response 
mode === "grounded"

— a numeric tool ran, or the cited docs retriever (
query_model_docs
) answered

highest trust
: every number traces to a frozen-engine tool call or a real cited passage

REASONED
response 
mode ===
"reasoned"
 — the REASONED route, a cited, number-disciplined LLM interpretation with NO fresh engine
computation
middle trust
: grounded in retrieved passages + the engine's own baseline snapshot,
but not a fresh computed number — treat as interpretation, not a new fact

OUT OF SCOPE
response 
mode ===
"refusal"
, OR a network/request failure
no claim made
 — refusal-by-design is a feature
(Chapter 8), not a degraded answer; a network error is shown identically so a connectivity blip never
reads as "the model refused"

Interpretation.
 This is the SAME 
mode
 field 
POST /api/agent/ask
 already
returns (§9.8) — the UI adds zero new server-side logic, only a consistent visual vocabulary layered on top of
three pre-existing values. Prefer 
res.mode
 when present; fall back to a route-name regex
(
isRefusalRoute
/
isReasonedRoute
, matching 
REFUSE
/
refusal

case-insensitively, since the live LangGraph router and the offline fallback router spell refusal
differently) only for callers that predate the 
mode
 field.

Check yourself.

A user clicks the ✦ icon on the Scenario table (Executive tab) right after the page loads, before any
control anywhere has been touched. What number(s) does the composed question actually contain?
  
Answer

Exactly the three scenario rows' weight/allowance/coverage as CURRENTLY rendered on the
  page — the recap is built from the same 
summary.scenarios
 array the table itself renders, at
  click time, via 
buildQuestion()
 called fresh — never a stale value and never a number the panel
  isn't already showing.

Why does a network failure render as "OUT OF SCOPE — request failed" rather than a distinct red error
state?
  
Answer

A deliberate design choice (
ExplainStrip
's own state machine) so a flaky
  connection is never visually confused with "the model did something dangerous or wrong" — refusal and
  network failure share the same muted, non-alarming visual register, distinct from how a genuine engine error
  elsewhere in the app (e.g. "Engine API offline") is shown.

Selection-explain is disabled inside the Copilot tab's own chat log. Why, given that IS visible text in
the main area?
  
Answer

inExcludedZone
 explicitly excludes 
.chat-panel
 (and
  
.mini-dock
, 
.explain-strip
, 
.selection-explain
 itself) — highlighting
  text inside an already-agent-mediated surface would be a confusing double affordance (explain-a-highlighted
  chat-answer, inside a surface whose whole purpose is already asking the agent things) — the exclusion keeps
  the two affordances non-overlapping.

### 9.10 The endpoint → panel wiring table

Every one of the 22 JSON endpoints 
docs/api_contract.md
's own summary table lists, cross-walked
to which panel(s) in this chapter call it — built from the actual 
app/ui/src/api.js
 function
list, cross-checked against every tab file's own import statements.

Exhibit 9.9
 — Tab → endpoint wiring, all 22 endpoints across 6 tabs plus the 3
static mounts and the app-boot health check — a structural diagram from 
app/ui/src/app.jsx
's

TABS
 array and every tab's own 
api.js
 calls, cross-checked against

docs/api_contract.md
's own summary table.

Endpoint
Method
Tab(s) / component
Key contract fields consumed

/api/health
GET
app boot (not tab-scoped)
status,
engine_warm, agent

/api/ecl/summary
GET
Executive (tiles, stage mix, narrative, scenario
table); app header
weighted_allowance, coverage, jensen_ratio, stage_mix, scenarios[]

/api/ecl/waterfall
GET
Executive Exhibit 3; Scenario Lab Exhibit 2
(fallback mode)
components[], identity_gap, period_t0, period_t1

/api/exhibits/credit_cycle
GET
Executive Exhibit 4

rho, points[]

/api/tools/shock_macro
POST
Scenario Lab (Macro shock control)

shocked_allowance, delta_pct, waterfall_vs_baseline, applied_peak_deltas_pp

/api/tools/reweight_scenarios
POST
Scenario Lab (Reweight control);
Policy Exhibit 2 (3× per page load)
weighted_allowance, jensen_ratio,
delta_vs_adopted_pct

/api/tools/rerun_ecl
POST
Scenario Lab (Rerun-by-segment control)

share_of_book_allowance_pct, stage_mix

/api/tools/decompose_waterfall
POST
Scenario Lab (Decompose control)

same shape as 
/api/ecl/waterfall

/api/agent/ask
POST
Copilot ChatPanel; MiniChatDock (5 tabs); ✦ explain
icon (every tab); selection-explain chip (every tab)
answer, route, mode, trace[]

/api/agent/stream
GET (SSE)
Copilot Agent trace panel

node-keyed event dicts

/api/agent/interpret
POST
Scenario Lab (auto-interpretation card)

interpretation, grounded, mode

/api/model/coefficients
GET
The Model Exhibits 1–2

models.{default,prepay}, fit_stats

/api/model/variable_dictionary
GET
The Model Exhibit 4

preamble, rows[]

/api/model/macro_glossary
GET
The Model Exhibit 5

series[]

/api/model/lgd
GET
The Model Exhibit 6

cure_rate, oot_calibration, cure_stage_coefficients, severity_stage_coefficients

/api/policy/staging_sensitivity
GET
Policy Exhibit 1

thresholds, rows[], reading, image_url

/api/policy/weights_table
GET
Policy Exhibit 2

weight_sets[], scenario_totals

/api/exhibits/list
GET
The Model Exhibit 3 (filtered), Exhibit 6
image grid (filtered)
exhibits[].{id, title, png_url, caption}

/api/freddie/summary
GET
Real Data hero tiles; Exhibit 8 (lstm
object)
panel, hazard, covid, lgd, backtest_headline, lstm, gate_verdict

/api/freddie/hazard
GET
Real Data Exhibits 5–6

coefficients[], dcr_sign_comparison[], covid

/api/freddie/backtest
GET
Real Data Exhibit 3

rows[], central_honesty_note, overlay_narrative

/api/freddie/exhibits
GET
Real Data Exhibits 1,2,4,6,7,8 (image
grids)
exhibits[].{id, title, png_url, caption, source}

/static/exhibits/*
GET (static)
every 
ExhibitImage
 on
Executive/Model/Policy
raw PNG bytes

/static/freddie/*
GET (static)
every 
ExhibitImage
 on Real
Data
raw PNG bytes

/static/mdd/*
GET (static)
the header MDD link (all tabs)

MDD.html

Gotcha — one endpoint, many callers.
 
POST /api/agent/ask
 is called from FIVE distinct UI
surfaces (Copilot's own chat, 5 instances of 
MiniChatDock
, every panel's ✦ icon, the
selection-explain chip, and indirectly by nothing else) — it is architecturally ONE endpoint with many wire-text
CONVENTIONS layered on top (§9.9), not five different endpoints. Similarly, 
GET
/api/policy/weights_table
 triggers three SEPARATE server-side 
reweight_scenarios
 calls
internally (one per canned weight set) purely to populate one page's table — a single page load can append
multiple audit-trail rows without the user ever touching Copilot.

### 9.11 Docker & deployment linkage

A single-image deploy (HF Spaces Docker SDK, port 7860) — the full stage-by-stage 
Dockerfile

read is Chapter 10's job; this section is the narrower bridge every panel above actually depends on:
which build stage puts which static asset where, so a panel that renders fine locally does not silently 404 in
the deployed Space.

Exhibit 9.10
 — Docker build stages → the static assets this chapter's panels
consume (
Dockerfile
, both stages; 
app/api/main.py
's static-mount block).

Two build stages, one runtime image.
 Stage 1 (
node:22-alpine
) runs 
npm ci
&& npm run build
 over 
app/ui/src
, producing 
app/ui/dist
 — the SPA
every tab in this chapter lives inside. Stage 2 (
python:3.13-slim
) is the runtime: an
EXPLICIT 
COPY
 allowlist (never a broad copy + 
.dockerignore
-exclude — Chapter 10's
own design-decision framing) brings in 
engine/ agent/ app/api/ analysis/ wiki/ knowledge/ data/

plus a curated slice of 
outputs/
: 
models
 (pre-fitted joblib cache, ~9s warm start),

hazard, lgd, staging, eda, vasicek, scenario_ecl, challenger
 (the App v2 consultant exhibits —
everything The Model/Policy/Executive tabs' 
/api/model/*
, 
/api/policy/*
,

/api/exhibits/*
 endpoints parse), and 
outputs/freddie
 + 
outputs/mdd
 (the
Real Data tab's four endpoints and the header's MDD link). Finally 
COPY --from=ui /build/dist
./app/ui/dist
 pulls stage 1's build output into the runtime image.

Static mount
Backs which panels
Guard

/
 → 
app/ui/dist
the entire SPA — every tab in this chapter

if (UI_DIST / "index.html").exists()
, else a plain "not built yet" fallback response

/static/exhibits/*
 → whole 
outputs/
 tree
every

ExhibitImage
 on Executive/Model/Policy (17-row list); ALSO covers

outputs/freddie/**
 as a side effect, since this mount is the WHOLE outputs tree

if OUTPUTS_DIR.exists()

/static/freddie/*
 → 
outputs/freddie/
Real Data tab's own

png_url
 convention (a SECOND, more convenient mount over files already reachable via

/static/exhibits/freddie/*
 above — the contract doc is explicit this is not because the files
are otherwise unreachable)
if FREDDIE_DIR.exists()

/static/mdd/*
 → 
outputs/mdd/
the header's MDD link (all tabs)

if MDD_DIR.exists()
 — 404s harmlessly if absent; the header link is wired unconditionally
regardless

Gotcha — a real deployment incident, not a hypothetical.
 The Dockerfile's own comments record a live
build failure: 9 consecutive HF Spaces build attempts (plain restarts, factory reboot, content-change repush,
atomic delete+re-add) all failed identically on the two 
outputs/freddie
/
outputs/mdd

COPY
 lines specifically — "failed to calculate checksum... not found," despite both directories
verifiably present and their LFS objects resolving fine over HTTP at every attempted commit. The two lines
were TEMPORARILY commented out to restore the Space to RUNNING (the app boots fine without them — the guarded

if FREDDIE_DIR.exists()
/
if MDD_DIR.exists()
 mounts mean only the Real Data tab's own
calls would 404/500 until re-enabled). As of this chapter's writing (2026-07-19) both lines are ACTIVE again
in the Dockerfile — the eventual fix was a longer wall-clock wait for backend LFS propagation, not more
aggressive cache-busting (full retry timeline: 
outputs/gate/mdd_freddie_gate.md
). The practical
lesson for anyone extending this app: a panel that reads live locally can still 404 in a freshly-deployed
Space if its backing 
outputs/
 subtree hit exactly this kind of platform-side propagation race —
check the guarded-mount log line, not just the endpoint's own 200/404, before assuming a code bug.

Security posture (bridges Chapter 10 in full): non-root 
appuser
 (uid 1000), no

.env
/
data/raw
/secrets baked into the image (
.dockerignore
-enforced,
CI-greps the saved image for key prefixes), 
OPENROUTER_API_KEY
 injected at RUN time only — absent
a key, the app still serves via the deterministic offline fallback router (a demoed feature, not a degraded
failure mode: refusal-over-guessing holds either way, Chapter 8).

### 9.12 Three design directions → the shipped spec

Before any of the panels above existed in their current visual form, three FULL candidate design
directions were built and judged in parallel (
outputs/design/{editorial,fintech,terminal}/
, each
with its own 
design_spec.md
 + 
preview.html
 + 
rationale.md
), then scored
against each other and merged into one binding spec, 
outputs/design/FINAL_SPEC.md
 — the document
every component in this chapter is actually built from.

Exhibit 9.11
 — Three design directions, judge scoring (
outputs/design/
FINAL_SPEC.md
 §0; totals 37/42/39 — 
fintech
 wins with 5 grafts adopted from the other
two).

Direction
Framing
Core bet
Where it risked failing (own rationale.md)

editorial
 — "The Consulting Deliverable"
Numbered exhibits, serif prose, a warm-paper
report register — "stop looking like an internal analytics dashboard and start looking like the deliverable a
consulting engagement actually produces."
Exhibit apparatus (numbered kicker + source footer) makes
"never hallucinated numbers" visually structural, not just a promise.
A stronger stylistic bet than
neutral (warm serif can read "considered" or "old-fashioned" depending on the viewer); the waterfall's own
worked numbers didn't reconcile in the mock (flagged honestly, not hidden).

fintech
 — "The Modern Risk Platform" 
(WINNER)
Crisp dashboard register, one
accent, hairline borders — "reads as the same visual register as the tools this audience already trusts...
does not read as a student project or a chatbot demo with charts bolted on."
The ✦ icon on EVERY
panel/tile (not tucked in a menu) + a citation chip on every agent surface, styled identically everywhere —
"trains the eye that this app always shows its work."
Blue means both "the confident thing to click"
(buttons/links/active tab) AND "this waterfall component increased the allowance" on the same screen — a real
tension the spec mitigates (never colour-only encode direction) but doesn't fully resolve.

terminal
 — "THE PRECISION INSTRUMENT"
Regulatory/quant-report grammar — hairlines,
dense tabular figures, a raw 
SOURCE · /api/ecl/summary
 provenance stamp on every panel.

The waterfall's explicit no-fake-scale rule: tiny floored bars + a footnote flag, rather than quietly
rescaling a ~2.6-order-of-magnitude roll-forward to look calmer than the data is.
Coldness for a
non-quant reader; all-caps micro-labels trade legibility for density; a real engineering trap this exploration
caught and fixed (a 
position: fixed
 chat dock that silently covered live content at ordinary
viewport heights) — the fix (collapse-first, reserved bottom padding) is exactly graft 5 below.

Five grafts, from the judge's decision summary (
FINAL_SPEC.md
, verbatim structure).

editorial → exhibit apparatus:
 the numbered 
Exhibit N
 kicker + mandatory source/caption
footer on every chart/table panel — literally the 
<span class="exhibit-kicker">
 and

<p class="panel-source">
 this chapter's own 
Panel.jsx
 reads use, every panel
doc block above.

terminal → grounding vocabulary:
 the 
GROUNDED
/
THINKING
/
OUT OF
SCOPE
 chat-dock status word + dot, tied to real 
/api/agent/ask
 states — §9.9's whole third
subsection.

terminal → adopted-row treatment + units-in-header:
 the 2px accent-border/6% wash/
ADOPTED

tag Policy's Exhibit 2 table uses (§9.6), and units-in-column-header (never repeated per cell) throughout
every data table in this chapter.

editorial → the explain-question figure recap:
 the code-generated recap sentence merged with
fintech's own 
[explain:<panel> <params>]
 tag — §9.9's ✦-icon convention is literally
this graft.

terminal → dock scroll reserve:
 
MiniChatDock
 collapsed-first on small viewports, every
tab's scroll container reserving ≥160px of bottom padding — directly traceable to the concrete engineering trap
the terminal rationale.md documents catching.

Interpretation.
 Every one of the app's five biggest single UI decisions — the exhibit numbering, the
chat-dock vocabulary, the adopted-row highlight, the explain-question convention, and the dock's collapse
behaviour — traces to a SPECIFIC losing direction's rationale, not to the winning direction alone. The shipped
product is a deliberate synthesis, not simply "fintech, unmodified" — reading only the winner's own rationale
without the two losers' would miss why several of this chapter's most load-bearing conventions look the way
they do.

Gotcha — "winner" does not mean "flawless."
 The fintech direction's OWN rationale.md names a real,
unresolved tension it did not fully fix (blue-for-button vs blue-for-increase, above) — reading the scoring
table's win as an endorsement that every remaining risk was solved would miss the losing directions' most
valuable contribution: each one's "where it risks failing" section is itself a live, still-relevant caveat
list for the shipped app, not an artifact of a rejected path.

### 9.13 Closing quiz bank — "where would you look to answer X"

One block per tab, cross-referenced to its documentation section above — the practical test of whether
this chapter's coverage actually works as a reference, not just a read-through.

Executive Overview (§9.3) & Scenario Lab (§9.5).

A client asks "how much of our allowance sits in loans that are already in default?" Which panel, and
what's the number?
  
Answer

Executive Overview's Stage mix of allowance (Exhibit 1, §9.3) — Stage 3
  (credit-impaired) carries 17.83% of the reported allowance, live capture.

A risk manager wants to see the effect of a 2pp unemployment shock BEFORE deciding whether to book it as
policy. Where do they go, and does it change the Executive tab's numbers?
  
Answer

Scenario Lab's "Macro shock" control (§9.5) — running 
shock_macro
 there
  updates ONLY that tab's own Result card and Allowance bridge; it does NOT change anything on the Executive
  tab (the reported allowance, KPI tiles, and historical waterfall there are unaffected) — the
  scenario-controls-vs-historical-waterfall distinction requirement 11 names explicitly.

Why does the Executive tab's waterfall show a tiny "new loans" bar while the Scenario Lab's default
waterfall (before any control is run) can show a much bigger one?
  
Answer

Different default windows: Executive Overview fixes 
t0=59, t1=60
 (the
  latest single quarter); Scenario Lab's fallback default is 
t0=20, t1=40
 (a long historical
  window spanning most of the panel's origination period) — both are the SAME component, just different props,
  per §9.3/§9.5.

The Model (§9.4) & Real Data (§9.7).

A modeller asks "is the unemployment-level coefficient really risk-REDUCING?" Where's the honest answer?
  
Answer

The Model tab's Fit statistics panel (Exhibit 2, §9.4), specifically the
  
net_uer_effect_note
 caveat — the level coefficient alone (HR 0.693) is a collinearity artifact;
  combined with the momentum term the NET effect is risk-INCREASING (hazard ratio 1.280 per pp).

A reviewer wants to know whether a macro series is a genuine live FRED pull or not, for a specific row in
a coefficient table. Which field, on which endpoint?
  
Answer

The row's own 
fred_series
 field (nullable) on
  
GET /api/model/coefficients
/
/api/model/variable_dictionary
 (always null — DCR/
  national is vendor-premerged, not live) or 
GET /api/freddie/hazard
 (populated with a real ID,
  e.g. 
{POSTAL}UR
, for the three genuinely state-level FRED-pulled rows) — or the dedicated
  Macro data glossary (Exhibit 5, §9.4) for the full cross-model picture in one table.

Where would you find evidence that a champion model genuinely could not have foreseen the 2008 financial
crisis, stated as an honest limitation rather than smoothed over?
  
Answer

Real Data's backtest honesty panel (Exhibit 3, §9.7) — the 2007-12 row's 9.42×
  miss ratio (frozen macro), explicitly framed as "the model was never wrong about its own coefficients, it
  simply never saw the crisis coming."

Policy (§9.6), Copilot (§9.8) & the app as a whole.

A credit-risk committee wants to see how sensitive the Stage 2 population is to the SICR threshold
choice, before they sign off on 2.0× as the house convention. Which exhibit?
  
Answer

Policy's Stage-2 share vs SICR threshold (Exhibit 1, §9.6) — at the stress
  reporting date the choice between 2.0× and 4.0× alone swings Stage-2's allowance share by over 72
  percentage points.

A user asks the Copilot a question, gets an answer, and wants to know whether to trust the specific
NUMBER in the reply or treat it as commentary. What single UI signal answers that fastest, without reading the
prose?
  
Answer

The chat-dock status word (§9.9): GROUNDED means every number traces to a tool call or
  cited passage; REASONED means it's a cited interpretation with no fresh computed number — the word alone,
  before reading a single sentence of the answer, tells you which.

An engineer deploys a fresh copy of the app and the Real Data tab returns 404s on every endpoint while
every other tab works fine. Where would you look first?
  
Answer

§9.11's Docker linkage note — check whether the 
outputs/freddie
 COPY line
  actually completed in this build (the guarded 
if FREDDIE_DIR.exists()
 static mount means a
  failed COPY degrades exactly this way: the rest of the app boots fine, only 
/api/freddie/*
 and
  
/static/freddie/*
 fail) — a real incident this exact chapter documents, not a hypothetical.

End of Chapter 9. Next: Chapter 10 — Docker & Deployment Guidebook (the
full stage-by-stage 
Dockerfile
 read this chapter's §9.11 only bridged to), building directly on
the linkage table above.

