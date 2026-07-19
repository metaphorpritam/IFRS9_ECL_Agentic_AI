# Coverage report — chapters 1-5 vs the topic map

Generated 2026-07-19, after ingesting `notes/chapters/{ch01,ch02,ch03,ch04,ch05}` into
`notes/corpus/` + `notes/index/` (PageIndex: **5 sources, 222 pages, 69 nodes** — see
`pageindex_query.py notes/index --render`). This is the batch-B revision of the batch-A
report: it re-diffs `notes/plan/topic_map.json` (46 concepts, A1-A23/B1-B11/C1-C6/D1-D6)
against what chapters 1-5 actually contain, read against the index tree and the corpus text
(`notes/corpus/ch0{1..5}_*.html.md`). Chapters 1-2's rows are carried forward unchanged from
the batch-A report (files unchanged this round — `ingest_notes.py` reported them
"2 unchanged"); chapters 3-5 are newly diffed.

## Method

Unchanged from batch A: for each concept, locate its `theory_anchor.section`, cross-check
against (a) the chapter's own "Compiled from … §N" byline, (b) the planned mapping in
`notes/plan/chapters.md` § "Chapter → concept coverage check", (c) a direct grep of the
generated corpus text / raw chapter HTML for the concept's named topics/keywords, and (d)
the chapter's own top-of-file HTML comment, which in batch B turned out to be an unusually
reliable source — both Ch.3 and Ch.4 self-document scope cuts there (see "Map gaps"
below). **Covered** = the concept's full topic list is present with derivation/worked-example
depth matching the plan. **Partial** = the concept is referenced/used as substrate, treated
as a scope-note aside, or split across chapters, but not given the full topic list at
planned depth. **NOT YET** = no chapter written yet, or a topic explicitly deferred by the
writing chapter itself.

## Coverage matrix

| id | title | status | chapter · anchor | note |
|----|-------|--------|-------------------|------|
| A1 | IFRS 9 standard: origins, scope, classification | **covered** | Ch.1 §1.1-1.2 (id=0004,0005) | unchanged from batch A |
| A2 | Staging, default definition, SICR | **covered** | Ch.1 §1.4-1.6 (id=0007,0008,0009) | unchanged from batch A |
| A3 | ECL mechanics: formula, term structure, worked example | **covered** | Ch.2 §2.1-2.3 (id=0016,0017,0018) | unchanged from batch A |
| A4 | IFRS 9 vs Basel IRB vs CECL | **covered** | Ch.1 §1.3 (id=0006) | unchanged from batch A |
| A5 | Data foundations: public datasets, macro series, scenarios, variable dictionary | NOT YET | planned Ch.11 intro | — |
| A6 | Retail scorecards: WOE, IV, logistic regression | **NOT YET** | planned Ch.3 intro | **Gap.** `chapters.md` explicitly assigns A6 to "Ch.3 intro (scorecard lineage before hazard models)"; grep of `ch03_hazard_modeling.html` for WOE/information-value/coarse-classing returns **zero** hits, and — unlike A8/A9, which Ch.3 explicitly scopes out in its own top-of-file comment — A6 is not mentioned as a deliberate cut anywhere in the chapter. Silently dropped, not flagged. |
| A7 | Lifetime PD via discrete-time survival (hazard/cloglog) | **covered** | Ch.3 §3.1-3.7 (id=0027-0033) | Full cloglog-from-continuous-hazard derivation (D-3, §3.1); competing-risk survival (§3.2); panel construction incl. left truncation (§3.3-3.4); seasoning hump (§3.5); timing convention (§3.6); champion coefficient table (§3.7) |
| A8 | Transition matrices (Markov chains) for wholesale/rating books | **partial** | Ch.3 (scope note only, id=0026 intro) | Exactly as planned — `chapters.md` calls this "a scope note", not a full treatment, since the project is retail-only. Ch.3's own top comment explicitly flags this cut. Matches plan; not a gap. |
| A9 | Corporate & low-default PD: Merton, shadow ratings, Pluto-Tasche | **partial** | Ch.3 (scope note only, id=0026 intro) | Same as A8 — deliberate, self-flagged scope note ("this capstone is retail-mortgage-only"). D-4 (Merton derivation) explicitly named as **not done**, deferred. Matches plan's intent to flag as a scope contrast, but D-4 remains genuinely open (see backlog below). |
| A10 | PIT vs TTC: Vasicek one-factor framework | **covered** | Ch.5 §5.1-5.8 (id=0059-0069) | Full one-factor Gaussian-copula derivation (D-5, §5.3); anchor property $E_Z[PD_{PIT}(Z)]=PD_{TTC}$ proved analytically + 2 numerical cross-checks (§5.4); interactive widget with TTC↔PIT converter and Z-recovery (§5.5); project ρ=0.0227 reconciled against textbook illustrative ρ=0.12 (§5.6-5.7); damped hybrid variant (§5.8) |
| A11 | Forward-looking scenarios: satellite (macro-link) models | NOT YET | planned Ch.6 | — |
| A12 | Multiple probability-weighted scenarios; Jensen's inequality | NOT YET | planned Ch.6 | D-6 (Jensen derivation) still not started |
| A13 | Post-model adjustments (overlays) | NOT YET | planned Ch.6 | — |
| A14 | Forecast horizon, lifetime, and the gross-up factor | **covered** | Ch.2 §2.4 (id=0019) | unchanged from batch A |
| A15 | LGD: workout definition and discounting | **covered** | Ch.4 §4.1 (id=0044) | workout LGD as $R_k$/$C_k$ discounted at original EIR, distinguished from the reporting-date rate |
| A16 | LGD distributional reality and model families | **covered** | Ch.4 §4.1, §4.3 (id=0044,0046) | bimodal cure×severity architecture, law-of-total-expectation derivation of $E[LGD]$ |
| A17 | LGD: secured/unsecured/corporate structural formula | **NOT YET** | planned Ch.4 §10.3 | **Gap.** The textbook's structural formula (indexed collateral value → forced-sale discount → time-to-repossession → loss = shortfall vs indexed collateral) has **zero** mentions in `ch04_lgd_ead.html` — grep for "indexed collateral"/"forced-sale discount"/"time-to-repossession" all return 0. Ch.4 covers the *project's* empirical two-stage cure×severity model (A16/B4) in depth but not this separate theoretical structural formula; not flagged as a cut in the chapter's own scope comment (which only names A18/D-7 and A19/D-8 as deferred — see below). |
| A18 | Net Credit Loss (NCL): loan- vs portfolio-level, discounting example | **NOT YET** | planned Ch.4 §11.1/11.3 | **Self-flagged gap.** Ch.4's own top-of-file HTML comment states verbatim: "chapters.md's original Ch.4 outline additionally lists the single-loan NCL PV(recoveries)/PV(costs) workout discounting example (compute_ecl.py section 10 / D-7) … neither is covered here; both remain open backlog items." Confirmed by grep — 0 mentions of NCL/`compute_ncl.py` keys in the chapter body. |
| A19 | 90-DPD vs 180-DPD default trigger; roll-rate bridge | **NOT YET** | planned Ch.4 §11.2/11.4 | **Self-flagged gap**, same comment as A18: "the 90-vs-180-DPD roll-rate bridge (D-8) … remain[s an] open backlog item." Confirmed by grep — 0 mentions of "roll-rate"/"180 DPD"/`compute_rollrate.py` keys. |
| A20 | EAD: term loans, revolver CCF, behavioural life | **covered** | Ch.4 §4.7-4.10 (id=0051,0054,0055) | Annuity balance $B(t)$ derived from the payment recursion (§4.7); revolver CCF EUR 14.0m worked example (§4.9); behavioural-life exception discussed (6 mentions); double-counting rule revisited from the EAD side, cross-referencing Ch.2 §2.6 (§4.10) exactly as batch A's report recommended |
| A21 | Validation: discrimination, calibration, PSI | **partial** | Ch.3 §3.8-3.10 (id=0034-0036) | **Notable finding: D-9 and D-10 were expanded in Ch.3, ahead of their planned Ch.7 slot** — see backlog section below. AUC/discrimination (§3.8) and PSI/stability (§3.9, full band-by-band KL-divergence derivation) and the binomial+Jeffreys backtest (§3.10) are all done, but scoped to the *hazard model* only. A21's full topic list also names Gini (mentioned once, as $\mathrm{Gini}=2\,\mathrm{AUC}-1$, not developed further), KS (0 mentions), and "LGD/EAD/ECL-level validation" (not covered — only PD/hazard-level). Ch.7 should cross-reference Ch.3's derivations (as Ch.3's own scope note instructs) and extend to the challenger-scorecard, Gini/KS, and LGD/EAD-level material to close this out. |
| A22 | Governance, disclosure, capital interaction, hot topics | NOT YET | planned Ch.13 | — |
| A23 | Learning path, tooling, interview drill (meta/appendix) | NOT YET | planned Ch.13 | — |
| B1 | DCR loan-quarter panel construction & waterfall | **partial** | Ch.1 (referenced); Ch.3 §3.3 now derives the eligibility waterfall in full | Upgraded substance since batch A: Ch.3 §3.3 walks the DCR eligibility waterfall (`outputs/panel/waterfall.md`, 622,489→50,000-loan panel, all 7 ordered exclusion steps with row-drop counts) as part of building the hazard-model panel — this is closer to a full B1 treatment than Ch.1's mention-only. Still recorded as **partial** because no chapter's own learning-goals section claims B1 as owned, and the topic map still has no single home for "panel construction" as its own titled topic; recommend the topic-map owner point B1's anchor at Ch.3 §3.3 explicitly, or keep the note here as the de facto home. |
| B2 | DCR EDA: default rates, hazard by age, LGD, origination quality, prepay | **partial** | Ch.3 intro references `eda_report.md` (5 hits); Ch.4 — 0 hits | Plan calls for a split: "Ch.3/Ch.4 intro (DCR EDA exhibits split across hazard and LGD framing, cross-referenced not duplicated)". Ch.3 cross-references the EDA report; Ch.4 does not reference it at all (0 mentions of `eda_report`/`vintage_cumulative_default`/`origination_quality`/`prepay_vs_rate`) — the LGD-side half of the planned split did not happen. |
| B3 | DCR hazard model (cloglog competing-risk PD engine) | **covered** | Ch.3 §3.7-3.8 (id=0033,0034) | AUC 0.748/0.661 (train/OOT), full coefficient table with hazard-ratio interpretation |
| B4 | DCR LGD model (two-stage cure x severity) | **covered** | Ch.4 §4.3 (id=0046) | cure/severity coefficients, interpretation |
| B5 | DCR EAD model | **covered** | Ch.4 §4.7,4.9 (id=0051,0054) | annuity balance + revolver CCF |
| B6 | DCR staging model & threshold sensitivity | **covered** | Ch.1 §1.7 + live widget (id=0010,0011) | unchanged from batch A |
| B7 | DCR ECL engine, gates & golden fixtures | **covered** | Ch.2 §2.3 (id=0018) | unchanged from batch A |
| B8 | Vasicek calibration on the project panel | **covered** | Ch.5 §5.6-5.7 (id=0067,0068) | ρ=0.0227 Belkin calibration, Z-recovery from observed default rates on `outputs/vasicek/z_path.csv`, credit-cycle exhibit |
| B9 | DFAST macro scenario paths & satellite fit | NOT YET | planned Ch.6 | — |
| B10 | Scenario ECL & the project's Jensen-gap exhibit | NOT YET | planned Ch.6 | — |
| B11 | Challenger scorecard: benchmarking & explainability | NOT YET | planned Ch.7 | Ch.3's D-9/D-10 derivations are directly reusable substrate here per Ch.3's own cross-reference instruction |
| C1 | SFLLD ingest & data-quality (Phase A) | NOT YET | planned Ch.11 | — |
| C2 | SFLLD EDA: vintage curves, roll-rates, state heterogeneity, COVID | NOT YET | planned Ch.11 | — |
| C3 | SFLLD hazard model (Phase B) & COVID-regime decision | **partial** | Ch.3 §3.5,3.8 (id=0031,0034) cross-reference; planned Ch.12 for the full treatment | Ch.3 uses SFLLD as a *corroboration* device throughout (seasoning-hump comparison §3.5: DCR 36mo vs SFLLD 42-48mo peak, incl. the "second peak is a crisis-vintage cohort artifact, not seasoning" honesty note; AUC comparison §3.8: SFLLD 0.854/0.685 vs DCR 0.748/0.661) — this covers 2 of C3's 5 named topics (seasoning curve, hazard AUC). The COVID-regime **decision** itself (COVID=exclude, stated in the topic map as "a review overturn") has **zero** mentions in Ch.3 — grep for "COVID" returns 0 hits. State-UER effect and calibration-by-year are also not covered here. Full C3 remains Ch.12's job; Ch.3's SFLLD mentions are a genuine but partial down payment. |
| C4 | SFLLD LGD (realized) model | **covered** | Ch.4 §4.6 (id=0050) | 44,593-loan SFLLD refit, 0.0148 excess-loss loading vs DCR's 0.0255, cycle range 0.0397 |
| C5 | SFLLD backtest: the 9.42x honesty exhibit | NOT YET | planned Ch.12 | — |
| C6 | SFLLD LSTM challenger & lift decomposition | NOT YET | planned Ch.12 | — |
| D1 | Agent layer: LangGraph router + Tier-1 tools | NOT YET | planned Ch.8 | — |
| D2 | Agent Tier-2 sandbox & Tier-3 retrieval | NOT YET | planned Ch.8 | — |
| D3 | App: FastAPI backend surface | NOT YET | planned Ch.9 | — |
| D4 | App: React UI (6 tabs) & design system | NOT YET | planned Ch.9 | — |
| D5 | Docker & deployment | NOT YET | planned Ch.10 | — |
| D6 | Model Documentation Deliverable (MDD) & governance close-out | NOT YET | planned Ch.13 | — |

## Tally

- **Covered:** A1, A2, A3, A4, A14, A7, A10, A15, A16, A20, B3, B4, B5, B6, B7, B8, C4 = **17**
  (batch A's 7 + 10 new: A7, A10, A15, A16, A20, B3, B4, B5, B8, C4)
- **Partial:** B1, A8, A9, A21, B2, C3 = **6**
  (batch A's B1 + 5 new: A8, A9, A21, B2, C3)
- **NOT YET:** A5, A6, A11, A12, A13, A17, A18, A19, A22, A23, B9, B10, B11, C1, C2, C5, C6, D1-D6 = **23**
- Total = 46 (17 + 6 + 23 = 46, reconciles to `topic_map.json` `concept_count`)

Net movement from batch A: Covered 7→17 (+10), Partial 1→6 (+5, includes 2 concepts —
A8, A9 — that were always going to land as "partial" by design, not slippage), NOT YET
38→23 (−15). Two concepts (A6, A17) are genuine unplanned gaps — assigned to Ch.3/Ch.4 by
`chapters.md` but not written and not self-flagged as cuts, unlike A18/A19 which the
chapter itself names as deferred.

## Derivation backlog status (`notes/plan/derivation_backlog.md`, 11 items)

| id | derivation | planned chapter | status |
|----|------------|------------------|--------|
| D-1 | Survival function from hazard, $S(t)=\prod_{k\le t}(1-\lambda_k)$ | Ch.2 | **done** — §2.2 (unchanged) |
| D-2 | Full 5-year ECL worked example, every year's substitution | Ch.2 | **done** — §2.3 (unchanged) |
| D-11 | Gross-up factor across the 4 horizons | Ch.2 | **done** — §2.4 (unchanged) |
| D-3 | Cloglog link from continuous-time proportional hazards | Ch.3 | **done** — full integral-to-closed-form derivation, §3.1 |
| D-5 | One-factor Gaussian copula → PD_PIT(Z) | Ch.5 | **done** — full asset-value-to-conditioning derivation + anchor-property proof, §5.3-5.4 |
| D-9 | Binomial backtest + Jeffreys | **Ch.3** (planned Ch.7) | **done, ahead of schedule** — §3.10, with an explicit scope note explaining the reassignment (see "Map gaps" below) |
| D-10 | PSI, band-by-band | **Ch.3** (planned Ch.7) | **done, ahead of schedule** — §3.9, symmetrised-KL-divergence derivation, same reassignment note |
| D-4 | Merton distance-to-default and PD | Ch.3 | **not started** — Ch.3 explicitly scopes this out (A9 treated as a scope-note aside only); Ch.3 is otherwise complete, so this is now an orphaned backlog item with no future chapter claiming it (see "Map gaps") |
| D-6 | Jensen's inequality applied to ECL | Ch.6 | not started |
| D-7 | NCL discounting, cash-flow by cash-flow | Ch.4 | **not started** — Ch.4's own top comment names this as deliberately deferred/open; Ch.4 is otherwise complete, so likewise now orphaned unless re-routed |
| D-8 | Roll-rate bridge (90→180 DPD) | Ch.4 | **not started** — same as D-7, self-flagged deferred, now orphaned |

**7/11 done** (up from 3/11 in batch A); **4/11 pending** (D-4, D-6, D-7, D-8). Of the
pending 4, only D-6 is still cleanly "gated on its future chapter" (Ch.6, not yet
written). **D-4, D-7, and D-8 are now orphaned** — their assigned chapters (Ch.3, Ch.4)
have already been written and shipped without them, and none of those chapters' own
scope notes name a replacement chapter. This needs an explicit routing decision from the
campaign owner (see next section) rather than assuming "gated, will happen later" is
still an accurate status.

## Map gaps discovered while writing/auditing Ch.3-5 (for the topic-map/campaign owner)

- **A6 (WOE/IV) is a silent gap, not a self-flagged scope cut.** Unlike A8/A9 (which Ch.3
  explicitly names as scoped out in its own top-of-file comment) and A18/A19 (which Ch.4
  explicitly names as deferred), A6 — "Ch.3 intro (scorecard lineage before hazard
  models)" per `chapters.md` §"Chapter → concept coverage check" — has zero trace in
  Ch.3: no WOE, information-value, or coarse-classing text anywhere, and no comment
  acknowledging the omission. Recommend either a short WOE/IV lineage paragraph added to
  Ch.3's intro in a follow-up pass, or an explicit scope-note match ing A8/A9's pattern if
  the omission was in fact deliberate.
- **A17 (the textbook's structural LGD formula) is a second silent gap**, same pattern as
  A6: planned for Ch.4 §10.3, present nowhere in the shipped chapter, and not named in
  Ch.4's own scope comment (which only names A18/D-7 and A19/D-8). Ch.4 covers the
  *project's* empirical two-stage model (A16/B4) thoroughly but never touches the
  indexed-collateral/forced-sale-discount/time-to-repossession structural formula the
  source notes' §10.3 present as the textbook framework. Recommend a short "structural
  LGD, textbook framework" subsection in a Ch.4 follow-up pass, since A17 is the only LGD
  sub-concept (of A15/A16/A17) still unwritten.
- **D-4, D-7, D-8 need explicit re-routing, not just "not started."** As flagged above,
  all three derivations' assigned home chapters are now fully written and shipped without
  them, self-documented as deliberate cuts in each chapter's own top comment (D-4 in
  Ch.3's comment; D-7/D-8 in Ch.4's comment) — but neither chapter names *where* the
  deferred material should land instead. Options for the campaign owner: (a) a short
  follow-up amendment to Ch.3/Ch.4 adding the missing derivation as a new subsection each
  (cleanest, keeps the derivation next to its natural narrative home); (b) formally
  re-route all three to Ch.7 (Challengers & Validation) or Ch.13 (closing synthesis) as a
  "backlog derivations" appendix, mirroring the D-9/D-10 precedent Ch.3 just set of moving
  a derivation to wherever it's actually needed first. Given Ch.3 already establishes the
  precedent (and explicitly instructs Ch.7 to build on its moved derivations rather than
  re-derive), option (a) is recommended for consistency — these are chapter-native
  derivations (Merton belongs next to the rest of Ch.3's PD material; NCL/roll-rate belong
  next to the rest of Ch.4's LGD material), not generically portable ones like D-9/D-10
  were.
- **D-9/D-10 were relocated from Ch.7 to Ch.3, with the relocation self-documented in
  Ch.3 §3.7's "Scope note — D-9 and D-10 expanded here, ahead of Chapter 7" box.** This is
  a genuine improvement over the original plan (both derivations complete the hazard
  model's own validation story, which is a more natural home than waiting for a
  general-purpose challenger-scorecard chapter) but it means `derivation_backlog.md`'s
  "planned chapter" column for D-9/D-10 is now stale — recommend the topic-map owner
  update `derivation_backlog.md` itself to read "Ch.3 (relocated from planned Ch.7)" so a
  future Ch.7 writer doesn't duplicate the derivation from scratch. Ch.3's own note already
  gives Ch.7 the correct instruction ("cross-reference this derivation … rather than
  re-derive"), so the risk is contained to the backlog *document*, not the chapters
  themselves.
- **The compendium is still 5 separate chapter files, not the single growing HTML file
  `conventions.md` mandates.** §"Layout" and §1 of `notes/plan/conventions.md` are
  explicit: "the 13-chapter compendium is a single growing HTML file
  (e.g. `notes/chapters/ifrs9_ecl_study_notes.html`) — each of the 13 planned chapters is
  one `<h2 id="sN">` section appended to that one file, in chapter-number order, never 13
  separate files." All five shipped chapters (`ch01…ch05_*.html`) are self-contained
  standalone files instead, each with its own `<h1>`/TOC/closing `<hr>` — and each one's
  own top comment explicitly acknowledges this ("Standalone deliverable for this build
  phase… per conventions.md this chapter's `<h2 id="sN">` is written so a later merge…
  is a straight splice"), i.e. every chapter author independently made the same documented
  scope call to defer the merge. This is consistent across all 5 chapters (so nothing is
  inconsistently built) and each `<h2 id="sN">` is genuinely splice-ready per the
  convention's own escape hatch, but the merge into one file has never actually happened.
  Flagging for the campaign owner: either perform the merge now (mechanical — five
  `str_replace`s stitching `<h2 id="s2">…</h2>...` blocks into one shell) before the
  compendium is considered "shipped," or amend `conventions.md` to bless the
  five-separate-files structure as the actual delivered shape. Not a blocker for this
  coverage/reindex task (which only re-diffs content, not file topology), but material to
  anyone treating the "one growing file" line in `conventions.md` as ground truth.
- **B1's Ch.3 upgrade should be reflected in the topic map.** Batch A's report flagged B1
  as under-specified (no chapter's own learning goals claim panel construction). Ch.3 §3.3
  now derives the DCR eligibility waterfall in real depth (all 7 ordered exclusion steps,
  622,489→50,000 loans, with per-step row-drop counts and reasons) as scaffolding for the
  hazard-model panel — closer to a full B1 treatment than anything in batch A. Still
  recorded "partial" here since no chapter explicitly claims ownership of B1 as a titled
  concept, but recommend the topic-map owner simply point B1's `theory_anchor` at Ch.3 §3.3
  now, rather than waiting for Ch.11.
- **B2's planned Ch.3/Ch.4 split only half-happened.** Ch.3 cross-references
  `outputs/eda/eda_report.md` in 5 places (mostly around the seasoning-hump discussion);
  Ch.4 references it in 0. If the LGD-side EDA framing (bimodality, origination quality)
  was meant to open Ch.4 per the plan, that did not happen — flag for a possible short
  intro-paragraph addition to Ch.4 in a follow-up pass, or accept Ch.3's partial coverage
  as sufficient and update the plan.

## Next-batch recommendation

**Write Ch.6 (Scenarios, Satellite Models & Jensen's Inequality) and Ch.7 (Challengers &
Validation) next**, in that order. Reasons:

1. **Direct narrative sequence.** Ch.5 ends on the Vasicek $Z$-factor and PIT/TTC
   conditioning; Ch.6 is the immediate next step (how $Z$ becomes a scenario, how
   scenarios combine under probability weights) — the two chapters share the $PD_{PIT}(Z)$
   machinery Ch.5 just derived (D-5), so Ch.6's convexity argument (D-6) can cite Ch.5's
   closed form directly instead of re-deriving it.
2. **Ch.7 is now cheaper than originally scoped**, because D-9 and D-10 — two of its four
   flagged derivations — are already done in Ch.3, with an explicit instruction there
   ("Chapter 7 should build on and cross-reference this derivation… rather than re-derive")
   for how to reuse them. Ch.7's remaining net-new derivation work is essentially none (all
   4 of A21's backlog derivations are now covered); its remaining net-new *writing* work is
   the challenger-scorecard material itself (B11: reliability diagram, permutation
   importance, PDP grid, swap-set analysis) plus the Freddie backtest's C5 honesty exhibit
   groundwork — though C5's full treatment is Ch.12's job, Ch.7 could at minimum name it.
3. **These two chapters clear the single remaining campaign-brief-flagged derivation**
   (D-6, Jensen's inequality) and close out A11, A12, A13, A21, B9, B10, B11 — 7 of the 23
   remaining NOT-YET/partial concepts in two chapters, second only to the batch-B haul.
4. **Fixture readiness confirmed**: `tests/fixtures/compute_scenarios.py` (16 keys) is the
   source of truth for Ch.6's Jensen-gap numbers; `tests/fixtures/compute_validation.py`
   (12 keys, already used once in Ch.3) is Ch.7's source of truth — both fixtures already
   exist and are gated, no new fixture-writing needed for either chapter.
5. **Before starting Ch.6/Ch.7, the campaign owner should resolve the four "Map gaps"
   above** (A6, A17 silent gaps; D-4/D-7/D-8 orphaned-derivation routing; the one-file vs
   five-file structural question) — none of them block Ch.6/Ch.7's *own* content, but
   D-4/D-7/D-8's routing decision in particular determines whether Ch.7's "backlog
   derivations" appendix (if that routing option is chosen) should be written alongside
   Ch.7 or held for Ch.13.

**Alternative if the campaign owner prefers closing the Freddie side next:** Ch.11
(Freddie Mac Panel & EDA) + Ch.12 (Freddie Models, Backtest & LSTM) would clear C1, C2, C5,
C6 (4 concepts) plus complete C3's remaining topics (COVID-regime decision, state-UER
effect, calibration-by-year) that Ch.3 only partially touched — a comparable-sized batch,
but with no derivation-backlog items to clear (Ch.11/Ch.12 have none assigned) and no
fixture dependency (`tests/test_freddie_hazard.py`/`test_freddie_lgd.py` are referenced,
not re-derived, per `chapters.md`'s own note). Ch.6/Ch.7 is still the primary
recommendation because of the derivation-backlog leverage (point 3 above).

## Ingestion notes (for the maintainer)

- Unchanged from batch A: `ingest_notes.py` must be run as
  `uv run .claude/skills/pageindex-plus/scripts/ingest_notes.py ...` (plain `uv run`);
  `build_pageindex.py`/`pageindex_query.py` run fine under `uv run --no-sync python ...`.
- **This round: `ingested 3 new/changed, 2 unchanged`** — `ch01`/`ch02` were skipped (byte
  content unchanged since batch A, manifest hash match); `ch03`/`ch04`/`ch05` were newly
  ingested. As with batch A, 0 figure cards were captured for the 3 new chapters (16
  `<img>` refs across ch03/ch04/ch05 all resolve to `../assets/img/ch0N/...`, outside the
  `notes/chapters` containment root — same deliberate `ingest_notes.py` safety refusal
  documented in batch A; captions remain fully text-indexed, only the PNG binaries/alt-text
  are outside the index).
- **The heading-split bug (documented in batch A) reappeared in all 3 new corpus files**,
  as expected since `ingest_notes.py` itself was left untouched (out of scope). Re-applied
  the same fix — merging each orphaned `#{1,6}` marker line onto its next non-blank line —
  to `ch03_hazard_modeling.html.md` (17 headings initially merged), `ch04_lgd_ead.html.md`
  (14 merged), `ch05_vasicek.html.md` (13 merged).
  **New finding this round: the merge heuristic over-fired once.** `ch03`'s raw corpus
  text contains a genuine bare `#` character at line ~520 that is *not* a heading-split
  artifact — it is the literal text of a Markdown table's first column header ("#" as in
  "row number"), from the DCR eligibility-waterfall table in §3.3. The naive "merge every
  bare `#{1,6}` line with its next non-blank line" heuristic wrongly merged this into a
  bogus `# Step` heading (17 vs the true 16 real `<hN>` tags in `ch03_hazard_modeling.html`,
  verified by `grep -oE '<h[1-6][^>]*>'` against the source chapter HTML). Detected by
  cross-checking the corpus's post-merge heading count against the source HTML's actual
  `<hN>` tag count for all 3 new chapters (ch03: 17 merged vs 16 real — caught; ch04: 14 vs
  14 — clean; ch05: 13 vs 13 — clean) and reverted the one spurious merge by hand. Confirmed
  harmless either way for `build_pageindex.py` specifically — its `HEADING_RE =
  re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")` requires at least one space and one non-whitespace
  character after the hashes, so a genuinely bare `#` alone on a line was never going to be
  picked up as a heading node regardless — but the merged `# Step` version *would* have been
  (it has both a space and following text), so the revert was necessary to avoid a
  phantom/mistitled node in the index tree. **Lesson for the next incremental ingest**: don't
  apply the heading-merge fix blindly — cross-check the post-fix bare-`#{1,6}`-line count
  against `grep -oE '<h[1-6][^>]*>' <source>.html | wc -l` for each newly-ingested file
  before building the index, the same verification step that caught this one.
  Re-running `ingest_notes.py` from scratch on any of these 5 files will reintroduce the bug
  and require re-running (and re-verifying) the merge.

## Verification performed

- `pageindex_query.py notes/index --render`: **5 sources, 222 pages, 69 nodes**, full
  heading hierarchy renders with real titles (chapter → section → sub-section → live-widget
  nodes) for all 5 chapters — no orphaned/blank-title nodes, no leftover `# Step`-style
  artifact from the merge over-fire (confirmed post-revert).
- `pageindex_query.py notes/index --search "cloglog link continuous-time hazard"`: top hit
  correctly resolves to Ch.3 §3.1 (score 39, next-closest 14).
- `pageindex_query.py notes/index --search "Vasicek conditioning PD_PIT"`: top hit resolves
  to the Ch.5 chapter root (score 10) with §5.3 (the D-5 derivation section) as the next
  most relevant sub-node (score 5).
- `pageindex_query.py notes/index --search "roll-rate bridge 90 180 DPD"`: **no section
  scores meaningfully high, and no hit lands on a dedicated roll-rate section** — this is
  expected and corroborates the A19/D-8 gap finding above (the topic genuinely isn't in the
  index because it isn't in any chapter yet).
- `notes/assets/check_notes.py notes/chapters/*.html`: **PASS on all 5 files** — tag
  balance, img resolution, MathJax delimiter parity, no leftover `{{...}}` placeholders,
  quiz answer-key completeness, and widget JS parse all green for ch01-ch05.
- Cross-checked derivation-backlog claims (D-3, D-5, D-9, D-10 "done"; D-4, D-7, D-8
  "not started") directly against each chapter's own derivation-backlog cross-reference
  comments/notes (`grep -in "backlog\|D-[0-9]"`), not just against section titles — every
  "done" status above is backed by an actual `<div class="derivation">` block with
  numbered `<span class="stepno">` steps in the chapter HTML, not merely a mention.
