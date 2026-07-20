# Coverage report — chapters 1-11 vs the topic map

Generated 2026-07-19, after ingesting `notes/chapters/{ch01..ch11}` into `notes/corpus/` +
`notes/index/` (PageIndex: **11 sources, 650 pages, 259 nodes** — see `pageindex_query.py
notes/index --render`). This is the batch-D revision of the batch-C report: it re-diffs
`notes/plan/topic_map.json` (46 concepts, A1-A23/B1-B11/C1-C6/D1-D6) against what chapters
1-11 actually contain. Chapters 1-8's rows are carried forward unchanged from the batch-C
report (`ingest_notes.py` reported them "8 unchanged" this round); chapters 9-11 are newly
diffed. **This batch also carries two indexing-infrastructure fixes** (both applied to the
`notes/corpus/*.md` build artifacts, not to the chapter HTML) — see "Ingestion notes" below
for the full account: (1) the recurring heading-split bug, applied to ch09-11 the same way
prior batches applied it to ch01-08; (2) a newly-discovered second heading-injection bug in
ch10 specifically (literal `#`-prefixed shell comments inside quoted trace blocks being
misread as markdown headings), fixed by fencing. The "0 figure cards captured" containment
issue recurs a fourth time and is analysed in depth below, per this batch's brief, rather
than re-accepted silently.

## Method

Unchanged from batch A/B/C: for each concept, locate its `theory_anchor.section`,
cross-check against (a) the chapter's own "Compiled from … §N" byline, (b) the planned
mapping in `notes/plan/chapters.md` § "Chapter → concept coverage check", (c) a direct grep
of the generated corpus text / raw chapter HTML for the concept's named topics/keywords, and
(d) the chapter's own top-of-file HTML comment and any inline "Scope note" boxes, which have
proven a reliable source of self-flagged cuts in every batch so far. **Covered** = the
concept's full topic list is present with derivation/worked-example depth matching the plan.
**Partial** = the concept is referenced/used as substrate, treated as a scope-note aside, or
split across chapters, but not given the full topic list at planned depth. **NOT YET** = no
chapter written yet, or a topic explicitly deferred by the writing chapter itself.

## Coverage matrix

| id | title | status | chapter · anchor | note |
|----|-------|--------|-------------------|------|
| A1 | IFRS 9 standard: origins, scope, classification | **covered** | Ch.1 §1.1-1.2 | unchanged from batch C |
| A2 | Staging, default definition, SICR | **covered** | Ch.1 §1.4-1.6 | unchanged from batch C |
| A3 | ECL mechanics: formula, term structure, worked example | **covered** | Ch.2 §2.1-2.3 | unchanged from batch C |
| A4 | IFRS 9 vs Basel IRB vs CECL | **covered** | Ch.1 §1.3 | unchanged from batch C |
| A5 | Data foundations: public datasets, macro series, scenarios, variable dictionary | **covered** | Ch.11 §11.1, §11.5 | **New this batch.** §11.1 ("Why real GSE data: the three upgrades") frames the DCR-vs-SFLLD data-provenance story explicitly (real dates/states/losses); §11.5's Requirement-12-style variable cards give the state-level FRED UER/HPI series full source/transformation/lag-rationale honesty treatment, matching the depth Ch.6 set for the national-level satellite variables. "Variable dictionary" as a literal named artifact is Ch.9 §9.4's job (App tab), cross-referenced not duplicated here — recorded as covered because the substantive topic list (public datasets, macro series, sourcing honesty) is present, not because every literal sub-phrase from the topic map recurs verbatim. |
| A6 | Retail scorecards: WOE, IV, logistic regression | **NOT YET** | planned Ch.3 intro | **Gap, carried forward unresolved, unchanged from batch C.** Ch.9/10/11 do not touch this (out of their scope — product/infra/Freddie-EDA, not scorecard-lineage). Still needs a Ch.3 follow-up pass specifically. |
| A7 | Lifetime PD via discrete-time survival (hazard/cloglog) | **covered** | Ch.3 §3.1-3.7 | unchanged from batch C |
| A8 | Transition matrices for wholesale/rating books | **partial** | Ch.3 (scope note) | unchanged from batch C — deliberate, self-flagged |
| A9 | Corporate & low-default PD: Merton, shadow ratings, Pluto-Tasche | **partial** | Ch.3 (scope note) | unchanged from batch C; D-4 still open, now explicitly re-routed to Ch.12 (batch E) — see backlog below |
| A10 | PIT vs TTC: Vasicek one-factor framework | **covered** | Ch.5 §5.1-5.8 | unchanged from batch C |
| A11 | Forward-looking scenarios: satellite (macro-link) models | **covered** | Ch.6 §6.5 | unchanged from batch C |
| A12 | Multiple probability-weighted scenarios; Jensen's inequality | **covered** | Ch.6 §6.7-6.8 | unchanged from batch C |
| A13 | Post-model adjustments (overlays) | **NOT YET** | planned Ch.6 | unchanged from batch C — silent gap, still open; Ch.9-11 do not touch it |
| A14 | Forecast horizon, lifetime, and the gross-up factor | **covered** | Ch.2 §2.4 | unchanged from batch C |
| A15 | LGD: workout definition and discounting | **covered** | Ch.4 §4.1 | unchanged from batch C |
| A16 | LGD distributional reality and model families | **covered** | Ch.4 §4.1, §4.3 | unchanged from batch C |
| A17 | LGD: secured/unsecured/corporate structural formula | **NOT YET** | planned Ch.4 §10.3 | unchanged from batch C — silent gap, unresolved; Ch.9-11 don't touch LGD structural formulas |
| A18 | Net Credit Loss (NCL): loan- vs portfolio-level, discounting example | **covered** | Ch.11 §11.12-11.13 | **New this batch, rerouted from Ch.4 to Ch.11 (as flagged in the campaign brief).** D-7 fully expanded: each of the 5 real cash flows' discount factor and PV shown individually, summed to `pv_recoveries_eur`/`pv_expenses_eur`, then tied through to the chapter's real SFLLD realized-LGD population (§11.13) rather than left as a synthetic toy — a stronger worked instance than the originally-planned Ch.4 placement would have given. |
| A19 | 90-DPD vs 180-DPD default trigger; roll-rate bridge | **covered** | Ch.11 §11.8-11.10 | **New this batch, rerouted from Ch.4 to Ch.11 (as flagged in the campaign brief).** D-8 fully expanded: each $q_b$ bucket division shown, the 3-term product $R=q_{90}q_{120}q_{150}$ built as a running partial product to 0.6824 (fixture value, differs from the backlog's illustrative 0.60 toy numbers — real fixture inputs, confirmed intentional), then §11.10 applies the SAME estimator to the real SFLLD roll-rate matrices across three calendar windows (GFC/Calm/COVID), giving this concept a real-data validation the original Ch.4 placement never had planned. |
| A20 | EAD: term loans, revolver CCF, behavioural life | **covered** | Ch.4 §4.7-4.10 | unchanged from batch C |
| A21 | Validation: discrimination, calibration, PSI | **partial** | Ch.3 §3.8-3.10 + Ch.7 (whole chapter) | unchanged from batch C — Gini/KS/LGD-EAD-level validation still the named sub-topic gap |
| A22 | Governance, disclosure, capital interaction, hot topics | NOT YET | planned Ch.13 | — |
| A23 | Learning path, tooling, interview drill (meta/appendix) | NOT YET | planned Ch.13 | — |
| B1 | DCR loan-quarter panel construction & waterfall | **partial** | Ch.3 §3.3 | unchanged from batch C |
| B2 | DCR EDA: default rates, hazard by age, LGD, origination quality, prepay | **partial** | Ch.3 intro (5 hits); Ch.4 — 0 hits | unchanged from batch C |
| B3 | DCR hazard model (cloglog competing-risk PD engine) | **covered** | Ch.3 §3.7-3.8 | unchanged from batch C |
| B4 | DCR LGD model (two-stage cure x severity) | **covered** | Ch.4 §4.3 | unchanged from batch C |
| B5 | DCR EAD model | **covered** | Ch.4 §4.7,4.9 | unchanged from batch C |
| B6 | DCR staging model & threshold sensitivity | **covered** | Ch.1 §1.7 | unchanged from batch C |
| B7 | DCR ECL engine, gates & golden fixtures | **covered** | Ch.2 §2.3 | unchanged from batch C |
| B8 | Vasicek calibration on the project panel | **covered** | Ch.5 §5.6-5.7 | unchanged from batch C |
| B9 | DFAST macro scenario paths & satellite fit | **covered** | Ch.6 §6.2-6.4 | unchanged from batch C |
| B10 | Scenario ECL & the project's Jensen-gap exhibit | **covered** | Ch.6 §6.9 | unchanged from batch C |
| B11 | Challenger scorecard: benchmarking & explainability | **partial** | Ch.7 (whole chapter) | unchanged from batch C — swap-set analysis still the self-flagged open item |
| C1 | SFLLD ingest & data-quality (Phase A) | **covered** | Ch.11 §11.2-11.4 | **New this batch.** 17-vintage sample design, the coverage gap, the 32-field layout verification story (§11.2), the D90 absorbing-default definition derived precisely with the tie-break logic (§11.3), and the full panel-construction waterfall with a regenerated flowchart (§11.4, Exhibit 11.1) — matches `outputs/freddie/ingest/dq_report.md`'s 837,500-loan, 39,522,565-loan-month scale. |
| C2 | SFLLD EDA: vintage curves, roll-rates, state heterogeneity, COVID | **covered** | Ch.11 §11.7, §11.10, §11.14-11.15 | **New this batch.** All 5 planned EDA exhibits present and regenerated/embedded with real data: vintage curves (§11.7, Exhibit 11.5 + live widget), roll-rate matrices (§11.10, Exhibit 11.6, three calendar windows GFC/Calm/COVID), state heterogeneity (§11.14, Exhibit 11.8, $r=0.89$ HPI-drawdown-vs-default correlation), realized LGD (§11.13, Exhibit 11.7), calendar-time series (§11.15, Exhibit 11.9) — plus the 2 state-macro map/series exhibits (Exhibits 11.3/11.4, HPI/UER). COVID-regime framing is present as the calendar-time contrast (§11.15) but the modelling DECISION (COVID=exclude from the hazard fit) stays correctly in Ch.12's scope, not duplicated here. |
| C3 | SFLLD hazard model (Phase B) & COVID-regime decision | **partial** | Ch.3 §3.5,3.8 cross-reference; planned Ch.12 for full treatment | unchanged from batch C |
| C4 | SFLLD LGD (realized) model | **covered** | Ch.4 §4.6 | unchanged from batch C |
| C5 | SFLLD backtest: the 9.42x honesty exhibit | **partial** | planned Ch.12 for full derivation; Ch.7 §7.10 forward pointer; **Ch.9 §9.7 new this batch** | Ch.9's Real Data tab documentation (§9.7, Exhibit 9.7 "Freddie backtest honesty panel") documents the miss-ratio panel with real live values from `/api/freddie/exhibits`, including the 200912 GFC-vintage spike — a genuine, live-verified partial treatment (product-surface framing: what the panel shows and how to read it), but Ch.12 still owns the full backtest-ratio DERIVATION (sign convention, the predicted/realized arithmetic reproducing 9.42x from first principles per the backlog's own note) — upgraded from NOT YET to partial, not to covered. |
| C6 | SFLLD LSTM challenger & lift decomposition | **partial** | planned Ch.12 for full treatment; **Ch.9 §9.7 new this batch** | Same pattern as C5 — Ch.9's Real Data tab documents the "LSTM path-dependence challenger, lift decomposition" panel (§9.7) as a product surface with real live values, but the lift-decomposition DERIVATION and the model's own fit statistics stay Ch.12's job — upgraded from NOT YET to partial. |
| D1 | Agent layer: LangGraph router + Tier-1 tools | **covered** | Ch.8 §8.1-8.2, §8.5 | unchanged from batch C |
| D2 | Agent Tier-2 sandbox & Tier-3 retrieval | **covered** | Ch.8 §8.3-8.4 | unchanged from batch C; the PageIndex heading-truncation cosmetic artifact noted in batch C for these two sub-sections is now understood to be a general single-line-merge-only limitation of the heading-split fix (see "Ingestion notes" below), not something specific to Ch.8 |
| D3 | App: FastAPI backend surface | **covered** | Ch.9 §9.2, §9.10 | **New this batch.** Architecture-at-a-glance (§9.2, single-origin no-CORS convention) and the full endpoint→panel wiring table (§9.10, Exhibit 9.9, all 22 live endpoints across 6 tabs plus the 3 static mounts including the MDD link) — every endpoint cited was called LIVE against a local `uv run --no-sync uvicorn app.api.main:app --port 7861` instance this session (engine warm, `agent="langgraph"`, not the offline fallback), not retyped from `docs/api_contract.md` alone. |
| D4 | App: React UI (6 tabs) & design system | **covered** | Ch.9 §9.3-9.9, §9.12 | **New this batch.** All 6 tabs documented to the requirement_11 checklist depth (what it shows / how to read it / how to use it / AI affordances / rendered image / gotchas) — Executive Overview (§9.3), The Model (§9.4), Scenario Lab (§9.5), Policy (§9.6), Real Data (§9.7), Copilot (§9.8) — plus AI affordances in full (§9.9) and the 3-design-direction-to-shipped-spec comparison (§9.12, judge scoring 37/42/39 from `outputs/design/FINAL_SPEC.md`). All 11 figures are labelled "rendered from a live `GET /api/...` call" or embedded from a live-captured source, per this batch's screenshot rule — none fabricated. Closing quiz bank present (§9.13, requirement_11's explicit "also required" item). **One planned-widget deviation, self-flagged in the chapter's own top comment:** the "live endpoint-picker table" `chapters.md` named as Ch.9's interactive widget was built as a static (non-JS-filterable) table instead, for dependency-free consistency with Ch.8's "neither inlined nor relative widgets.js" precedent for non-formula chapters — a deliberate, documented scope choice, not a silent cut. |
| D5 | Docker & deployment | **covered** | Ch.10 (whole chapter) | **New this batch.** Multi-stage Dockerfile walked stage-by-stage with 28 `<details>` collapsibles (§10.2) — the planned static-reference format, no JS — non-root `appuser` posture, the `requirements.docker.txt` torch-pruning decision (§10.3), the explicit-COPY-allowlist-vs-broad-copy-plus-dockerignore-exclude decision and its 9-failure incident (§10.4), HF Spaces port-7860/README-metadata convention (§10.5), the ship-pipeline state machine and queue-stall playbook (§10.6-10.7, drawn from real gate reports and git log), local dev flows (§10.8), image-contents inventory (§10.9, Exhibit 10.3), and the joblib cold/warm-start cache story (§10.10). |
| D6 | Model Documentation Deliverable (MDD) & governance close-out | NOT YET | planned Ch.13 | Ch.9/Ch.10 both mention the MDD only incidentally (the header's MDD link as an app feature; the MDD static mount and its role in the 9-failure Dockerfile incident) — neither attempts the actual governance-content walkthrough D6 requires, so this remains correctly un-double-covered and reserved for Ch.13. |

## Tally

- **Covered:** A1, A2, A3, A4, A14, A7, A10, A15, A16, A20, B3, B4, B5, B6, B7, B8, C4, A11,
  A12, B9, B10, D1, D2, **A5, A18, A19, C1, C2, D3, D4, D5** = **31**
  (batch C's 23 + 8 new: A5, A18, A19, C1, C2, D3, D4, D5)
- **Partial:** B1, A8, A9, A21, B2, C3, B11, **C5, C6** = **9**
  (batch C's 7 + 2 new: C5, C6, both upgraded from NOT YET via Ch.9's product-surface
  documentation, not yet fully derived)
- **NOT YET:** A6, A13, A17, A22, A23, **D6** = **6**
  (batch C's 16, minus 8 now-covered [A5, A18, A19, C1, C2, D3, D4, D5], minus 2 now-partial
  [C5, C6])
- Total = 46 (31 + 9 + 6 = 46, reconciles to `topic_map.json` `concept_count`)

Net movement from batch C: Covered 23→31 (+8), Partial 7→9 (+2), NOT YET 16→6 (−10). This is
the campaign's largest single-batch coverage jump so far. Three concepts remain genuine
unplanned/silent gaps: **A6, A17, A13** (all carried forward unchanged — Ch.9/10/11's scope
is app/infra/Freddie-EDA, none of which touches PD-scorecard-lineage, LGD-structural-formula,
or overlay-governance material). Two further gaps are self-flagged, not silent: **B11's
swap-set analysis** and **A21's Gini/KS/LGD-EAD-level-validation** sub-topics (both carried
from batch C, both untouched by this batch's scope). D-4/Merton (A9) is the one item this
batch explicitly re-routes rather than resolves — see the derivation-backlog section below.

## Derivation backlog status (`notes/plan/derivation_backlog.md`, 11 items)

| id | derivation | planned chapter | status |
|----|------------|------------------|--------|
| D-1 | Survival function from hazard | Ch.2 | **done** — §2.2 (unchanged) |
| D-2 | Full 5-year ECL worked example | Ch.2 | **done** — §2.3 (unchanged) |
| D-11 | Gross-up factor across the 4 horizons | Ch.2 | **done** — §2.4 (unchanged) |
| D-3 | Cloglog link from continuous-time proportional hazards | Ch.3 | **done** — §3.1 (unchanged) |
| D-5 | One-factor Gaussian copula → PD_PIT(Z) | Ch.5 | **done** — §5.3-5.4 (unchanged) |
| D-9 | Binomial backtest + Jeffreys | Ch.3 (relocated from planned Ch.7) | **done** — §3.10 (unchanged) |
| D-10 | PSI, band-by-band | Ch.3 (relocated from planned Ch.7) | **done** — §3.9, applied again in §7.6 (unchanged) |
| D-6 | Jensen's inequality applied to ECL | Ch.6 | **done** — §6.7-6.9 (unchanged) |
| D-7 | NCL discounting, cash-flow by cash-flow | **Ch.11** (relocated from planned Ch.4, per this batch's brief) | **done, this batch** — §11.12-11.13, all 5 real cash flows' $DF(m)$/PV shown individually, tied to the real SFLLD realized-LGD population |
| D-8 | Roll-rate bridge (90→180 DPD) | **Ch.11** (relocated from planned Ch.4, per this batch's brief) | **done, this batch** — §11.8-11.10, the 3-bucket $q_b$ divisions and the $R=q_{90}q_{120}q_{150}$ running product shown step by step, then re-applied to 3 real calendar windows |
| D-4 | Merton distance-to-default and PD | **Ch.12** (re-routed, was orphaned as of batch C) | **not started** — correctly still open; this batch's own scope (Ch.9 app/Ch.10 Docker/Ch.11 Freddie EDA) has no natural home for it, matching batch C's own prediction; Ch.12 (batch E, per `notes/plan/chapters.md`'s own Ch.3→corporate/LDP PD sub-section note and the orchestrator's stated batch E composition) is the confirmed next and final destination — **flagged explicitly here so batch E does not have to rediscover this** |

**10/11 done** (up from 8/11 in batch C, +2: D-7, D-8); **1/11 pending** (D-4), now with a
named, confirmed future home (Ch.12/batch E) rather than an open routing question — the
single most consequential resolution this batch made to the backlog, since batch C's own
report flagged D-4/D-7/D-8's orphan status as "the single most actionable open item for the
campaign owner." Two of the three are now closed; the third has a firm assignment.

## Map gaps discovered while writing/auditing Ch.9-11 (for the topic-map/campaign owner)

- **A6, A17, A13 remain unresolved, unchanged from batch C** — Ch.9 (app product docs),
  Ch.10 (Docker/infra), Ch.11 (Freddie ingest/EDA) none touch PD-scorecard-lineage,
  LGD-structural-formula, or overlay-governance material; these still need a Ch.3/Ch.4/Ch.6
  follow-up pass specifically, not a "later chapter will pick it up" assumption. Flagging
  again with rising urgency since only Ch.12-13 remain in the plan and neither is a natural
  home for these three either (Ch.12 is Freddie models/backtest/LSTM; Ch.13 is
  governance/MDD/closing synthesis) — **recommend the campaign owner schedule a dedicated
  short follow-up pass to Ch.3/Ch.4/Ch.6 after Ch.13, or explicitly accept these three as
  permanent scope cuts and update `topic_map.json`/`chapters.md` to say so**, rather than
  let them carry forward silently into the campaign's close-out.
- **C5/C6 are now "partial" via a genuine but incomplete route**: Ch.9's Real Data tab
  documents the backtest-honesty and LSTM-lift-decomposition PANELS (what a user sees, live
  values, how to read them) but explicitly does not re-derive the 9.42x ratio's arithmetic or
  the LSTM's own fit statistics — that remains Ch.12's job as planned. This is the intended
  "product tour documents the panel, the modelling chapter derives the number behind it"
  split the campaign has used before (D-9/D-10's Ch.3→Ch.7 precedent), working as designed,
  not a new gap.
- **The compendium is still 11 separate chapter files, not the single growing HTML file
  `conventions.md` mandates.** Same finding as batches B/C, now applying to 3 more files:
  `ch09_app_guide.html`, `ch10_docker_deployment.html`, `ch11_freddie_panel_eda.html` all
  carry the identical self-documented deferral pattern in their own top comments. With only
  Ch.12-13 left, this is now the second-most urgent open item after the A6/A17/A13 routing
  decision above — recommend the campaign owner schedule the merge (11 `str_replace`s,
  growing to 13 after Ch.12-13) explicitly rather than let it default to "after Ch.13."

## Ingestion notes (for the maintainer)

- **This round: `ingested 3 new/changed, 8 unchanged`** — ch01-ch08 skipped (byte-identical
  since batch C); ch09/ch10/ch11 newly ingested.
- **The recurring heading-split bug reappeared exactly as in batches A/B/C**, and was fixed
  with the same "orphan `#{1,6}` marker line + next non-blank line" merge heuristic, applied
  this time via a small standalone scratch script
  (`ingest_notes.py`'s `from_html()` inserts the `#`-prefix hashmarks and the heading's own
  text as separate sibling text nodes in the BeautifulSoup tree; `soup.get_text("\n")` then
  puts a newline between them because they are different nodes, orphaning the hashmarks onto
  their own line — a bug in the ingest script itself, not something a corpus-side merge can
  fix at the root, only patch downstream). Cross-checked against
  `grep -oE '<h[1-6][^>]*>' <source>.html | wc -l` minus each chapter's own top-of-file
  HTML-comment literal-tag-syntax offset (the same 2-tag artifact every prior batch found:
  `<h1>`/`<h2 id="sN">` appearing as example syntax in the chapter's own build-notes comment)
  — ch09: raw 90 − 2 = 88 true headings, 88 orphan markers found, **0 discrepancy**; ch10:
  raw 19 − 2 = 17, 17 orphan markers, **0 discrepancy**; ch11: raw 21 − 2 = 19, 19 orphan
  markers, **0 discrepancy**. Zero false merges across all three files, verified before
  trusting the merge (same discipline as every prior batch).
- **A second, previously-undetected heading-injection bug was found and fixed this batch,
  specific to Ch.10.** Ch.10 quotes literal shell/Dockerfile comment lines (`# NOTE`,
  `# TEMPORARILY DISABLED`, `# local`, `# open http://localhost:7860`, `# terminal 1 —
  ...`, `# terminal 2 — ...`) inside `<pre class="trace">` blocks and inline `<code>` spans.
  `ingest_notes.py`'s `from_html()` flattens all HTML to plain text via `get_text()`, so these
  literal `#`-prefixed comment lines survive into the corpus `.md` verbatim, indistinguishable
  from real markdown ATX headings once written to a `.md` file. `build_pageindex.py`'s
  `HEADING_RE` (correctly, per markdown semantics) then treated all 6 as real headings,
  producing 6 spurious top-level nodes (`NOTE`, `TEMPORARILY DISABLED`, `local`,
  `open http://localhost:7860`, `terminal 1 — backend...`, `terminal 2 — frontend...`)
  sitting as SIBLINGS of the chapter's own `<h1>`/`ch10_docker_deployment.html` node rather
  than nested under §10.4/§10.8 where they actually belong — a real, verified degradation of
  the index tree (confirmed via `--render` before the fix: these appeared as flat top-level
  entries between Ch.10 and Ch.11's own nodes). **Fixed** by wrapping each offending
  line/line-range in a ` ``` ` fence pair in the corpus `.md` — `build_pageindex.py`'s own
  module docstring already documents that fenced code blocks are skipped when scanning for
  headings, so this uses an existing, intended escape hatch rather than inventing a new one.
  Verified via `--render`: top-level node count dropped from 28 to 22 after the fix, and all
  6 lines now render correctly nested inside §10.4's "9-failure incident" and §10.8's
  "Local dev flow" sub-sections instead of as false chapter-level siblings. This bug is
  latent in `ingest_notes.py`+`build_pageindex.py` for ANY future chapter that quotes a
  shell/Dockerfile comment as literal prose-embedded text — worth a note for a future
  hardening pass on the shared skill scripts (out of scope for this notes-only reindex task
  to fix at the root, since `ingest_notes.py`/`build_pageindex.py` live under
  `.claude/skills/`, not `notes/`).
- **The "8.3 Tier-2: the sandboxed" / "8.4 Tier-3:" title-truncation artifact flagged in
  batch C is now understood precisely**, having watched the same merge heuristic run on
  three more files this batch: the fix merges an orphan marker with only the IMMEDIATELY
  NEXT non-blank line, not with every line up to the next blank line — so a heading whose
  text is itself split across multiple lines by an inline `<code>`/`<em>`/etc. span inside
  the `<hN>` tag (e.g. `<h3>Tier-2: the sandboxed <code>analyze_data</code></h3>` → three text
  nodes → three corpus lines) only recovers its first line-worth of text; the remainder
  (`analyze_data`) becomes a trailing content line, not part of the node title. This is now
  visible again in ch09/ch10's node titles this batch (e.g. §9.10's own children truncate at
  a `<code>` boundary in a few places, `Panel — 4 KPI tiles (` stopping before
  `StatTile.jsx`; §10.3/§10.4/§10.7 similarly stop just before an inline `<code>` span). Full
  heading text and content remain correct in the source chapter HTML in every case — this is
  a PageIndex node-title cosmetic limitation only, confirmed spot-checked against the source
  HTML for §9.10, §10.3, §10.4, §10.7 specifically this batch. **Recommend, if a future
  hardening pass on `ingest_notes.py` is ever scheduled, extending the merge to gather every
  line up to the next blank line rather than just the first** — this would fix both the batch
  C truncation finding and this batch's version of the same limitation in one change.

### "0 figure cards captured" — full root-cause account (not re-accepted silently)

This is the fourth consecutive batch to report **0 figure cards captured** (23 `<img>` refs
across ch09/ch10/ch11 this round: 11+3+9), and per this batch's own brief the boilerplate
one-line explanation used in batches A-C is not repeated verbatim — here is the precise
mechanism, the options considered, and what is actually lost.

**Root cause.** `ingest_notes.py`'s containment check (`from_html`, line ~248-253) resolves
every `<img src="...">` reference against `args.notes_root = Path(notes_dir).resolve()` — the
SAME directory passed as the script's first positional argument — and refuses to copy any
reference that resolves outside it. The established campaign convention (`conventions.md`
§1, followed by all 11 chapters so far) places every chapter's images in ONE shared sibling
directory, `notes/assets/img/<chNN>/`, referenced from `notes/chapters/<file>.html` via
`../assets/img/<chNN>/<file>.png`. Because the recipe's own invocation is
`ingest_notes.py notes/chapters notes/corpus` (`notes/plan/chapters.md`, `conventions.md` §1
step 5), `notes_root = notes/chapters`, and EVERY chapter's image references escape it by
construction — this is not a per-file mistake, it is guaranteed by the directory layout the
whole campaign is built on.

**Options considered and why each was rejected, this batch (tested, not just reasoned about):**

1. **Widen `notes_dir` to `notes/` (the parent of both `chapters/` and `assets/`).** Tested
   directly this batch in a scratch sandbox: `ingest_notes.py notes <scratch-corpus-dir>`
   picks up 35 files (11 chapter HTMLs, 11 already-generated `notes/corpus/*.md` outputs, 7
   `notes/plan/*.md` planning docs, `notes/assets/template.html`/`widget_demo.html`, and 4
   `notes/assets/data/*.xlsx` workbooks) — confirmed by direct run, not assumption. This
   would (a) re-ingest the corpus's own already-converted `.md` files as fresh "sources"
   alongside the chapters that produced them, doubling every chapter's content under two
   different slugs; (b) sweep in 7 planning documents and 2 non-chapter HTML files that were
   never meant to be part of the compendium's own PageIndex; (c) if `corpus_dir` were the
   real `notes/corpus` (as the recipe uses) rather than a scratch directory, the walk would
   be reading from a directory it is simultaneously writing into. Rejected: breaks the
   established "N chapters = N sources" invariant every coverage report to date has relied on
   for its source/page/node counts, for a benefit (image containment) that a symlink-based
   alternative (below) doesn't need this cost to achieve — except that alternative doesn't
   work either, see (2).
2. **Symlink `notes/chapters/assets → ../assets`, or similar, so the escaping path resolves
   inside the containment root.** Does not work: the containment check resolves
   `(path.parent / src).resolve()` from the LITERAL `<img src="../assets/img/...">` string
   already committed in the chapter HTML — the `../` walks up and out of `notes/chapters`
   via ordinary path arithmetic before any symlink placed INSIDE `notes/chapters` would ever
   be consulted. A symlink only helps a path that stays inside the root and reaches the
   target via the link; this path leaves the root first.
3. **Add a separate `--images-root` flag to `ingest_notes.py`, distinct from the document
   traversal root, so the campaign's chapters/assets split can be expressed directly.**
   Feasible in principle — the fix is a few lines, replacing the single `args.notes_root`
   containment check with `args.images_root or args.notes_root`. Not done this batch:
   `ingest_notes.py` lives under `.claude/skills/pageindex-plus/scripts/`, a shared skill
   script, not a `notes/` deliverable — this reindex task's remit is `notes/` content and the
   existing flag surface ("pass the right root/flag"), not modifying shared infrastructure.
   Recorded here as the concrete, scoped fix a future skill-maintenance pass should make;
   the change is small and low-risk (loosens a safety check only for an explicitly-named
   second root, not a blanket disable) if the skill owner chooses to take it.
4. **Restructure the repo so each chapter's images live under `notes/chapters/img/<chNN>/`
   instead of `notes/assets/img/<chNN>/`.** Would fix the root cause outright, but requires
   rewriting the `<img src>` attribute in all 11 shipped, QA-passed chapter files (and every
   chapter still to come, Ch.12-13) plus moving ~70 PNGs — a repo-convention change with a
   blast radius far beyond a reindex/coverage task, and would invalidate `check_notes.py`'s
   already-passing "img resolves" checks mid-flight if done partially. Not attempted.

**What is actually lost, precisely (not "captions are lost" — they are not):** the PNG BINARY
and the `<img alt="...">` text of each of the 23 references this batch (69 across the full
compendium to date) are not copied into `notes/corpus/img/` and not catalogued as a
`FigCardWriter` figure card, so a `pageindex_query.py --search` cannot surface "the figure
that shows X" as a distinct visual-asset hit, and no downstream tool reading only
`notes/index/` (without also reading the chapter HTML directly) can retrieve the image bytes.
**What is NOT lost:** every figure's EXHIBIT caption (`<div class="figcap">`), the full
surrounding prose that describes what the figure shows, and — critically — every `alt=`
attribute's full descriptive text (verified this batch: ch09's `alt=` strings alone run to
2-4 full sentences per figure, e.g. Exhibit 9.1's alt text fully describes the tab layout in
prose) ARE captured, because they live in the chapter's own HTML text, not inside the PNG
file — `get_text()` extracts them like any other text. So `pageindex_query.py --search` can
and does surface figure-adjacent content correctly (confirmed this batch: searching "roll-rate
matrices heatmap COVID GFC calm" surfaces §11.10's node, whose text includes the full
`alt=` description of Exhibit 11.6). The gap is specifically: no one can extract the actual
image BYTES via the PageIndex tooling alone; they must open the chapter HTML file directly
(a one-line `grep -A2 "Exhibit 11.6" notes/chapters/ch11_freddie_panel_eda.html` finds the
exact relative path). For a study-notes compendium whose real consumer is a human reading the
rendered HTML chapters (not an agent doing PNG-level visual retrieval over the index), this
is a bounded, well-understood gap, not a silent one.

## Verification performed

- `pageindex_query.py notes/index --render`: **11 sources, 650 pages, 259 nodes**, full
  heading hierarchy renders with real titles for all 11 chapters — ch09 (§9.1-9.13, full
  6-tab + AI-affordances + wiring-table + design-comparison + quiz-bank tree), ch10
  (§10.1-10.10, the 9-failure incident and dev-loop sub-sections correctly nested, NOT as
  false top-level siblings post-fence-fix), ch11 (§11.1-11.15, D-7/D-8 derivation
  sub-sections and both interactive-widget sections present) all confirmed present with
  correct nesting depth.
- `pageindex_query.py notes/index --search "D90 absorbing default definition"`: top hit
  correctly resolves to Ch.11 §11.3 (score 21), well ahead of Ch.1 §1.4's related-but-distinct
  general default definition (score 10).
- `pageindex_query.py notes/index --search "endpoint wiring table tabs panels"`: top hit
  resolves to Ch.9 §9.10 (score 21), the exact wiring-table section.
- `pageindex_query.py notes/index --search "dockerignore 9 failure lesson"`: top 2 hits both
  resolve to Ch.10 §10.4 and its "9-failure incident, reconstructed" child (score 4 each) —
  confirms the fence fix nested this content correctly rather than losing it as a flat
  sibling.
- `notes/assets/check_notes.py notes/chapters/*.html`: **PASS on all 11 files** — tag
  balance, img resolution, MathJax delimiter parity, no leftover `{{...}}` placeholders,
  quiz answer-key completeness, and widget JS parse all green for ch01-ch11 (re-run after
  every corpus/index edit this batch, per convention — no chapter HTML was touched, so this
  result was expected to hold, and did).
- Figure/exhibit numbering cross-checked: Ch.9 has 11 `Exhibit 9.x` captions matching 11 PNGs
  in `notes/assets/img/ch09/` (the 2 extra files on disk, `build_diagrams.py` and
  `__pycache__/`, are the regeneration script and its cache, not orphaned images); Ch.10 has
  3 matching 3 PNGs in `ch10/`; Ch.11 has 9 matching 9 PNGs in `ch11/` — no gaps, no orphaned
  images, no unlabelled figures, across all three new chapters.
- Cross-checked derivation-backlog claims (D-7/D-8 "done, this batch, rerouted to Ch.11";
  D-4 "not started, re-routed to Ch.12/batch E") directly against §11.8-11.13's actual
  `<div class="derivation">` blocks with numbered `<span class="stepno">` steps (4 total,
  matching the 4 `class="derivation"` count grepped from the chapter), and against Ch.3's
  scope-note text confirming D-4/Merton is still explicitly deferred there, not silently
  dropped.
- Cross-checked the requirement_11 binding checklist against Ch.9 directly: all 6 tabs
  present (`TABS` array match), closing "where would you look to answer X" quiz bank present
  (§9.13), endpoint→panel wiring table present (§9.10, 22 live endpoints + 3 static mounts),
  every one of the 11 figures' caption states its live data source and capture date — the
  one deviation (static endpoint table instead of a client-side-filterable widget) is
  self-flagged in the chapter's own top comment, not silently cut.

## Next-batch recommendation

**Write Ch.12 (Freddie Models, Backtest & LSTM) and Ch.13 (Governance, MDD & Closing
Synthesis) next**, completing the 13-chapter plan, per the orchestrator's stated batch E
composition (`notes/plan/chapters.md`'s own outline; this batch's brief already confirms
D-4/Merton is routed to Ch.12).

1. **Ch.12 has a fully-specified, unambiguous scope after this batch**: C3 (hazard + COVID
   decision, currently partial), C4 (already covered, cross-reference only), C5/C6 (now
   partial via Ch.9's product-surface documentation — Ch.12 owes the derivations), and D-4
   (Merton, now explicitly assigned here, not merely "not Ch.9-11's job"). No routing
   ambiguity remains for batch E to resolve first, unlike batch D's own D-7/D-8 routing task.
2. **Ch.13 closes A22, A23, D6 (all still NOT YET) and should absorb the A6/A13/A17
   resolution decision** flagged above — either a genuine short follow-up pass to Ch.3/4/6,
   or an explicit "permanent scope cut" recorded in `topic_map.json`. Recommend the campaign
   owner decide this explicitly before or during Ch.13, since Ch.13 is the last chapter and
   there is no batch F to defer it to again.
3. **The one-file-compendium merge (11→13 files) should be scheduled once Ch.12-13 land** —
   flagged with rising urgency in every batch's report since batch B; doing it once, after
   the full 13 chapters exist, is one mechanical pass rather than 13 incremental ones.
4. **A campaign-wide final adversarial pass** (per the orchestrator's own stated eventual
   scope) is the natural batch-F-or-final-step after Ch.13 lands: re-verify every "done"
   derivation-backlog claim against its actual `<div class="derivation">` block one more
   time end-to-end, re-run `check_notes.py` on the final merged single-file compendium, and
   re-diff the full `topic_map.json` against all 13 chapters in one pass rather than the
   incremental per-batch diffs this report series has used — the incremental method has
   caught real gaps (A13 in batch C, the ch10 fence bug in this batch) but a single
   end-to-end pass is the right final gate before calling the compendium complete.
