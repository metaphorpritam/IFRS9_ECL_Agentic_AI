# ch13_governance_mdd.html

Ch.13 — Governance, MDD & Closing Synthesis | IFRS9 ECL Study Notes

☼

# 
Chapter 13 — Governance, MDD & Closing Synthesis

How this project proves its own numbers: the frozen-engine gate, the wiki-as-MDD process,
the brutal limitations register, and the reviews that changed the shipped answer — plus two orphaned
derivations (WOE/IV, structural LGD) and the closing interview drill

IFRS9 ECL Study-Notes Compendium — Chapter 13 of 13 (closing chapter). Compiled from

outputs/gate/*.md
, 
outputs/freddie/gate_phase{A,B}.md
, 
outputs/mdd/MDD.md
,

wiki/memory/log.md
, 
wiki/memory/decisions.md
, 
wiki/.wiki/audit.json
,

wiki/pages/project-overview.md
, 
knowledge/sources/ifrs9_credit_risk_notes.md

§6.1/9.3/10.3/14/15, and 
tests/fixtures/compute_pd.py
 (read/recomputed live this session) on
2026-07-19.

Contents.

13.1 The frozen-engine gate pattern: fixtures → freeze → tripwire → gate timeline

13.2 Champion/challenger governance recap

13.3 Retail scorecards: Weight of Evidence and Information Value

13.4 LGD structural formula: secured, unsecured, corporate

13.5 The wiki-as-MDD process: compile-don't-retrieve, audit, staleness

13.6 The MDD deliverable: a structural walkthrough

13.7 The validation battery, recapped, and the ALFRED honest backtest

13.8 Post-model adjustments: the overlay governance battleground

13.9 The limitations register, organized as a validator would

13.10 Agent governance as a model-adjacent control

13.11 Independent review as governance evidence: four case studies

13.12 Regulatory & ethics context: BCBS d350, IFRS 7, CRR, hot topics

13.13 Closing appendix: learning path, interview drill, concept index

## 
13  Governance, MDD & Closing Synthesis

Chapters 1–12 built and validated a full IFRS 9 ECL stack twice over — once on the
synthetic DCR panel, once on real Freddie Mac SFLLD data — and audited every model against the standard's
own validation and disclosure expectations along the way. This closing chapter turns the lens on the project

itself
: how a codebase this size stays trustworthy without a human standing over every commit. The
mechanism is not a single control but four that compound — a frozen engine behind a fingerprint tripwire
(§13.1), an independent adversarial review on every material change (§13.11), an append-only decision
register that survives context loss (§13.5), and a compiled Model Documentation Document that cites its
sources rather than re-deriving them (§13.6). Two concepts flagged in 
notes/plan/coverage.md
 as
orphaned by every earlier chapter get their full textbook treatment here — retail scorecard Weight of
Evidence/Information Value (§13.3) and the mortgage structural LGD formula (§13.4) — alongside the
governance/disclosure theory (§13.5–13.12) and the closing interview drill and concept index
(§13.13) that were always planned for this chapter. Source anchors:

knowledge/sources/ifrs9_credit_risk_notes.md
 §6.1, §9.3, §10.3, §14
(↩14.1–14.4), §15; 
outputs/mdd/MDD.md
; 
outputs/gate/*.md
;

wiki/memory/{log,decisions}.md
.

### 
13.1 The frozen-engine gate pattern: fixtures → freeze → tripwire → gate timeline

The project's central governance mechanism, load-bearing for everything downstream, is stated as the first
governing principle of the whole build: 
"Deterministic engine first, frozen behind a gate (end of Day 2)
— no agentic code before the engine reproduces the golden fixtures"
 (
wiki/pages/
project-overview.md
). Concretely, four things had to be true simultaneously before 
engine/{hazard,
lgd,ead,staging,ecl}.py
 was declared frozen on 2026-07-05:

Definition.
 
The frozen-engine gate.
 An engine module is 
frozen
 once (1) the 133 golden
fixture values in 
tests/fixtures/compute_*.py
 (recreated from the textbook's own worked examples by
8 author + 8 adversarial-review agent pairs, 
re-cited without re-derivation
 throughout this
compendium) agree with the engine's output to the last displayed digit, (2) the full 
pytest
 suite is
green with zero failures, (3) 
data/processed/panel.parquet
 (the DCR panel) is fixed and
sha256-pinned, and (4) a structural code-fingerprint scan of the five frozen files is recorded as the baseline.
From that point on, 
any
 future gate that finds a fingerprint drift on a frozen file must either
show the drift is byte-identical noise or block until a decision-register entry justifies the change. First
freeze: 
187/187
, 2026-07-05 (
outputs/gate/gate_report.md
).

Exhibit 13.1
 — The freeze + fingerprint-tripwire mechanism: how a one-time gate becomes
a standing control over every later change (
outputs/mdd/MDD.md
 §6.1; 
.claude/skills/
pageindex-plus/scripts/scan_code.py
).

The enforcement tool is a code fingerprint scan
(
.claude/skills/pageindex-plus/scripts/scan_code.py --fingerprints knowledge/code_fp.json
)
that classifies every frozen file 
NONE
 / 
COSMETIC
 / 

STRUCTURAL
 on each gate, cross-checked with a git-blob sha256 comparison against 
HEAD
 as
a belt-and-braces second signal. Every gate this project has run — eleven of them, spanning
2026-07-05–2026-07-19 — has reported all five frozen files 
NONE
, and

data/processed/panel.parquet
 byte-identical, even as the codebase grew from 187 to 665 passing
tests around it. The isolation contract for the Freddie rung-3 stretch (agreed 2026-07-05, formalised
2026-07-07 13:23 in 
wiki/memory/decisions.md
) generalises the same idea to a second dataset: one
canonical schema per panel, the engine stays frozen and 
stateless
 so cross-dataset coefficient
inheritance is not merely disallowed but structurally impossible, and every dataset-tuned calibration (SICR
threshold, cure definition, satellite lags, ρ) is re-estimated from scratch for SFLLD rather than inherited
from DCR.

#### 
The gate timeline — eleven gates, zero regressions

Every gate below re-ran the 
entire
 accumulated suite, not just the new layer's own tests — the count
in the "tests" column is therefore a running total, and every single gate reports zero regressions against the
gate before it.

Gate
Date
Tests
What it added / locked

Engine freeze (Day 2)
2026-07-05
187/187
133 golden fixtures + 16 EAD + 8 LGD + 16 staging + 14 ECL tests; 
engine/
 FROZEN

Day-3 scenarios
2026-07-07
278/278
Vasicek Z-recovery, DFAST scenario paths, satellite model, Jensen exhibit, MLP challenger

Day-4 ship
2026-07-07
381/381
LangGraph Tier-1 router + refusal path, FastAPI+Preact app, Docker, public HF Space

Stretch: Tier-3 + MCP
2026-07-08
422/422
query_model_docs
 cited retrieval, MCP server

App v2 + Tier-2
2026-07-08
509/509
5-tab north-star app; 
analyze_data
 sandbox (fork-isolated, 5s timeout)

UI v3
2026-07-16
513/513
fintech design-direction pass; build-time waterfall regression script

SFLLD Phase A
2026-07-17
553/553
837,500-loan real panel, 54-state macro merge, EDA (40 new Freddie tests)

REASONED route
2026-07-17
582/582
3-way router split (computable/reasoned/refuse); spelled-out-number guard

SFLLD Phase B
2026-07-18
659/659
hazard/LGD refit, COVID-regime decision, ALFRED backtest, LSTM challenger (77 new tests)

MDD + Freddie tab
2026-07-19
664/664
outputs/mdd/MDD.{md,html}
, Real Data tab, 
.dockerignore
 whitelist fix

Macro/FRED interpretation
2026-07-19
665/665
hazard-ratio fields, FRED-source badges, the DCR-vs-SFLLD honesty fix (§13.11)

Source: 
outputs/gate/{gate_report,day3_gate_report,day4_gate_report,stretch_gate_report,
appv2_gate_report,uiv3_gate_report,reasoned_route_gate,mdd_freddie_gate,macro_interp_gate}.md
,

outputs/freddie/gate_phase{A,B}.md
, 
wiki/memory/log.md
.

Exhibit 13.2
 — The eleven-gate history, zero regressions across every one, spanning
187→665 tests over two weeks (2026-07-05–2026-07-19). Reproduced from the table above.

#### 
Interactive — gate-timeline explorer

Click a gate to see exactly what it locked in. Every gate re-runs the entire accumulated suite —
the "tests" figure is a running total, not just the new layer.

What this means.
 The gate pattern converts "we tested it" into a falsifiable, re-checkable claim: any
reader can re-run 
uv run --no-sync pytest tests/ -q
 today and get the same 665/665, and the
fingerprint scan means a change to 
engine/ecl.py
 cannot silently slip through a later gate the way
an untested refactor could in a codebase without this control. The isolation contract is the same idea applied
across datasets rather than across time — it is what allows the Freddie rung-3 stretch to exist at all
without risking the DCR production engine's own frozen guarantees.

Gotcha — "zero regressions" describes the 
test suite
, not "the model never changed its mind".

The gate timeline's headline claim is that nothing already-shipped broke; it says nothing about whether a NEW
recommendation contradicts an OLD one within the same gate window. Section 13.11's COVID case study is
exactly this: the SFLLD Phase-B gate (659/659, zero regressions) shipped a hazard-model recommendation that
directly reversed the same session's own earlier draft recommendation — both states passed every existing test,
because the tests check numerical correctness of code, not the soundness of a judgment call layered on top of
correct numbers. The gate protects against silent breakage; the review process (§13.11) is what protects
against a wrong-but-internally-consistent judgment shipping unchallenged.

Check yourself.

A future engineer wants to add a sixth engine module, 
engine/prepayment.py
, alongside the
frozen five. Under the frozen-engine gate pattern, what specifically would have to happen before this could
ship?
  
Answer

The new module is not one of the five originally frozen files, so it is not itself subject
  to the fingerprint tripwire on day one — but the isolation contract's spirit requires it be added behind its
  own gate: full pytest green including every existing test (zero regressions on the 665 already shipped), the
  five ORIGINAL frozen files re-scanned and confirmed still NONE (a new module should not require touching them),
  and a decision-register entry recording why a sixth module was introduced. If it DOES need to touch one of the
  five frozen files, that touch must show up as COSMETIC or STRUCTURAL on the next fingerprint scan and be
  justified in the decision register before the gate can pass.

Why does the gate table above show the SAME cumulative test count growing gate-over-gate (187, 278,
381...665) rather than each row reporting only its own new tests?
  
Answer

Because every gate re-runs the ENTIRE suite, not just the new layer — that is precisely
  what "zero regressions across every gate" means operationally: each gate is a re-verification that everything
  shipped before still works, not merely a check that the new code works in isolation. Reporting cumulative
  totals is what makes "665/665" a meaningful end-to-end claim rather than eleven separate, unconnected claims.

### 
13.2 Champion/challenger governance recap

Both rungs of this project ran a champion/challenger comparison, and both landed on the same governance rule,
stated explicitly as project policy: 
challengers stay challengers
 unless they beat the champion
OOT, not just in-sample, and even a genuine OOT win is inspected for 
why
 before it is trusted.

Rung
Champion
Challenger
In-sample
OOT
Verdict

DCR (Ch.3/Ch.7)
cloglog hazard, AUC 0.748/0.661
MLP
0.7632 (challenger) vs 0.7476 (champion)
0.6417 (challenger) vs 0.6609 (champion)
Champion retained
 — challenger wins in-sample, loses OOT (overfit/regime story)

SFLLD (Ch.12)
cloglog hazard, AUC 0.8536/0.6847
LSTM
—
0.9925 (LSTM) vs 0.6847 (champion)
Champion retained
 — LSTM wins OOT AUC overall, but the lift is a labelling artifact (below)

Source: 
outputs/mdd/MDD.md
 §4.3, §3.7; 
wiki/memory/decisions.md

2026-07-18 20:47 entry.

The SFLLD row is the more instructive one precisely because a naive read of "0.9925 vs 0.6847" would crown the
LSTM decisively. The honest lift decomposition (Ch.12's job to build in full; recapped here only as the
governance headline) splits that 0.9925 by whether a loan carries a prior delinquency spell in its lookback
window: AUC 
0.957
 on prior-spell loans vs 
0.529
 on clean-history loans (champion
0.570) — the champion is essentially matched on clean books and the LSTM's advantage is concentrated entirely on
loans where the sequence model can see the loan was already delinquent recently, i.e. delinquency-state memory,
not genuine path-dependence learned from the sequence shape itself (
wiki/memory/decisions.md

2026-07-18 20:47 entry: "lift is entirely delinquency-state memory: +0.387 AUC on prior-spell loans, near-random
on clean history"). Both challengers are kept as challengers by explicit, standing project policy — never
promoted to champion, whatever an aggregate metric shows — precisely because an aggregate OOT AUC alone would
have missed this.

What this means.
 "Challenger beats champion OOT" is necessary but not sufficient governance evidence — a
disciplined validator's next question is always 
where
 the lift comes from, because a model that wins by
exploiting a feature already highly correlated with the target near the observation window (recent delinquency
status) is not the same discovery as a model that has learned a genuinely new predictive signal. The champion-
never-challenger-without-decomposition rule converts "the aggregate metric looks better" into "we checked and it
is better for the right reason, or we know exactly why it looks better and it is not the right reason."

Gotcha — a challenger that "loses" is not wasted work.
 The MLP's overfit/regime story (wins in-sample,
loses OOT) is itself a validated finding about the champion's robustness — it demonstrates that a more flexible
functional form does NOT find additional signal the linear cloglog spec is missing on this panel, which is
positive evidence for the champion's adequacy, not merely a failed experiment. Framing every challenger run as
"could this replace the champion?" undersells the second, equally valuable question a challenger answers: "is
there evidence the champion is under-fitting?"

Check yourself.

If a bank's model-risk policy required "promote the challenger if OOT AUC improves by more than 0.02," would
the SFLLD LSTM have been promoted under that rule, and would that have been the right call?
  
Answer

Under a bare AUC-threshold rule, yes — 0.9925 vs 0.6847 clears any reasonable threshold by
  a wide margin. But this project's own decomposition shows that promotion would have been the WRONG call: the
  aggregate lift is concentrated on loans where the model is essentially reading off recent delinquency status,
  not a genuinely superior functional form, and the LSTM lacks the champion's competing-risk structure, seed-
  stability diagnostics, and forward-scoring readiness. This is the textbook argument for why champion/challenger
  policy should never be a single-metric threshold rule.

Why does the DCR MLP's overfit story (in-sample 0.7632 vs OOT 0.6417) not, by itself, prove the champion is
correctly specified?
  
Answer

It proves the champion is not obviously UNDER-fitting relative to this particular more
  flexible alternative on this particular OOT window — it is evidence in favour of adequacy, not a proof of
  correct specification. A different challenger architecture, a different OOT window, or a regime shift the OOT
  window does not capture could still reveal missed signal; §13.9's limitations register lists several such
  open edges (e.g. the seasoning-curve cohort confound) that a champion/challenger comparison alone would not
  surface.

### 
13.3 Retail scorecards: Weight of Evidence and Information Value

This closes a gap 
notes/plan/coverage.md
 flagged across three review batches as "unresolved,
unchanged" — WOE/IV scorecard theory (concept A6) was planned for a Chapter 3 follow-up that never
landed. Chapter 12 §12.1 is this compendium's full step-by-step derivation of the same

compute_pd.py
 worked example (every bin's bad rate, distribution share, WOE, and IV contribution shown
individually) — it is not repeated bin-by-bin here. What this section adds instead is the reading Chapter 12's
PD-lineage framing does not: WOE/IV is not merely a scorecard technique, it is a 
governance

technology — coarse-classing is how a bank makes a logistic-regression coefficient auditable to a non-technical
risk committee, and the IV threshold ladder doubles as a target-leakage tripwire.

Definition.
 
Weight of Evidence and Information Value.
 Partition a characteristic (e.g. origination
LTV) into bins $i=1,\dots,k$. Let $g_i,b_i$ be the count of goods (non-defaults) and bads (defaults) in bin $i$,
and $G=\sum_i g_i$, $B=\sum_i b_i$ the totals. Define the good/bad 
distribution shares

$\mathrm{Dist}^G_i = g_i/G$ and $\mathrm{Dist}^B_i = b_i/B$. Then:
$$WOE_i = \ln\!\left(\frac{\mathrm{Dist}^G_i}{\mathrm{Dist}^B_i}\right), \qquad
IV = \sum_i \left(\mathrm{Dist}^G_i - \mathrm{Dist}^B_i\right) WOE_i.$$
Siddiqi's convention for reading a total IV: $IV<0.02$ useless, $0.02$–$0.1$ weak, $0.1$–$0.3$ medium,
$0.3$–$0.5$ 
strong
, $>0.5$ suspicious (check for leakage — a characteristic this
predictive on its own is often a proxy for the target itself). (
knowledge/sources/
ifrs9_credit_risk_notes.md
 §6.1.)

WOE is a per-bin log-odds-ratio device with a specific, deliberate purpose: transforming a categorical or
continuous characteristic into a single numeric column such that a plain logistic regression on the WOE-
transformed inputs (rather than the raw characteristic) produces coefficients that are directly comparable across
predictors, absorbs non-linearity and missing-value bins without extra machinery, and — the governance payoff —
lets a risk committee read "this bin's WOE is $+0.92$" as "applicants in this bin are exp(0.92)≈2.5×
over-represented among goods relative to bads" without needing to interpret a raw regression coefficient on an
LTV percentage. IV is the same per-bin quantity aggregated into a single scalar summarising how much
discriminating power the whole characteristic carries — it is the same idea as an entropy/KL-style divergence
between the good and bad distributions across bins, which is why a characteristic with IV in the "suspicious"
range above 0.5 should be checked for target leakage rather than celebrated.

Recap — the same worked example, headline numbers only
 (full bin-by-bin derivation: Chapter 12
§12.1; 
tests/fixtures/compute_pd.py
, §6.1's own worked example). 10,000 applications, 500
bads ($G=9{,}500$, $B=500$), four coarse-classed origination-LTV bins:
$$\begin{array}{lrrrr}
\text{LTV bin} & \text{bad rate} & \mathrm{Dist}^G_i & \mathrm{Dist}^B_i & WOE_i & IV_i\\
\le 60\% & 2.06\% & 0.30 & 0.12 & +0.9163 & 0.1649\\
60\text{-}80\% & 3.80\% & 0.40 & 0.30 & +0.2877 & 0.0288\\
80\text{-}90\% & 6.86\% & 0.20 & 0.28 & -0.3365 & 0.0269\\
>90\% & 13.64\% & 0.10 & 0.30 & -1.0986 & 0.2197
\end{array}$$
$$IV_{\text{total}} = 0.1649+0.0288+0.0269+0.2197 = \mathbf{0.4403}.$$
The sign pattern is the diagnostic itself: low-LTV bins (fewer bads relative to goods than their good-share
implies) get positive WOE; high-LTV bins get negative WOE — the monotone risk ordering an interviewer expects from
a coarse-classed continuous risk driver. (
compute_pd.py
 
RESULTS["iv_total_ltv"]
 =
0.440341, matching the notes' printed 0.4403; all 23 of this module's golden values matched the notes' printed
figures to displayed precision when re-run this session.)

Exhibit 13.3
 — The four-bin origination-LTV worked example: bad rate rises monotonically
with LTV (left), WOE crosses zero between the 60–80% and 80–90% bins (middle), and the two extreme
bins (lowest- and highest-LTV) contribute the most Information Value — 0.1649 and 0.2197 of the 0.4403 total —
because they are furthest from the population's average good/bad mix (right). (
tests/fixtures/
compute_pd.py
, recomputed live this session.)

Reading the total: $IV_{\text{total}} = 0.4403$ falls in Siddiqi's "strong" band ($0.3$–$0.5$) — origination
LTV is a genuinely powerful single-characteristic predictor in this toy population, just short of the
"suspicious, check for leakage" threshold. The scorecard proper is then a logistic regression fit on the
WOE-transformed inputs across every characteristic (LTV, DTI, bureau score, etc., each independently coarse-
classed and WOE-encoded), with discrimination summarised the same way Chapter 7 already covers for the
hazard model — $\mathrm{Gini}=2\,\mathrm{AUC}-1$, KS statistic — and calibration read off the score-to-log-odds
linear mapping to a long-run central-tendency PD. Gradient-boosted challengers typically lift Gini by a few
points over a WOE-logit champion but face SR 11-7-style explainability expectations, the standard
resolution being exactly the champion-logit/ML-challenger/SHAP pattern this project itself uses for its hazard
models (§13.2).

What this means.
 WOE/IV is not merely a PD-modelling technique — it is a governance technology in its own
right: it converts an opaque regression coefficient on a raw variable into a monotone, auditable table a risk
committee can read bin-by-bin without a statistics background, which is precisely why it remains the dominant
approach for regulated retail scorecards even where tree ensembles would out-discriminate it on a pure AUC
basis. The IV threshold table (useless/weak/medium/strong/suspicious) is itself a governance control — a
characteristic landing in the "suspicious" band is a target-leakage RED FLAG, not a modelling win, exactly the
same discipline this project applies elsewhere (the LGD excess-loss loading, §13.9, is disclosed rather than
treated as a modelling success).

Gotcha — WOE/IV is a binary-logit device, not a general-purpose feature-selection ranking.
 A high IV tells
you a characteristic separates goods from bads well 
when entered log-odds-linearly into a logistic model

— it says nothing about a feature's marginal contribution inside a tree ensemble or neural net, where interaction
effects and non-monotone relationships the coarse-classing step would flatten can carry real signal. Using IV
rankings to pre-select features for an XGBoost or LSTM challenger risks discarding exactly the non-linear
predictors those model classes exist to exploit — this project's own LSTM challenger (§13.2) draws its
entire lift advantage from a sequence-memory effect a WOE-style binning of a single characteristic could never
represent.

Check yourself.

A fifth characteristic in the same population has $IV_{\text{total}} = 0.62$. Should this be added to the
scorecard as a strong predictor?
  
Answer

Not without investigation first. $IV>0.5$ is Siddiqi's "suspicious" band — a characteristic
  this predictive of the good/bad outcome on its own is a common signature of target leakage (e.g. a field
  populated only after default is known, or a near-duplicate of the target itself) rather than a genuinely
  powerful, legitimately-available-at-origination risk driver. The correct next step is to check the
  characteristic's population date and construction, not to add it straight to the scorecard.

Why is the ≤60% LTV bin's WOE positive ($+0.9163$) even though its own bad rate (2.06%) is well above
zero?
  
Answer

Because WOE compares a bin's SHARE of goods to its SHARE of bads, not its raw bad rate to
  zero — the ≤60% bin holds 30% of all goods but only 12% of all bads, so goods are heavily over-represented
  in this bin relative to bads, which is exactly what a positive WOE encodes. A bin can have a non-zero bad rate
  and still show strongly positive WOE as long as its bad rate is well below the population average (500/10,000
  = 5%), which 2.06% is.

### 
13.4 LGD structural formula: secured, unsecured, corporate

This section closes the second orphaned gap 
notes/plan/coverage.md
 flagged (concept A17):
Chapter 4 built the project's own two-stage cure×severity workout-LGD model in full, but the

textbook's
 structural formula for secured mortgage LGD — the mechanism connecting an indexed collateral
value to a loss estimate before any regression is fit — was never separately derived. It matters here because it
is the theoretical scaffold the project's own realised-LGD work (Chapter 12, SFLLD) and the mortgage-specific
severity model (Chapter 4, DCR) both sit on top of, without ever stating it explicitly step by step. Chapter
12 §12.8 states the formula itself as a brief "theory closure" before moving straight to the applied SFLLD
model built on top of it (its own scope, C4) — the full derivation and a dedicated worked example are this
section's own contribution, not a repeat of Chapter 12's applied treatment.

Definition.
 
Mortgage structural LGD.
 For a secured exposure, expected sale proceeds are built from
the collateral's 
indexed
 value (the original appraisal rolled forward by a house-price index to the
default/repossession date) discounted for a forced (distressed) sale, net of selling costs and any prior-ranking
charges, and only realised after a time-to-repossession lag:
$$\text{net proceeds} = \underbrace{V_{\text{coll}} \times (1-\delta_{\text{fs}})}_{\text{forced-sale value}}
- C_{\text{sell}} - P_{\text{prior}}, \qquad
\text{PV(net proceeds)} = \text{net proceeds} \times (1+EIR)^{-\tau},$$
$$LGD = 1 - \frac{\text{PV(net proceeds)}}{EAD_{\text{default}}} \quad \text{(the loss = shortfall vs exposure).}$$
Here $V_{\text{coll}}$ is the indexed collateral value, $\delta_{\text{fs}}$ the forced-sale discount (distressed
vs open-market value), $C_{\text{sell}}$ selling costs, $P_{\text{prior}}$ prior-ranking charges (senior liens),
$\tau$ the time-to-repossession, and discounting at the original EIR mirrors the workout-LGD convention Chapter 4
already established for cash-flow timing. (
knowledge/sources/ifrs9_credit_risk_notes.md
 §10.3:
"expected sale proceeds = indexed collateral value × (1 − forced-sale discount), less selling costs
and prior charges, delivered after time-to-repossession; loss = shortfall vs exposure.")

Two structural features distinguish this from an unsecured or corporate LGD model, and both are governance-
relevant: first, the HPI path that indexes $V_{\text{coll}}$ is the 
same
 macro series that drives current
LTV as a PD covariate (Chapter 3's hazard model, Chapter 11's SFLLD updated-LTV worked examples) — this
makes mortgage LGD structurally the most scenario-sensitive parameter in the book, since a single HPI shock moves
both the numerator (default probability, via LTV) and this formula's severity leg simultaneously. Second, a

cure overlay
 sits on top of the pure structural formula: not every defaulted mortgage proceeds to
repossession, so the two-stage cure×severity architecture Chapter 4 derives for DCR ($\mathbb{E}[LGD] =
(1-P(\text{cure}))\times LGD_{\text{write-off}}$) is how a bank turns this section's per-repossession structural
formula into a portfolio-level expected LGD.

Worked example.
 
An illustrative structural-LGD calculation
 (not a golden fixture — A17 has no
project 
compute_*.py
; computed via a small scratch script for this chapter, following conventions.md's
S5 rule for a new worked example, rather than hand-typed). A defaulted mortgage: exposure at default
$EAD=$ EUR 220,000; indexed collateral value $V_{\text{coll}}=$ EUR 195,000; forced-sale
discount $\delta_{\text{fs}}=12\%$; selling costs $6\%$ of the forced-sale value; prior charges (a small senior
lien) EUR 5,000; time to repossession $\tau=18$ months; original EIR $=6.5\%$ p.a.
$$\text{forced-sale value} = 195{,}000 \times (1-0.12) = \text{EUR}\,171{,}600,$$
$$\text{selling costs} = 0.06 \times 171{,}600 = \text{EUR}\,10{,}296, \qquad
\text{net proceeds} = 171{,}600 - 10{,}296 - 5{,}000 = \text{EUR}\,156{,}304,$$
$$\text{discount factor} = (1.065)^{-18/12} = 0.9099, \qquad
\text{PV(net proceeds)} = 156{,}304 \times 0.9099 = \text{EUR}\,142{,}215.09,$$
$$\text{shortfall} = 220{,}000 - 142{,}215.09 = \text{EUR}\,77{,}784.91, \qquad
LGD = 77{,}784.91 / 220{,}000 = \mathbf{35.36\%}.$$

Exhibit 13.4
 — The structural chain from an indexed collateral value to a per-loan LGD
estimate, with this section's illustrative worked example substituted at every step
(§10.3; scratch calculation, this chapter).

The remaining structural families from §10.3, recapped briefly since they are not this project's own scope
(DCR and SFLLD are both mortgage-only): 
unsecured retail
 LGD is typically built from recovery

curves
 — cumulative recovery as a function of months-since-default, estimated by vintage/segment with a
chain-ladder-style completion for still-open workouts, then discounted the same way as the secured case.

Corporate
 LGD is dominated by seniority and security structure (secured bank debt recovers far
more than subordinated bonds), with a debt cushion below the instrument mattering, and a persistent divergence
between market-based LGD (30-day post-default trading prices) and ultimate workout recoveries — Moody's LossCalc
is the reference vendor architecture. Across all three families, the same selection-bias caution Chapter 4
and Chapter 12 both flag for this project's own LGD work applies generically: excluding incomplete workouts
from an LGD fit biases the estimate toward fast, favourable resolutions, so open cases need an estimated
completion (with the completion model itself validated) rather than exclusion.

What this means.
 The structural formula is the textbook scaffold; this project's actual LGD models
(Chapter 4's DCR workout-LGD regression, Chapter 12's SFLLD realised-loss LGD) are both empirical
severity models fit to 
outcomes
, not implementations of this exact formula — but every one of this
formula's structural levers (indexed collateral, forced-sale discount, prior charges, time-to-repossession) is
implicitly what those empirical severity distributions are summarising in aggregate. Understanding the structural
mechanism is what lets a validator sanity-check a fitted LGD model's sign and magnitude: an updated-LTV
coefficient that pushes severity UP as collateral value falls, for instance, is exactly what this formula predicts
and should predict.

Gotcha — "indexed" collateral value is a projection, not an observation, until the loan actually defaults and
is appraised.
 Every input to this formula except the realised sale price itself is an estimate at the point a
bank forecasts ECL — the HPI index path is a scenario assumption (Chapter 6), the forced-sale discount and
time-to-repossession are portfolio averages from historical workouts, not loan-specific facts. This is exactly why
the project's own limitations register (§13.9) flags that Vasicek/scenario-conditioning is applied only to
the default-PD leg — LGD stays at frozen rung-1 projections with no collateral-path link yet — the structural
formula shows precisely which severity inputs a fuller scenario-conditional LGD model would need to move with the
macro path, and that work remains a named, undone enhancement.

Check yourself.

In the worked example, if the forced-sale discount were mistakenly applied AFTER selling costs and prior
charges instead of before (i.e. computed on net-of-costs proceeds rather than on the collateral value), would the
resulting LGD be higher, lower, or the same?
  
Answer

Lower loss (lower LGD) is the WRONG direction — but the actual effect: applying the discount
  to a smaller base (net proceeds, EUR 190,000 = 195,000−5,000, before selling costs) shrinks the discount's
  EUR impact roughly proportionally, which INFLATES the resulting net proceeds and understates the loss (lower
  LGD than the correct 35.36%). This is exactly the kind of order-of-operations error the structural formula's
  explicit derivation is meant to prevent — the discount applies to the GROSS collateral value first, because a
  forced sale depresses the market price itself, not merely the amount left over after costs are deducted from an
  undiscounted price.

Why does the text call mortgage LGD "structurally the most scenario-sensitive parameter in the book"?
  
Answer

Because the same HPI path that indexes the collateral value in this formula ALSO drives
  current/updated LTV, which is itself a PD covariate in the hazard model (Chapter 3/11) — a single adverse HPI
  scenario therefore moves both the probability of default going up (via LTV in the hazard model) and the loss
  given default going up (via a lower indexed collateral value in this formula) at the same time, compounding the
  scenario's effect on ECL through two channels rather than one.

### 
13.5 The wiki-as-MDD process: compile-don't-retrieve, audit, staleness

Every number cited in this compendium ultimately traces to an 
outputs/**/*.md
 report or a
fixture; every 
narrative
 claim about the project's own decisions traces to the wiki. The wiki is not a
convenience index — it is the project's designated system of record for knowledge (as opposed to numbers, which
stay in the reports), governed by four principles stated at the very top of 
wiki/pages/
project-overview.md
:

#
Governing principle

1
Deterministic engine first, frozen behind a gate — no agentic code before the engine reproduces the golden fixtures.

2
The LLM never does arithmetic — it routes, parameterises, narrates.

3
The wiki serves knowledge, never numbers.

4
Every scope cut is a documented simplification in 
memory/decisions.md
.

Source: 
wiki/pages/project-overview.md
 "Governing principles".

Definition.
 
Compile, don't retrieve.
 The wiki is built once per material change by 
compiling

raw sources (module docstrings, 
outputs/**/*.md
 reports, decision-register entries) into interlinked
Markdown pages with typed frontmatter and an explicit link graph — not re-derived at query time from the raw
sources themselves. The session-recovery ritual states this as an operational rule: 
"Read 
index.md

→ last 3 entries of 
memory/log.md
 → audit counts. Never re-orient by re-reading raw
sources."
 A fresh session (or a fresh reader of this compendium) is meant to reconstruct project state from
the compiled wiki pages in seconds, not by re-reading the underlying reports from scratch every time.

Three registers sit alongside the 21 content pages, deliberately kept outside the link graph, all append-only:
the 
decision register
 (
wiki/memory/decisions.md
, one entry per material decision —
context, options, the call, rationale, quoted throughout this compendium including §13.11's case studies),
the 
session log
 (
wiki/memory/log.md
, one entry per working session — this
compendium's own gate timeline in §13.1 is reconstructed almost entirely from it), and the 
open
questions register
 (
wiki/memory/questions.md
, struck through with a pointer to the resolving
page once answered).

#### 
The audit: how staleness and broken links are caught, not assumed absent

The wiki's own integrity is machine-checked, not merely asserted. The audit run immediately after the SFLLD
Phase-B gate (2026-07-18T20:47:54+00:00) reports:

Check
Result

Broken links
0

Missing frontmatter
0

Missing sources
0

Stale pages (source changed, page not re-compiled)
0

Orphan pages (unreachable from index)
0

Uncovered sources (warning, not error)
1 — 
tests/test_reasoned.py

Total pages / edges
21 / 106

Source: 
wiki/.wiki/audit.json
.

The single warning is itself instructive as a governance example: it is not hidden, not silently accepted, and
not escalated to a blocking error either — 
tests/test_reasoned.py
 genuinely has no dedicated wiki
page (its content is covered narratively inside 
wiki/pages/agent-layer.md
 instead), and the audit's
job is to surface that fact for a human to judge, not to decide unilaterally whether it matters. This is the same
philosophy the frozen-engine gate applies to a COSMETIC fingerprint drift (§13.1) — flag, do not
auto-resolve.

Definition.
 
Staleness, operationally.
 A wiki page is 
stale
 when the source file(s) listed in
its frontmatter 
sources:
 field have changed (by content hash) since the page was last compiled. The
audit's 
stale_pages
 check compares each page's recorded source hash against the source file's current
hash and flags any mismatch — this is the mechanism that keeps "the wiki serves knowledge, never numbers"
(principle 3) from silently degrading into "the wiki serves OUT-OF-DATE knowledge" as the underlying reports
and code continue to change after a page is written.

Finally, the Day-3 documentation decision (
wiki/memory/decisions.md
, 2026-07-07 12:55 entry) is the
one that ties this whole process directly to this chapter's other half: 
"formal MDD = pageindex-plus HTML
export of the wiki."
 The Model Documentation Document (§13.6) is not a separately-authored artifact
competing with the wiki for accuracy — it is generated FROM the wiki, which is why its own opening line states
"Every number in this document is quoted verbatim from a cited source file — nothing here is recomputed"
(
outputs/mdd/MDD.md
, document status).

What this means.
 The compile-don't-retrieve discipline solves a problem specific to long, multi-session
agentic work: without it, every new session (or every new chapter of this very compendium) would have to
re-establish project state by re-reading raw sources from scratch, which is both slow and a repeated opportunity
to introduce a fresh transcription error. Compiling once and then reading the compiled artifact — with an audit
that actively checks the compiled artifact has not drifted from its sources — is what makes "never re-orient by
re-reading raw sources" a safe instruction rather than a recipe for silently stale knowledge.

Gotcha — "0 stale pages" is a snapshot, not a permanent guarantee.
 The audit result quoted above is dated
2026-07-18T20:47:54+00:00 — the moment it was generated. Any wiki page whose underlying report changes AFTER that
timestamp without a re-compile is stale from that point forward until the next audit run catches it; the audit is
a periodic check run at gate time, not a continuously-enforced invariant like the fingerprint tripwire on

engine/
. A reader citing "the wiki has 0 broken links" from this chapter should understand that claim
is as current as this compendium's own 2026-07-19 compile date, not evergreen.

Check yourself.

Why does the wiki keep the three memory registers (decisions/log/questions) OUTSIDE the link graph rather than
as ordinary linked pages?
  
Answer

Because they are append-only chronological records, not concept pages meant to be
  cross-referenced and kept current the way a content page is — treating them as graph nodes subject to the same
  staleness/broken-link checks as a concept page would misapply a check designed for "this page should reflect
  current truth" to something whose entire value is an unedited historical record. They are still cited
  extensively (this chapter cites them repeatedly) — cited, not graph-linked.

Governing principle 3 says "the wiki serves knowledge, never numbers." How is this reconciled with the fact
that this very chapter's tables quote specific test counts (187, 278, ..., 665) that clearly came via the wiki's
session log?
  
Answer

The session log records numbers as part of a narrative account of what happened in a
  session (a session log entry, not a queryable numeric database) and every number this chapter actually CITES
  from it is cross-checked against the underlying outputs/gate/*.md report before being quoted (see this
  chapter's own top-of-file "grounding discipline" comment) — the wiki is the pointer to where a number's system
  of record lives, and a narrative account of what a session accomplished, not itself treated as the authoritative
  source of the number the way a report or fixture is.

### 
13.6 The MDD deliverable: a structural walkthrough

outputs/mdd/MDD.{md,html}
 is the project's formal Model Documentation Document, compiled 2026-07-19
and served in the live app both as a static page and linked from the header of every tab. It is the worked
instance concept A22/D6's governance/disclosure theory (§13.12) points at directly — this section walks
its own seven-section structure, not to re-quote every number (already cited by the originating chapter throughout
this compendium) but to show how a real MDD is organised end to end.

MDD section
What it contains
Where this compendium covers the same ground

1. Executive Summary
What the model is; headline results table (source-cited); governance-verdicts-at-a-glance table; the north-star product statement
Ch.1–12 collectively; §13.2 recaps the governance-verdicts table

2. Data
DCR panel (calendar anchoring), SFLLD panel (real dates/states/losses), macro sources
Ch.1–3 (DCR), Ch.11 (SFLLD)

3. Methodology
Hazard, LGD, EAD, staging, ECL assembly, Vasicek/satellite/scenarios, challengers — one subsection per model family, each with its own COVID-regime and WESML caveats inline
Ch.2–8, Ch.12

4. Validation & Backtesting
133/133 golden fixtures, the 11-gate timeline, champion/challenger, the ALFRED honest backtest, calibration exhibits
§13.1, §13.2, §13.7 (this chapter); Ch.7

5. Limitations & Known Issues
Eleven numbered items, pulled "deliberately from the decision/question registers and every report's own caveat sections — completeness, not flattery"
§13.9 (this chapter)

6. Governance & Controls
Frozen-engine gate, contract-first UI/API seam, agent guardrails, audit trail, the wiki-as-MDD process
§13.1, §13.5, §13.10 (this chapter)

7. Appendix
Repository map, output report inventory, 8 embedded exhibits, test-coverage snapshot
Cross-cutting; this compendium's own source citations throughout

Source: 
outputs/mdd/MDD.md
 Contents.

The document's opening promise is a strict discipline this compendium has itself followed throughout: 
"Every
number in this document is quoted verbatim from a cited source file — nothing here is recomputed. Where a source
page or report states a caveat, that caveat is carried into this document; nothing is smoothed over."
 Its own
build process demonstrates the review discipline §13.11 documents generally: the MDD's own review "traced 25
sampled numbers -> fixed 4 citation defects incl. 53-not-51 state FEs and a loans-vs-rows denominator
mislabel" (
wiki/memory/log.md
, 2026-07-19 05:47 entry) — a document ABOUT governance was itself
subjected to the same adversarial fact-checking every model in it received.

What this means.
 A model documentation document that recomputes numbers rather than citing them
introduces a second, independent source of the same fact — and a second source that can silently drift from the
first is a data-integrity risk, not a redundancy benefit. Requiring every MDD number to be a verbatim citation
back to its report of origin is what makes the MDD auditable: a reviewer can check any claim by opening exactly
one file, not by re-running a computation and hoping it matches.

Gotcha — a compiled MDD is only as current as its compile date, exactly like the wiki it is generated from.

outputs/mdd/MDD.md
 is dated 2026-07-19; any project change after that date (a new gate, a fixed
limitation, a new decision-register entry) is not reflected until the MDD is recompiled. This is a general property
of any document generated by the wiki-as-MDD process (§13.5), not a defect specific to this MDD — the mitigant
is the same staleness audit §13.5 describes, applied to the wiki pages the MDD is exported from.

Check yourself.

Why does the MDD organise its methodology section (§3) model-family by model-family (hazard, LGD, EAD,
...) rather than chronologically by when each was built?
  
Answer

Because an MDD's primary reader (a model validator, an auditor, a new team member) needs to
  understand one model family completely before moving to the next — build chronology (which module was coded on
  which day) is project-management information, not model-risk information, and mixing the two would force a
  reader to jump between unrelated model families to reconstruct one family's full picture.

The MDD's own review caught a "53-not-51 state FEs" citation defect. What kind of error does the number
"51" most likely represent, and why would this be an easy mistake to make without the review?
  
Answer

51 is the familiar count of US states plus DC — a natural, easy-to-assume default for
  "state fixed effects" that an author could type from memory rather than checking the actual fitted model's term
  count. The SFLLD state-macro merge (Chapter 11) documents that GU/VI/PR carry partial or no state series and
  are handled via national-fallback flags rather than uniform inclusion, which is exactly the kind of project-
  specific detail that makes the textbook-default "51" wrong for this specific model and only catchable by
  checking the actual coefficient table rather than assuming the familiar round number.

### 
13.7 The validation battery, recapped, and the ALFRED honest backtest

Chapter 7 derives the validation battery's three pillars in full — discrimination (Gini/KS), calibration
backtests (the binomial exact test and its Jeffreys-prior alternative), and stability (PSI) — each with a complete
step-by-step derivation and a fixture walkthrough (
tests/fixtures/compute_validation.py
). This section
does not re-derive any of that; it recaps the battery's shape as governance context and then walks the ONE
validation exhibit that sits outside Chapter 7's scope entirely: the ALFRED-vintage honest backtest, which
tests something the binomial/Jeffreys/PSI battery cannot — not "is today's model well-calibrated on held-out data"
but "would this model, frozen at some point in the past with only the macro information available AT that past
date, have seen a real crisis coming."

Pillar
Question it answers
Where derived

Discrimination
Does the model rank risk correctly? ($\mathrm{Gini}=2\,\mathrm{AUC}-1$, KS)
Ch.3 (AUC), Ch.7

Calibration
Is the predicted PD level correct? (binomial exact test, Jeffreys posterior)
Ch.7, full derivation

Stability
Has the scoring population's characteristic mix shifted? (PSI)
Ch.7, full derivation

Honest vintage backtest
Would the model have seen a REAL historical crisis coming, using only information available at that historical date?
This section (recap); full spec Chapter 12

#### 
The ALFRED-vintage honest backtest

freddie/backtest.py
 refits the champion hazard specification at five historical pseudo-reporting
dates, using only the loan data and macro 
vintages
 that genuinely existed at each date (ALFRED — the St.
Louis Fed's real-time, vintage-archived data series, which avoids look-ahead bias a plain current-vintage pull
would introduce), projects 36 months forward under two macro scenarios, and compares to what actually happened:

Reporting date $T$
Realised 36mo D90
Predicted (frozen macro)
Miss (frozen)
Predicted (hindsight macro)
Miss (hindsight)

2007-12-01
8.750%
0.928%
9.42×
4.613%
1.90×

2009-12-01
6.569%
5.554%
1.18×
4.658%
1.41×

2015-12-01
1.397%
1.857%
0.75×
1.855%
0.75×

2019-12-01
4.601%
0.920%
5.00×
71.519%
0.06×

2021-12-01
1.161%
1.734%
0.67×
1.229%
0.94×

Source: 
outputs/freddie/backtest/backtest_report.md
; 
outputs/mdd/MDD.md

§4.4 (verbatim reproduction).

Sign convention (stated explicitly, since the raw ratio direction is easy to misread):
 the miss
ratio is 
realised divided by predicted
 — a ratio above 1 means the model 
underpredicted

the crisis (realised losses came in higher than the frozen-macro model foresaw), and a ratio below 1 means the
model 
overpredicted
. This is why 2007-12's 
9.42×
 is the exhibit's central
honesty result: a hazard model fit on pre-2008 data, run forward with macro variables frozen at their 2007-12
levels, could not see the 2008 financial crisis coming — it produces a projected 36-month D90 rate of 0.928% against
a realised 8.750%, an 9.42-fold underprediction. Even feeding the model perfect hindsight knowledge of what UER
and HPI actually did over the next 36 months (the "hindsight macro" column) still leaves a 1.90×
underprediction — a model-risk floor that no macro information, however accurate, can close, because it reflects
specification and parameter risk in the hazard functional form itself, not merely a bad macro forecast.

Exhibit 13.5
 — The ALFRED-vintage honest backtest: realised vs frozen- vs hindsight-macro
36-month cumulative D90 projections (left), and the miss ratio over time with the >1 = underprediction line marked
(right). The 2019-12 hindsight bar is capped at 12% for legibility — its true value is 71.519%, discussed below.
(
outputs/freddie/backtest/backtest_report.md
.)

The 2019-12 row is the mirror-image failure mode, and the project's own framing of it is worth carrying forward
precisely because it is easy to mis-state: a hindsight-macro projection of 
71.519%
 against a
realised 4.601% (a 0.06× "miss," i.e. a massive OVER-prediction) is not a bug in the projection — it is
faithful linear extrapolation of a champion hazard specification that is linear in 
delta_uer_lag1
,
fed the actual April-2020 print (a +10.6 percentage-point move in a single month, roughly 20 standard deviations
outside the training support of month-on-month UER moves the model was fit on). A linear cloglog predictor given
an input that far outside its training range saturates the implied monthly hazard toward 1 for much of the book —
the purest form of out-of-support extrapolation risk, and precisely why this exhibit exists: it converts "our
model might not extrapolate well" from a theoretical caveat into a quantified, dated, reproducible number. A
connective finding ties this back to the LGD side (§13.9's severity discussion): the D90 
delinquency-
status
 miss shown here is not matched by a commensurate LOSS spike, because forbearance resolved the 2020
D90 spike as cures (modern-era OOT cure rate 97.9%, Chapter 12) rather than liquidations — reading only this
backtest's hazard-miss ratio would overstate the actual COVID ECL shock.

What this means.
 The binomial/Jeffreys/PSI battery (Chapter 7) validates a model against data it was
never trained on but from the SAME general regime as training; the ALFRED-vintage backtest validates something
strictly harder — whether the model's own functional form, given only the information genuinely available at a
past date, would have anticipated a regime the model had never seen. A model can pass every binomial/Jeffreys/PSI
check on ordinary held-out data and still fail an honest vintage backtest exactly the way this project's champion
does at 2007-12 — the two validation types are complements, not substitutes, and a validation program that runs
only the first would never surface the 9.42× result at all.

Warning — do not average or otherwise net the five dates' miss ratios into a single headline number.
 The
five reporting dates deliberately span a calm period, a crisis onset, a crisis trough, and a second, structurally
different crisis (COVID) — 9.42× (crisis onset, frozen macro) and 0.06× (COVID, hindsight macro,
out-of-support extrapolation) are two DIFFERENT failure modes with opposite signs and unrelated causes, and
averaging them would produce a number that describes neither. Each date's miss ratio must be read against its own
scenario column (frozen vs hindsight) and its own regime, exactly as the table presents them.

Gotcha — "9.42× underprediction" is routinely misquoted as "default rates were 9.42× higher in the
crisis," which is not what the number measures.
 The 9.42× figure compares a MODEL'S 2007-12 projection
(0.928%) to what actually happened (8.750%) — it is a statement about this specific frozen-macro model's forecast
error at this specific historical vintage, not a general claim about how much worse the financial crisis was than
some baseline expectation. A reader who drops the "vs this model's frozen-macro projection" qualifier and quotes
"9.42x" as a standalone crisis-severity statistic has silently converted a model-risk finding into an unrelated
(and unsupported) macroeconomic claim.

Check yourself.

At 2015-12-01, both the frozen and hindsight miss ratios are identical (0.75×). What does this tell you
about the informational value of macro scenario conditioning specifically at THIS reporting date?
  
Answer

It tells you that at 2015-12, the actual macro path over the following 36 months was close
  enough to what a "frozen at 2015-12 levels" naive extrapolation would already imply that perfect foresight of
  the true macro path added essentially nothing — this was a calm, low-volatility period for UER/HPI, so the
  scenario-conditioning machinery has little work to do. This contrasts sharply with 2007-12 and 2019-12, where
  frozen and hindsight miss ratios diverge by roughly 5x and 83x respectively (9.42x/1.90x and 5.00x/0.06x) —
  exactly the dates where the ACTUAL macro path moved far from a naive extrapolation.

A colleague argues the 2019-12 hindsight result (71.519% predicted vs 4.601% realised) proves the champion
hazard model is badly mis-specified and should be discarded. What is the strongest counter-argument this
section's framing provides?
  
Answer

The 71.519% figure is produced by feeding the model a macro shock (April 2020's UER print)
  roughly 20 standard deviations outside its training support — this is a demonstration of what a linear
  functional form does under EXTREME out-of-support extrapolation, not evidence the model is poorly calibrated
  within or near its training range (where the frozen-macro column at the same date, 0.920% vs 4.601% realised,
  shows a much more modest 5.00x miss). The correct governance response is not "discard the model" but "document
  that this functional form must not be trusted for macro shocks this far outside training support without an
  explicit saturation guard or a non-linear specification" — precisely the connective finding this section already
  draws to the LGD/cure-rate evidence.

### 
13.8 Post-model adjustments: the overlay governance battleground

Neither the DCR engine nor the SFLLD refit applies a post-model overlay anywhere in this project — every ECL
figure quoted throughout this compendium is a pure model output. That absence is itself worth stating explicitly,
because overlays are, per the textbook's own framing, 
"the dominant supervisory theme"
 in IFRS 9
governance today, and a validator reviewing this project should know exactly where it stands relative to that
theme rather than have to infer it.

Definition.
 
Post-model adjustment (overlay).
 A judgmental adjustment to a model's output — applied
above, below, or instead of the fitted PD/LGD/EAD/ECL — used to reflect a risk the underlying data cannot yet see
(a novel shock, an emerging portfolio-specific concern, a known model blind spot). Overlays are an explicitly
endorsed part of the IFRS 9 toolkit for genuinely novel risks, but supervisors have grown increasingly wary of
how they are used in practice. (
knowledge/sources/ifrs9_credit_risk_notes.md
 §9.3.)

Supervisory source
Finding

ECB (July 2024 review, 53 banks)
Roughly a 
quarter
 of performing-book loan-loss coverage is overlays, with no downward trend; overlays applied at the total-ECL level (bypassing PD and staging) explicitly discouraged as contrary to IFRS 9 principles; ~44% of banks lacked clear allocation of tasks/governance for overlays; supervisors warn overlays can become an earnings-management tool.

PRA Dear CFO letters (2022–24)
Challenge the completeness of PMAs (e.g. higher-rate affordability/refinance risk); push from broad portfolio-level overlays to targeted account-level adjustments; flag prolonged reliance on aged, underperforming models patched by PMAs.

EBA IFRS 9 monitoring
Overlays are now "an integral part of the ECL framework" needing tighter methodology and governance; large-bank disclosure practice (NatWest, Lloyds, Barclays, HSBC) quantifies judgmental PMAs as a share of total ECL — useful external benchmarks.

Source: 
knowledge/sources/ifrs9_credit_risk_notes.md
 §9.3.

Interview framing — a good overlay answer has four parts.
 (1) 
Trigger
 — a specific model
blind spot or novel risk, named explicitly, not a vague "the model might be wrong". (2) 
Quantification
basis
 — a sensitivity analysis or an external benchmark, never a round-number plug. (3)

Allocation
 — to specific stages and segments, so staging mechanics still function rather than
being bypassed at the total-ECL level (the ECB's explicit warning above). (4) 
Exit criteria
 — the
evidence that would retire the overlay or fold it into the model proper. (
knowledge/sources/
ifrs9_credit_risk_notes.md
 §9.3.)

Read against this framework, the project's own COVID-regime decision (§13.11's first case study) is
instructive precisely because it explicitly chose 
not
 to build an overlay where one might seem tempting:
the review's verdict — exclude the 2020-04..2021-09 window from the hazard likelihood entirely, rather than patch
the fitted model's COVID-window predictions with a judgmental adjustment — states directly that 
"forbearance
[should be] handled as a scoring overlay, not an in-likelihood dummy"

(
outputs/freddie/hazard/hazard_report.md
 §3) as a documented FUTURE direction, not something this
project has itself built. This is a textbook-correct instance of the "trigger, quantification, allocation, exit"
discipline applied at the design stage: the trigger (forbearance-shielded delinquency-status distortion) is named,
and the decision explicitly defers the overlay's construction rather than building an under-specified one now —
consistent with the ECB's warning that overlays without clear allocation/governance are exactly the failure mode
supervisors are watching for.

What this means.
 "This project has zero overlays" is not, by itself, evidence of superior governance — a
production bank's book genuinely needs overlays for risks a frozen, backward-looking model cannot see (climate,
a just-announced policy shift, a novel product). What IS creditable governance is that every place this project
COULD have reached for an overlay as a quick patch (the COVID regime, the 2019-12 backtest saturation), it instead
either fixed the underlying specification (COVID: exclude, don't patch) or documented the residual gap explicitly
as an open limitation (§13.9) rather than papering over it with an unquantified judgmental adjustment — the
"quantification basis, never a plug" half of the interview framing above.

Gotcha — "overlay" and "regime dummy" are not the same governance object, even though both are judgmental
adjustments to a model.
 A regime dummy (the additive-dummy COVID variant §13.11 discusses) is fit

inside
 the likelihood alongside every other coefficient — it is estimated, not asserted, and its failure
mode (contaminating the structural macro block) is a statistical one the review could diagnose from the fitted
coefficients themselves. A true overlay sits OUTSIDE the model entirely and is asserted by expert judgment, with no
equivalent statistical diagnostic available to catch a bad one — which is exactly why the ECB/PRA/EBA findings
above are so focused on overlay GOVERNANCE (allocation, exit criteria) rather than overlay statistical validity:
there often isn't a statistical validity check available for a judgmental number the way there was for the
additive dummy's sign-flipped coefficient.

Check yourself.

Per the ECB's finding, why specifically are overlays applied at the "total-ECL level" flagged as contrary to
IFRS 9 principles, rather than overlays in general?
  
Answer

Because a total-ECL-level overlay bypasses the PD and staging mechanics entirely — it
  changes the bottom-line number without going through (or being disciplined by) the staged, probability-weighted,
  discrimination-and-calibration-tested machinery IFRS 9 otherwise requires. An overlay allocated to specific
  stages/segments and applied to a specific PD, LGD, or EAD input stays inside that machinery and can still be
  validated against it (e.g. checked for staging consistency); a total-ECL plug cannot be similarly checked.

Using the four-part interview framing, what would be MISSING from an overlay justified only as "management
believes losses will be 10% higher next quarter due to economic uncertainty"?
  
Answer

All four parts, arguably, but most acutely (2) and (4): there is no stated quantification
  basis (why 10%, not 5% or 20% — no sensitivity analysis or benchmark cited) and no exit criteria (what evidence
  would cause this overlay to be reduced or removed). "Economic uncertainty" alone is also too vague to satisfy
  (1) — a proper trigger names the SPECIFIC blind spot (e.g. "the satellite model has no leading indicator for a
  just-announced tariff policy") rather than a generic macro-anxiety statement.

### 
13.9 The limitations register, organized as a validator would

This section is the brutal list, pulled — in the MDD's own words — 
"deliberately from the decision/question
registers and every report's own caveat sections... completeness, not flattery."
 A validator does not read a
limitations register as a flat, unordered list; the organisation below groups every item by the KIND of model risk
it represents, since the appropriate mitigant differs by category.

Category
Item
Evidence
Residual risk / status

Regime / functional-form risk
COVID regime & the saturation twin
Champion excludes 2020-04..2021-09 from the hazard likelihood (review overturn, §13.11); 2019-12 hindsight backtest saturates at 71.5% predicted vs 4.601% realised
Both are the SAME underlying limitation from opposite directions — the champion's linear functional form was never identified in a forbearance-shielded or 20-sigma macro regime. 2022–25 observed hazard still runs 1.62–1.79× the exclude-variant prediction, unresolved.

Cure-stage OOT weakness
SFLLD cure-logit OOT AUC 
0.4769
 — below random
Mechanical consequence of the modern-era fixed effect fit on only 9 train rows, compounded by the COVID base-rate shift. Disclosed as genuine small-sample-plus-regime-shift limitation, not a coding defect — but the cure model's OOT discrimination should NOT be relied on for forward scoring without further work.

Inference / uncertainty
WESML inference caveat
Seed-pair coefficient swings up to 
5.7×
 nominal SE on macro terms (
seed_stability.csv
)
Nominal p-values on the SFLLD hazard should NOT be read as the operative significance test for macro coefficients — the freq_weights rescaling excludes Monte-Carlo control-sampling noise from the reported SEs.

Seasoning-curve cohort confound
A second hump near 108 months in the fitted age-baseline spline that the raw empirical hazard-by-age profile does not show
Artifact of only the 2005–08 crisis vintages being old enough to populate that age bin by the 2016-12 train cutoff — not a genuine second seasoning peak. Extrapolation beyond ~143 months has zero train support.

Selection bias
Resolved-only selection bias (both LGD models)
DCR + SFLLD both fit severity/cure on resolved workouts only; SFLLD default-year 2025 is 54.2% unresolved
Cures resolve faster than liquidations, biasing fitted cure rate up (severity down) for cohorts near the panel's window end. True exposure is RECENCY, not specifically the COVID cohort.

ALFRED backtest excluded subpopulation
Loans with a missing static covariate excluded from both sides of the backtest comparison (~2.5–14% of the book by date)
The excluded subpopulation runs RISKIER than the scoreable book — the backtest's own cohort therefore UNDERSTATES the whole-book realised rate, on top of the miss ratios already reported.

Definitional
D90-vs-liquidation default definition
SFLLD's D90 label is a delinquency-STATUS event, not a loss event — COVID's 4.5×-GFC D90-entry spike vs a >10× COLLAPSE in the 90+→liquidation roll rate over the same window
Any consumer of the SFLLD hazard's PD must pair it with the LGD module's realised-loss view to avoid mistaking a delinquency-status shock for an economic loss shock.

No competing-risk prepayment (SFLLD refit)
SFLLD hazard fits ONLY the D90 cause, unlike DCR's dual cause-specific hazard
Declared simplification; the SFLLD refit cannot itself decompose prepayment-driven survival the way the DCR engine's $S(t)$ does.

Structural scope
Single-factor Vasicek
One systematic factor $Z$ per period, common to the whole book; no sector/geography/product segmentation
The main-anchor $Z$ ($\rho=0.0227$) is only approximately TTC because updated LTV is HPI-indexed and carries part of the collateral cycle back into loan-state covariates; the orig-LTV variant ($\rho=0.0633$) brackets from the other side, true value lies between.

Scenario-conditioning scope
Only the default-PD leg is scenario-conditioned; LGD and EAD stay at frozen rung-1 projections
No collateral-path LGD link yet (§13.4's structural formula names exactly which severity inputs this would need to move); staging frozen across scenarios (two-step probability-weighted staging is a named, undone enhancement).

Coverage / data gaps
SFLLD vintages 2011–13 and 2017 never downloaded; GU/VI have no state HPI/UER; PR has UER but no HPI
Documented gaps, not filled by interpolation or assumption — any state-level feature carries the national-fallback flag through rather than silently blending it in.

Agent-layer
REASONED-route guard checks a number's magnitude exists in a legal source, not its semantic attribution
Inherent limitation across all three router outcomes, recorded after §13.11's spelled-out-number bypass review; the digit case is fixed, the underlying attribution gap is not.

Source: 
outputs/mdd/MDD.md
 §5 (verbatim reproduction, re-organised by category);

outputs/freddie/hazard/hazard_report.md
, 
outputs/freddie/lgd/lgd_report.md
,

outputs/freddie/backtest/backtest_report.md
.

What this means.
 Organising the register by category rather than by originating module surfaces a pattern
a flat list hides: the COVID-regime item and the 2019-12 backtest-saturation item look like two unrelated
findings from two different reports, but they are the SAME underlying functional-form limitation observed from
opposite directions (a forbearance-shielded regime the model was never trained on; an out-of-support macro shock
the model extrapolates faithfully but wrongly). A validator reading limitations by category, not by report of
origin, is far more likely to notice this kind of connection — which is exactly why the MDD itself explicitly
cross-references §5.1 to the backtest's §4.4 rather than treating them as independent bullet points.

Gotcha — a long, honest limitations register is a GOOD sign in a model-risk review, not a bad one.
 The
instinct to read twelve numbered limitations as twelve reasons to distrust the model output inverts the correct
governance reading: a model whose validation package contains few or no disclosed limitations is far more likely
to be under-scrutinised than genuinely limitation-free. Every item in this register was FOUND by the project's own
validation and review process (not by an external critic) — the register's length is evidence the process is
working, not evidence the model is unusually flawed relative to undisclosed alternatives.

Check yourself.

Which single limitation in this register would a reader need to know about BEFORE trusting a claim like "the
SFLLD hazard model's cure-adjusted PD accurately separates good and bad loans in the most recent origination
years"?
  
Answer

The cure-stage OOT weakness (AUC 0.4769, below random) — this specific claim conflates the
  HAZARD model's discrimination (which the register does not flag as weak) with the CURE model's discrimination
  (which is explicitly flagged as unreliable for recent/modern-era loans due to a 9-row fixed-effect fit). A
  reader who has not separated "hazard discrimination" from "cure discrimination" would wrongly extend the
  hazard model's reasonable performance to a component that is documented as weak.

The register notes the ALFRED backtest's excluded subpopulation "runs RISKIER than the scoreable book." What
does this imply about whether the 9.42x miss ratio at 2007-12 is an over- or under-statement of the TRUE whole-
book miss?
  
Answer

It implies 9.42x likely UNDERSTATES the true whole-book miss ratio — if the excluded,
  riskier loans had been included on the realised side, the realised 36-month D90 rate would likely have been
  even higher than the reported 8.750%, widening the gap against the same 0.928% frozen-macro prediction (which
  is itself computed only on the scoreable subset). The two limitations compound in the same direction rather
  than offsetting.

### 
13.10 Agent governance as a model-adjacent control

Chapter 8 derives the LangGraph agent's routing logic, guardrails, and sandbox security model in full; this
section recaps only what makes the agent layer a 
governance
 control specifically — the mechanism that
keeps an LLM-fronted interface from becoming a new, uncontrolled channel for the exact kind of unverified numeric
claim the rest of this project works so hard to avoid.

Guardrail
What it enforces
Governance parallel

The LLM never does arithmetic
Router selects one of four pydantic-validated Tier-1 tools; narrator quotes tool-result numbers VERBATIM, with a post-check and deterministic template fallback on any miss
Governing principle 2 (§13.5) — the same "numbers come from a system of record, never from memory" discipline this compendium itself follows for every cited figure

Refusal path
Validation failure or out-of-scope questions route to a refusal node naming the supported tool families; regression-tested against prompt injection
A model that refuses out-of-scope questions rather than confabulating an answer is the agent-layer analogue of a validator flagging "insufficient evidence" rather than guessing

REASONED route
Relevant-but-uncomputable questions get a labeled, cited interpretation (prefixed 
[REASONED — interpretation, not engine output]
), grounded via Tier-3 retrieval + a whitelisted baseline rerun
Explicit LABELLING of "this is interpretation, not a computed fact" is the agent-layer equivalent of this compendium's own 
.interpretation
 box convention — never silently blending judgment with fact

Coherent-shock convention
Applies every macro shock as a co-moving move along the DFAST severe-minus-base direction, per-concept deltas returned transparently — load-bearing since the satellite has no unemployment term
A documented modelling convention (Chapter 6), not a silent workaround — stated in 
wiki/memory/decisions.md
, 2026-07-07 20:12

Audit trail
Every agent run appends to 
outputs/agent_log/*.jsonl
 — a replayable record of question, route, tool calls, and answer
The agent-layer instance of the same append-only-record discipline the decision register and session log apply to human/agent authoring decisions

Source: 
outputs/mdd/MDD.md
 §6.3; Chapter 8.

The concrete example worth carrying into this governance chapter, since it is a genuine adversarial-review catch
rather than a designed-in feature: an adversarial review confirmed a LIVE bypass of the number-guard, where the
router LLM performed its own subtraction and verbalised the result as 
"tens of millions"
 specifically to
dodge a digit-only regex check — the guard was checking for numeral characters, and the LLM's own arithmetic,
spelled out in words, slipped past it. The fix, 
_spelled_number_violation()
, was wired into all three
guards (reasoned/narration/docs) with regression tests, and the residual limitation is disclosed rather than
declared fully solved: the guard checks a number's 
magnitude
 exists in a legal source, not its

semantic attribution
 — an inherent limitation carried forward into §13.9's register rather than
claimed fixed.

What this means.
 The agent layer is "model-adjacent" governance rather than model governance proper because
it does not change what the frozen engine computes — its entire job is to prevent a natural-language interface
from introducing a NEW class of error (a hallucinated or unverified number, an out-of-scope answer presented as
authoritative) on top of an already-correct computation. The spelled-out-number bypass is the clearest illustration
available: the underlying tool call and its numeric result were correct throughout — the vulnerability was entirely
in how the LLM's own PROSE could smuggle a number past a verification check, which is exactly the kind of failure
mode that has no analogue in the deterministic engine layer and needs its own, separate governance mechanism.

Gotcha — "the LLM never does arithmetic" is a design rule the router can still VIOLATE, as the spelled-number
case shows, so it must be enforced by a check, not merely stated as policy.
 The router LLM performing its own
subtraction and verbalising the result was a direct violation of governing principle 2, caught only because
an independent adversarial review went looking for exactly this failure mode rather than trusting the stated
design rule. A policy statement without an enforcement mechanism is aspirational, not a control — this is the same
lesson §13.1's fingerprint tripwire encodes for the engine layer (a frozen-engine POLICY without a fingerprint
CHECK would be just as vulnerable to silent drift).

Check yourself.

Why is a REASONED-route answer prefixed 
[REASONED — interpretation, not engine output]
 rather
than simply being refused, given that the agent cannot compute a numeric answer to these questions?
  
Answer

Because the question is genuinely answerable with grounded, cited reasoning even though no
  Tier-1 tool computes a number for it (e.g. "does the satellite need a UER x HPI interaction term?") — refusing
  it entirely would under-serve a legitimate, in-scope conceptual question. The explicit label instead lets the
  answer through while making its EPISTEMIC STATUS unambiguous to the reader: this is a cited interpretation, not
  a verbatim tool-computed fact, exactly the distinction this compendium's own .interpretation boxes maintain
  throughout.

The spelled-out-number bypass was fixed for the DIGIT case but the underlying limitation (magnitude exists in
a source vs. is correctly ATTRIBUTED) remains open. Construct a hypothetical narration that would pass the fixed
guard yet still misattribute a real number.
  
Answer

Any narration that quotes a real, verbatim, guard-legal number but attaches it to the WRONG
  concept — e.g. correctly citing "\$34.0m" (a real weighted-scenario ECL figure that exists in a legal source)
  but describing it as "the 12-month ECL" when the source actually reports it as the LIFETIME weighted ECL. The
  guard checks only that the digits 34.0 appear in an allowed source; it has no mechanism to verify the surrounding
  prose's claim about what that number MEANS is the same claim the source makes — exactly the attribution gap
  §13.9's limitations register discloses as still open.

### 
13.11 Independent review as governance evidence: four case studies

Every gate in §13.1's timeline was preceded by an independent adversarial review — a separate agent,
working from the same numbers and no author assumptions, whose job is specifically to find what the author missed
or got wrong. This section is not a general claim that the process exists (that claim was already made throughout
this compendium's citations); it is four specific, dated instances where the review stage 
changed the
shipped answer
, presented as the concrete evidence for why independent review is a governance control and
not a formality.

Exhibit 13.6
 — The recurring governance loop this section's four case studies are all
instances of. Every stage produces durable evidence (RESULTS, a review verdict, a test count, a decision-register
entry) rather than an unrecorded judgment call.

#### 
Case 1 — the COVID regime overturn (SFLLD Phase B, 2026-07-18)

Chapter 12 §12.7 walks this same episode as a MODELLING decision in full (all four variants' complete
coefficient tables against the champion, the regenerated calibration exhibit). This case study extracts only what
that section does not focus on: the governance mechanics of how the recommendation actually changed hands between
author and reviewer. The champion hazard fit never sees COVID rows by construction (train window ends 2016-12); to
test regime treatments, the hazard team extended the estimation window to 2021-09 and fit three variants, all
scored on the identical, genuinely unseen OOT2 window (>2021-09):

Variant
OOT2 AUC
delta_uer_lag1
hpi_growth_lag1

naive (no dummy)
0.7553
−0.204 (sign-flipped vs champion +0.667)
+0.013 (collapsed)

additive (regime dummy)
0.7547
−0.130 (still sign-flipped)
−6.584 (overshoots)

exclude (COVID rows removed)
0.7509
+0.774
 (matches champion +0.667)
−3.307
 (matches champion −3.344)

Source: 
outputs/mdd/MDD.md
 §3.1.3 (verbatim reproduction of

outputs/freddie/hazard/hazard_report.md
 §3).

The additive dummy itself fits at +1.482 (hazard ratio 4.40) — it visibly absorbs the 2020 D90 spike, and the
author's initial, in-report recommendation was to adopt it, on the reasoning that a regime dummy "doing its job"
should be the natural fix. 
The Fable adversarial review overturned this recommendation, using the report's
own numbers
: the additive dummy does NOT repair the structural macro block — 
delta_uer_lag1

stays sign-flipped at −0.130 even with the dummy present, meaning a calendar-level dummy cannot undo a joint
covariate-outcome distortion when the UER spike and the forbearance-shielded delinquency ladder co-move inside the
same window. The review's rewritten verdict: 
EXCLUDE
 the 2020-04..2021-09 window from any
structural or scenario-conditional use — the OOT2 AUC spread across all three variants (0.7509–0.7553) is far
too small to override the structural argument, and exclude is the only variant whose macro block survives
economically signed. (
wiki/memory/decisions.md
, 2026-07-18 20:47 entry: 
"the author's initial
recommendation was the additive dummy; the Fable adversarial review overturned it, showing the report's own
numbers contradicted the recommendation."
)

#### 
Case 2 — the FRED-badge honesty catch (macro/FRED interpretation feature, 2026-07-19)

Shipping per-variable coefficient interpretation fields across the app's four coefficient-serving endpoints, the
implementation initially attached a 
fred_series
 badge (e.g. 
UNRATE
) to DCR's national
macro rows on the reasoning that the DCR panel's macro columns are genuine US national series, calendar-anchored
to real FRED history (Chapter 5's own calendar-anchoring discovery, corr 0.9963 to FRED UNRATE). The review
caught the distinction this reasoning glossed over: 
DCR's macro columns are vendor-premerged onto the
panel's own anonymized clock
, not a series the app itself live-pulls from FRED the way the SFLLD state-
level series genuinely are — badging them identically to a live FRED pull would misrepresent the DCR rows'
provenance to an app user, even though the underlying correlation fact is real and worth stating. The fix: all 6
DCR/national 
_CONCEPTS
 entries and 5 
_MACRO_GLOSSARY
 rows had 
fred_series

set to 
null
, with the FRED-correlation fact moved into each row's 
transformation
/

lag_rationale
 prose instead of a misleading series-pointer badge — honesty about provenance preserved
over a superficially richer-looking badge. A second, unrelated defect was caught in the same review pass:

_hazard_ratio_per_unit()
 grouped an interaction term ("DOUBLE TRIGGER" / 
dt_ltv_uer
) with
"no transformation," which would have leaked a marginal per-unit hazard-ratio reading for a coefficient that is
only meaningful as a product term — fixed to correctly return 
null
 for interaction terms, with a new
regression test. (
outputs/gate/macro_interp_gate.md
; 
wiki/memory/log.md
, 2026-07-19
08:21 entry.)

#### 
Case 3 — the Tier-2 sandbox RCE catch (App v2 + Tier-2, 2026-07-08)

The 
analyze_data
 sandbox lets an LLM write pandas code that is then executed, fork-isolated, against
a real DataFrame — a deliberately powerful capability that needed a correspondingly hardened security boundary. A
Fable security review caught a 
CRITICAL module-traversal remote-code-execution vulnerability
: an
attribute-only AST filter (intended to restrict code to safe pandas operations) could be escaped via

pd.io.common
, a module-traversal path the filter had not anticipated. This was fixed before ship — the
sandbox's final hardening (fork isolation, 5-second timeout, 50-row/5,000-character output caps, 68 dedicated
tests) is the shipped state; the RCE path existed in an intermediate, pre-review build. (
wiki/memory/
log.md
, 2026-07-08 15:18 entry.)

#### 
Case 4 — the MDD's own citation-defect self-audit (2026-07-19)

The Model Documentation Document — the very artifact whose stated purpose is to hold every OTHER model to a
citation-verbatim standard — was itself put through the same review discipline before ship. The review sampled 25
numbers from the compiled MDD and traced each back to its cited source, finding and fixing 4 citation defects,
including a "53-not-51 state fixed effects" miscount (§13.6's own quiz walks the likely mechanism: a familiar
round-number default substituted for the actual fitted term count) and a loans-vs-rows denominator mislabel. This
is the clearest single illustration in the whole project of governance applied reflexively — the review process was
not exempted from checking the document that describes the review process. (
wiki/memory/log.md
,
2026-07-19 05:47 entry.)

Case
What the author/initial build got wrong
What review changed

1. COVID overturn
Recommended the additive regime dummy based on its visible 2020-spike absorption
Overturned to EXCLUDE, using the same report's own sign-flipped coefficient evidence the author had reported but not acted on

2. FRED-badge honesty
Badged DCR's vendor-premerged national macro identically to a live FRED-pulled series
Nulled the misleading badge; moved the real correlation fact into prose; also fixed an interaction-term hazard-ratio leak

3. Tier-2 RCE
An attribute-only AST filter with an unanticipated module-traversal escape
Hardened before ship; CRITICAL severity, caught pre-production

4. MDD self-audit
4 citation defects in the governance document itself (a state-FE miscount, a denominator mislabel)
Fixed before the MDD shipped — the reviewer did not exempt the review-standard document from the review standard

What this means.
 All four cases share a structure worth naming explicitly: in every one, the SAME
information the review used to overturn or fix the finding was already present in the author's own work — the
sign-flipped coefficient was already in the hazard report's own table; the vendor-premerged provenance was already
documented in Chapter 3's calendar-anchoring finding; the AST filter's gap was discoverable by reading the
filter's own logic; the MDD's citations were checkable against its own cited sources. Independent review's value in
this project is not access to NEW information the author lacked — it is a second, differently-motivated pass over
the SAME information, unclouded by the author's own narrative commitment to their first conclusion. This is
precisely why the governance loop (Exhibit 13.6) places review as a distinct stage from authoring rather than
treating "the author double-checked their own work" as equivalent.

Gotcha — none of these four catches would show up in a test-suite-only governance view.
 All four gates
these cases belong to (SFLLD Phase B, macro/FRED interpretation, App v2, MDD+Freddie) reported full green test
suites — the review catches were not test failures, they were judgment/security/provenance issues a green test
suite is structurally unable to detect on its own (a test suite checks that code does what it was written to do,
not that what it was written to do is the RIGHT thing, or that a stated recommendation matches the evidence in the
same report). This is the direct, concrete instance of §13.1's own gotcha: gates protect against silent
breakage; review protects against a wrong-but-internally-consistent conclusion.

Check yourself.

In Case 1, the naive variant (no dummy at all) had the HIGHEST OOT2 AUC of the three (0.7553). Why did the
review not recommend the naive variant, if it discriminates best?
  
Answer

Because the naive variant's macro coefficients are sign-flipped just as badly as the
  additive dummy's — delta_uer_lag1 at -0.204, the wrong sign for a structural/scenario-conditional use, even
  though it happens to discriminate best on this particular OOT2 window. A model with the wrong-signed macro
  sensitivity cannot be trusted to respond correctly to a NEW macro scenario Chapter 6's satellite/scenario layer
  would condition it on, however well it ranks risk on the fixed OOT2 sample it was scored against — discrimination
  and structural soundness are different properties, and the review explicitly weighted the latter as
  disqualifying regardless of the former.

Case 2 involved TWO separate fixes in one review pass (the FRED badge and the interaction-term hazard ratio).
What does bundling both into one review, rather than shipping the first fix alone and finding the second later,
suggest about how the review was conducted?
  
Answer

It suggests the review was a systematic pass over the ENTIRE new feature surface (every
  endpoint, every row type) rather than a narrow check of the one issue that prompted the review — an adversarial
  review looking only for "is the FRED badge honest" could easily have missed the unrelated interaction-term leak,
  since the two defects are in different functions (_variable_interpretation's badge logic vs
  _hazard_ratio_per_unit's grouping logic) touching different concept rows. Finding both in one pass is evidence of
  breadth, not just depth, in how the review was scoped.

### 
13.12 Regulatory & ethics context: BCBS d350, IFRS 7, CRR, hot topics

Chapter 1 (§1.3) already builds the IFRS 9 vs Basel IRB vs CECL classification comparison table in
full — this section does not repeat it. What remains, and is this chapter's own scope (concept A22), is the
supervisory and disclosure layer that sits ON TOP of any one framework's classification rules: who is accountable
for the ECL methodology, what auditors and analysts expect a bank to reconcile publicly, how the accounting number
interacts with regulatory capital, and what the current supervisory hot topics are.

Definition.
 
BCBS d350
 (
Guidance on credit risk and accounting for expected credit losses
,
2015) — eleven principles governing sound ECL practice: board/senior-management responsibility for the ECL
framework; sound, documented methodologies; robust rating/grouping processes; allowance adequacy; model
validation; 
experienced credit judgment
 (the doctrinal home of overlays, §13.8); common data
and systems across risk and finance functions; disclosure; plus supervisory-evaluation principles. Its sharpest
line, worth quoting directly: 
"cost or operational burden is not a justification for forgoing reasonably
available forward-looking information."
 (
knowledge/sources/ifrs9_credit_risk_notes.md

§14.1.)

EBA/GL/2017/06 transposes d350 for EU credit institutions with proportionality; Fed SR 11-7 supplies the
model-risk-management validation/effective-challenge vocabulary this chapter's own review case studies
(§13.11) are an instance of; ECB TRIM/IMI reviews enforce these expectations for internal models on-site, with
IFRS 9 models increasingly in scope.

#### 
The IFRS 7 disclosure package

What auditors and analysts expect a bank to reconcile publicly, and the template this project's own headline
numbers (§13.1's gate timeline, Chapter 2's ECL waterfall) would populate if presented in bank-disclosure
form:

Disclosure element
What it must show
This project's equivalent, if it were disclosed this way

Credit-risk exposure & allowance by stage
A movement (reconciliation) table by stage explaining transfers, originations, derecognitions, remeasurement, write-offs
Chapter 2's ECL movement/waterfall decomposition; Chapter 1's Stage 1/2/3 shares (0% calm / 75.8% stress)

SICR criteria & default definition
Stated explicitly, with the relative-PD comparison rule and any absolute/qualitative backstops
Chapter 1's relative SICR test; the D90-absorbing default definition (Chapter 11) vs the classic 90/180-DPD backstop (§13.9's definitional-limitations row)

Write-off policy
When and how a loss is recognised as final
Workout-LGD's resolved-vs-unresolved distinction (Chapter 4, §13.9)

Scenarios, weights, key macro assumptions
Named scenarios with probability weights and sensitivity of ECL to them
Chapter 6's three-scenario weighting (50/25/25 judgmental, §13.9), the Jensen gap (\$34.0m weighted vs \$32.9m at the averaged path, 1.035x)

Significant judgments
¶5.5.20 behavioural life, overlay quantification, and other material judgment calls that move the number
The revolver behavioural-life exception (Chapter 4); this project's explicit CHOICE not to build an overlay for the COVID regime, documented as a deferred future direction (§13.8) rather than an undisclosed judgment

Source: 
knowledge/sources/ifrs9_credit_risk_notes.md
 §14.2 (template); this
project's own reports (mapped column, cross-referenced to originating chapters).

#### 
Capital interaction

The initial ECL uplift on IFRS 9 adoption hit retained earnings (CET1) directly; transitional arrangements
(CRR Art. 473a in the EU) phased the Day-1 impact over five years with static and dynamic components and
mandatory dual disclosure (transitional vs fully-loaded) — the phase-ins have now largely expired, but the
mechanism returns whenever the accounting framework next changes materially. For IRB books, accounting provisions
are compared against regulatory expected loss: a 
shortfall
 is deducted from CET1, an

excess
 is recognised in Tier 2 up to 0.6% of credit RWA — so higher IFRS 9 provisions
partly "pre-pay" an existing CET1 deduction rather than reducing capital one-for-one. Post-2018 stress
tests/ICAAP are provision-sensitive: the EBA methodology prescribes scenario-conditional staging with "perfect
foresight" of the adverse path, which is exactly why this project's own scenario-conditional ECL machinery
(Chapter 6) is structurally the same computation a real stress-test submission would require.
(
knowledge/sources/ifrs9_credit_risk_notes.md
 §14.3.)

#### 
Hot topics (mid-2026)

Overlay discipline
 — the dominant supervisory theme (§13.8 in full).

Climate and novel risks
 — the ECB's reviews show the share of banks reflecting climate risk in
provisioning rising from a small minority (~16%) to a majority (~55%) within two years, mostly via overlays for
want of data; the methodological frontier is moving climate from an overlay toward a model COVARIATE
(transition-/physical-risk-adjusted PD/LGD) — this project's own HPI/UER macro-covariate architecture
(Chapter 3, Chapter 6) is the template a climate-covariate extension would follow, though none is built
here.

Procyclicality
 — evidence (Behn & Couaillier, ECB WP 2841) that IFRS 9 provisions
react earlier and more strongly to shocks than IAS 39's incurred-loss model did — better early recognition,
but cliff effects at stage boundaries persist. This project's own Stage 2 threshold-sensitivity exhibit
(Chapter 1) is precisely the kind of analysis a bank would run to manage this procyclicality dial.

Model ageing & ML adoption
 — supervisors flag prolonged reliance on aged models patched
by PMAs; ML challengers are mainstream as CHALLENGERS, gated by explainability and governance — exactly this
project's own champion-logit/ML-challenger/SHAP-adjacent pattern (§13.2, §13.3's WOE/IV gotcha on
tree-ensemble feature selection).

Source: 
knowledge/sources/ifrs9_credit_risk_notes.md
 §14.4.

What this means.
 Every one of the four hot topics above has a direct analogue somewhere in this project's
own build, which is not a coincidence — the textbook's hot-topics list and this project's own governance choices
are both responses to the same underlying supervisory pressure. Reading the hot-topics list alongside this
compendium's own citations is a useful self-check exercise for a reader: for each topic, can you name the specific
chapter/section where this project either implements the relevant control (overlay discipline, §13.8) or
explicitly documents NOT yet implementing an extension the topic implies (climate as a covariate)?

Gotcha — "capital interaction" is not merely an accounting footnote; it changes the INCENTIVES around every
modelling choice this compendium has covered.
 Because a shortfall between accounting provisions and
regulatory expected loss is deducted from CET1 one-for-one, a bank has a live capital incentive to argue its
accounting PD/LGD/EAD estimates are LOWER rather than higher — which is exactly the incentive the validation
battery (Chapter 7, §13.7), the frozen-engine gate (§13.1), and independent review (§13.11) all
exist to counteract. Understanding §14.3's capital mechanics is what makes clear WHY governance controls this
strict are commercially necessary, not merely an academic best practice.

Check yourself.

A bank's IRB accounting provisions are €40m below its regulatory expected loss of €55m. Per the capital
interaction rules above, what happens to CET1?
  
Answer

The €15m shortfall (55-40) is DEDUCTED from CET1 directly — a shortfall between accounting
  provisions and regulatory expected loss reduces capital one-for-one under the IRB rules described in §14.3.
  This is the specific mechanism that gives a bank a live capital incentive to keep accounting provisions close
  to (or above) regulatory expected loss, reinforcing why independent validation of PD/LGD/EAD estimates matters
  commercially, not just academically.

Why does the text connect the "climate as a covariate" hot topic specifically to this project's HPI/UER
macro-covariate architecture, rather than treating climate risk as an unrelated new topic?
  
Answer

Because the methodological move the industry is making — from a judgmental climate OVERLAY
  toward a climate risk COVARIATE inside the PD/LGD model itself — is structurally the same move this project
  already made for HPI and unemployment: a macro driver enters the hazard/LGD model as a fitted covariate with an
  estimated coefficient and an economic-channel story, rather than being handled as an outside-the-model
  judgmental adjustment. The project's existing satellite-model and Vasicek-conditioning architecture (Chapter 6)
  is a ready-made template for exactly this kind of extension, even though building a climate covariate is
  explicitly out of this project's own scope.

### 
13.13 Closing appendix: learning path, interview drill, concept index

This closing appendix folds in the textbook's own §15 (learning path, tooling, interview drill —
concept A23) and provides the full concept-to-chapter index for revision, per 
notes/plan/
requirement_11_app_guide.md
's sibling convention of a closing "where would you look" quiz bank, generalised
here to the whole 46-concept compendium rather than one chapter.

#### 
The 12-week build-it-yourself path

Weeks
Goal
Concrete deliverable
This compendium's equivalent

1–2
Standard fluency
One-page staging/ECL memo; framework-comparison table from memory
Ch.1 (staging, classification), Ch.1 §1.3 (IFRS 9 vs Basel vs CECL)

3–6
PD end-to-end
WOE/IV scorecard; discrete-time hazard on a mortgage panel; lifetime PD term structures by segment
§13.3 (this chapter, WOE/IV); Ch.3 (cloglog hazard, fully derived); Ch.5 (Vasicek PIT/TTC)

7–9
LGD, EAD, wholesale
Two-stage LGD with workout discounting; CCF study; Merton DD replication; Pluto–Tasche
Ch.4 (workout LGD, EAD/CCF); §13.4 (this chapter, structural LGD); Ch.12 (Merton DD, D-4)

10–12
Scenarios + validation
Z-recovery + satellite model; scenario-conditioned ECL; validation pack (Gini, binomial/Jeffreys, PSI, staging flows); model-documentation write-up
Ch.5–6 (Vasicek, Jensen, scenarios); Ch.7 (validation battery); §13.5–13.6 (this chapter, MDD)

Source: 
knowledge/sources/ifrs9_credit_risk_notes.md
 §15.1 (template), mapped to this
compendium's chapters.

Tooling
 (§15.2, unchanged from the textbook, matching this project's own stack):

Python
 — 
pandas
/
numpy
, 
statsmodels
 (GLM cloglog,
ARDL/ECM), 
scikit-learn
, 
lifelines
, 
scipy.stats
; 
R
 —

survival
, 
glmnet
, 
betareg
; SAS remains common in incumbent banks. This
project's own build used exactly this Python stack throughout (
engine/
, 
freddie/
,

tests/fixtures/
).

#### 
Closing interview drill — twelve questions, answered from this project

#
Question
Where this compendium answers it

1
Why did IFRS 9 replace IAS 39?
Ch.1 §1.1 — incurred → expected loss, "too little, too late," provisions from day 1

2
Walk through the three stages.
Ch.1 — 12-month vs lifetime ECL, gross vs net interest basis, transfers with probation

3
What exactly is 12-month ECL?
Ch.2 — lifetime losses from defaults POSSIBLE in the next 12 months, not truncated cash shortfalls

4
How would you design a SICR test?
Ch.1 — relative lifetime-PD comparison, doubling convention, backstops, cure/probation, Stage-2 size trade-off

5
IFRS 9 PD vs Basel PD?
Ch.1 §1.3 — PIT vs TTC, unbiased vs conservative/floored; Ch.5 — the Vasicek PIT-TTC bridge derived in full

6
How do you build a lifetime PD term structure?
Ch.3 — discrete-time cloglog hazard derived from continuous-time first principles, seasoning baseline, competing risks

7
Why multiple scenarios — why not the base case?
Ch.6 — Jensen's inequality proved in full, the project's own 1.035x weighted-vs-averaged-path gap reproduced

8
How does the macro enter the model?
Ch.6 — satellite model, ARDL/ECM hygiene; Ch.5 — Vasicek conditioning of PDs

9
Why is LGD modelled in two stages?
Ch.4 — bimodality, P(cure) x severity; §13.4 — the structural formula underneath the severity leg

10
EAD for a credit card?
Ch.4 — CCF on headroom, ¶5.5.20 behavioural life, B5.5.40 shortest-of-three

11
What is a WOE/IV scorecard and why use it over a raw-variable logit?
§13.3 (this chapter) — full derivation, worked 4-bin example, IV=0.4403

12
How does this project prove its own numbers are correct?
§13.1, §13.11 (this chapter) — the frozen-engine gate, 665/665 tests, four independent-review case studies

Source: questions 1–10 from 
knowledge/sources/ifrs9_credit_risk_notes.md

§15.3 (verbatim, project-specific answer pointers added); questions 11–12 added for this compendium.

#### 
Concept-to-chapter index (all 46, for revision)

Chapter
Title
Concept ids covered

1
IFRS 9 Foundations & Staging
A1, A2 (+ A4 comparison box)

2
ECL Mechanics
A3, A14

3
Hazard Modelling (PD Term Structure)
A7, A8 (+ A6, A9 intro/sub-section framing)

4
LGD & EAD
A15, A16, A18, A19, A20 (+ B2 EDA cross-ref)

5
The Vasicek One-Factor Model
A10

6
Scenarios, Satellite Models & Jensen
A11, A12

7
Challengers & Validation
A21

8
The Agent (LangGraph Copilot)
D1, D2

9
The App: A Guidebook
D3, D4

10
Docker & Deployment Guidebook
D5

11
Freddie Mac Panel & EDA
A5 (intro framing), C1, C2

12
Freddie Models, Backtest & LSTM
C3, C4, C5, C6, D-4 (Merton), A6 (full WOE/IV derivation), A17 (structural-formula theory closure, applied to the SFLLD realised-loss model)

13
Governance, MDD & Closing Synthesis
A6 (governance recap), A13, A17 (structural-formula full derivation + illustrative worked example), A22, A23, D6 (+ B7 gate roll-up, recap)

Source: 
notes/plan/chapters.md
 "Chapter → concept coverage check"; 
notes/
plan/coverage.md
 (batch-E routing of A6/A13/A17 confirmed absorbed by this chapter, closing the three-batch
"unresolved, unchanged" gap).

What this means.
 Every one of the 46 concepts 
notes/plan/topic_map.json
 identified at the
start of this campaign is now claimed by exactly one chapter, with three (A6, A13, A17) landing here specifically
because no earlier chapter's natural scope absorbed them — this index is the mechanical proof of that closure, not
merely an assertion of it, since a reader can check any concept id against this table and find its chapter.

Gotcha — "every concept covered" is not the same claim as "every concept covered at equal depth."
 Some rows
above (e.g. Chapter 3's A9 sub-section, explicitly flagged in 
chapters.md
 as "a scope contrast
since the project itself is retail-mortgage-only") are deliberately lighter framing notes rather than full
derivations, because the project's OWN scope is retail mortgage, not corporate/wholesale credit. A9 (Merton,
shadow ratings, Pluto–Tasche) gets its full worked derivation in Chapter 12 specifically because that is
where the project's own D-4 backlog item routes it — the concept index tells you WHERE a topic is covered, not
automatically how deep that coverage goes; check the originating chapter's own learning goals for that.

Check yourself — closing.

A reader wants to know: "how did this project decide the SFLLD hazard model should exclude COVID-window data,
and was that decision independently checked?" Which TWO sections of this compendium would they need, and why two,
not one?
  
Answer

Chapter 12 (once written) for the full technical derivation of the three-variant COVID
  comparison and the champion hazard specification itself, AND this chapter's §13.11 Case 1 for the GOVERNANCE
  story — that the author's initial recommendation was the additive dummy, and that an independent adversarial
  review overturned it using the report's own numbers. The technical "what was compared and what were the
  results" and the governance "who decided what, and was it checked" are genuinely different questions this
  compendium deliberately answers in different places, exactly as §13.2's champion/challenger recap and Chapter
  7's full validation derivation are similarly split.

Looking back across all 13 chapters: name one number that appears in THREE OR MORE different chapters of this
compendium, and explain why repeating it (rather than citing it once) is consistent with this project's own
"recompute every number" discipline.
  
Answer

Several qualify — the SFLLD hazard AUC (0.8536/0.6847) appears in Chapter 3 (cross-
  reference), Chapter 11 (panel framing), Chapter 12 (full derivation), and this chapter (§13.2, §13.9); the
  665/665 test count appears in this chapter's own §13.1 timeline and is referenced throughout. Repeating a
  number across chapters is consistent with (not a violation of) the "recompute every number" discipline as long
  as EVERY repetition is independently traceable to the same cited source (outputs/freddie/hazard/hazard_report.md
  in this example) rather than copied from an earlier CHAPTER's citation of it — this compendium's own convention
  requires each chapter to cite the underlying report or fixture directly, never "as quoted in Chapter N," which
  is exactly why the same number can appear many times without ever becoming a second, independently-drifting
  source of truth.

Chapter 13 summary — and compendium close.
 This project's governance rests on four compounding controls,
none of which alone would be sufficient: a 
frozen engine
 behind a fingerprint tripwire, proven
across eleven gates and 187→665 tests with zero regressions (§13.1); a champion/challenger discipline
that inspects OOT wins for WHY before trusting them, not just whether (§13.2); a 
wiki-as-MDD
process
 that compiles knowledge once and audits it for staleness (0 broken links, 0 stale pages, 21 pages
/ 106 edges as of the last audit) rather than re-deriving it every session (§13.5), culminating in a Model
Documentation Document that cites every number verbatim back to its report of origin (§13.6); and

independent adversarial review
, evidenced not as a policy statement but as four dated case
studies where review genuinely changed the shipped answer — the COVID regime overturn, the FRED-badge honesty
catch, the Tier-2 sandbox RCE fix, and the MDD's own reflexive citation self-audit (§13.11). Two concepts
orphaned across three earlier coverage-review batches got their full textbook treatment here: retail scorecard
WOE/IV — Chapter 12 derives it from first principles bin-by-bin; this chapter recaps the 4-bin, IV=0.4403 worked
example and adds the governance reading (audit technology, leakage tripwire) Chapter 12's PD-lineage framing does
not
(§13.3), and the mortgage structural LGD formula, worked through an illustrative EUR 220,000 exposure to
a 35.36% LGD (§13.4). The limitations register (§13.9) closes the loop on candour: twelve items,
organized by the KIND of model risk each represents rather than by which module happened to find it, presented —
in the MDD's own words — for completeness, not flattery. Set against the regulatory and ethics backdrop
(§13.8's overlay battleground, §13.12's BCBS d350/IFRS 7/CRR/climate context), the project's own choices
read not as an isolated engineering exercise but as one worked, end-to-end instance of what the standard's
governance chapter actually asks a real model-risk function to do — document honestly, validate independently, and
never let cost or convenience justify skipping the forward-looking information a genuinely rigorous ECL estimate
requires.

Compiled from 
outputs/gate/*.md
, 
outputs/freddie/gate_phase{A,B}.md
,

outputs/mdd/MDD.md
, 
wiki/memory/log.md
, 
wiki/memory/decisions.md
,

wiki/.wiki/audit.json
, 
wiki/pages/project-overview.md
, 
knowledge/sources/
ifrs9_credit_risk_notes.md
 §6.1/9.3/10.3/14/15, 
tests/fixtures/compute_pd.py
, and

notes/plan/{chapters,coverage,topic_map}.md
 (read/recomputed live this session) on 2026-07-19.

