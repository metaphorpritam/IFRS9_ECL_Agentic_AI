# Coverage report — chapters 1-8 vs the topic map

Generated 2026-07-19, after ingesting `notes/chapters/{ch01..ch08}` into `notes/corpus/` +
`notes/index/` (PageIndex: **8 sources, 395 pages, 132 nodes** — see `pageindex_query.py
notes/index --render`). This is the batch-C revision of the batch-B report: it re-diffs
`notes/plan/topic_map.json` (46 concepts, A1-A23/B1-B11/C1-C6/D1-D6) against what chapters
1-8 actually contain. Chapters 1-5's rows are carried forward unchanged from the batch-B
report (`ingest_notes.py` reported them "5 unchanged" this round); chapters 6-8 are newly
diffed.

## Method

Unchanged from batch A/B: for each concept, locate its `theory_anchor.section`, cross-check
against (a) the chapter's own "Compiled from … §N" byline, (b) the planned mapping in
`notes/plan/chapters.md` § "Chapter → concept coverage check", (c) a direct grep of the
generated corpus text / raw chapter HTML for the concept's named topics/keywords, and (d)
the chapter's own top-of-file HTML comment and any inline "Scope note" boxes, which have
proven a reliable source of self-flagged cuts in every batch so far. **Covered** = the
concept's full topic list is present with derivation/worked-example depth matching the
plan. **Partial** = the concept is referenced/used as substrate, treated as a scope-note
aside, or split across chapters, but not given the full topic list at planned depth. **NOT
YET** = no chapter written yet, or a topic explicitly deferred by the writing chapter
itself.

## Coverage matrix

| id | title | status | chapter · anchor | note |
|----|-------|--------|-------------------|------|
| A1 | IFRS 9 standard: origins, scope, classification | **covered** | Ch.1 §1.1-1.2 | unchanged from batch B |
| A2 | Staging, default definition, SICR | **covered** | Ch.1 §1.4-1.6 | unchanged from batch B |
| A3 | ECL mechanics: formula, term structure, worked example | **covered** | Ch.2 §2.1-2.3 | unchanged from batch B |
| A4 | IFRS 9 vs Basel IRB vs CECL | **covered** | Ch.1 §1.3 | unchanged from batch B |
| A5 | Data foundations: public datasets, macro series, scenarios, variable dictionary | NOT YET | planned Ch.11 intro | — |
| A6 | Retail scorecards: WOE, IV, logistic regression | **NOT YET** | planned Ch.3 intro | **Gap, carried forward unresolved.** Still zero WOE/information-value/coarse-classing text anywhere in the compendium; not self-flagged as a cut by any chapter. Ch.6/7/8 do not touch this (out of their scope), so this remains exactly as batch B left it. |
| A7 | Lifetime PD via discrete-time survival (hazard/cloglog) | **covered** | Ch.3 §3.1-3.7 | unchanged from batch B |
| A8 | Transition matrices for wholesale/rating books | **partial** | Ch.3 (scope note) | unchanged from batch B — deliberate, self-flagged |
| A9 | Corporate & low-default PD: Merton, shadow ratings, Pluto-Tasche | **partial** | Ch.3 (scope note) | unchanged from batch B; D-4 still open (see backlog) |
| A10 | PIT vs TTC: Vasicek one-factor framework | **covered** | Ch.5 §5.1-5.8 | unchanged from batch B |
| A11 | Forward-looking scenarios: satellite (macro-link) models | **covered** | Ch.6 §6.5 | **New this batch.** Fitted satellite regression $Z_t=f(hpi\_growth\_lag1,\,gdp\_growth\_lag2)$, full variable cards (Requirement 12: source/transformation/lag/units/coefficient-reading honesty for both regressors, DCR-panel-not-live-FRED disclosure), ADF/KPSS stationarity + lag-selection hygiene (§6.5 sub-section), R&S-window framing (§6.4, IFRS 9 §5.5.17(c) cited) |
| A12 | Multiple probability-weighted scenarios; Jensen's inequality | **covered** | Ch.6 §6.7-6.8 | **New this batch.** D-6 fully expanded: Jensen's inequality proved via the supporting-line argument (§6.7a), $PD_{PIT}(Z)$ convexity proved via the Vasicek second derivative (§6.7b), convexity propagated through the linear EAD·LGD scale-up to ECL (§6.7c), then the toy 3-scenario fixture quantified band-by-band to the 1.9x understatement (§6.8) |
| A13 | Post-model adjustments (overlays) | **NOT YET** | planned Ch.6 | **New silent gap, same pattern as A6/A17.** `chapters.md` assigns A13 to Ch.6; the shipped chapter covers "reasonable and supportable" information and the R&S window (§6.4) but has **zero** mentions of "overlay", "ECB thematic review", "quarter of coverage", or "exit criteria" anywhere — confirmed by grep. Not named as a deliberate cut in Ch.6's top comment (which only discusses D-6 and Requirement 12). Recommend a short overlay-governance subsection added to Ch.6 in a follow-up pass, alongside the A6/A17 fixes below. |
| A14 | Forecast horizon, lifetime, and the gross-up factor | **covered** | Ch.2 §2.4 | unchanged from batch B |
| A15 | LGD: workout definition and discounting | **covered** | Ch.4 §4.1 | unchanged from batch B |
| A16 | LGD distributional reality and model families | **covered** | Ch.4 §4.1, §4.3 | unchanged from batch B |
| A17 | LGD: secured/unsecured/corporate structural formula | **NOT YET** | planned Ch.4 §10.3 | unchanged from batch B — silent gap, unresolved (Ch.6/7/8 don't touch LGD) |
| A18 | Net Credit Loss (NCL): loan- vs portfolio-level, discounting example | **NOT YET** | planned Ch.4 §11.1/11.3 | unchanged from batch B — self-flagged in Ch.4, D-7 still orphaned |
| A19 | 90-DPD vs 180-DPD default trigger; roll-rate bridge | **NOT YET** | planned Ch.4 §11.2/11.4 | unchanged from batch B — self-flagged in Ch.4, D-8 still orphaned |
| A20 | EAD: term loans, revolver CCF, behavioural life | **covered** | Ch.4 §4.7-4.10 | unchanged from batch B |
| A21 | Validation: discrimination, calibration, PSI | **partial** | Ch.3 §3.8-3.10 + Ch.7 (whole chapter) | **Substantially strengthened this batch but still partial.** Ch.7 adds a full champion-vs-challenger validation pass — reliability/calibration (§7.5), PSI stability train→OOT (§7.6, D-10 applied to real recomputed scores after Ch.3's toy derivation), and an AUC-intuition widget (§7.9) — on top of Ch.3's PD-level discrimination/PSI/backtest. A21's full topic list still names **Gini** (1 mention total across the whole compendium, Ch.3 only, as $\mathrm{Gini}=2\,\mathrm{AUC}-1$, not developed further; **0 mentions in Ch.7**), **KS** (0 mentions anywhere), and **LGD/EAD/ECL-level validation** (0 mentions — everything so far is PD/hazard-model-level only). Ch.7 itself self-flags two further gaps explicitly (see below): it does not re-apply D-9 (binomial/Jeffreys) to the challenger's grades, and does not add a swap-set staging comparison. |
| A22 | Governance, disclosure, capital interaction, hot topics | NOT YET | planned Ch.13 | — |
| A23 | Learning path, tooling, interview drill (meta/appendix) | NOT YET | planned Ch.13 | — |
| B1 | DCR loan-quarter panel construction & waterfall | **partial** | Ch.3 §3.3 | unchanged from batch B |
| B2 | DCR EDA: default rates, hazard by age, LGD, origination quality, prepay | **partial** | Ch.3 intro (5 hits); Ch.4 — 0 hits | unchanged from batch B |
| B3 | DCR hazard model (cloglog competing-risk PD engine) | **covered** | Ch.3 §3.7-3.8 | unchanged from batch B |
| B4 | DCR LGD model (two-stage cure x severity) | **covered** | Ch.4 §4.3 | unchanged from batch B |
| B5 | DCR EAD model | **covered** | Ch.4 §4.7,4.9 | unchanged from batch B |
| B6 | DCR staging model & threshold sensitivity | **covered** | Ch.1 §1.7 | unchanged from batch B |
| B7 | DCR ECL engine, gates & golden fixtures | **covered** | Ch.2 §2.3 | unchanged from batch B |
| B8 | Vasicek calibration on the project panel | **covered** | Ch.5 §5.6-5.7 | unchanged from batch B |
| B9 | DFAST macro scenario paths & satellite fit | **covered** | Ch.6 §6.2-6.4 | **New this batch.** Baseline/Severely-Adverse 13-quarter DFAST 2026 CSVs ingested and rebased onto the DCR panel's own clock (the "two clocks" rebasing derivation, §6.2), judgmental upside construction (§6.3, since DFAST publishes no upside path), extension to the 40-quarter R&S/reversion window (§6.4), satellite regression fit (§6.5). Named topic "UER and HPI fan charts" specifically is not present by that name (no fan-chart visualization) — the underlying UER/HPI path data and their role in the satellite are fully covered, so this is a minor terminology gap, not a substance gap. |
| B10 | Scenario ECL & the project's Jensen-gap exhibit | **covered** | Ch.6 §6.9 | **New this batch.** The project's real 1.035x ratio (vs the toy's 1.9x) derived and honestly decomposed into 4 compounding reasons (calibrated ρ=0.0227 vs toy's 0.12 being the dominant one), plus a weights-sensitivity governance exhibit (§6.9, adopted 50/25/25 vs two alternate weightings) |
| B11 | Challenger scorecard: benchmarking & explainability | **partial** | Ch.7 (whole chapter) | **New this batch, most topics covered.** Reliability diagram (§7.5), PSI across time (§7.6), permutation importance (§7.7, 11 mentions), PDP grid including the "double trigger" LTV×unemployment finding (§7.7) all present and worked with real recomputed numbers (`notes/assets/img/ch07/recompute_challenger_scoring.py`, champion train/OOT AUC 0.7476/0.6609 vs challenger 0.7632/0.6417 matching `outputs/challenger/scorecard.md` to 4dp). **Staging swap-set analysis is the one B11 topic not done** — Ch.7 §7.6's own text explicitly says so: "this chapter does not re-apply [D-9] to the challenger's grades or add a swap-set staging comparison — both are scoped out of this build and remain open items against the campaign's original Ch.7 learning goals." Self-flagged, not silent — recommend a short swap-set addendum in a Ch.7 follow-up pass, or explicit re-routing to Ch.13's closing synthesis. |
| C1 | SFLLD ingest & data-quality (Phase A) | NOT YET | planned Ch.11 | — |
| C2 | SFLLD EDA: vintage curves, roll-rates, state heterogeneity, COVID | NOT YET | planned Ch.11 | — |
| C3 | SFLLD hazard model (Phase B) & COVID-regime decision | **partial** | Ch.3 §3.5,3.8 cross-reference; planned Ch.12 for full treatment | unchanged from batch B |
| C4 | SFLLD LGD (realized) model | **covered** | Ch.4 §4.6 | unchanged from batch B |
| C5 | SFLLD backtest: the 9.42x honesty exhibit | NOT YET | planned Ch.12; Ch.7 §7.10 names it as a forward pointer only | Ch.7's closing section explicitly points ahead to "Chapter 12 runs a[n LSTM challenger]" without pre-empting C5's content — a clean forward reference, not a coverage claim |
| C6 | SFLLD LSTM challenger & lift decomposition | NOT YET | planned Ch.12; same Ch.7 §7.10 forward pointer | see C5 |
| D1 | Agent layer: LangGraph router + Tier-1 tools | **covered** | Ch.8 §8.1-8.2, §8.5 | **New this batch.** The governing rule quoted verbatim from `agent/graph.py`'s module docstring (§8.1); all four Tier-1 tools (`shock_macro`, `reweight_scenarios`, `rerun_ecl`, `decompose_waterfall`) walked individually with real live-called examples against the frozen engine + warm model cache (§8.2); the three-way router scope split (COMPUTABLE/REASONED/OUT-OF-SCOPE) with an interactive decision-tree explorer (§8.5) |
| D2 | Agent Tier-2 sandbox & Tier-3 retrieval | **covered** | Ch.8 §8.3-8.4 | **New this batch.** Tier-2 `analyze_data` sandbox (§8.3) and Tier-3 `query_model_docs` wiki/index Graph-RAG retrieval (§8.4) — chapter headings render with truncated titles in the PageIndex tree (`8.3 Tier-2: the sandboxed` / `8.4 Tier-3:` — the trailing `analyze_data`/`query_model_docs` code-font text is being cut by the index's heading-text truncation, a cosmetic indexing artifact only, confirmed the full text is present and correct in the source chapter HTML) |
| D3 | App: FastAPI backend surface | NOT YET | planned Ch.9 | — |
| D4 | App: React UI (6 tabs) & design system | NOT YET | planned Ch.9 | — |
| D5 | Docker & deployment | NOT YET | planned Ch.10 | — |
| D6 | Model Documentation Deliverable (MDD) & governance close-out | NOT YET | planned Ch.13 | — |

## Tally

- **Covered:** A1, A2, A3, A4, A14, A7, A10, A15, A16, A20, B3, B4, B5, B6, B7, B8, C4, A11,
  A12, B9, B10, D1, D2 = **23**
  (batch B's 17 + 6 new: A11, A12, B9, B10, D1, D2)
- **Partial:** B1, A8, A9, A21, B2, C3, B11 = **7**
  (batch B's 6 + 1 new: B11)
- **NOT YET:** A5, A6, A13, A17, A18, A19, A22, A23, B9(—now covered, removed), C1, C2, C5,
  C6, D3, D4, D5, D6 = **16**
  (batch B's 23, minus the 6 now-covered concepts above, plus 1 new gap surfaced: A13)
- Total = 46 (23 + 7 + 16 = 46, reconciles to `topic_map.json` `concept_count`)

Net movement from batch B: Covered 17→23 (+6), Partial 6→7 (+1), NOT YET 23→16 (−7, i.e.
−6 for newly-covered concepts, +1 for the newly-surfaced A13 gap). Three concepts are now
confirmed genuine unplanned/silent gaps across the whole compendium so far: **A6, A17**
(carried forward from batch B, still unresolved — Ch.6/7/8 don't touch PD-scorecard-lineage
or LGD-structural-formula material) and **A13** (new this batch). Two further gaps are
self-flagged, not silent: **B11's swap-set analysis** (Ch.7 names it explicitly as
deferred) and **A21's Gini/KS/LGD-EAD-validation** sub-topics (not explicitly named as cut,
but the chapter's own "what this chapter covers" framing is honest about being PD/hazard-
scoped throughout, so this reads as a scope choice rather than an oversight — recorded as
partial rather than a fresh "silent gap" flag).

## Derivation backlog status (`notes/plan/derivation_backlog.md`, 11 items)

| id | derivation | planned chapter | status |
|----|------------|------------------|--------|
| D-1 | Survival function from hazard | Ch.2 | **done** — §2.2 (unchanged) |
| D-2 | Full 5-year ECL worked example | Ch.2 | **done** — §2.3 (unchanged) |
| D-11 | Gross-up factor across the 4 horizons | Ch.2 | **done** — §2.4 (unchanged) |
| D-3 | Cloglog link from continuous-time proportional hazards | Ch.3 | **done** — §3.1 (unchanged) |
| D-5 | One-factor Gaussian copula → PD_PIT(Z) | Ch.5 | **done** — §5.3-5.4 (unchanged) |
| D-9 | Binomial backtest + Jeffreys | Ch.3 (relocated from planned Ch.7) | **done** — §3.10; Ch.7 explicitly declines to re-derive it, cross-referencing instead (§7.6) — see "Map gaps" below, this is the precedent working as designed |
| D-10 | PSI, band-by-band | Ch.3 (relocated from planned Ch.7) | **done** — §3.9 first, then §7.6 applies the same formula to real recomputed champion/challenger scores rather than re-deriving — the precedent's intended payoff realised this batch |
| D-6 | Jensen's inequality applied to ECL | Ch.6 | **done, this batch** — §6.7, full 3-part proof (Jensen → PD_PIT convexity → ECL convexity) plus the quantified toy fixture (§6.8) and the project's real 1.035x (§6.9) |
| D-4 | Merton distance-to-default and PD | Ch.3 | **not started** — still orphaned (see batch B's finding, unchanged; no Ch.6/7/8 content touches this) |
| D-7 | NCL discounting, cash-flow by cash-flow | Ch.4 | **not started** — still orphaned, unchanged |
| D-8 | Roll-rate bridge (90→180 DPD) | Ch.4 | **not started** — still orphaned, unchanged |

**8/11 done** (up from 7/11 in batch B, +1: D-6); **3/11 pending** (D-4, D-7, D-8), all
three now genuinely orphaned with no future chapter (Ch.9-13 in the remaining plan) named
as their new home. This is the single most actionable open item for the campaign owner:
none of Ch.9 (app guide), Ch.10 (Docker), or Ch.11 (Freddie panel) — the recommended next
batch — are natural homes for Merton/NCL/roll-rate content, so these three will very likely
still be orphaned after batch D too, unless explicitly re-routed to Ch.13's closing
synthesis as a "backlog derivations" appendix (the option batch B's report flagged as
plausible for exactly this scenario).

## Map gaps discovered while writing/auditing Ch.6-8 (for the topic-map/campaign owner)

- **A13 (overlay governance) is a new silent gap, same shape as A6/A17.** `chapters.md`
  assigns A13 to Ch.6; the shipped chapter's own top-of-file comment names D-6 and
  Requirement 12 as its scope commitments but never mentions overlays as an intentional
  cut. Zero mentions of "overlay"/"ECB thematic review"/"quarter of coverage"/"exit
  criteria" anywhere in the chapter. Recommend a short overlay-governance subsection
  (a natural fit right after §6.4's R&S-window discussion, since overlays are precisely
  what banks reach for when the R&S window and the fitted satellite together still
  understate a risk the model can't see) added to Ch.6 in a follow-up pass — this would
  also let Ch.13's governance chapter (A22) cross-reference rather than introduce overlays
  cold.
- **A6 and A17 remain unresolved from batch B, and no chapter in this batch could have
  fixed them** (Ch.6/7/8's scope is scenarios/challengers/agent, not scorecard-lineage or
  LGD-structural-formula material) — flagging again only so the campaign owner doesn't lose
  track of them once Ch.9-11 start: they need a Ch.3/Ch.4 follow-up pass specifically, not
  a "later chapter will pick it up" assumption.
- **B11's swap-set analysis and A21's challenger-grade D-9 backtest are Ch.7's own
  self-flagged deferrals**, quoted verbatim above — genuinely the cleanest kind of gap
  (explicit, reasoned, with a named reason: "scoped out of this build"), but still open.
  Recommend either a short Ch.7 addendum or explicit assignment to Ch.13.
- **The compendium is still 8 separate chapter files, not the single growing HTML file
  `conventions.md` mandates.** Same finding as batch B, now applying to 3 more files:
  `ch06_scenarios_satellite_jensen.html`, `ch07_challengers.html`, `ch08_the_agent.html`
  all carry the identical self-documented deferral pattern in their own top comments
  ("Standalone deliverable for this build phase… `<h2 id="sN">` is written so a later merge
  … is a straight splice"). Consistent across all 8 chapters now (nothing built
  inconsistently), but the actual merge into
  `notes/chapters/ifrs9_ecl_study_notes.html` has still never happened. With 5 chapters
  left to write (Ch.9-13), this is worth flagging with rising urgency: the merge is
  mechanical (8 `str_replace`s) but the more chapters accumulate unmerged, the larger that
  one deferred step gets. Not a blocker for this reindex/coverage task, but recommend the
  campaign owner schedule the merge explicitly rather than let it default to "after
  Ch.13."
- **D1/D2's PageIndex node titles are truncated** (`8.3 Tier-2: the sandboxed` / `8.4
  Tier-3:` instead of the full `8.3 Tier-2: the sandboxed analyze_data` / `8.4 Tier-3:
  query_model_docs` headings) — checked against the source chapter HTML and confirmed this
  is a `build_pageindex.py` heading-title truncation artifact (the code-font
  `analyze_data`/`query_model_docs` spans appear to be getting dropped by the same class of
  markdown-conversion quirk `ingest_notes.py` has shown in every batch so far, not a
  content gap — the full heading text and content are correct in
  `notes/chapters/ch08_the_agent.html` itself). Cosmetic only; noting for the maintainer in
  case a future batch wants to harden the ingest/build pipeline against it.

## Next-batch recommendation

**Write Ch.9 (The App: A Guidebook), Ch.10 (Docker & Deployment Guidebook), and Ch.11
(Freddie Mac Panel & EDA) next**, per the orchestrator's stated batch D composition. This
also happens to be the natural next slice on independent merits:

1. **Clears the entire D-series (agent/app/infra) except D6**, which is Ch.13's job
   (MDD/governance close-out) — D1/D2 are now done (this batch), so Ch.9+Ch.10 would take
   D3, D4, D5 to 5/6 done, leaving only D6 for the closing chapter.
2. **Ch.9 is binding-scope-overridden by `notes/plan/requirement_11_app_guide.md`** and is
   the single largest remaining chapter by required exhaustiveness (6 tabs, per-panel
   documentation, 24-endpoint wiring table, quiz bank) — starting it earliest in the
   remaining schedule gives the most runway if it needs a multi-pass build.
3. **No fixture/derivation dependency for any of the three** — Ch.9/10/11 all pull from
   live app inspection, the Dockerfile, and `outputs/freddie/ingest|eda/*.md` respectively,
   none from `tests/fixtures/compute_*.py`, so none are gated on anything this batch
   touched.
4. **Ch.11 begins the Freddie-side arc** (C1, C2) that Ch.12 (not yet scheduled) will
   complete alongside C3's remaining topics (COVID-regime decision, state-UER effect,
   calibration-by-year) and C5/C6 — recommend Ch.12 immediately follow in batch E so the
   Freddie arc isn't left half-finished the way Ch.6/7 briefly were between batches B and C.

**Before or during batch D, the campaign owner should also resolve:** the A13 overlay gap
and the A6/A17 carried-forward gaps (small follow-up passes to Ch.6/Ch.3/Ch.4
respectively — none block Ch.9-11's own content); the D-4/D-7/D-8 orphaned-derivation
routing decision (increasingly urgent as noted above); and a decision on when the
one-file-compendium merge actually happens.

## Ingestion notes (for the maintainer)

- **This round: `ingested 3 new/changed, 5 unchanged`** — ch01-ch05 skipped (byte-identical
  since batch B); ch06/ch07/ch08 newly ingested.
- **0 figure cards captured for the 3 new chapters** — same deliberate `ingest_notes.py`
  safety refusal as every prior batch (`<img>` refs resolve to `../assets/img/ch0N/...`,
  outside the `notes/chapters` containment root). 17 `<img>` refs across ch06/07/08 all
  refused identically; captions remain fully text-indexed, only the PNG binaries/alt-text
  are outside the index.
- **The heading-split bug reappeared exactly as in batch A/B**, and was fixed with the same
  merge heuristic (orphan `#{1,6}` marker line + next non-blank line). This round's
  cross-check against `grep -oE '<h[1-6][^>]*>' <source>.html | wc -l` found each new
  file's raw `<hN>` count 2 higher than the true content-heading count, in every one of the
  3 files — traced to each chapter's own top-of-file HTML *comment* containing a literal,
  human-readable example of the tag syntax ("`<h2 id="s6">` is written so a later merge…"),
  which a naive tag-count grep cannot distinguish from a real heading. Once that 2-tag
  comment-artifact offset is subtracted, the true heading counts (26 / 16 / 18 for ch06 /
  ch07 / ch08) matched the merge-heuristic's actual merge count **exactly**, with **zero**
  false merges this round (unlike batch B's one over-fire on a literal `#`-as-table-header
  character) — verified before trusting the merge, not after.
- **Lesson reinforced for the next incremental ingest**: when cross-checking merged heading
  counts against `grep -oE '<h[1-6][^>]*>' <source>.html | wc -l`, first check whether the
  chapter's own top-of-file comment contains literal example tag text (a recurring pattern
  across ch06/07/08's authoring style, documenting the "straight splice" convention) —
  subtract those before comparing counts, or the check will show a false discrepancy and
  invite an unnecessary manual heading hunt.

## Verification performed

- `pageindex_query.py notes/index --render`: **8 sources, 395 pages, 132 nodes**, full
  heading hierarchy renders with real titles for all 8 chapters — no orphaned/blank-title
  nodes, no leftover artifact from the merge (verified 0 remaining bare `#{1,6}` lines in
  all 3 new corpus files post-fix).
- `pageindex_query.py notes/index --search "Jensen inequality convexity PD_PIT"`: top hits
  correctly resolve to Ch.6 §6.7's three parts (score 10) and its parent sections, ahead of
  the related-but-distinct Ch.5 §5.5 Vasicek widget (score 4).
- `pageindex_query.py notes/index --search "LangGraph router tier1 tier2 sandbox"`: top hit
  resolves to Ch.8 §8.5 (score 10), with §8.3 (Tier-2 sandbox) and §8.2 (Tier-1 tools) both
  surfacing in the top 6.
- `pageindex_query.py notes/index --search "PSI stability challenger reliability"`: top hits
  resolve to Ch.7 as a whole (score 15) and its §7.6/§7.5 sub-sections (score 11 each), with
  Ch.3's earlier PSI derivation (§3.9) correctly surfacing alongside as a related score-11
  hit rather than out-ranking the challenger-specific content.
- `notes/assets/check_notes.py notes/chapters/*.html`: **PASS on all 8 files** — tag
  balance, img resolution, MathJax delimiter parity, no leftover `{{...}}` placeholders,
  quiz answer-key completeness, and widget JS parse all green for ch01-ch08.
- Figure/exhibit numbering cross-checked: Ch.6 has 7 `Exhibit 6.x` captions matching 7 PNGs
  in `notes/assets/img/ch06/`; Ch.7 has 6 matching 6 PNGs in `ch07/`; Ch.8 has 4 matching 4
  PNGs in `ch08/` — no gaps, no orphaned images, no unlabelled figures.
- Cross-checked derivation-backlog claims (D-6 "done, this batch"; D-9/D-10 "done,
  cross-referenced not re-derived in Ch.7"; D-4/D-7/D-8 "not started, orphaned") directly
  against each chapter's own derivation cross-reference text/scope notes, not just section
  titles — every "done" status is backed by an actual `<div class="derivation">` block with
  numbered `<span class="stepno">` steps.
