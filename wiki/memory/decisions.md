# Decision records

Append-only. One entry per decision: context, options, the call, and why.

## 2026-07-05 05:49 UTC — tags: bootstrap, environment

Build-plan contradictions resolved (MASTER_PLAN §3.6): uv+Python 3.13 everywhere incl. Docker image (resolved 3.13.13); Tier-1 router = Gemma 4 31B via OpenRouter with DeepSeek V4 Flash as demo-day fallback; repo root is /mnt/d/Python-UV/IFRS9_ECL_Agentic_AI (9P mitigations apply); wiki uses draft stub pages instead of dangling links; skill scripts always get explicit output paths. Full rationale: [[Bootstrap Decisions]].

## 2026-07-05 05:49 UTC — tags: defaults

User accepted all 8 MASTER_PLAN §7 defaults ('accept, may flag changes later'): Freddie SFLLD (rung 3), HF Spaces Docker SDK, Apache ECharts, LiteLLM failover, 50/25/25 scenario weights + SPF anchoring documented, PD tail level-off, HPI forward-fill, MathJax CDN for standalone notes only. Changes get superseding entries.

## 2026-07-05 05:49 UTC — tags: testing, gate

Golden-fixture precision rule: a derived value matches the notes' printed target when within one unit of the last displayed digit (notes truncate as well as round; trailing .0 floats are artifacts). Torch deferred to challenger phase. Corpus layout knowledge/{sources,corpus,index} + captions.json in git.
