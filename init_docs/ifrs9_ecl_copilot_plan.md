# IFRS9 ECL Copilot with Agentic Macro Scenarios — Master Build Plan

*A placement-grade capstone: a classical IFRS9 ECL engine, a deep-learning challenger, a Vasicek scenario layer, and an agentic natural-language interface — deployed as an interactive app. This document records not just **what** to build but **why each decision point is resolved the way it is**, because the reasoning is what interviews test.*

---

## 0. Operating Instructions for Claude Code (read first)

These rules govern every session that executes this plan. They exist because the operator is new to this stack — the assistant carries the burden of surfacing prerequisites, never the other way around.

### 0.1 Surface prerequisites — data and keys — before writing dependent code

After processing any prompt, and **before** writing or running code that depends on an external resource, enumerate what is needed as an explicit checklist and wait for confirmation:

- **Data:** which file, the exact download page (§2.3 / §14 links), whether registration is required, where to place it in the repo (`data/raw/`), and **why this step exists** in one plain-English sentence (e.g., "`mortgage.csv` from creditriskanalytics.net is the loan-month panel the PD model trains on — nothing downstream runs without it").
- **API keys:** which key, the exact console URL to create it (§14), which `.env` variable name it goes into, whether it costs money, and **why it's needed** (e.g., "`OPENROUTER_API_KEY` powers the Tier-1 router via paid Gemma 4 31B — without it the agent layer can't call any model").
- If a required file or key is missing at runtime, stop with a beginner-readable message ("you need to download X from Y first — here's why"), never a bare stack trace, and never a silent fallback to synthetic data.

### 0.2 Ask, don't assume

When a decision is not already pinned by this document, **ask a targeted question with a recommended default** instead of assuming. One question at a time, concrete options, plain language. This applies especially to: anything that spends paid credits; anything destructive (overwrites, deletions, `git push --force`, dropping data); any deviation from the frozen-engine gate or the 4-day scope; ambiguous file locations or naming; and any step where the operator would be surprised by the outcome. Silence is never consent — if no answer is available, choose the reversible option and flag it in `memory/decisions.md`.

### 0.3 Secrets hygiene — non-negotiable

- All secrets (API keys, tokens, email IDs, passwords) live **only** in `.env` locally and in the platform's secrets manager when deployed ([HF Spaces secrets](https://huggingface.co/docs/hub/spaces-overview#managing-secrets), Render environment variables). Commit #1 includes `.gitignore` covering `.env`, `*.key`, and credential files, plus a committed `.env.example` containing **placeholder names only**.
- Never hardcode a secret in code, notebooks, tests, the Dockerfile (no `ENV` with real values, no `COPY .env`), wiki pages, logs, agent traces, error messages, README, or any file written to outputs. Load via [`python-dotenv`](https://github.com/theskumar/python-dotenv) / `os.environ`. The Preact frontend never sees a key — every model call goes server-side through FastAPI.
- **Before every commit,** run a secret scan ([gitleaks](https://github.com/gitleaks/gitleaks), or at minimum grep for `sk-or-`, `AIza`, and similar key prefixes). If a key ever lands in git history, **rotate the key immediately** — deleting the file does not remove it from history.
- When confirming a key is loaded, mask it ("OpenRouter key ending …1234 loaded") — never echo the full value to console, chat, or logs. Remember HF Spaces repos are public by default: nothing pushed there may contain a secret.

### 0.4 Environment & machine facts (assume these; never assume otherwise)

- **Machine:** i7-12650H + RTX 4060 Mobile (8 GB VRAM). **WSL2 (Ubuntu) is the working environment**; CUDA passes through via the Windows NVIDIA driver, so PyTorch cu126 works inside WSL. GPU is fine for the MLP challenger; local Ollama fallback limited to ~4–8B quantized VL models (31B-class does not fit in 8 GB).
- **Repo location:** on the Windows filesystem, accessed from WSL at `/mnt/c/...` (operator's choice for easy Windows browsing). **Mandatory mitigations for the 9P mount:** `.gitattributes` + `git config core.autocrlf input` (LF endings on scripts/Dockerfile); Vite hot-reload needs `server.watch.usePolling: true` (inotify does not cross the mount); expect slow `npm install`/git hooks (thousands of small files) — scope gitleaks to tracked files. *Known-better alternative, offer once if friction bites:* keep the repo in WSL-native `~/projects/` and browse it from Windows via the Explorer "Linux" sidebar node or `\\wsl$\Ubuntu\...` — full speed, same browsability.
- **Python & packages:** managed with [uv](https://docs.astral.sh/uv/) inside WSL (`uv init` / `uv add` / `uv sync`; commit `uv.lock`). Python pinned on the 3.13 line — if the exact pin (e.g., 3.13.13) isn't found, pin `3.13` and let uv resolve the latest patch. PyTorch via its CUDA index (`uv add torch --index https://download.pytorch.org/whl/cu126`); never introduce TensorFlow.
- **Docker:** Docker Desktop with the WSL2 backend — local `docker build` works; the private-HF-Space remote build remains the deploy-path verification. Keep the Dockerfile on LF endings.
- **Claude Code skills:** [pageindex-plus](file:.claude/skills/pageindex-plus/SKILL.md) and [llm-wiki](file:.claude/skills/llm-wiki/SKILL.md) live at **`.claude/skills/<name>/SKILL.md`** inside the repo (project-scoped, committed, auto-discovered) — a plain repo-root `skills/` folder is *not* auto-loaded. Claude Code runs in WSL, so *personal* skills would live in WSL's `~/.claude/skills/`, not `C:\Users\...`. LF endings on any scripts inside skills.
- **Day-1 account/download checklist:** no account — `mortgage.csv` (creditriskanalytics.net) + DCR data (deepcreditrisk.com) → `data/raw/`; Fed 2026 scenario CSVs + IMF WEO → `data/scenarios/`. Free accounts — Google AI Studio key (vision), Groq key (dev loops), Hugging Face write-token (Spaces), FRED key (agent's data-fetch tool), existing OpenRouter key + GitHub. Registration-gated Freddie Mac SFLLD = stretch only. All keys → `.env` per §0.3.

---

## 1. Architecture at a Glance

### 1.1 The two governing principles (and why they exist)

**Principle 1 — Deterministic engine first, frozen behind a gate.**
The classical engine (panel → PD → LGD → EAD → staging → discounting → ECL) is built, unit-tested against worked examples, and *frozen* before a single agentic component is written. Reasoning:

- *Agents amplify whatever they sit on.* If the engine has a bug, the agent doesn't just produce a wrong number — it produces a wrong number wrapped in a fluent, confident explanation. Fluency makes errors *more* dangerous, not less. A frozen, tested engine is the only defensible base.
- *It mirrors real model governance.* In a bank, the quantitative model goes through independent validation and is version-locked before any consumption layer touches it. Reproducing that discipline is itself a portfolio differentiator: you can say "I ran my capstone like a governed model" in an interview.
- *It de-risks the timeline.* If the agentic layer slips, you still have a complete, demonstrable IFRS9 engine — which alone is a strong credit-risk portfolio piece. The reverse (agents without an engine) is a demo of nothing.

**Principle 2 — The LLM never does arithmetic.**
Every number shown to the user comes from the engine; the LLM only *routes, parameterises, and narrates*. Reasoning:

- Autoregressive LLMs generate digits token by token; they have no internal calculator, and their arithmetic reliability degrades with operand length and composition depth. For a regulated-domain artifact, even a 1% numeric hallucination rate is disqualifying.
- Auditability: a tool call like `shock_macro(var="UER", shock=+2.0)` is a logged, replayable event. Regenerating the same answer later is possible because the engine is deterministic and versioned. An LLM "recalling" a number is neither replayable nor explainable.
- This split — *LLM as interface and orchestrator, validated quant model as calculator* — is exactly the pattern banks are converging on for GenAI in risk, which makes the project legible to every risk-analytics interviewer.

### 1.2 Build flow

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1250" font-family="Segoe UI, Helvetica, Arial, sans-serif">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569"/>
    </marker>
    <marker id="arrowAmber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#ca8a04"/>
    </marker>
  </defs>
  <rect x="0" y="0" width="1000" height="1250" fill="#ffffff"/>
  <text x="500" y="40" text-anchor="middle" font-size="21" font-weight="700" fill="#0f172a">IFRS9 ECL Copilot — End-to-End Build Flow</text>
  <text x="500" y="63" text-anchor="middle" font-size="12.5" fill="#64748b">Deterministic engine first · agents as orchestrators · the LLM never does arithmetic</text>
  <rect x="40" y="95" width="610" height="86" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="95" width="5" height="86" rx="2" fill="#64748b"/>
  <text x="58" y="121" font-size="14" font-weight="700" fill="#475569">PHASE 0 — SETUP</text>
  <text x="58" y="143" font-size="11.5" fill="#334155">Repo + test scaffold · all API keys day one (Gemini, Groq, OpenRouter, Cerebras) + failover router</text>
  <text x="58" y="162" font-size="11.5" fill="#334155">llm-wiki init over repo + notes · pageindex-plus ingest of the document corpus</text>
  <line x1="345" y1="181" x2="345" y2="205" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="207" width="610" height="124" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="207" width="5" height="124" rx="2" fill="#2563eb"/>
  <text x="58" y="233" font-size="14" font-weight="700" fill="#2563eb">PHASE 1 — DATA FOUNDATION</text>
  <text x="58" y="255" font-size="11.5" fill="#334155">Loan-month panel: CRA/DCR 50k×60 prototype → Freddie Mac SFLLD sample (truncation + censoring)</text>
  <text x="58" y="274" font-size="11.5" fill="#334155">Re-flag default at 90 DPD from monthly delinquency status (agency data anchors on 180 DPD)</text>
  <text x="58" y="293" font-size="11.5" fill="#334155">Macro merge: FRED/ALFRED · BLS LAUS · FHFA HPI · PMMS — lag 1–2q · keep macro-at-origination</text>
  <text x="58" y="312" font-size="11.5" fill="#334155">Scenario paths: Fed DFAST CSVs · IMF WEO baseline · SPF-derived upside · weights documented</text>
  <line x1="345" y1="331" x2="345" y2="355" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="357" width="610" height="104" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="357" width="5" height="104" rx="2" fill="#0891b2"/>
  <text x="58" y="383" font-size="14" font-weight="700" fill="#0891b2">PHASE 2 — EDA &amp; WATERFALLS</text>
  <text x="58" y="405" font-size="11.5" fill="#334155">Sample/eligibility waterfall — every exclusion counted and justified (model-doc exhibit)</text>
  <text x="58" y="424" font-size="11.5" fill="#334155">Vintage default curves · seasoning hump · roll/cure rates · prepayment incidence</text>
  <text x="58" y="443" font-size="11.5" fill="#334155">Macro sanity: ADF + KPSS · breaks (2008, 2020) · FRED vs primary source · ALFRED revisions</text>
  <line x1="345" y1="461" x2="345" y2="485" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="487" width="610" height="124" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="487" width="5" height="124" rx="2" fill="#7c3aed"/>
  <text x="58" y="513" font-size="14" font-weight="700" fill="#7c3aed">PHASE 3 — CLASSICAL ECL ENGINE (deterministic core)</text>
  <text x="58" y="535" font-size="11.5" fill="#334155">PD: discrete-time cloglog hazard + competing-risk prepayment → lifetime term structure</text>
  <text x="58" y="554" font-size="11.5" fill="#334155">LGD: cure × severity, EIR-discounted · EAD: amortisation/prepay, CCF for revolvers</text>
  <text x="58" y="573" font-size="11.5" fill="#334155">Staging: relative lifetime-PD SICR + 30 DPD backstop · ECL = Σ S(t−1)·λ·LGD·EAD·disc</text>
  <text x="58" y="592" font-size="11.5" fill="#334155">Interpretation: hazard ratios · double trigger (LTV × UER) · seasonality dummies · APC caveat</text>
  <line x1="345" y1="611" x2="345" y2="621" stroke="#475569" stroke-width="2"/>
  <rect x="145" y="622" width="400" height="24" rx="12" fill="#fef2f2" stroke="#dc2626"/>
  <text x="345" y="638" text-anchor="middle" font-size="11.5" font-weight="600" fill="#dc2626">GATE — engine frozen &amp; unit-tested (worked examples as fixtures)</text>
  <line x1="345" y1="646" x2="345" y2="655" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="657" width="610" height="86" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="657" width="5" height="86" rx="2" fill="#db2777"/>
  <text x="58" y="683" font-size="14" font-weight="700" fill="#db2777">PHASE 4 — DEEP LEARNING CHALLENGER</text>
  <text x="58" y="705" font-size="11.5" fill="#334155">Neural hazard / LSTM PD term structure vs the logistic champion (champion–challenger)</text>
  <text x="58" y="724" font-size="11.5" fill="#334155">SHAP · partial dependence · monotonic constraints · AUC / calibration / PSI validation suite</text>
  <line x1="345" y1="743" x2="345" y2="767" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="769" width="610" height="104" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="769" width="5" height="104" rx="2" fill="#ea580c"/>
  <text x="58" y="795" font-size="14" font-weight="700" fill="#ea580c">PHASE 5 — SCENARIO LAYER</text>
  <text x="58" y="817" font-size="11.5" fill="#334155">Invert Vasicek → recover Zₜ · calibrate ρ · satellite model on macro drivers (ARDL/ECM hygiene)</text>
  <text x="58" y="836" font-size="11.5" fill="#334155">Scenario macro paths → Z paths → PIT PD / migration matrices → scenario-conditional ECL</text>
  <text x="58" y="855" font-size="11.5" fill="#334155">Probability-weighted ECL &gt; base case (Jensen, ≈1.9× in worked example) — dashboard exhibit</text>
  <line x1="345" y1="873" x2="345" y2="897" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="899" width="610" height="180" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="899" width="5" height="180" rx="2" fill="#16a34a"/>
  <text x="58" y="925" font-size="14" font-weight="700" fill="#16a34a">PHASE 6 — AGENTIC LAYER (LangGraph)</text>
  <text x="58" y="946" font-size="11.5" fill="#334155">Router classifies the question and picks a tier — the engine returns every number</text>
  <rect x="52" y="959" width="188" height="80" rx="6" fill="#f0fdf4" stroke="#86efac"/>
  <text x="146" y="979" text-anchor="middle" font-size="11.5" font-weight="700" fill="#15803d">TIER 1 · Parameterized tools</text>
  <text x="146" y="998" text-anchor="middle" font-size="10.5" fill="#334155">shock_macro · reweight_scenarios</text>
  <text x="146" y="1014" text-anchor="middle" font-size="10.5" fill="#334155">rerun_ecl · decompose_waterfall</text>
  <rect x="252" y="959" width="188" height="80" rx="6" fill="#f0fdf4" stroke="#86efac"/>
  <text x="346" y="979" text-anchor="middle" font-size="11.5" font-weight="700" fill="#15803d">TIER 2 · Sandboxed code</text>
  <text x="346" y="998" text-anchor="middle" font-size="10.5" fill="#334155">read-only pandas on output tables</text>
  <text x="346" y="1014" text-anchor="middle" font-size="10.5" fill="#334155">generated code shown for audit</text>
  <rect x="452" y="959" width="188" height="80" rx="6" fill="#f0fdf4" stroke="#86efac"/>
  <text x="546" y="979" text-anchor="middle" font-size="11.5" font-weight="700" fill="#15803d">TIER 3 · Doc retrieval</text>
  <text x="546" y="998" text-anchor="middle" font-size="10.5" fill="#334155">wiki-pattern graph retrieval</text>
  <text x="546" y="1014" text-anchor="middle" font-size="10.5" fill="#334155">page#heading citations</text>
  <text x="58" y="1062" font-size="11.5" fill="#334155">Out-of-scope → explicit refusal (governance feature) · tool-call log = reproducible audit trail</text>
  <line x1="345" y1="1079" x2="345" y2="1103" stroke="#475569" stroke-width="2" marker-end="url(#arrow)"/>
  <rect x="40" y="1105" width="610" height="104" rx="8" fill="#f8fafc" stroke="#cbd5e1"/>
  <rect x="40" y="1105" width="5" height="104" rx="2" fill="#dc2626"/>
  <text x="58" y="1131" font-size="14" font-weight="700" fill="#dc2626">PHASE 7 — APP &amp; DEPLOY</text>
  <text x="58" y="1153" font-size="11.5" fill="#334155">Dashboard: scenario sliders · ECL movement waterfall · live agent trace · chat interface</text>
  <text x="58" y="1172" font-size="11.5" fill="#334155">Preact + Vite SPA served by FastAPI · multi-stage Docker (port 7860) · HF Spaces Docker SDK / Render — live CV link</text>
  <text x="58" y="1191" font-size="11.5" fill="#334155">Demo script · README · CV bullet (AUC, tools orchestrated, turnaround time, ≈1.9× Jensen exhibit)</text>
  <rect x="690" y="95" width="270" height="1114" rx="8" fill="#fefce8" stroke="#ca8a04" stroke-dasharray="6 4"/>
  <text x="825" y="123" text-anchor="middle" font-size="14" font-weight="700" fill="#a16207">CONTINUOUS — llm-wiki</text>
  <text x="825" y="141" text-anchor="middle" font-size="10.5" fill="#a16207">runs alongside every phase</text>
  <text x="706" y="172" font-size="11.5" font-weight="600" fill="#713f12">Each session:</text>
  <text x="706" y="190" font-size="11.5" fill="#57534e">compile pages → wiki_graph.py</text>
  <text x="706" y="208" font-size="11.5" fill="#57534e">→ wiki_audit.py (must be clean)</text>
  <text x="706" y="242" font-size="11.5" font-weight="600" fill="#713f12">memory/decisions.md records:</text>
  <text x="706" y="260" font-size="11.5" fill="#57534e">90DPD re-flag · cloglog choice</text>
  <text x="706" y="278" font-size="11.5" fill="#57534e">macro lags · scenario weights</text>
  <text x="706" y="312" font-size="11.5" font-weight="600" fill="#713f12">Pages update-in-place =</text>
  <text x="706" y="330" font-size="11.5" fill="#57534e">the IFRS9 model documentation</text>
  <text x="706" y="348" font-size="11.5" fill="#57534e">(waterfalls, variable rationale,</text>
  <text x="706" y="366" font-size="11.5" fill="#57534e">validation results, overlays)</text>
  <text x="706" y="400" font-size="11.5" font-weight="600" fill="#713f12">index.md + memory/log.md =</text>
  <text x="706" y="418" font-size="11.5" fill="#57534e">new-session state restore</text>
  <text x="706" y="436" font-size="11.5" fill="#57534e">(never re-read raw sources)</text>
  <text x="706" y="470" font-size="11.5" font-weight="600" fill="#713f12">Ingestion partners:</text>
  <text x="706" y="488" font-size="11.5" fill="#57534e">pageindex-plus → doc corpus</text>
  <text x="706" y="506" font-size="11.5" fill="#57534e">scan_code.py → code call graph</text>
  <text x="706" y="965" font-size="11.5" font-weight="600" fill="#713f12">Wiki pages become the corpus</text>
  <text x="706" y="983" font-size="11.5" font-weight="600" fill="#713f12">behind query_model_docs:</text>
  <line x1="700" y1="999" x2="646" y2="999" stroke="#ca8a04" stroke-width="2" stroke-dasharray="5 4" marker-end="url(#arrowAmber)"/>
  <text x="706" y="1190" font-size="10.5" font-style="italic" fill="#a16207">Serves knowledge, never numbers —</text>
  <text x="706" y="1205" font-size="10.5" font-style="italic" fill="#a16207">the engine stays deterministic.</text>
</svg>

*The inline SVG above renders in VS Code preview, Obsidian, Typora, and any markdown→HTML pipeline. GitHub strips inline SVG from README rendering — for GitHub, reference the standalone `ecl_copilot_flowchart.svg` with an image link instead.*

---

## 2. Data Foundation

### 2.1 Decision: why mortgages (and not cards, personal loans, or corporates)

- **Public loan-level *panel* data essentially only exists for US mortgages.** The GSEs (Freddie/Fannie) publish monthly performance histories per loan to support credit-risk-transfer investors; no equivalent exists for cards or personal loans (Lending Club gives final outcomes, not monthly states; Home Credit is application-level). A lifetime PD term structure *requires* the monthly state history — so the asset class is effectively chosen for you.
- **Collateral makes LGD a real model.** Mortgage LGD depends on HPI-indexed collateral, giving you a second macro-sensitive component and the PD–LGD co-movement story. Unsecured LGD is closer to a constant.
- **The histories span a full cycle** (1999→): you get the 2008–10 crisis for identification, 2020 for a regime-break case study, and calm periods for baseline behaviour. Macro-sensitivity models can only be estimated on data that contains macro variation.
- Corporate loan-level data is scarce/paywalled; the corporate route (Merton, agency transition matrices) is a different project.

### 2.2 Decision: why a loan-month panel and a survival model (not a 12-month logistic)

The classic scorecard approach — one row per loan, 12-month default flag, logistic regression — is what most public tutorials do. It is the wrong shape here, for four reasons:

1. **IFRS9 Stage 2 requires *lifetime* ECL**, i.e. a marginal PD for every future period, not a single 12-month probability. Stacking separate logits per horizon produces incoherent term structures (survival probabilities that don't multiply consistently); one hazard model produces the entire curve S(t|x)=∏(1−λₖ) by construction.
2. **Censoring and truncation are first-class citizens.** Loans that prepay or mature before defaulting are *right-censored*, not "non-defaults"; loans already alive at the observation-window start are *left-truncated*. A cross-sectional logit silently mishandles both, biasing PDs. The panel + hazard framework handles them natively — and mishandling them is *the* classic survival-model bug to name-drop.
3. **Time-varying covariates are the whole point.** Updated LTV, current delinquency state, and this-quarter's unemployment can only enter a model whose observation unit is loan-month.
4. **Scenario conditioning needs a place for macros to enter *over time*.** The hazard λₜ = f(loan covariates, macroₜ) is exactly the object a scenario path perturbs, period by period. There is no analogous entry point in a single-shot logit.

**Why the cloglog link specifically:** the complementary log-log is the exact grouped-duration analogue of the continuous-time Cox model — discrete monthly observation of an underlying continuous default process. Logit is an acceptable approximation at small hazards; cloglog is the theoretically clean choice and costs nothing. Saying *why* is an easy interview differentiator.

**Why competing risks (prepayment) is non-optional:** prepayment and default compete — a loan that refinances can never default. Treating prepaid loan-months as ordinary survivals biases the default hazard, and ignoring prepayment overstates late-horizon EAD (balances that would have gone) and hence lifetime ECL. Estimate cause-specific hazards for both events; the Deep Credit Risk panel is built for exactly this.

### 2.3 The dataset ladder (prototype → industry scale) and why to climb it in order

| Rung | Dataset | Why this rung exists |
|---|---|---|
| 1 | **Credit Risk Analytics `mortgage`** (Baesens–Rösch–Scheule, [creditriskanalytics.net](http://www.creditriskanalytics.net), free) — 50,000 US mortgage borrowers × 60 periods, origination + performance, with `gdp_time`, `uer_time`, `hpi_time` **already merged**, realistic left truncation & right censoring | *Isolates modelling risk from engineering risk.* The macro merge is the single most bug-prone step in the whole pipeline; starting on a pre-merged panel means your first hazard model tests your modelling code, not your join logic. Small enough to iterate in seconds. |
| 2 | **Deep Credit Risk data** (Rösch–Scheule, [deepcreditrisk.com](https://www.deepcreditrisk.com), free) — same universe expanded: ~15,000 defaults **with workout losses**, payoff events, exposures | Unlocks LGD and EAD from the *same* panel, plus competing-risk prepayment. You can complete the entire engine on this rung. |
| 3 | **[Freddie Mac SFLLD](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset)** (free registration) — ~55M mortgages 1999→; quarterly origination files + monthly performance to disposition; **actual-loss fields** (net sale proceeds, MI/non-MI recoveries, expenses) | Industry credibility ("I processed GSE loan-level data") and genuine workout-LGD from realised cash flows. Start with the ~50k-loan **sample files** — full files are tens of GB and add nothing methodological. |
| 3′ | **[Fannie Mae SFLP](https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data)** (free registration) — single-file 108-field layout | Interchangeable alternative; pick one, don't do both. |

**Macro conditioning per rung — which variables, which transformations, which lags, and why they fit each dataset:**

| Rung | Macro set & frequency | Transformations that fit | Lag structure & why |
|---|---|---|---|
| 1 — CRA `mortgage` | National `uer_time`, `gdp_time`, `hpi_time`, pre-merged on the panel's abstract quarterly time index | UER in level **and** change; GDP and HPI as growth rates (log-differences) — trending *levels* are nonstationary and would hand the hazard a spurious trend to fit | Build lags *inside* the panel (`groupby(loan_id).shift(1–2)`); 1–2 periods proxies publication + transmission delay. Calendar dates are abstracted here, so ALFRED vintages don't apply — this rung tests lag **mechanics** and coefficient signs, not real-time realism |
| 2 — Deep Credit Risk | Same national set, now feeding **two** models (PD and LGD/cure) | PD: as rung 1. LGD/cure: **cumulative** HPI change over the workout window (HPI at resolution ÷ HPI at default) and UER *at the default date* — severity depends on how far collateral moved over the whole recovery period, not on any single quarter's growth | PD lags as rung 1. LGD needs no lag at all — it needs **alignment** to default and resolution dates (window aggregation, not shifting), which is a different discipline and the reason rung 2 exists |
| 3/3′ — Freddie/Fannie | State-level LAUS UER (monthly), FHFA state/MSA HPI (quarterly), PMMS rate (weekly), national series via FRED — merged on property state + calendar month | State UER level and 12-month change (the cash-flow channel *where it actually varies* — national averages smear it out); **HPI_t/HPI_orig × original LTV = updated LTV**, the single most important transformed variable in the model; 4-quarter HPI growth as a period covariate; rate incentive = contract rate − current PMMS (drives the prepayment hazard) | Publication lags are now real: LAUS ~3 weeks after month-end, FHFA HPI ~2 months after quarter-end — so lag ≥1 month/quarter mechanically, then add transmission (job loss → 90 DPD takes months; test 3/6/12-month lags, choose by fit *and* story). Frequency alignment needed: step quarterly HPI to the monthly panel (document forward-fill vs interpolation). ALFRED vintages apply at this rung — honest backtesting becomes possible |

The general principle the table encodes: **a dataset's frequency, geography, and date-realism determine which macro transformations and lags are even meaningful.** National series on an abstract clock (rung 1) can only validate mechanics and signs; workout data (rung 2) changes macros from lagged covariates into window aggregates; state-level, calendar-dated data (rung 3) is what unlocks geographic identification, publication-lag realism, and vintage-aware backtests — which is exactly why the rungs are climbed in this order.

The ladder is also a schedule hedge: each rung leaves you with a complete, demonstrable artifact if later rungs slip.

### 2.4 Decision: the default definition (90 DPD re-flag, not a conversion factor)

Agency data anchors "credit events" at **180 DPD** (the CRT/STACR convention); IFRS9/Basel default is **90 DPD + materiality + unlikeliness-to-pay**. Two routes exist, and the choice matters:

- **Route 1 — re-flag and re-estimate (chosen).** You hold the monthly delinquency status, so redefine default at 90 DPD across the whole history and re-estimate everything. It is *exact* — on loan-level data it is literally a threshold change — and it is what EU regulators and model vendors prescribe.
- **Route 2 — roll-rate bridge (know it, don't use it).** When only D180-calibrated parameters exist: PD₉₀ = PD₁₈₀ / R where R = P(reach 180 | reached 90) chained from delinquency-bucket roll rates, with LGD₉₀ scaled down symmetrically. **The intuition worth internalising:** moving the boundary earlier catches more "defaults", but the extra ones are mostly loans that would have cured — so PD rises (~×1.66 at R≈0.6), LGD falls (~×0.6), and **expected loss is almost exactly preserved** when cures are loss-free. The decomposition shifts; the economics barely move. R is segment- and cycle-dependent (roll-through jumps in downturns; GSE mortgages R≈0.8, unsecured retail far lower), which is why the single-factor bridge is fragile and Route 1 wins whenever the data allows.

Attach **cure/probation periods** to the flag so loans don't oscillate across the boundary — otherwise a borrower bouncing between 85 and 95 DPD generates spurious default/cure churn.

### 2.5 Macro data and the merge recipe — each rule has a reason

| Source | Series | Why it's in |
|---|---|---|
| [FRED](https://fred.stlouisfed.org) / [ALFRED](https://alfred.stlouisfed.org) | National GDP, unemployment, rates, CPI | The workhorse conditioning set; [`fredapi`](https://github.com/mortada/fredapi) / [`pandas-datareader`](https://pandas-datareader.readthedocs.io) against the [FRED API](https://fred.stlouisfed.org/docs/api/fred/) (free key) |
| [BLS LAUS](https://www.bls.gov/lau/) | **State-level** unemployment, monthly | The Freddie file carries property state — and state unemployment was the single most powerful macro driver in the landmark 120-million-loan deep-learning mortgage study (Sirignano–Sadhwani–Giesecke, [arXiv:1607.02470](https://arxiv.org/abs/1607.02470)). National averages smear out exactly the variation that identifies the cash-flow default channel. |
| [FHFA HPI](https://www.fhfa.gov/data/hpi) (state/MSA) + [Case-Shiller via FRED](https://fred.stlouisfed.org/series/CSUSHPINSA) | House prices | Collateral indexation → updated LTV → both PD (strategic default) and LGD (severity). |
| [Freddie Mac PMMS](https://www.freddiemac.com/pmms) | Mortgage rates | The prepayment incentive (contract rate − current market rate) — the main driver of the competing risk. |

**Merge rules and their reasoning:**

- **Lag macros 1–2 quarters.** Two effects stack: *publication delay* (Q1 GDP isn't known in Q1 — using contemporaneous values leaks the future into the model) and *transmission lag* (job loss precedes missed payments by months: savings buffers, grace periods). Choosing the lag by fit *and* by story is the model-documentation move.
- **Store macro-at-origination columns.** The SICR test is "lifetime PD *now* vs lifetime PD *at initial recognition*" — you cannot run the comparison later if you didn't freeze origination-date conditions into the panel now. Retrofitting this is painful; storing it is free.
- **Use ALFRED vintages for anything backtested.** FRED silently revises history (GDP especially). A model backtested on today's revised series "knew" things nobody knew at the time — quiet look-ahead bias. ALFRED serves the series *as published on any given date*, so the backtest honestly reconstructs "information available at the reporting date". Mentioning this unprompted signals real-world modelling maturity.
- **Index collateral:** HPI(now)/HPI(orig) × original LTV ≈ updated collateral cover — one line that powers both the double-trigger PD interaction and the LGD severity model.

### 2.6 Scenario paths and the probability-weights decision

| Source | Role | Why |
|---|---|---|
| **[Fed DFAST supervisory scenarios](https://www.federalreserve.gov/publications/2026-stress-test-scenarios.htm)** (CSVs each February via the [DFAST hub](https://www.federalreserve.gov/supervisionreg/dfa-stress-tests-2026.htm); 2026 set finalised 4 Feb 2026, paths 2026Q1–2029Q1) | Downside path(s) | 28 variables on quarterly paths, designed by a supervisor to be coherent (unemployment, HPI, GDP, rates move *together* sensibly). Hand-rolling a coherent multivariate stress path is genuinely hard — don't. |
| **[IMF WEO](https://www.imf.org/en/Publications/WEO) / consensus forecasts** | Baseline | DFAST's "baseline" is a supervisory convention, not a best-estimate forecast; IFRS9 wants an unbiased central path. |
| **[Philadelphia Fed SPF](https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters) percentiles** | Upside | The forecaster distribution gives you a defensible optimistic path without inventing one. |
| **[EBA/ECB](https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-stress-testing), [Bank of England](https://www.bankofengland.co.uk/stress-testing)** | Alternates | Country-granular; useful if you want an EU flavour. |
| **[RBI DBIE](https://data.rbi.org.in)** | India replica | Supports an Ind AS 109-framed version of the same pipeline — a nice "I can localise this" appendix. |

**Why weights are judgmental (and why that's fine):** scenario probabilities are not statistically identified — there is no dataset of "how likely was the severe scenario". Real banks set them by governance committee (e.g., 50/25/25) and *document the rationale*; auditors test the documentation, not the number. Reproducing that — a stated rationale, a sensitivity table showing ECL under alternative weights — is more realistic than pretending to estimate them. (A defensible enhancement: anchor weights to SPF distribution percentiles.)

### 2.7 Backtest design — and why 2020 is an exhibit, not a validation window

Train to a cutoff (e.g., ≤2018), hold out subsequent quarters, condition on ALFRED-vintage macro. **Treat COVID separately:** in 2020, forbearance programmes let borrowers stop paying without being reported delinquent — the delinquency→default link that the entire model rests on was administratively severed. A model "failing" on 2020 is not evidence against the model; it is evidence of a regime break, which is precisely what management overlays exist for. Presenting 2020 as an overlay case study (trigger, quantification basis, exit criteria) turns an embarrassment into a sophistication signal.

---

## 3. EDA, Profiling & Waterfalls

### 3.1 Two waterfalls — different audiences, both mandatory exhibits

1. **Sample/eligibility waterfall (input side).** Raw record count → each exclusion step, with counts and a stated reason per step (missing key fields, product exclusions, incomplete workouts dropped before LGD severity, servicing-transfer gaps). *Why:* it forces you to justify every filter — silent exclusions are how selection bias enters a model unexamined — and it is a standard exhibit in every real model development document. Example of a reasoned exclusion: loans with missing net sale proceeds must be dropped before computing LGD severity, or severity is biased by half-resolved cases.
2. **ECL movement waterfall (output side).** Decompose period-on-period allowance change into: stage migration, macro/scenario update, model change, portfolio growth/run-off. *Why:* this is how ECL is actually explained to CFOs and auditors (it mirrors the IFRS 7 movement disclosure), and it becomes the dashboard's centrepiece visual — the agent's `decompose_waterfall` tool returns exactly this.

### 3.2 The diagnostic EDA set — each chart is a *test*, not decoration

The organising idea: **each chart has a known expected shape; deviation means a data bug, not an insight.** This converts EDA from ritual into verification.

| Chart | Expected shape | If it doesn't appear |
|---|---|---|
| Default rate by calendar quarter | Spike 2008–10; distortion in 2020 | Default flag or date join is broken |
| Default rate by loan age (seasoning) | Hump: hazard rises ~years 2–5, then falls | Age computation or truncation handling is wrong. *Intuition:* very young loans rarely default (borrowers were just underwritten and have savings); very old survivors are self-selected good risks; trouble concentrates in between |
| Cumulative default curves by origination vintage | 2006–07 cohorts visibly worst | If 2006–07 doesn't stand out, the panel is mis-built — this is the single sharpest data-quality test available |
| Delinquency roll rates (current→30→60→90) & cure rates | Roll-forward worsens in downturns; meaningful cures from 90 DPD (~20% for GSE mortgages) | Delinquency-state coding errors |
| Prepayment incidence vs rate incentive | Prepayment surges when contract rate ≫ market rate | PMMS merge or incentive sign is wrong |
| Univariate FICO / LTV / DTI distributions | Known ranges; FICO left-skewed, LTV massed near 80 | Field-mapping errors (agency layouts shift across vintages) |

### 3.3 Econometric sanity for the macro layer — why each test is there

- **ADF + KPSS together**, not either alone: their nulls are *complementary* (ADF null = unit root; KPSS null = stationarity). Agreement is evidence; disagreement flags borderline series. Regressing a credit index on a nonstationary macro level invites spurious regression — the satellite would "fit" beautifully and forecast garbage.
- **Structural-break tests (Chow, CUSUM) around 2008 and 2020:** a satellite fitted through both crises without break handling misbehaves in *both* directions — it under-predicts stress (2008 averaged in) and over-predicts calm (2020's administrative distortions). Crisis dummies or sample splits are the standard fix; *saying why* is the interview answer.
- **Cross-verify FRED against primary sources** (BLS for unemployment, FHFA for HPI) for at least two series: cheap insurance against ID-mapping mistakes, and it demonstrates data-lineage discipline.
- **Inspect revision magnitude in ALFRED** for GDP and unemployment: seeing that "first-print GDP" and "today's GDP" differ by whole percentage points makes the look-ahead-bias argument concrete rather than theoretical.

**The universal intuition test:** every chart must be narratable as one of three stories — *negative equity* (collateral channel), *payment shock* (affordability channel), or *unemployment spell* (cash-flow channel). A pattern that maps to none of these is, until proven otherwise, a bug.

---

## 4. The Classical ECL Engine

Core identity:  **ECL = Σₜ S(t−1)·λₜ · LGDₜ · EADₜ · (1+EIR)^(−t)**, with 12-month ECL = the first 12 months of the same sum (losses from defaults *possible* in the next 12 months — not truncated cash shortfalls).

### 4.1 PD — discrete-time hazard

cloglog(λᵢₜ) = baseline(loan age) + β′xᵢₜ + γ′mₜ, where xᵢₜ are loan/borrower covariates (possibly time-varying: updated LTV, delinquency state) and mₜ are lagged macro drivers. Then S(t|x) = ∏ₖ≤ₜ(1−λₖ) and marginal PDs S(t−1)λₜ feed the ECL sum directly. Distinguish carefully in code and in speech: *conditional/forward PD* λₜ, *marginal PD* S(t−1)λₜ, *cumulative PD* 1−S(t) — confusing these is the most common junior error.

**Extrapolation is a named model risk:** hazards are only observed to the panel's maximum age; beyond it, small hazard errors compound multiplicatively over long horizons. Document the tail assumption explicitly (level-off vs decay to a long-run rate) — having *a documented assumption* is the point; the specific choice matters less.

### 4.2 LGD — two stages, because the data is bimodal

Realised loss rates cluster at ~0 (cures, full recoveries) and at high severities — a single regression through a bimodal target predicts the probability-weighted middle, a value that almost never occurs. Hence: **P(cure) model × severity-given-liquidation model.** Severity uses EIR-discounted workout cash flows (recoveries minus direct/indirect costs, over time-to-resolution); the HPI-indexed collateral value is the dominant severity driver — the same HPI series that drives PD, which is *why* PD and LGD co-move in downturns (downturn LGD). Note the agency-data subtlety: supplied nominal severities embed a lost-interest proxy rather than IFRS9 EIR discounting — discount the dated cash-flow components yourself.

### 4.3 EAD — the forgotten multiplier

Amortising loans: projected outstanding balance along the contractual schedule, *adjusted for prepayment* (SMM/CPR hazard with rate-incentive and seasoning covariates — the same competing-risk machinery as §4.1). Missing the prepayment adjustment overstates late-horizon EAD and hence lifetime ECL — balances the model thinks are still there have actually refinanced away. Revolvers: EAD = drawn + CCF × headroom, CCF estimated from defaulted accounts' drawdown behaviour.

### 4.4 Staging (SICR) — why a *relative* test

Stage 2 is triggered by a **significant increase in credit risk since initial recognition**, so the test compares lifetime PD *now* against lifetime PD *at origination* (this is what the stored macro-at-origination columns enable). Why relative, not absolute: a loan originated at high PD hasn't *deteriorated* just by being risky — IFRS9 tracks deterioration, not level. Standard architecture: relative-PD threshold (doubling convention + absolute add-on, grade-sensitive so thin-PD loans don't flip on noise), qualitative triggers, the **30 DPD backstop** (deliberately hard to game), and cure/probation periods so loans don't oscillate between stages. Expose the Stage-2 population size as a dashboard sensitivity — the threshold choice is a genuine trade-off (early warning vs P&L volatility) and showing the trade-off is the mature move.

### 4.5 Interpreting the fitted model — variable families mapped to the real world

exp(β) ≈ hazard ratio (multiplicative effect on the per-period default intensity).

| Family | Variables | The real-world story |
|---|---|---|
| Static origination | FICO, original LTV, DTI, occupancy, purpose, documentation | Ability/willingness to pay; equity cushion; payment burden. Investor-owned properties default more *strategically* (no home to lose); cash-out refis signal extraction of equity |
| Time-varying loan | Loan age (spline/dummies = the seasoning baseline), **updated LTV**, delinquency state, rate incentive | Updated LTV is the strategic-default trigger: once equity is negative, default becomes economically rational |
| Macro (period) | State unemployment, HPI growth, rates — lagged 1–2q | Unemployment = cash-flow channel; HPI = collateral channel (hits PD *and* LGD); rates = affordability and prepayment |
| Season / incident / cohort | Month dummies; crisis dummies (2008–09, 2020); vintage dummies | Q1 tax refunds cure delinquencies; post-holiday budgets miss payments. Crisis dummies absorb regime effects macros can't. Vintage dummies capture underwriting-standard cohorts (2006–07 = the low-doc era) |

**The double trigger — the single best interaction story in retail credit:** borrowers rarely default from negative equity alone (they keep paying for the home) or a cash-flow shock alone (they sell at a gain or draw savings). The *combination* — can't pay **and** owes more than the house is worth — is lethal. Implemented as updated-LTV × unemployment (or × ΔHPI). If your model has one interaction term, it is this one, and being able to *tell the story* is worth more than the coefficient.

**The APC identification caveat:** loan **A**ge + origination **C**ohort = calendar **P**eriod, exactly. Age, period, and cohort effects are therefore perfectly collinear — one must be constrained (e.g., vintage dummies grouped, or period effects loaded onto macros). Every seasoning-curve model faces this; knowing it unprompted is a senior-level tell.

---

## 5. Deep Learning Challenger

**Decision: DL is the challenger, never the champion — why:**
- *Governance realism:* no validation function signs off an unconstrained network as the provisioning model; the realistic deployment is challenger/benchmarking — so build it that way and say so.
- *Attribution:* the logistic hazard gives you the baseline; the challenger's job is to reveal what the linear model misses — interactions and nonlinearities (the network discovering the double trigger on its own is a lovely exhibit) and path dependence (an LSTM reading the delinquency *trajectory*, not just the current state: a loan that went 30→current→30→60 is different from one at a clean 60).
- *The literature supports exactly this framing:* the Sirignano–Sadhwani–Giesecke 120M-loan study ([arXiv:1607.02470](https://arxiv.org/abs/1607.02470)) found neural hazards materially outperform logistic ones, with state unemployment the most powerful covariate — cite it as the design precedent.

**Constraints and diagnostics — why each:**
- **Monotonic constraints** (PD ↑ in LTV, ↓ in FICO): an unconstrained net *will* find pockets where PD falls as LTV rises (data noise), and any validator will find them too. Enforcing economically-signed monotonicity is standard model-risk practice and a great line: "I constrained the network the way validation would have forced me to."
- **SHAP + partial dependence:** global ranking sanity (macro and LTV families should dominate) and shape inspection (the seasoning hump should reappear).
- **Champion–challenger scorecard:** AUC/Gini uplift, calibration (Hosmer–Lemeshow, reliability curves), stability (PSI, 0.10/0.25 bands), **out-of-time** as the headline (in-time fit and out-of-time generalisation are different claims — report both, separately), plus staging-effectiveness impact: does the challenger move loans across the Stage-2 boundary, and is the movement defensible?

---

## 6. Scenario Layer — Vasicek Conditioning and Jensen's Inequality

### 6.1 Why the Vasicek/Z framework (the conceptual core of the project)

The problem: the hazard model produces (roughly) through-the-cycle PDs; IFRS9 wants **point-in-time, scenario-conditional** PDs. The Vasicek one-factor framework (Vasicek 2002, *The Distribution of Loan Portfolio Value*, Risk 15(12)) is the standard bridge because it gives a *single dial* — the systematic factor Z — that consistently conditions *everything*:

**PD_PIT(Z) = Φ[(Φ⁻¹(PD_TTC) − √ρ·Z) / √(1−ρ)]**, with the anchor property **E_Z[PD_PIT] = PD_TTC** (the PIT PDs average back to the TTC level over the cycle — the internal-consistency check to verify numerically).

*The intuition:* each borrower defaults if a latent asset value falls below a threshold; asset values share a common factor Z (the economy) with loading ρ. Conditioning on "the economy is at Z" shifts every borrower's default threshold simultaneously — one number moves the whole portfolio coherently, including migration matrices (condition the whole transition matrix on the same Z). This coherence is why the framework, and not ad-hoc scalar multipliers, is the professional answer.

### 6.2 Estimating Z and ρ (Belkin / Z-shift), and the satellite model

From a history of portfolio default rates, invert the Vasicek formula each period to recover Zₜ; calibrate ρ so Var(Zₜ)=1 (the Z-shift method of Belkin–Suchower–Forest 1998, *CreditMetrics Monitor*). Then the **satellite model** regresses Zₜ on macro drivers — this is the hinge that converts a macro scenario path into a Z path into scenario-conditional PD term structures ([statsmodels](https://www.statsmodels.org) covers ADF/KPSS, ARDL bounds, and the diagnostics below).

Satellite hygiene, in the order an interviewer expects it: stationarity (ADF+KPSS; difference I(1) series or model cointegration), **ARDL bounds** when regressors mix I(0)/I(1) (the error-correction term must be negative and significant — its magnitude is the adjustment speed), lag selection by AIC/SBC, crisis dummies/break tests, and a **logit/probit transform of the target** so fitted values cannot escape [0,1] under an extreme scenario — an unbounded linear satellite will cheerfully predict a negative default rate in the upside scenario, in front of your interviewer.

Known caveat to name: naïve TTC↔PIT round-trips are inconsistent if ρ, the default definition, or the cycle index differ between legs — fix conventions once and test the round trip.

**The credit-cycle exhibit (free by-product of this step):** plotting the recovered Zₜ-implied PIT PD path against the flat TTC anchor across the panel's 60 quarters reproduces the textbook PIT-vs-TTC credit-cycle chart *from your own engine* — the 2008–10 hump appears exactly where the stylized diagrams put the recession peak. It's a stronger exhibit than any textbook version because it's generated, not drawn, and it visually answers both "what's the difference between PIT and TTC?" and "show me your model responds to the cycle" in one chart. A hybrid PD variant (condition on a damped αZ, 0 < α < 1) can be overlaid later if an interviewer raises the Basel-stability-vs-IFRS9-responsiveness blend — worth knowing as a talking point even unimplemented.

### 6.3 Why multiple probability-weighted scenarios — Jensen's inequality

**ECL is convex in the macro state**: a downside scenario adds more ECL than a symmetric upside removes. Two mechanisms create the convexity: PD_PIT(Z) is nonlinear in Z (normal-CDF geometry), and the downside hits PD and LGD *together* (the collateral channel). By Jensen, E[ECL(Z)] > ECL(E[Z]) — so measuring on the single most-likely path **systematically understates** expected loss. In the worked example the probability-weighted ECL is ≈**1.9×** the average-path ECL. This is the analytical justification for [IFRS9](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/)'s multiple-scenario requirement (¶5.5.17), the best exam answer to "why not just use the base case?", and — reproduced from your own engine as a chart — the intellectual centrepiece of the dashboard.

---

## 7. The Agentic Layer

### 7.1 Why agents at all — the honest justification

The reflexive criticism is "this is a calculator with a chat skin." The rebuttal is that the *genuinely multistep, judgment-laden glue-work* around an ECL engine is exactly what agents automate:

1. **Data currency:** fetch the latest FRED/LAUS releases, detect that a new quarter has landed, refit the satellite, flag coefficient drift against the previous fit.
2. **Narrative → numbers:** translate "assume a mild recession in H2 with a slow housing correction" into a coherent multivariate path (select a DFAST-shaped template, scale it, sanity-check co-movements) — a task with structure *and* judgment.
3. **Explanation:** run the movement decomposition and narrate *why* ECL moved — stage migration vs macro vs portfolio — in language a non-modeller reads.
4. **Documentation:** draft the scenario-justification memo from the tool-call log (which scenario, which weights, what rationale) — the audit artifact real banks struggle to keep current.

Each step's output gates the next; the branching (e.g., "satellite drifted → refit → revalidate → then answer") is why this is agentic *by problem structure*, not by fashion — which was the selection criterion for the project in the first place.

### 7.2 Mechanism — function calling, precisely

The LLM analyses the question, extracts intent, and **emits a structured tool call** (function name + typed, schema-validated arguments). The application executes the function; the LLM never executes anything and never produces a number (a clean write-up of the pattern: [martinfowler.com/articles/function-call-LLM.html](https://martinfowler.com/articles/function-call-LLM.html)). Example flow:

> "What happens to Stage 2 ECL if unemployment rises 2%?"
> → router: Tier 1 → `shock_macro(var="UER", shock=+2.0, shape="parallel")`
> → engine: satellite → Z path → PIT PDs → staging → ECL
> → agent: narrates the *returned* numbers, renders the waterfall, logs the call.

The tool schema is the contract: argument validation rejects malformed shocks *before* they reach the engine, and the log line is a replayable audit event.

### 7.3 The three-tier design — reasoning per tier

The design question behind "how can it answer any random question?" is really: **how much freedom do you give the agent, and at what cost?** The answer is a graduated ladder — maximum determinism for common questions, maximum flexibility only where needed, knowledge questions routed away from the engine entirely.

| Tier | Route | Covers | Why this tier exists |
|---|---|---|---|
| 1 | **Parameterized tools** — `shock_macro()`, `reweight_scenarios()`, `rerun_ecl(segment)`, `decompose_waterfall()` | The designed scenario space — most realistic questions reduce to these | Deterministic, schema-validated, fast, trivially auditable. Freedom is *removed* on purpose: a fixed argument surface cannot be prompted into doing something undefined |
| 2 | **Sandboxed code interpreter** — agent writes pandas against *read-only* engine output tables (scored loan-month panel, scenario ECL tables) with a documented schema; generated code displayed to the user | Long-tail analytical questions: "which vintage drives the downside Stage-2 increase?" | You cannot pre-write a tool for every question; code generation is the flexibility valve. Guardrails (read-only, whitelisted libraries, result-size caps, code shown for audit) price that flexibility correctly |
| 3 | **Documentation retrieval** — vectorless graph retrieval over the model-documentation wiki (§8), answering with page#heading citations | Methodology questions: "how is Stage 2 defined here?", "why lag unemployment two quarters?" | These questions need *knowledge*, not computation — routing them to the engine would be a category error; routing them to the LLM's memory would be hallucination-prone. Citations make the answer checkable |

**Empirical grounding for the 1+2 hybrid:** a controlled comparison of the two agent designs on a structured-analysis benchmark (GeoJSON Agents, [arXiv:2509.08863](https://arxiv.org/abs/2509.08863)) found code generation more accurate on complex open-ended tasks (≈97% vs ≈86%) while function calling was more stable on structured operations — which is precisely why the architecture uses *both*, routed by question type, rather than picking a side.

**Refusal as a feature:** questions outside all three tiers get an explicit "outside my validated scope" plus an offer to extend the toolset. In a regulated-model context, an assistant that knows its boundary *is the demonstration of model governance* — demo a refusal on purpose.

### 7.4 The value proposition, stated for interviews

1. **Correctness & auditability** — every figure from a governed engine; the tool-call log is a replayable audit trail. Contrast explicitly with "ask ChatGPT about your portfolio."
2. **Cycle-time** — scenario turnaround from an analyst-day to seconds, *without* loosening governance, because the engine version is pinned.
3. **Accessibility** — a risk manager interrogates a model that previously required a SAS programmer as intermediary.
4. **Pattern-match to industry** — LLM as interface/orchestrator over validated quant models is the architecture banks are actually adopting; you built the reference version.

---

## 8. llm-wiki Integration — three roles, one boundary

**The underlying pattern (compile, don't retrieve):** instead of re-reading raw sources every session, compile them once into small interlinked Markdown pages with a typed link graph, then answer from the wiki and file every new insight back. Knowledge compounds; the second time is free.

1. **Build-time project memory.** A multi-session build bleeds context at every session boundary — on a compressed 4-day clock, each lost re-orientation hour hurts proportionally more. The wiki fixes this structurally: one page per module (panel builder, hazard, satellite, scenario engine, agent tools), `memory/decisions.md` for the decision record (90DPD re-flag, cloglog choice, macro-lag selection, scenario-weight rationale — every decision point in this document gets an entry), `wiki_graph.py` + `wiki_audit.py` run each session (audit must be clean; the manifest hashing means the audit *tells you which pages went stale* when code changes). New-session recovery ritual: read `index.md` → last 3 log entries → audit counts. Never re-orient by re-reading the repo. Ingestion partners: **pageindex-plus** for the document corpus (IFRS9 notes, Freddie file layouts, papers), its `scan_code.py` for the code call graph.
2. **It doubles as the model development document.** IFRS9 model development *requires* documentation — data waterfall, variable rationale, validation results, overlay justifications. Wiki pages maintained update-in-place with provenance *are* that documentation; compiling them into a formal MDD at the end is an export step, not a writing project. "Audit-ready documentation was generated as a byproduct of building" is a differentiator no other candidate will have.
3. **Run-time Tier 3.** The deployed chatbot's methodology questions retrieve from the wiki using its vectorless pattern — lexical seeds + k-hop graph expansion → ordered reading list → answer with `page.md#Heading` citations. The wiki content is the corpus behind `query_model_docs`; the retrieval is deterministic and explainable (no embedding similarity to hand-wave about).

**The boundary:** the wiki serves knowledge, never numbers. Arithmetic stays in the engine — the two systems answer different question types and must never blur.

---

## 9. Stack & APIs — choices with reasons

**Orchestration — [LangGraph](https://langchain-ai.github.io/langgraph/):** the agent is a *graph* (router → tier → engine → narrator, with refit-and-revalidate branches), and LangGraph makes that graph an explicit, inspectable object — which is both the engineering choice and the interview exhibit ("here is my agent's state machine"). **Backend — [FastAPI](https://fastapi.tiangolo.com):** async, typed, and the tool schemas double as API schemas.

**Frontend — [Preact](https://preactjs.com) SPA (built with [Vite](https://vitejs.dev)), served by FastAPI, shipped as one Docker image.** Reasoning:

- **Preact is the modern React API in ~3 kB** — hooks, components, JSX — scaffolded in one command (`npm init preact` / Vite's preact template). You get real SPA control without React's bundle weight; if a React-only chart library is ever needed, [`preact/compat`](https://preactjs.com/guide/v10/switching-to-preact/) aliases it in. For charts, framework-agnostic [Apache ECharts](https://echarts.apache.org) or [Chart.js](https://www.chartjs.org) avoid even needing compat.
- **The UI this project needs is interaction-heavy** — scenario sliders that re-hit the engine, an ECL waterfall that animates on update, a live agent-trace panel streamed over [SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) from FastAPI, and a chat pane. These are patterns a hand-built SPA does naturally and Streamlit's rerun-the-script model actively fights.
- **One container, one port.** `npm run build` emits a static `dist/`; FastAPI mounts it with `StaticFiles` and serves `/api/*` beside it — exactly the shape [Hugging Face Spaces' Docker SDK](https://huggingface.co/docs/hub/spaces-sdks-docker) expects (single container listening on port 7860). The same image runs unchanged on [Render](https://render.com), a VPS, or a laptop — that portability *is* the argument for Docker.
- **Placement signal:** a hand-built Preact SPA + multi-stage Docker build reads as full-stack engineering; a Streamlit page reads as a notebook wrapper. Trade-off: more front-end work on a 4-day clock — de-risked by scaffolding the app shell on Day 1 and capping the UI at four components (`ScenarioControls`, `WaterfallChart`, `AgentTrace`, `ChatPanel`).

Multi-stage Dockerfile sketch:

```dockerfile
# stage 1 — build the Preact bundle
FROM node:20-alpine AS ui
WORKDIR /ui
COPY app/ui/package*.json ./
RUN npm ci
COPY app/ui/ .
RUN npm run build                      # → /ui/dist

# stage 2 — Python runtime: engine + agent + API + static UI
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine/ ./engine/
COPY agent/ ./agent/
COPY app/api/ ./api/
COPY --from=ui /ui/dist ./static       # FastAPI mounts this via StaticFiles
EXPOSE 7860                            # HF Spaces Docker SDK convention
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
```

*Why multi-stage:* Node exists only at build time — the shipped image carries Python, the engine, and a static folder, staying small and with a minimal attack/dependency surface. **Deploy — [HF Spaces (Docker SDK)](https://huggingface.co/docs/hub/spaces-sdks-docker) or [Render](https://render.com):** a live link on the CV converts "project" into "product".

**Model APIs — free tiers, assigned by role** (limits change monthly; verify in each dashboard):

| Provider | Role here | Why / notes (mid-2026) |
|---|---|---|
| **[DeepSeek V4 Pro](https://openrouter.ai/deepseek/deepseek-v4-pro)** (paid OpenRouter credits) | Tier-2 code generation, heavy reasoning, doc drafting; **V4 Flash** = paid, reliable Tier-1 routing on demo day | ~$0.44/M in, $0.87/M out; 1M context; function calling + structured outputs; top coder (SWE-bench Verified 80.6, LiveCodeBench 93.5); **text-only** — Gemini keeps the multimodal slot; run routing in non-think mode (thinking tokens bill as output); credits are account-level, so the same balance buys [V4 Flash](https://openrouter.ai/deepseek/deepseek-v4-flash) (~$0.09/$0.18) for high-frequency calls; $5 ≈ 900–1,000 full agent queries |
| **[Google AI Studio](https://aistudio.google.com) — Gemini 3.5 Flash / 3 Flash / 3.1 Flash-Lite** | Multimodal slot: image/PDF understanding (file-layout PDFs, scanned notes, chart reading), routed via a modality check in LangGraph | All three carry free tiers (quotas reduced Apr 2026, per-project — check [AI Studio limits](https://ai.google.dev/gemini-api/docs/rate-limits)); 3.5 Flash for hard vision + reasoning ($1.50/$9 beyond free quota), 3.1 Flash-Lite for high-volume light extraction ($0.25/$1.50, vision + function calling); use a **direct Google key** (via OpenRouter Gemini bills paid credits); avoid the "3.1 Flash Image" *generation* model (per-image billing, no free tier); free-tier prompts may be used for training (off once billing is added) |
| **[Groq](https://console.groq.com)** | High-frequency routing/tool loops | LPU speed (Llama 3.3 70B at 700+ tok/s) makes multi-step agent loops feel instant; Llama 4 Scout (multimodal) on the roster; ~30 RPM ([rate-limit docs](https://console.groq.com/docs/rate-limits)); **token/day caps often bind before request caps** — budget tokens, not calls |
| **[OpenRouter](https://openrouter.ai)** | Fallback + breadth; **paid [Gemma 4 31B](https://openrouter.ai/google/gemma-4-31b-it)** = default Tier-1 router *and* vision node | Paid Gemma 4 31B: $0.12/$0.37 per M, multimodal + native function calling, 256K context, 7 providers — ~$0.0005 per routing call, so it unifies routing and image understanding in one cheap node; the [`:free` variant](https://openrouter.ai/google/gemma-4-31b-it:free) (same weights, $0) shares the account-wide free pool — 20 RPM, 50 req/day (1,000/day only after lifetime $10 purchases) — use for light dev calls only; other [`:free` models](https://openrouter.ai/models?q=free) incl. Nemotron Nano 2 VL (OCR/chart understanding); free endpoints may log/train and carry no uptime guarantee |
| **[Cerebras](https://cloud.cerebras.ai)** | Bulk text volume | ~1M free tokens/day, very fast; text-focused |
| **[Mistral La Plateforme](https://console.mistral.ai)** | Spare capacity | Free Experiment tier requires a data-training opt-in — acceptable here (public data), know the trade |
| **[Ollama](https://ollama.com) (local)** | Demo-day safety net | Qwen-VL-class multimodal locally; zero cost, no rate limits, immune to quota surprises during a live demo |

**Operating rules:** all keys on day one; a failover router (OpenRouter or LiteLLM) so one exhausted quota never breaks the app; exponential backoff everywhere; nothing user-facing on a single free tier. **Credit discipline:** develop on the free tiers (Groq/Gemini) and spend the paid DeepSeek credits only on Tier-2 code-gen and demo-day runs; note OpenRouter's lifetime-$10 purchase threshold lifts the free-model cap from 50 to 1,000 requests/day — a $5 top-up is the highest-leverage spend left.

---

## 10. Repo Skeleton

```
ecl-copilot/
├── wiki/                      # llm-wiki: pages, memory, index (also = model documentation)
├── data/
│   ├── ingest/                # SFLLD/CRA loaders, FRED/ALFRED, LAUS, FHFA pulls
│   └── panel/                 # loan-month panel builder, 90DPD re-flag, macro merge
├── engine/                    # deterministic, versioned, no LLM anywhere
│   ├── hazard.py              # discrete-time cloglog PD; competing-risk prepayment
│   ├── lgd.py                 # cure × severity, EIR discounting
│   ├── ead.py                 # amortisation + prepayment; CCF
│   ├── staging.py             # SICR: relative PD test, 30DPD backstop, probation
│   ├── vasicek.py             # Z recovery, ρ calibration, PIT conditioning
│   ├── satellite.py           # macro-link model (ARDL/ECM hygiene)
│   ├── scenarios.py           # scenario paths, weighting, scenario-conditional ECL
│   └── ecl.py                 # the sum; movement decomposition
├── challenger/                # neural hazard / LSTM; SHAP, PDP, monotonic constraints
├── agent/
│   ├── tools_tier1.py         # shock_macro, reweight_scenarios, rerun_ecl, waterfall
│   ├── tools_tier2.py         # sandboxed code interpreter (read-only schemas)
│   ├── tools_tier3.py         # query_model_docs (wiki-pattern retrieval)
│   └── graph.py               # LangGraph orchestration + routing
├── app/
│   ├── api/                   # FastAPI: /api/* endpoints + StaticFiles serving the built UI
│   └── ui/                    # Preact + Vite SPA: ScenarioControls, WaterfallChart, AgentTrace, ChatPanel
├── Dockerfile                 # multi-stage: node builds ui/dist → python:slim runtime, port 7860
└── tests/                     # engine unit tests: worked examples as fixtures
```

*Why worked examples as test fixtures:* the notes' worked examples (roll-rate bridge R=0.60; CCF EAD €14.0m; the ≈1.9× Jensen ratio) are independently computed ground truth — encoding them as unit tests means the engine is verified against numbers you can defend line by line.

---

## 11. Four-Day Plan — with the dependency logic

Compressing 8 weeks into 4 days is a scoping exercise, and the scope cuts are made **by rule**, not ad hoc:

1. **Cut engineering, never methodology.** Every conceptual component survives (hazard PD, two-stage LGD, staging, Vasicek/Z, Jensen, Tier-1 agent); what gets cut is data-scale and infrastructure work. A small pipeline with all the ideas beats a big pipeline missing the point.
2. **Every cut is a *documented simplification*, not a silent omission** — one line each in `memory/decisions.md`. "I simplified X, here's what full-scale looks like" is a strong interview position; a silent gap is a weak one.
3. **The freeze gate moves to end of Day 2 but does not disappear.** The discipline is the point.
4. **Each day ends at a shippable state** — the plan still degrades gracefully, just on a faster clock.

**Scope decisions this implies:** data = rungs 1–2 only (CRA/DCR pre-merged panels — this deletes the entire macro-merge week and the 90DPD re-flag, since the panels arrive merged and flagged); satellite = simple lagged regression with logit transform (full ARDL/ECM hygiene documented as the full-scale method); challenger = MLP hazard, not LSTM; agent = Tier 1 + refusal path; app = Preact SPA + FastAPI in a single Docker image on HF Spaces (Docker SDK).

| Day | AM | PM | Definition of done |
|---|---|---|---|
| 1 | Repo + `.env`/`.gitignore`/`.env.example` + gitleaks pre-commit hook + keys + wiki init; scaffold the Preact app shell (`npm init preact`, Vite polling on per §0.4); verify `docker build` locally (Docker Desktop, WSL2 backend) or via a private HF Space; load CRA `mortgage` + DCR panels; sample waterfall; EDA test suite (vintage curves, seasoning hump, roll rates, macro co-movement) | Discrete-time cloglog hazard + competing-risk prepayment; double-trigger interaction; PD term-structure chart | Every expected EDA shape appears or the deviation is explained; seasoning baseline visible in the fitted model; the shell container builds; secret scan runs clean |
| 2 | LGD (cure × severity on DCR workout losses); EAD (amortisation + prepay); staging (relative SICR + 30 DPD backstop) | ECL sum + movement decomposition; unit tests on worked-example fixtures | **GATE passes — engine frozen by end of day.** Fixtures reproduce; `decisions.md` records every simplification |
| 3 | Z recovery + ρ calibration (verify E_Z[PD_PIT]≈PD_TTC); simple satellite (lagged UER/HPI, logit transform); DFAST + WEO path ingestion; scenario-conditional ECL; **Jensen exhibit**; **credit-cycle exhibit** — plot the Zₜ-implied PIT PD path against the flat TTC anchor over the panel's 60 quarters (the 2008–10 hump reproduces the textbook PIT-vs-TTC chart *from your own engine*) | MLP hazard challenger + SHAP; champion–challenger AUC/calibration on an out-of-time split | The ≈1.9×-style Jensen chart and the PIT-vs-TTC cycle chart both render from your own numbers; challenger scorecard exists |
| 4 | Tier-1 tools (`shock_macro`, `reweight_scenarios`, `rerun_ecl`, `decompose_waterfall`) + LangGraph router + deliberate refusal path | Preact dashboard wired to the FastAPI endpoints (sliders, ECL waterfall via ECharts, PIT-vs-TTC cycle chart, SSE agent trace, chat); `docker build` + deploy to HF Spaces (Docker SDK); README + demo script + CV bullet | The unemployment-shock question answers end-to-end with a logged trace; a stranger can use the live link unaided |

**Stretch backlog (post-Day-4, ordered by placement value):** Tier-2 sandboxed code interpreter → Tier-3 wiki retrieval (`query_model_docs`) → expose the frozen engine's Tier-1 tools as an MCP server ([modelcontextprotocol.io](https://modelcontextprotocol.io); ~20-line [FastMCP](https://github.com/jlowin/fastmcp) wrapper — lets any MCP client such as Claude Desktop interrogate the governed engine, the "one validated model server, many consuming surfaces" story) → Freddie SFLLD scale-up with the full macro merge + 90DPD re-flag → LSTM challenger + monotonic constraints → ALFRED-vintage backtest → UI polish pass (animations, responsive layout).

Day 1–2 alone yield a complete classical IFRS9 engine; Day 3 adds the scenario layer and challenger; Day 4 ships the copilot. The wiki costs ~15 minutes a day (log + decisions + audit) and is what makes the pace survivable across sessions.

---

## 12. Interview Mapping — which artifact answers which recurring question

| Recurring interview question | Your artifact |
|---|---|
| "Why did IFRS9 replace IAS 39?" / "Walk through the three stages" | Staging module + dashboard stage view |
| "How would you design a SICR test?" | §4.4 reasoning + the Stage-2-size sensitivity slider |
| "How do you build a lifetime PD term structure?" | The hazard model itself + the seasoning/term-structure chart |
| "Why multiple scenarios — why not the base case?" | The Jensen exhibit (≈1.9×) generated by your own engine |
| "How does the macro enter the model?" | Satellite + Vasicek modules; the ARDL/ECM hygiene write-up |
| "IFRS9 PD vs Basel PD?" / "PIT vs TTC vs hybrid?" | The credit-cycle exhibit (Zₜ-implied PIT path vs TTC anchor from your own panel) + the E_Z[PD_PIT]=PD_TTC check + the αZ-damping hybrid talking point |
| "Why is LGD modelled in two stages?" | §4.2 bimodality argument + the severity model |
| "How do you validate an IFRS9 suite?" | Day-3 out-of-time comparison + champion–challenger scorecard |
| "When is an overlay acceptable?" | The 2020/COVID overlay case study (§2.7) |
| "What's your GenAI point of view for risk?" | The entire Tier 1/2/3 architecture + the refusal demo |

## 13. CV Bullet Raw Material

Deployed live link · engine unit-test coverage · PD model AUC/Gini and calibration (out-of-time) · number of orchestrated tools and the three-tier routing · scenario turnaround (analyst-day → seconds) · "probability-weighted ECL ≈ 1.9× base-case" Jensen exhibit · audit-ready model documentation auto-maintained via the wiki.

---

## 14. Source & Reference Directory

**Loan-level data**
- Credit Risk Analytics datasets (Baesens–Rösch–Scheule): http://www.creditriskanalytics.net
- Deep Credit Risk data & code (Rösch–Scheule): https://www.deepcreditrisk.com
- Freddie Mac Single-Family Loan-Level Dataset: https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset
- Fannie Mae Single-Family Loan Performance Data: https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data

**Macroeconomic data**
- FRED: https://fred.stlouisfed.org · API docs: https://fred.stlouisfed.org/docs/api/fred/ · `fredapi`: https://github.com/mortada/fredapi · `pandas-datareader`: https://pandas-datareader.readthedocs.io
- ALFRED (vintage/real-time series): https://alfred.stlouisfed.org
- BLS Local Area Unemployment Statistics: https://www.bls.gov/lau/
- FHFA House Price Index: https://www.fhfa.gov/data/hpi · Case-Shiller (via FRED): https://fred.stlouisfed.org/series/CSUSHPINSA
- Freddie Mac Primary Mortgage Market Survey: https://www.freddiemac.com/pmms

**Scenario paths**
- Federal Reserve 2026 supervisory stress-test scenarios: https://www.federalreserve.gov/publications/2026-stress-test-scenarios.htm · DFAST hub (all years, CSVs): https://www.federalreserve.gov/supervisionreg/dfa-stress-tests-2026.htm
- IMF World Economic Outlook: https://www.imf.org/en/Publications/WEO
- Philadelphia Fed Survey of Professional Forecasters: https://www.philadelphiafed.org/surveys-and-data/real-time-data-research/survey-of-professional-forecasters
- EBA EU-wide stress testing: https://www.eba.europa.eu/risk-and-data-analysis/risk-analysis/eu-wide-stress-testing · Bank of England stress testing: https://www.bankofengland.co.uk/stress-testing
- RBI Database on Indian Economy: https://data.rbi.org.in

**Papers & standards**
- Sirignano, Sadhwani & Giesecke, *Deep Learning for Mortgage Risk*: https://arxiv.org/abs/1607.02470
- Vasicek (2002), *The Distribution of Loan Portfolio Value*, Risk 15(12)
- Belkin, Suchower & Forest (1998), *A one-parameter representation of credit risk and transition matrices*, CreditMetrics Monitor
- IFRS 9 Financial Instruments (¶5.5.17 multiple scenarios): https://www.ifrs.org/issued-standards/list-of-standards/ifrs-9-financial-instruments/
- GeoJSON Agents — function calling vs code generation: https://arxiv.org/abs/2509.08863
- Function calling with LLMs (pattern write-up): https://martinfowler.com/articles/function-call-LLM.html

**Frameworks & deployment**
- LangGraph: https://langchain-ai.github.io/langgraph/ · FastAPI: https://fastapi.tiangolo.com
- Preact: https://preactjs.com · Vite: https://vitejs.dev · Apache ECharts: https://echarts.apache.org · Chart.js: https://www.chartjs.org
- Hugging Face Spaces Docker SDK: https://huggingface.co/docs/hub/spaces-sdks-docker · Render: https://render.com
- SHAP: https://shap.readthedocs.io · statsmodels: https://www.statsmodels.org · Ollama: https://ollama.com
- Secrets hygiene: gitleaks: https://github.com/gitleaks/gitleaks · python-dotenv: https://github.com/theskumar/python-dotenv · HF Spaces secrets: https://huggingface.co/docs/hub/spaces-overview#managing-secrets

**Model API consoles & rate-limit pages** (limits change monthly — always verify)
- Google AI Studio: https://aistudio.google.com · Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Groq console: https://console.groq.com · rate limits: https://console.groq.com/docs/rate-limits
- OpenRouter: https://openrouter.ai · free models: https://openrouter.ai/models?q=free · DeepSeek V4 Pro: https://openrouter.ai/deepseek/deepseek-v4-pro · DeepSeek V4 Flash: https://openrouter.ai/deepseek/deepseek-v4-flash
- Cerebras: https://cloud.cerebras.ai · Mistral La Plateforme: https://console.mistral.ai
