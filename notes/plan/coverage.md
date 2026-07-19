# Coverage report — chapters 1-2 vs the topic map

Generated 2026-07-19, after ingesting `notes/chapters/{ch01,ch02}` into `notes/corpus/` +
`notes/index/` (PageIndex: 2 sources, 79 pages, 23 nodes — see `pageindex_query.py notes/index
--render`). This diffs `notes/plan/topic_map.json` (46 concepts, A1-A23/B1-B11/C1-C6/D1-D6)
against what chapters 1-2 actually contain, read against the index tree and the corpus text
(`notes/corpus/ch01_ifrs9_foundations_staging.html.md`, `...ch02_ecl_mechanics.html.md`).

## Method

For each concept: located its `theory_anchor.section` and cross-checked against (a) the
chapter's own "Compiled from ... §N" byline, (b) the planned mapping in
`notes/plan/chapters.md` § "Chapter → concept coverage check", (c) a direct grep of the
generated corpus text for the concept's named topics/keywords. **Covered** = the concept's
full topic list is present with derivation/worked-example depth matching the plan.
**Partial** = the concept is referenced/used as substrate but not treated as its own
topic. **NOT YET** = no chapter written yet (by plan, chapters 3-13).

## Coverage matrix

| id | title | status | chapter · anchor | note |
|----|-------|--------|-------------------|------|
| A1 | IFRS 9 standard: origins, scope, classification | **covered** | Ch.1 §1.1-1.2 (index id=0004,0005) | IAS39→IFRS9, scope, business-model test, SPPI test, simplified approach, POCI all present |
| A2 | Staging, default definition, SICR | **covered** | Ch.1 §1.4-1.6 (id=0007,0008,0009) | 3-stage model, 90-DPD/UTP default, relative SICR test (toy example expanded), backstops, low-credit-risk exemption all present |
| A3 | ECL mechanics: formula, term structure, worked example | **covered** | Ch.2 §2.1-2.3 (id=0016,0017,0018) | formula derived from cash-shortfall first principles, S(t) derived (D-1), 5-yr loan digit-by-digit (D-2) |
| A4 | IFRS 9 vs Basel IRB vs CECL | **covered** | Ch.1 §1.3 (id=0006) | folded as the planned "comparison box"; day-one CECL vs IFRS9 allowance quiz confirms depth |
| A5 | Data foundations: public datasets, macro series, scenarios, variable dictionary | NOT YET | planned Ch.11 intro | — |
| A6 | Retail scorecards: WOE, IV, logistic regression | NOT YET | planned Ch.3 intro | — |
| A7 | Lifetime PD via discrete-time survival (hazard/cloglog) | NOT YET | planned Ch.3 | cloglog derivation (D-3) not yet expanded |
| A8 | Transition matrices (Markov) for wholesale/rating books | NOT YET | planned Ch.3 (scope note) | — |
| A9 | Corporate & low-default PD: Merton, shadow ratings, Pluto-Tasche | NOT YET | planned Ch.3 sub-section | Merton derivation (D-4) not yet expanded |
| A10 | PIT vs TTC: Vasicek one-factor framework | NOT YET | planned Ch.5 | Vasicek derivation (D-5) not yet expanded |
| A11 | Forward-looking scenarios: satellite (macro-link) models | NOT YET | planned Ch.6 | — |
| A12 | Multiple probability-weighted scenarios; Jensen's inequality | NOT YET | planned Ch.6 | Jensen derivation (D-6) not yet expanded |
| A13 | Post-model adjustments (overlays) | NOT YET | planned Ch.6 | — |
| A14 | Forecast horizon, lifetime, and the gross-up factor | **covered** | Ch.2 §2.4 (id=0019) | all 4 horizons (12/36/60/84m), gross-up derivation D-11 shown |
| A15 | LGD: workout definition and discounting | NOT YET | planned Ch.4 | — |
| A16 | LGD distributional reality and model families | NOT YET | planned Ch.4 | — |
| A17 | LGD: secured/unsecured/corporate structural formula | NOT YET | planned Ch.4 | — |
| A18 | Net Credit Loss (NCL): loan- vs portfolio-level, discounting example | NOT YET | planned Ch.4 | NCL derivation (D-7) not yet expanded |
| A19 | 90-DPD vs 180-DPD default trigger; roll-rate bridge | NOT YET | planned Ch.4 | roll-rate derivation (D-8) not yet expanded |
| A20 | EAD: term loans, revolver CCF, behavioural life | NOT YET | planned Ch.4 | revolver EAD fixture keys appear only in Ch.2 §2.6 as a cross-reference, not a full EAD treatment |
| A21 | Validation: discrimination, calibration, PSI | NOT YET | planned Ch.7 | binomial/Jeffreys (D-9), PSI (D-10) not yet expanded |
| A22 | Governance, disclosure, capital interaction, hot topics | NOT YET | planned Ch.13 | — |
| A23 | Learning path, tooling, interview drill (meta/appendix) | NOT YET | planned Ch.13 | — |
| B1 | DCR loan-quarter panel construction & waterfall | **partial** | Ch.1 (referenced, id=0009,0010) | panel is the population staging is applied to and is named throughout, but panel *construction* (ingest waterfall, row-drop/data-quality gates) is not itself derived in Ch.1 — by plan this belongs to Ch.11's data-foundations intro |
| B2 | DCR EDA: default rates, hazard by age, LGD, origination quality, prepay | NOT YET | planned Ch.3/Ch.4 intro | — |
| B3 | DCR hazard model (cloglog competing-risk PD engine) | NOT YET | planned Ch.3 | — |
| B4 | DCR LGD model (two-stage cure x severity) | NOT YET | planned Ch.4 | — |
| B5 | DCR EAD model | NOT YET | planned Ch.4 | — |
| B6 | DCR staging model & threshold sensitivity | **covered** | Ch.1 §1.7 + live widget (id=0010,0011) | calm/stress stage shares, ratio_threshold sensitivity sweep, live SICR-threshold widget all present |
| B7 | DCR ECL engine, gates & golden fixtures | **covered** | Ch.2 §2.3 (id=0018) | all 11 `compute_ecl.py` RESULTS keys walked through |
| B8 | Vasicek calibration on the project panel | NOT YET | planned Ch.5 | — |
| B9 | DFAST macro scenario paths & satellite fit | NOT YET | planned Ch.6 | — |
| B10 | Scenario ECL & the project's Jensen-gap exhibit | NOT YET | planned Ch.6 | — |
| B11 | Challenger scorecard: benchmarking & explainability | NOT YET | planned Ch.7 | — |
| C1 | SFLLD ingest & data-quality (Phase A) | NOT YET | planned Ch.11 | — |
| C2 | SFLLD EDA: vintage curves, roll-rates, state heterogeneity, COVID | NOT YET | planned Ch.11 | — |
| C3 | SFLLD hazard model (Phase B) & COVID-regime decision | NOT YET | planned Ch.12 | — |
| C4 | SFLLD LGD (realized) model | NOT YET | planned Ch.12 | — |
| C5 | SFLLD backtest: the 9.42x honesty exhibit | NOT YET | planned Ch.12 | — |
| C6 | SFLLD LSTM challenger & lift decomposition | NOT YET | planned Ch.12 | — |
| D1 | Agent layer: LangGraph router + Tier-1 tools | NOT YET | planned Ch.8 | — |
| D2 | Agent Tier-2 sandbox & Tier-3 retrieval | NOT YET | planned Ch.8 | — |
| D3 | App: FastAPI backend surface | NOT YET | planned Ch.9 | — |
| D4 | App: React UI (6 tabs) & design system | NOT YET | planned Ch.9 | — |
| D5 | Docker & deployment | NOT YET | planned Ch.10 | — |
| D6 | Model Documentation Deliverable (MDD) & governance close-out | NOT YET | planned Ch.13 | — |

## Tally

- **Covered:** A1, A2, A3, A4, A14, B6, B7 = **7**
- **Partial:** B1 = **1**
- **NOT YET:** A5-A13, A15-A23, B2-B5, B8-B11, C1-C6, D1-D6 = **38**
- Total = 46 (7 + 1 + 38 = 46, reconciles to `topic_map.json` `concept_count`)

## Derivation backlog status (`notes/plan/derivation_backlog.md`, 11 items)

| id | derivation | planned chapter | status |
|----|------------|------------------|--------|
| D-1 | Survival function from hazard, $S(t)=\prod_{k\le t}(1-\lambda_k)$ | Ch.2 | **done** — full one-period-conditional-probability derivation, §2.2 |
| D-2 | Full 5-year ECL worked example, every year's substitution | Ch.2 | **done** — digit-by-digit, §2.3 |
| D-11 | Gross-up factor across the 4 horizons | Ch.2 | **done** — §2.4, all 12 `compute_grossup.py` keys across 12/36/60/84m |
| D-3 | Cloglog link from continuous-time proportional hazards | Ch.3 | not started |
| D-4 | Merton distance-to-default and PD | Ch.3 | not started |
| D-5 | One-factor Gaussian copula → PD_PIT(Z) | Ch.5 | not started |
| D-6 | Jensen's inequality applied to ECL | Ch.6 | not started |
| D-7 | NCL discounting, cash-flow by cash-flow | Ch.4 | not started |
| D-8 | Roll-rate bridge (90→180 DPD) | Ch.4 | not started |
| D-9 | Binomial backtest + Jeffreys | Ch.7 | not started |
| D-10 | PSI, band-by-band | Ch.7 | not started |

3/11 done (all three assigned to the two chapters written so far); 8/11 pending, gated on
their respective chapters.

## Next-batch recommendation

**Write Ch.3 (Hazard Modelling / PD Term Structure) and Ch.4 (LGD & EAD) next.** Reasons:

1. They are the largest concentration of untouched concepts reachable in two chapters — A6,
   A7, A8, A9, B2, B3 (Ch.3) and A15-A20, B2, B4, B5 (Ch.4) — 11 of the 38 NOT-YET concepts
   in one batch (B2 is claimed by both as a split intro, so it counts once).
2. They clear 5 of the 8 remaining derivation-backlog items in one pass: D-3, D-4 (Ch.3);
   D-7, D-8 (Ch.4) — the campaign brief flags D-3 (cloglog) explicitly as a must-expand.
3. They are direct narrative successors to Ch.2: Ch.2 ended on "given a hazard curve", Ch.3
   is "where the hazard curve comes from"; Ch.4 completes the ECL formula's other two
   factors (LGD, EAD) that Ch.2 treated as given.
4. Fixture readiness: `tests/fixtures/compute_ncl.py` (20 keys) and
   `compute_rollrate.py` (10 keys) are already the source of truth for Ch.4's LGD/NCL
   numbers; Ch.3 has no `compute_*.py` (values come from fitted-model reports per
   `chapters.md`) — flag this to the writer so it pulls `outputs/hazard/fit_stats.md`,
   `outputs/hazard/hazard_ratios.md`, and `outputs/freddie/hazard/hazard_report.md`
   instead of a golden-fixture script.

**Map gaps discovered while writing/auditing Ch.1-2** (for the topic-map owner, not
blocking Ch.3-4):

- **B1's split is under-specified.** `chapters.md` assigns B1 (DCR panel construction &
  waterfall) to Ch.1, but Ch.1's own learning goals never mention the panel build — it only
  *consumes* the panel. The panel-construction waterfall (ingest report, row-drop gates)
  has no natural home in the current 13-chapter plan; Ch.11's "data-foundations intro"
  (currently reserved for A5, the Freddie/SFLLD side) is the closest fit but that chapter
  is titled "Freddie Mac Panel & EDA" — recommend explicitly widening Ch.11's intro to cover
  *both* panels' construction (DCR B1 + SFLLD C1) side by side, or add a short "the DCR
  panel, in one paragraph" callout box to Ch.1 itself so B1 graduates from partial to
  covered without waiting for Ch.11.
- **A20 (EAD) has a partial forward-reference already in Ch.2.** §2.6 ("The double-counting
  rule: EAD vs. survival") uses `revolver_ead_eur_m` / `revolver_ead_over_drawn` from
  `compute_ecl.py` as a worked example of the EAD/survival interaction, ahead of A20's own
  chapter (Ch.4). This is intentional scope (Ch.2 needed *a* concrete EAD number to make the
  double-counting point) and not double work — flag it to the Ch.4 writer so the CCF/EAD
  chapter cross-references §2.6 rather than re-deriving revolver EAD from scratch.
- **No topic-map concept currently owns "panel-to-population" framing for staging.** A2
  defines SICR/staging in the abstract; B1/B6 apply it to the DCR panel. Both are covered in
  Ch.1, but the topic map has no single id for "how the abstract test becomes a per-loan
  quarterly rule" (the §1.6 material) — it is implicitly split across A2 and B6. Not a
  blocker, just noted in case a future audit expects a dedicated concept id for it.

## Ingestion notes (for the maintainer)

- `ingest_notes.py` has an inline PEP 723 dependency block (`beautifulsoup4`, `lxml`, ...)
  and must be run as `uv run .claude/skills/pageindex-plus/scripts/ingest_notes.py ...`
  (plain `uv run`, not `--no-sync`) so uv resolves its own ephemeral tool environment —
  the project venv has no `bs4`. `build_pageindex.py` and `pageindex_query.py` are pure
  stdlib and run fine under `uv run --no-sync python ...`.
- **Heading-split workaround applied.** `ingest_notes.py`'s `from_html()` inserts the ATX
  marker (`"\n#### "`) as a sibling text node immediately before each `<hN>` tag, then joins
  all text nodes with `get_text("\n")`. Because the join separator lands *between* the
  marker node and the heading's own text node, every heading was extracted as an orphaned
  `"####"` line followed by its title on the next line — `build_pageindex.py`'s ATX-heading
  regex then saw title-less headings and the real titles fell through as plain paragraph
  text, so the first index build had blank section names throughout the tree. Fixed by
  merging each orphaned `#{1,6}` marker line back onto its next line, in place, in the two
  corpus `.md` files only (21 headings across both files); the shared skill script itself
  was left untouched since it is out of this task's scope. Re-running `ingest_notes.py`
  from scratch will reintroduce the bug and require re-running the merge.
- **0 figure cards captured.** `notes/chapters/*.html` reference their exhibit PNGs via
  external relative paths (`../assets/img/ch0N/...`, 5 per chapter, 10 total) that point
  outside the ingested tree (`notes/chapters`); `ingest_notes.py` refuses to copy `<img>`
  assets that resolve outside its `notes_dir` containment root (a deliberate safety check),
  so no figure-card nodes exist in the index and `<img alt="...">` text is not indexed
  (BeautifulSoup's `get_text()` does not surface `alt` attributes). The exhibit *captions*
  (e.g. "Exhibit 1.2 — The general (three-stage) model...") are ordinary body text next to
  each image and remain fully text-indexed and keyword-searchable; only the PNG binaries
  and alt-text are outside the index. This is a corpus-boundary side effect of the exact
  `ingest_notes.py notes/chapters notes/corpus` invocation specified for this task (which
  deliberately excludes `notes/assets/`), not a chapter-authoring defect.

## Verification performed

- `pageindex_query.py notes/index --render`: 2 sources, 79 pages, 23 nodes, full heading
  hierarchy renders with real titles (chapter → section → sub-section → live-widget nodes).
- `pageindex_query.py notes/index --search "gross-up factor"`: top hit correctly resolves to
  Ch.2 §2.4.
- `notes/assets/check_notes.py notes/chapters/*.html`: **PASS** on both files — tag balance,
  img resolution, MathJax delimiter parity, no leftover `{{...}}` placeholders, quiz
  answer-key completeness, and widget JS parse all green.
