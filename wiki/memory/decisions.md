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
