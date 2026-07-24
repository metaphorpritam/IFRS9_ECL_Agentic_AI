# Dossier v2 + propagation plan (FINAL, user-approved structure — awaiting GO)

Status 2026-07-24: planned, NOT executed. Prior workflow attempt (wf_2689d5df-c55) was
stopped by the user mid-run — any partial edits from it are uncommitted. Execution mode:
**NO ultracode / no multi-agent fleets** — one background agent for the dossier author at
most, orchestrator reviews personally; site+app edits done directly.

## The canonical CV card (byte-exact, render bolds)

| Field | Content |
|---|---|
| Title | IFRS 9 ECL Copilot: agentic credit-risk analytics platform (LangGraph + vectorless RAG) |
| Problem | Estimated forward-looking IFRS9 expected credit losses (ECL) on mortgages with a grounded AI copilot. |
| Method (ECL) | Modelled PD, LGD & EAD on a 621K-row mortgage panel; staged loans & probability-weighted scenarios. |
| Method (Agentic AI) | Shipped a LangGraph tool-calling agent+vectorless RAG (PageIndex), Dockerised CI/CD deployment. |
| Results | Evaluated on 133 golden fixtures & 548 tests; guardrails force every AI figure to be engine-sourced. |
| Live app | https://huggingface.co/spaces/Preetomsorkar/ifrs9-ecl-copilot |
| Website | https://metaphorpritam.github.io/IFRS9_ECL_Agentic_AI/ |
| CV Defense Dossier | https://metaphorpritam.github.io/IFRS9_ECL_Agentic_AI/cv_dossier.html |
| Source | https://github.com/metaphorpritam/IFRS9_ECL_Agentic_AI |

NO "Model performance" pointer (user cut it) — performance lives in the dossier S1 defense.
Bold targets: IFRS9 expected credit losses (ECL); PD, LGD & EAD; staged loans; LangGraph
tool-calling agent; vectorless RAG; CI/CD; 133 golden fixtures; guardrails.

## Dossier v2 structure

- PART I: card (byte-exact) + 4 pointer sections (DCR-scoped; 548 tests everywhere in I-II).
- PART II — defense sections, EACH with a **revalidation manifest** (fact → value → how
  re-verified → command → date; facts RE-EXECUTED at build time, not quoted):
  - S1 ECL model performance defense: hazard 0.748/0.661 (rescore from saved artifacts);
    prepay 0.684/0.584; MLP challenger 0.642 (back-pocket Q&A, NOT a pointer); PSI 0.0632 +
    binomial/Jeffreys (rerun fixtures); LGD cure 0.837/0.769, +4.7pp conservative, loading
    0.0255 vs realized 0.0236, resolved-only trap (24.6% open workouts, 58% fake-zero lgd_time,
    9,496 fit rows); staging 0%→75.8% + sensitivity; ECL coverage 1.28%→28.4%, waterfall
    residual <$0.01 (rerun snapshot); Vasicek rho=0.0227, anchor by quadrature, Jensen 1.035x;
    OOT-vs-backtesting explainer (temporal holdout w/ realized covariates vs as-of-date
    forward prediction; the 0.661-passes/9.42x-fails gap = the scenario-overlay argument);
    EAD (annuity B(t) closed form, double-counting rule, CCF EUR14.0m fixture, denormal guard);
    EIR (original-EIR discounting rationale, quarterly from note rate, fees-approximation
    disclosure); per-component cards each: definition/formula/worked fixture/defense Q.
  - S2 LLM agent evaluation defense: per-family fresh pytest counts (router/reasoned/tools/
    tier2/tier3/api/contract); attack battery table (fake digits, comma/scientific formats,
    spelled-number "tens of millions" live bypass found→fixed→pinned, poisoned narration,
    pd.io RCE regression); routing 100% on pinned set; optional dated live 3-route smoke.
  - S3-S6 implementation deep-dives: LangGraph (how it works; vs LangChain verified against
    installed packages; the real graph from agent/graph.py); PageIndex+LLM-wiki (built/works/
    implemented; corpus+wiki stats from artifacts; one recorded retrieval demo); Docker CI/CD
    (gate stack, multi-stage anatomy, 9-failure COPY case study, ship verification, honest
    Actions-billing-lock note); fixtures anatomy + 548-test taxonomy (three-kinds thesis,
    fossil origin stories, EUR4,952.83 dissected end-to-end with real assertion snippet).
- VISUALS (matplotlib, image-QA'd; reuse ch08 diagrams where they fit): request-lifecycle
  sequence diagram; LangGraph state-machine flowchart (actual nodes/edges); guard-chain
  flowchart + attack-results table; RAG pipeline diagram + vectorless-vs-embeddings table;
  three-tier capability table; CI/CD flowchart; LangGraph-vs-LangChain table.
- AI-DEV GAUNTLET (~12 tough Q&A): why LangGraph vs raw function-calling; evaluating
  non-determinism; prompt-injection limits; temp-0 scope; guardrail false-positive cost;
  vectorless-vs-embeddings scale tradeoff; sandbox escape surface (RCE story); model-swap
  resilience; latency/cost; observability/audit trail; measuring hallucination (engine-sourced
  invariant); magnitude-vs-attribution limitation (volunteer it).
- PART III: Freddie second act (9.42x/1.90x/0.06x, LSTM lift decomposition, 665 full-suite
  figure) framed as beyond-the-CV spoken depth; ~15-question Q&A bank; artifact index.
- Honesty laws: no CI/CD overclaim; LangChain/LangGraph facts package-verified; never imply
  LSTM ran through the backtest; DCR macro = vendor-premerged anonymized clock (not live FRED).
- Gates: check_notes.py (7) + verify_math.py PASS; every image VIEWED; card byte-diffed.

## App changes (contract-additive, static grounded copy)

1. Model tab TOP: "Model at a glance" panel — ECL formula, each term (S, lambda, LGD, EAD,
   discount) a chip linking to its panel, explain icon per term.
2. Model tab: "EAD & EIR method" panel — annuity profile + double-counting rule + CCF; EIR
   original-rate rationale + note-rate approximation.
3. Copilot tab: "How grounding works" panel — 4-step guard chain, status-dot legend
   (GROUNDED/REASONED/THINKING/OUT OF SCOPE), honest limitation sentence.
4. Header: "Notes" link -> the Pages site (beside MDD).
Gates: pytest 665 + npm build (waterfall prebuild) green; copy grounded in
wiki/pages/agent-layer.md + engine docstrings; no invented numbers.

## Website changes

1. Landing hero: add CV Dossier link.
2. Reading-paths strip: Recruiter -> dossier; Practitioner -> ch01; AI engineer -> ch08+ch09.
3. "Model components" quick-index strip: each IFRS9 component -> its chapter anchor.

## Execution stages

1. Dossier v2: one agent authors WITH live revalidation runs; orchestrator reviews
   (byte-diff card, spot-recompute 10 manifest rows, view diagrams, run gates). ~45 min.
2. App panels + website strips: direct edits. ~25 min.
3. Ship: Space upload+verify; gh-pages rebuild + EXPLICIT Pages build trigger
   (POST /pages/builds — the flip alone never queues); live card grep; commits + wiki log.
