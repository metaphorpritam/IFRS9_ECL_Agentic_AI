# Decision records

Append-only. One entry per decision: context, options, the call, and why.

## 2026-07-05 05:49 UTC — tags: bootstrap, environment

Build-plan contradictions resolved (MASTER_PLAN §3.6): uv+Python 3.13 everywhere incl. Docker image (resolved 3.13.13); Tier-1 router = Gemma 4 31B via OpenRouter with DeepSeek V4 Flash as demo-day fallback; repo root is /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI (9P mitigations apply); wiki uses draft stub pages instead of dangling links; skill scripts always get explicit output paths. Full rationale: [[Bootstrap Decisions]].

## 2026-07-05 05:49 UTC — tags: defaults

User accepted all 8 MASTER_PLAN §7 defaults ('accept, may flag changes later'): Freddie SFLLD (rung 3), HF Spaces Docker SDK, Apache ECharts, LiteLLM failover, 50/25/25 scenario weights + SPF anchoring documented, PD tail level-off, HPI forward-fill, MathJax CDN for standalone notes only. Changes get superseding entries.

## 2026-07-05 05:49 UTC — tags: testing, gate

Golden-fixture precision rule: a derived value matches the notes' printed target when within one unit of the last displayed digit (notes truncate as well as round; trailing .0 floats are artifacts). Torch deferred to challenger phase. Corpus layout knowledge/{sources,corpus,index} + captions.json in git.

## 2026-07-05 16:33 UTC — tags: lgd, engine

LGD conventions (engine/lgd.py, review-verified): fit on RESOLVED train workouts only (9,496 of 11,420 - unresolved lgd_time is not a realised outcome; selection bias documented); cure threshold lgd<=0.05 (decomposition near-invariant 0.0/0.05/0.10); LGD>1 tail (14.2% of non-cures, max 3.17) handled as constant excess-loss loading +0.0255 added back after the capped fractional-logit - never clipped; LGD_cure=0 (understates ~0.04pp, reported); positive cure-stage uer coefficient disclosed not asserted.

## 2026-07-05 16:33 UTC — tags: staging, ecl, gate

Staging config defaults: ratio 2x + 0.5pp annualised add-on + 2q probation; 30DPD backstop inert on DCR (no delinquency ladder). Finding: Stage 2 EMPTY at t=20 calm under this config, 75.8% at t=40 stress - threshold sensitivity exhibit is the governance dial. ECL: reported allowance 12m(S1)/lifetime(S2/S3); EAD contractual (double-counting rule); EIR quarterly from note rate. GATE PASSED 2026-07-05: 187/187 tests, fingerprint tripwire baselined (knowledge/code_fp.json) - engine/ is FROZEN; any STRUCTURAL change requires full suite + decision entry.

## 2026-07-07 12:55 UTC — tags: documentation, mdd

Operator requirement (2026-07-05): model documentation must foreground (1) mathematical form of each model, (2) coefficients + fit stats with interpretation, (3) per-feature rationale/representation, (4) data windows + transformations/lags for all time series. Mostly satisfied in module docstrings + outputs/*/**.md + wiki pages; GAPS to close at Day-3 wrap: consolidated VARIABLE DICTIONARY exhibit (variable, source col, transformation, lag/window, rationale, expected vs fitted sign, consumer model) spanning hazard/LGD/EAD/staging/satellite; Day-4 site gets a methodology surface backed by Tier-3 wiki retrieval; formal MDD = pageindex-plus HTML export of the wiki.

## 2026-07-07 13:23 UTC — tags: rung3, isolation

Multi-dataset isolation contract (agreed 2026-07-05, binding for the Freddie rung-3 stretch and any other dataset): (1) per-dataset panel builder -> data/processed/<dataset>/panel.parquet emitting ONE canonical schema contract, asserted by a schema test; engine consumes only the contract; (2) engine stays frozen + stateless (fit objects, no module caches) - cross-dataset coefficient inheritance impossible; (3) all DCR-tuned calibrations (SICR 2x+0.5pp, cure 0.05, satellite lags, rho) are dataset-scoped decisions - rung 3 RE-ESTIMATES, never inherits, each with its own decision entry; (4) outputs and wiki pages dataset-namespaced (outputs/<dataset>/, <dataset>-panel page); (5) one uv.lock across analyses for attribution; (6) each dataset build = own workflow + adversarial reviews, worktree isolation if concurrent.

## 2026-07-07 20:12 UTC — tags: day4, agent

Coherent-shock convention (load-bearing, agent/tools_tier1.py): satellite has no unemployment term, so shock_macro applies shocks along the DFAST severe-minus-base co-movement direction (named var normalised to 1), per-concept deltas returned transparently. Also: torch pruned from Docker image (challenger-only, ~5GB); parallel shock = permanent level shift, peak_revert = ramp/hold/decay; staging frozen across shocks (inherited Day-3).
