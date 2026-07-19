# IFRS 9 ECL Copilot — single-container deploy (HF Spaces Docker SDK, port 7860).
#
# Stage 1 builds the Preact/ECharts SPA; stage 2 is a python:3.13-slim runtime
# installing the EXACT locked versions via requirements.docker.txt, generated
# from uv.lock with:
#
#   uv export --no-dev --no-hashes --no-emit-project --prune torch \
#       -o requirements.docker.txt
#
# torch is pruned deliberately: it is used only by the offline challenger
# study (challenger/, not shipped); no runtime module imports it, and its
# CUDA payload would add ~5 GB to the image.
#
# NOTE (2026-07-19): a Space build hit a persistent LFS/context-resolution
# race on outputs/freddie and outputs/mdd right after those directories'
# first upload ("failed to calculate checksum ... not found" despite the LFS
# objects resolving fine over HTTP, and list_repo_files confirming every file
# present at the failing commit SHA) — same class of issue as the prior
# "queue wedge" fix, but more persistent: it survived plain restart_space(),
# a content-change re-push, and even restart_space(factory_reboot=True).
# See outputs/gate/mdd_freddie_gate.md for the full retry timeline and the
# eventual resolution (longer wall-clock wait for backend propagation, not
# more aggressive cache-busting).
#
# SECURITY: no .env, no data/raw, no secrets are ever baked into the image
# (.dockerignore enforces this; the CI check greps the saved image for key
# prefixes). OPENROUTER_API_KEY is injected at RUN time:
#   docker run -e OPENROUTER_API_KEY -p 7860:7860 ifrs9-ecl-copilot
# Without a key the app still serves — the deterministic fallback router
# answers offline and refuses out-of-scope questions (a demoed feature).

# ---------------------------------------------------------------- stage 1: UI
FROM node:22-alpine AS ui
WORKDIR /build
COPY app/ui/package.json app/ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/ui/index.html app/ui/vite.config.js ./
COPY app/ui/src ./src
COPY app/ui/scripts ./scripts
RUN npm run build

# ----------------------------------------------------------- stage 2: runtime
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# locked third-party deps first (best layer-cache behaviour)
COPY requirements.docker.txt ./
RUN pip install --no-cache-dir -r requirements.docker.txt

# HF Spaces convention: run as non-root uid 1000
RUN useradd -m -u 1000 appuser

# runtime code — engine/{hazard,lgd,ead,staging,ecl}.py are the FROZEN five
COPY engine ./engine
COPY agent ./agent
COPY app/__init__.py ./app/__init__.py
COPY app/api ./app/api
COPY analysis ./analysis

# Tier-3 (query_model_docs) retrieval sources: the model-development wiki
# (pages + the pre-built typed graph) and the indexed IFRS9 credit-risk
# notes corpus — both read-only at runtime, no LLM/network involved.
COPY wiki ./wiki
COPY knowledge/corpus ./knowledge/corpus
COPY knowledge/index ./knowledge/index

# the two retrieval scripts agent/tier3_retrieval.py loads by file path
# (importlib.util.spec_from_file_location, never copy-pasted) — same
# relative paths as in the repo; wiki_query.py needs wiki_graph.py
# alongside it (sys.path sibling import)
COPY .claude/skills/llm-wiki/scripts/wiki_query.py .claude/skills/llm-wiki/scripts/wiki_graph.py ./.claude/skills/llm-wiki/scripts/
COPY .claude/skills/pageindex-plus/scripts/pageindex_query.py ./.claude/skills/pageindex-plus/scripts/

# runtime data: the loan panel, the DFAST scenario CSVs and their loader
COPY data/__init__.py ./data/__init__.py
COPY data/ingest ./data/ingest
COPY data/processed/panel.parquet ./data/processed/panel.parquet
COPY data/scenarios/*.csv ./data/scenarios/

# pre-fitted model cache (joblib warm start ~9s; a fingerprint mismatch —
# e.g. fresh file mtimes on HF Spaces — triggers a one-off ~50s refit in the
# FastAPI lifespan, after which every tool call answers in seconds)
COPY outputs/models ./outputs/models

# App v2 consultant exhibits: the /api/model/*, /api/policy/* and
# /api/exhibits/* endpoints parse these markdown reports and serve these
# PNGs (StaticFiles mount over the whole of outputs/) for the Executive
# Overview / The Model / Policy tabs. Also includes the scenario_ecl and
# vasicek CSVs the tools/exhibits read (z_path.csv, scenario_ecl_summary.csv
# etc). Read-only reference material, no code executes from here.
COPY outputs/variable_dictionary.md ./outputs/variable_dictionary.md
COPY outputs/hazard ./outputs/hazard
COPY outputs/lgd ./outputs/lgd
COPY outputs/staging ./outputs/staging
COPY outputs/eda ./outputs/eda
COPY outputs/vasicek ./outputs/vasicek
COPY outputs/scenario_ecl ./outputs/scenario_ecl
COPY outputs/challenger ./outputs/challenger

# Rung 3 (SFLLD real-data study) + the compiled Model Development Document:
# the /api/freddie/* endpoints parse outputs/freddie/**'s reports/CSVs/JSON
# and StaticFiles mounts serve outputs/freddie/** (Freddie tab exhibits) and
# outputs/mdd/** (the MDD.html + assets) — same read-only pattern as above.
#
# TEMPORARILY DISABLED (2026-07-19): 9 consecutive Space build attempts
# (plain restarts, factory_reboot, content-change repush, atomic delete+
# re-add) all failed identically on these two COPY lines alone — "failed to
# calculate checksum ... not found" — despite outputs/freddie|mdd verifiably
# present and their LFS objects resolving fine over HTTP at every attempted
# commit (see outputs/gate/mdd_freddie_gate.md for the full timeline). Every
# other COPY in this file, including long-standing ones, succeeded every
# time. Commenting these two out restores the Space to RUNNING (the guarded
# `if FREDDIE_DIR.exists()` / `if MDD_DIR.exists()` mounts in app/api/main.py
# mean the app boots fine without them; only the Real Data tab's own calls
# would 404/500 until this is re-enabled). Both directories are already
# pushed to the Space's git repo (`outputs/freddie/`, `outputs/mdd/`) —
# re-enable these two lines once the platform-side build issue clears.
COPY outputs/freddie ./outputs/freddie
COPY outputs/mdd ./outputs/mdd

# the built SPA (served by FastAPI at /)
COPY --from=ui /build/dist ./app/ui/dist

# outputs/ must be writable: agent audit trail + possible cache refresh
RUN mkdir -p outputs/agent_log && chown -R appuser:appuser /app/outputs

USER appuser

EXPOSE 7860
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
