# Chapter plan — IFRS9 ECL study-notes compendium

13 chapters. Each entry: learning goals, source anchors (concept ids from `topic_map.json`/`topic_map.md`),
fixture walkthroughs to include, derivations to EXPAND (flagged where the source notes leave a step
compressed or asserted-not-derived), planned interactive widgets, planned diagrams. Build order follows
this numbering; each chapter is a `<h2>` section appended incrementally to the single growing HTML file
per `html_notes_build.md`.

Cross-reference key: concept ids are `A#` (IFRS9 theory), `B#` (DCR pipeline), `C#` (Freddie SFLLD),
`D#` (agent/app/docker). Full detail for every id is in `notes/plan/topic_map.md`.

---

## Ch.1 — IFRS 9 Foundations & Staging

**Learning goals.** State why IFRS 9 replaced IAS 39 (incurred → expected loss); apply the business-model
and SPPI tests to classify a financial asset; define default per the 90-DPD/UTP backstop; run the SICR
relative test and place a loan in Stage 1/2/3; recognise the simplified approach and POCI carve-outs.

**Source anchors.** A1 (scope/classification, s1), A2 (staging/SICR/default, s2), B1 (DCR panel — the
population this staging logic is later applied to), B6 (DCR staging model results).

**Fixture walkthroughs.** None native to this chapter (A1/A2 have no compute_*.py) — instead walk the
`outputs/staging/staging_report.md` numbers (Stage 2 share 0% calm / 75.8% stress) as the worked
illustration of the SICR test in action.

**Derivations to EXPAND.** None flagged (definitional chapter) — but the SICR test's "lifetime PD at
origination vs lifetime PD now" comparison should be shown with an explicit toy numeric pair (two lifetime
PD curves, one shifted) since the source notes state the rule without a worked number.

**Planned interactive widgets.** Staging-threshold slider → live stage-share bar chart (drives off the
`stage2_sensitivity.png` data, recomputed from `outputs/staging/staging_report.md` figures — this is the
widget named explicitly in the campaign brief).

**Planned diagrams.** Flowchart (matplotlib box-arrow): asset → business-model test → SPPI test →
classification (amortised cost / FVOCI / FVTPL) → staging state machine (Stage 1 ⇄ Stage 2 → Stage 3,
with backstops and cure paths annotated). Embed/regenerate Fig. 1 (three-stage model) — regenerate if
the underlying stage-horizon logic is recoverable, else embed `knowledge/corpus/img/..._fig001.png`.

---

## Ch.2 — ECL Mechanics

**Learning goals.** Derive the ECL formula from first principles (hazard → survival → discounted expected
loss); distinguish 12-month vs lifetime ECL; work the full 5-year amortising-loan example end to end;
understand the movement/waterfall decomposition used for period-over-period ECL analysis.

**Source anchors.** A3 (formula + worked example, s3), A14 (gross-up factor, s9.4 — placed here since it
completes the horizon story), B7 (DCR ECL engine, gates, golden fixtures roll-up).

**Fixture walkthroughs.** `compute_ecl.py` — all 11 RESULTS keys (ecl_12m_eur, ecl_lifetime_eur,
lifetime_over_12m_ratio, cumulative_pd_5y_pct, workout_pv_recoveries_eur, workout_pv_costs_eur,
workout_recovery_rate_pct, workout_lgd_pct, workout_lgd_undiscounted_pct, revolver_ead_eur_m,
revolver_ead_over_drawn); `compute_grossup.py` — all 12 keys across the 4 horizons (12/36/60/84m).

**Derivations to EXPAND.** The ECL decomposition THEOREM box (§3) states
$ECL=\sum_t DF(t)\cdot S(t-1)\cdot\lambda_t\cdot LGD_t\cdot EAD_t$ without deriving $S(t)=\prod_{k\le
t}(1-\lambda_k)$ from first principles — show the survival-product derivation and then walk every year's
substitution in the 5-year loan example with intermediate values (not just the final EUR figures).

**Planned interactive widgets.** ECL vs LGD/EIR sliders (named in the campaign brief) — number inputs for
LGD and EIR redriving a live-recomputed year-by-year ECL table and a stacked bar of 12m vs lifetime ECL.

**Planned diagrams.** Regenerated waterfall chart (from `outputs/ecl/ecl_waterfall.png` data, redrawn
themed); a hazard→survival→PV pipeline flowchart (box-arrow, matplotlib) showing the four-stage
computation explicitly.

---

## Ch.3 — Hazard Modelling (PD Term Structure)

**Learning goals.** Build a discrete-time survival/hazard PD model on a loan-month panel; understand why
cloglog (not logit) is the theoretically correct link for grouped continuous-time hazards; read hazard
ratios and AUC/discrimination diagnostics; recognise the seasoning hump.

**Source anchors.** A7 (discrete-time hazard, s6.2), A8 (transition matrices — scope note, no project
fixture), B3 (DCR hazard model), C3 (Freddie SFLLD hazard model + COVID-regime decision).

**Fixture walkthroughs.** No `compute_*.py` for hazard directly (values come from fitted-model reports) —
walkthrough is instead over `outputs/hazard/fit_stats.md` + `outputs/hazard/hazard_ratios.md` (DCR,
AUC 0.748/0.661) and `outputs/freddie/hazard/hazard_report.md` (SFLLD, AUC 0.854/0.685).

**Derivations to EXPAND.** **Flagged in the campaign brief explicitly:** the cloglog link function is
asserted in §6.2 without derivation. Expand: start from the continuous-time hazard $h(t)$ and the
proportional-hazards assumption $h(t\mid x)=h_0(t)\exp(x'\beta)$; integrate over a discrete interval to
get $P(T\ge t+1\mid T\ge t,x)=\exp\!\big(-\!\int_t^{t+1} h_0(u)\exp(x'\beta)\,du\big)$; show this collapses
to $\lambda(t\mid x)=1-\exp(-\exp(\alpha_t+x'\beta))$, i.e. the cloglog form, under a piecewise-constant
baseline — the algebra from the integral to the closed form must be shown step by step.

**Planned interactive widgets.** None primary here (Vasicek chapter carries the main slider workload) —
optional: age-baseline hazard curve with a toggleable macro-shift overlay.

**Planned diagrams.** Regenerate `age_baseline.png`/`pd_term_structure.png`/`seasoning_curve.png` themed;
COVID-regime calibration comparison (regenerate from `covid_calibration_comparison.png` data if
recoverable, else embed).

---

## Ch.4 — LGD & EAD

**Learning goals.** Distinguish workout LGD from realised/NCL loss measures; understand the bimodal LGD
distribution and why a single Gaussian regression fails; work the mortgage structural LGD formula
(indexed collateral, forced-sale discount, time-to-repossession); build EAD for term loans (amortisation +
prepayment) and revolvers (CCF); apply the behavioural-life exception for revolving facilities.

**Source anchors.** A15/A16/A17 (LGD theory, s10.1–10.3), A18 (NCL discounting worked example, s11.1/11.3),
A19 (90/180 DPD roll-rate bridge, s11.2/11.4), A20 (EAD term loans/CCF/behavioural life, s12), B4/B5 (DCR
LGD/EAD models), C4 (Freddie realised LGD).

**Fixture walkthroughs.** `compute_ncl.py` — all 20 keys (per-cashflow discount factors and PVs, face vs
discounted severity, nominal vs discounted NCL); `compute_rollrate.py` — all 10 keys (eventual roll-forward
per bucket, roll-through rate R, PD_90/LGD_90/EL comparisons); `compute_ecl.py` revolver keys
(revolver_ead_eur_m, revolver_ead_over_drawn) reused here for the CCF worked example.

**Derivations to EXPAND.** NCL discounting: show each of the 5 cash flows' $DF(m)=(1+EIR)^{-m/12}$ and PV
individually before summing to `pv_recoveries_eur`/`pv_expenses_eur` (currently a compressed table in the
source). Roll-rate bridge: derive $q_b=\text{fwd}/(\text{fwd}+\text{cure})$ per bucket from the
transition-matrix logic, then $R=q_{90}q_{120}q_{150}$, then the EL_90/EL_180 rescaling — every
multiplication shown, not just the final 0.60.

**Planned interactive widgets.** ECL vs LGD/EIR slider (shared build with Ch.2, LGD half); optional CCF
slider showing EAD response for a revolver as headroom utilisation varies.

**Planned diagrams.** Bimodal LGD histogram (regenerate from `lgd_realised_bimodal.png`/`lgd_distribution.png`
data); mortgage structural-LGD flowchart (collateral value → forced-sale discount → net proceeds → loss);
90-vs-180-DPD timeline diagram (regenerate Fig. 9 concept, box-arrow).

---

## Ch.5 — The Vasicek One-Factor Model (PIT vs TTC)

**Learning goals.** Explain the TTC/PIT philosophical distinction; derive the one-factor Gaussian copula
default-threshold model from an asset-value latent-factor representation; derive the PD_PIT(Z)
conditioning formula; verify the law-of-total-probability identity $E_Z[PD_{PIT}(Z)]=PD_{TTC}$ both by
Gauss–Hermite quadrature and fine-grid integration; interpret ρ (asset correlation).

**Source anchors.** A10 (s8, Fig. 5), B8 (project calibration, ρ=0.0227 vs textbook illustrative ρ=0.12).

**Fixture walkthroughs.** `compute_vasicek.py` — all 9 keys (default_threshold_ppf_002,
pd_pit_pct_z_plus_2_0 … z_minus_2_5, expected_pd_pit_gauss_hermite, expected_pd_pit_fine_grid).

**Derivations to EXPAND. Flagged in the campaign brief explicitly.** Full one-factor Gaussian-copula
derivation: start from asset value $A_i=\sqrt{\rho}\,Z+\sqrt{1-\rho}\,\varepsilon_i$ with $Z,\varepsilon_i
\sim N(0,1)$ independent; default when $A_i<\Phi^{-1}(PD_{TTC})$; condition on $Z$ to get
$P(A_i<\Phi^{-1}(PD_{TTC})\mid Z)=\Phi\!\Big(\frac{\Phi^{-1}(PD_{TTC})-\sqrt{\rho}Z}{\sqrt{1-\rho}}\Big)$ —
show every algebraic step (standardising the residual, why the substitution is valid). Then prove
$E_Z[PD_{PIT}(Z)]=PD_{TTC}$ analytically (tower property / definition of the unconditional default event)
before cross-checking it numerically against the two fixture integration methods.

**Planned interactive widgets.** **Named explicitly in the campaign brief.** PD_PIT vs Z and ρ: two
sliders (Z ∈ [-3,3], ρ ∈ [0.01,0.30]) driving a live-recomputed SVG/canvas curve of $PD_{PIT}(Z)$ plus a
readout table at marked Z points, reproducing the fixture's 6-point table live.

**Planned diagrams.** Regenerate the credit-cycle exhibit (`credit_cycle.png`/Fig. 5) themed; a
"Z-to-default" conceptual diagram (bell curve with the conditional threshold shaded).

---

## Ch.6 — Scenarios, Satellite Models & Jensen's Inequality

**Learning goals.** Build a satellite (macro-link) regression for a credit index; understand why IFRS 9
requires multiple probability-weighted scenarios rather than a single base case; prove and apply Jensen's
inequality to show single-scenario ECL understates probability-weighted ECL; place the reasonable-and-
supportable window against the full lifetime horizon; discuss overlay governance.

**Source anchors.** A11 (satellite models, s9.1), A12 (Jensen's inequality, s9.2, Fig. 6), A13 (overlays,
s9.3), B9 (DFAST paths + satellite fit), B10 (project's 1.035× Jensen-gap exhibit).

**Fixture walkthroughs.** `compute_scenarios.py` — all 16 keys (per-scenario Z/PD_PIT/ECL for
upside/base/downside, weighted_pd_pct, weighted_ecl_eurm, avg_gdp_growth_pct, avg_path_pd_pct,
avg_path_ecl_eurm, understatement_pct, weighted_over_single_ratio).

**Derivations to EXPAND. Flagged in the campaign brief explicitly.** Full proof of Jensen's inequality for
a convex function ($f(\lambda x+(1-\lambda)y)\le\lambda f(x)+(1-\lambda)f(y)$ generalised to
$E[f(X)]\ge f(E[X])$ via the supporting-line/tangent-line argument), then show PD_PIT(Z) is convex in Z for
Z below the inflection point (second-derivative sign check on the Φ conditioning formula from Ch.5), and
finally chain the convexity through to ECL's convexity in the macro state — reproducing the
understatement_pct/weighted_over_single_ratio numbers as the concrete instance of the general proof.

**Planned interactive widgets. Named explicitly in the campaign brief** (as the 3-scenario weight
example): weight sliders (w_up, w_base, w_down, constrained to sum to 1) driving a live-recomputed
weighted-ECL vs single-average-path-ECL bar pair, exposing the Jensen gap numerically as weights move.

**Planned diagrams.** Regenerate `jensen_gap.png` (convex ECL(Z) curve with chord vs curve shaded to show
the gap), `z_paths.png` (three scenario Z-paths over the horizon), satellite fit scatter+line.

---

## Ch.7 — Challengers & Validation

**Learning goals.** Apply the three validation pillars (discrimination, calibration, stability); run and
interpret a binomial backtest and its Jeffreys alternative; compute PSI band-by-band and interpret the
stability threshold; read a challenger scorecard's reliability diagram, permutation importance, and
partial-dependence plots; use swap-set analysis to compare staging outcomes across models.

**Source anchors.** A21 (validation theory, s13), B11 (DCR challenger scorecard), C5 (Freddie backtest —
the 9.42× honesty exhibit), C6 (Freddie LSTM challenger + lift decomposition).

**Fixture walkthroughs.** `compute_validation.py` — all 12 keys (binomial_backtest_p_value,
binomial_rejects_at_5pct, binomial_critical_count, jeffreys_p_value, jeffreys_rejects_at_5pct,
psi_term_band1…band5, psi_total, psi_is_stable).

**Derivations to EXPAND.** Binomial exact test: derive the one-sided p-value
$p=P(D\ge d\mid n,PD)=1-F_{\text{Binom}(n,PD)}(d-1)$ and the critical count from the inverse CDF, applied
to n=1000, PD=2%, d=28. Jeffreys interval: derive the Beta(d+½, n−d+½) posterior from the Jeffreys prior
Beta(½,½) and a Binomial likelihood, then the one-sided posterior tail test. PSI: derive
$PSI=\sum_i(\text{Actual}_i-\text{Expected}_i)\ln(\text{Actual}_i/\text{Expected}_i)$ from its
KL-divergence-style motivation and show all 5 band terms individually before summing to psi_total.

**Planned interactive widgets.** Optional: PSI band-share sliders (5 bins) with live-recomputed PSI total
and stability-flag readout — natural extension of the fixture's fixed example.

**Planned diagrams.** Regenerate reliability diagram, PSI-over-time, permutation importance bar, PDP grid
(from `outputs/challenger/*.png` data); Freddie backtest walk (predicted-vs-realized panel across the 5
snapshot dates, highlighting the 200912 GFC-vintage spike).

---

## Ch.8 — The Agent (LangGraph Copilot)

**Learning goals.** Understand the agent's routing logic (docs / analyze / reasoned / refusal); read the
four deterministic Tier-1 tools (shock_macro, reweight_scenarios, rerun_ecl, decompose_waterfall) as a
coherent-shock re-run pipeline; understand the number-guarded narration guardrail (LLM prose may only cite
numbers the tool actually returned); understand the Tier-2 sandbox's restricted-AST security model and
Tier-3's wiki/index Graph-RAG retrieval; walk the REASONED route's labeled-interpretation convention for
conceptual questions.

**Source anchors.** D1 (LangGraph router + Tier-1), D2 (Tier-2 sandbox + Tier-3 retrieval).

**Fixture walkthroughs.** None numeric (this is architecture, not a worked example) — instead walk one
recorded trace from `outputs/agent_log/agent_runs.jsonl` or `outputs/demo/*.json` end to end: question →
route decision → tool call → narration, annotating each hop against the `agent/graph.py` functions
(`_route`, `_run_agent`, `narration_numbers_ok`, `_allowed_numbers`).

**Derivations to EXPAND.** None (systems chapter, not a mathematical one) — but the number-guardrail logic
(`_number_tokens`, `_spelled_number_violation`, `_allowed_numbers`, `narration_numbers_ok` in
`agent/graph.py`) should be walked as pseudocode with a worked pass/fail example (one narration that would
be rejected, one that passes).

**Planned interactive widgets.** None (code-reading chapter) — a static sequence diagram substitutes.

**Planned diagrams.** Flowchart (box-arrow): question → `_route` → {docs | analyze | reasoned | refusal}
→ tool node → narrator node → number-guard check → response. Tier-2 sandbox hardening diagram
(restricted globals → AST validation → child-process isolation → resource caps).

---

## Ch.9 — The App: A Guidebook

**BINDING SCOPE OVERRIDE.** `notes/plan/requirement_11_app_guide.md` (user-mandated, pre-existing in
`notes/plan/` at planning time) supersedes the lighter "tour" framing below wherever the two conflict.
This chapter is NOT a tour — it is a complete, mechanically-derived reference: every tab, every panel,
every image, provably exhaustive (author derives the checklist from the code; reviewer re-derives the
same checklist and diffs it against the written chapter). The coverage checklist:

1. **Tabs** — enumerate from the `TABS` array in `app/ui/src/app.jsx` (6: Executive Overview, The Model,
   Scenario Lab, Policy, Real Data, Copilot).
2. **Panels per tab** — grep `Panel`/`PanelHeading`/`<h2>`/EXHIBIT kickers in each
   `app/ui/src/tabs/*.jsx` plus shared components (WaterfallChart, CreditCycleChart, StatTile rows,
   SearchableTable, WeightsBarChart, StageGuide, AgentTrace, ChatPanel, MiniChatDock, SelectionExplain,
   ExplainButton/ExplainStrip) — locate and enumerate these components under `app/ui/src/` before writing.
3. **Images/exhibits** — enumerate via `/api/exhibits/list`, `/api/freddie/exhibits`, plus any static PNGs
   referenced directly by the UI, plus the MDD link in the header.

Per tab/panel/image, document ALL of: what it shows (exact data source = endpoint + contract field +
`outputs/*` file behind it, and the meaning of every number/axis/color); how to read it (plain-language
interpretation + one concrete example using real live values); how to use it (every control — sliders,
dropdowns, buttons, text inputs — what changes and what does NOT change, e.g. the recorded user confusion
between scenario controls and the historical waterfall); AI affordances (✨ explain-icon behavior,
selection-explain chip, chat-dock status states GROUNDED/REASONED/THINKING/OUT OF SCOPE and what each
implies about trustworthiness); a screenshot/rendered image of the panel (captured live or local-run,
image-QA'd like every other figure); and panel-specific Gotchas (empty states, API-offline behavior,
refusal cases).

**Learning goals.** Navigate the FastAPI endpoint surface and its response contracts; walk every tab and
every panel to mechanically-verified completeness per the checklist above; see how the 3 explored design
directions (fintech/editorial/terminal) were judged down to the shipped `FINAL_SPEC.md`; complete a
60-second orientation quick-start through the app.

**Source anchors.** D3 (FastAPI backend, 24 endpoints, `docs/api_contract.md`), D4 (React UI, 6 tabs,
design system), `notes/plan/requirement_11_app_guide.md` (binding scope).

**Fixture walkthroughs.** None (product-documentation chapter) — instead (a) the full endpoint→panel
wiring table (which API call feeds which panel, with exact contract field names — required by
requirement_11) built from `docs/api_contract.md` + the `@app.get/@app.post` sweep of `app/api/main.py`;
(b) the per-panel documentation blocks above, each citing its live values.

**Derivations to EXPAND.** None.

**Planned interactive widgets.** A live endpoint-picker table (client-side filter/search over the 24-row
endpoint table).

**Planned diagrams.** Tab-to-endpoint dependency diagram (6 tabs → which of the 24 endpoints each calls,
matching the wiring table); before/after design-direction comparison strip (embed representative
screenshots/specs if available, else a structured comparison table from the 3 `rationale.md` files);
Docker/deployment linkage diagram (which image layers in `Dockerfile` serve which static assets consumed
by this chapter's panels — bridges to Ch.10).

**Also required (requirement_11).** A closing "where would you look to answer X" quiz bank, one question
per major panel, cross-referenced to its documentation block.

---

## Ch.10 — Docker & Deployment Guidebook

**Learning goals.** Read the multi-stage Dockerfile (node UI build → python runtime); understand the
non-root `appuser` security posture; understand why an explicit `COPY` allowlist beat a broad-copy +
`.dockerignore`-exclude strategy; trace the HF Spaces port-7860 deployment convention.

**Source anchors.** D5 (Docker & deployment).

**Fixture walkthroughs.** None — instead a stage-by-stage read of `Dockerfile` (33–135) annotated against
`outputs/gate/mdd_freddie_gate.md`'s dockerignore-lesson narrative and the relevant git log entries.

**Derivations to EXPAND.** None (infra chapter).

**Planned interactive widgets.** None planned (static reference chapter) — a collapsible stage-by-stage
Dockerfile walkthrough (plain HTML `<details>`, no JS needed) substitutes.

**Planned diagrams.** Multi-stage build flowchart (box-arrow): `node:22-alpine` build stage → artifact
copy → `python:3.13-slim` runtime stage → explicit COPY allowlist (engine/agent/app/analysis/wiki/
knowledge/skills/data/outputs subsets) → non-root user → EXPOSE 7860 → CMD uvicorn.

---

## Ch.11 — Freddie Mac Panel & EDA

**Learning goals.** Understand the SFLLD ingest pipeline (837k loans, 17 vintages, D90 absorbing state, 54
-state macro merge); read the 5 EDA exhibits (vintage curves, roll-rate matrices, calendar-time series,
state heterogeneity, realized LGD) and the COVID-regime framing that motivates the Phase-B modelling
decisions.

**Source anchors.** C1 (ingest & DQ, Phase A), C2 (EDA exhibits).

**Fixture walkthroughs.** None numeric-fixture-based — walk `outputs/freddie/ingest/dq_report.md` and
`outputs/freddie/eda/eda_report.md` as the worked "real data" counterpart to the DCR synthetic panel
(Ch.1–2's B1/B2), explicitly contrasting scale (837k vs 621,736 rows) and provenance (real dates/states/
losses vs synthetic).

**Derivations to EXPAND.** None (data-engineering chapter).

**Planned interactive widgets.** None planned — the 5 static exhibits carry this chapter.

**Planned diagrams.** Regenerate/embed the 5 EDA exhibits + 2 state-macro maps/series
(`state_hpi_growth_2000_2025.png`, `state_uer_2000_2025.png`); ingest-pipeline flowchart (raw quarterly
origination + monthly performance files → merge → D90 absorbing-state panel → macro merge on state ×
month).

---

## Ch.12 — Freddie Models, Backtest & LSTM

**Learning goals.** Read the Phase-B hazard model (AUC 0.854/0.685) and the COVID=exclude decision as a
case study in macro-regime modelling judgment; read the realized-LGD model; work through the 9.42×
backtest exhibit as an honesty check on model performance across a crisis vintage; understand the LSTM
challenger's lift decomposition over the cloglog baseline.

**Source anchors.** C3 (hazard + COVID decision), C4 (realized LGD), C5 (backtest, 9.42× exhibit), C6
(LSTM challenger).

**Fixture walkthroughs.** None via `tests/fixtures/compute_*.py` (Freddie has its own
`tests/test_freddie_hazard.py` / `tests/test_freddie_lgd.py`, referenced but not re-derived here since
they test fitted-model code, not closed-form worked examples) — walk `outputs/freddie/hazard/
hazard_report.md`, `outputs/freddie/lgd/lgd_report.md`, `outputs/freddie/backtest/backtest_report.md`,
`outputs/freddie/lstm/lstm_report.md` numbers directly, citing the report as source.

**Derivations to EXPAND.** The backtest ratio definition (predicted/realized, or its inverse — confirm
sign convention from `backtest_report.md` before writing) should be spelled out with the 200912 snapshot's
actual predicted and realized figures substituted explicitly to produce 9.42×, not stated as a bare
multiplier.

**Planned interactive widgets.** None planned (empirical-results chapter).

**Planned diagrams.** Regenerate the 4 hazard exhibits, 1 LGD exhibit, 5 backtest panels, 2 LSTM exhibits;
a lift-decomposition waterfall (LSTM lift split into components, from `lift_split.png` data if
recoverable).

---

## Ch.13 — Governance, MDD & Closing Synthesis

**Learning goals.** Connect the disclosure/governance theory (BCBS d350, IFRS 7 reconciliation tables, CRR
Art. 473a transitional arrangements, overlay discipline, climate-risk hot topic) to the project's own
Model Documentation Deliverable as a worked instance; close the compendium with the interview-drill
question bank and a full concept-to-source index for revision.

**Source anchors.** A22 (governance/disclosure/capital/hot topics, s14), A23 (learning path/tooling/
interview drill, s15 — folded in as the closing appendix), D6 (MDD walkthrough), B7 (golden-fixtures/gate
roll-up — referenced again here as the project's own governance evidence trail).

**Fixture walkthroughs.** None new — this chapter is a synthesis; it may re-cite headline numbers from
earlier fixtures (e.g. ECL gate 187/187, 133/133 golden values, Freddie gate 659/659) as the project's
demonstrated audit trail, always sourced back to their originating chapter, never re-derived.

**Derivations to EXPAND.** None (narrative/governance chapter).

**Planned interactive widgets.** None planned.

**Planned diagrams.** IFRS 7 disclosure-reconciliation table template (styled table, not a chart);
project timeline/gate-history diagram (box-arrow: Phase −1 bootstrap → Day-3 gate → Day-4 gate → App v2
gate → Freddie Phase-A gate → Freddie Phase-B gate → UI v3 gate → MDD/Freddie gate) reproduced from the
`outputs/gate/*.md` sweep and `wiki/memory/log.md`.

---

## Chapter → concept coverage check

Every concept id in `topic_map.json` is claimed by at least one chapter above:

- A1–A23 → Ch.1 (A1,A2), Ch.2 (A3,A14), Ch.3 (A7,A8), Ch.4 (A15–A20), Ch.5 (A10), Ch.6 (A11,A12,A13),
  Ch.7 (A21), Ch.13 (A22,A23). A4 (IFRS9 vs Basel vs CECL), A5 (data foundations), A6 (WOE/IV), A9
  (Merton/Pluto-Tasche) are folded as sub-sections: A4 → Ch.1 comparison box; A5 → Ch.11 intro
  (data-foundations framing before the Freddie-specific build); A6 → Ch.3 intro (scorecard lineage before
  hazard models); A9 → Ch.3 sub-section (corporate/LDP PD alongside retail hazard, flagged as a scope
  contrast since the project itself is retail-mortgage-only).
- B1–B11 → Ch.1 (B1,B6), Ch.2 (B7), Ch.3 (B3), Ch.4 (B4,B5), Ch.5 (B8), Ch.6 (B9,B10), Ch.7 (B11); B2 →
  Ch.3/Ch.4 intro (DCR EDA exhibits split across hazard and LGD framing, cross-referenced not duplicated).
- C1–C6 → Ch.11 (C1,C2), Ch.12 (C3,C4,C5,C6).
- D1–D6 → Ch.8 (D1,D2), Ch.9 (D3,D4), Ch.10 (D5), Ch.13 (D6).

No concept id is orphaned; total 46 concepts distributed across 13 chapters.
