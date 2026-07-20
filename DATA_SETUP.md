# Data Setup — replicating this repository

The repo ships **all code, tests, exhibits, notes, and reports**, but **no licensed loan-level
data and no secrets**. To run the pipelines yourself you download the data below into the
exact paths shown, create your own `.env`, and run the rebuild commands. Everything else
(macro pulls, model fits, caches) regenerates from these inputs via checkpointed scripts.

What's already in the repo (nothing to download): the DFAST 2026 scenario CSVs in
`data/scenarios/` (public Federal Reserve data) and every derived report/exhibit under
`outputs/` — so you can read all results without downloading anything at all.

## 1. Python environment

```bash
# Python 3.13 via uv (https://docs.astral.sh/uv/)
uv sync                      # installs from uv.lock (torch is large, ~2GB with CUDA)
uv run pytest tests/ -q      # 133 golden-fixture tests pass with NO data downloaded
```

The 133 golden fixtures are self-contained worked examples — they prove the engine's
algebra before you download a single row.

## 2. DeepCreditRisk mortgage panel (rungs 1–2: the frozen DCR engine)

1. Go to <https://www.deepcreditrisk.com> and obtain the dataset that accompanies the
   *Deep Credit Risk* book (Scheule & Roesch). It is free with book registration.
2. Download **both** files and place them at:
   - `data/raw/dcr.csv`
   - `data/raw/dcr_full.csv`
3. Rebuild the loan-quarter panel (~1 min):

```bash
uv run python -m data.panel.build_panel     # -> data/processed/panel.parquet (621,736 rows)
```

The build script verifies its own output (row counts, updated-LTV vendor match to 5e-9,
left-truncation consistency) and refuses to write on mismatch.

## 3. Freddie Mac SFLLD samples (rung 3: real GSE data)

1. Register (free) at Freddie Mac's **CRT Data Intelligence** portal:
   <https://crt-data.freddiemac.com> → *SFLLD Data* → *Standard Dataset Download by Year*.
   Approval can take a day — register early.
2. From the **Sample File** column download these 17 vintages (50,000 loans each):
   `2005–2010, 2014–2016, 2018–2025` (the gaps 2011–2013/2017 are intentional and
   documented in `outputs/freddie/ingest/dq_report.md`).
3. Place the zips (do **not** unzip) at `data/SFLLD/sample_<year>.zip`.
4. Rebuild the monthly panel (~6 min) and the state-macro merge:

```bash
uv run python -m freddie.build_panel   # -> data/processed/freddie/*.parquet (39.5M rows)
uv run python -m freddie.macro         # pulls state UER/HPI from FRED (needs FRED_API_KEY),
                                       # caches CSVs so later runs are offline
```

## 4. API keys — `.env`

```bash
cp .env.example .env    # then fill in your own keys; .env is gitignored — NEVER commit it
```

| Key | Needed for | Where to get it |
|---|---|---|
| `FRED_API_KEY` | state/national macro pulls (`freddie.macro`, backtest ALFRED vintages) | free at <https://fred.stlouisfed.org/docs/api/api_key.html> |
| `OPENROUTER_API_KEY` | the LLM copilot (router + narrator) | <https://openrouter.ai> |
| `HF_TOKEN` | only if you deploy your own Space | <https://huggingface.co/settings/tokens> |
| `GOOGLE_API_KEY` | optional narrator fallback | Google AI Studio |

The app runs **without any keys** in read-only mode (all exhibits, coefficients, scenario
maths); keys are only needed for live agent answers and fresh macro pulls.

## 5. Refit the models (optional — all outputs are committed)

```bash
uv run python -m freddie.fit_hazard    # champion + COVID variants; checkpointed, resumable
uv run python -m freddie.fit_lgd       # realized-loss LGD
uv run python -m freddie.backtest      # ALFRED-vintage honest backtest (needs FRED key)
uv run python -m freddie.fit_lstm      # LSTM challenger (GPU used if available)
uv run pytest tests/ -q                # full suite: 665 tests
```

Every fit script caches converged stages under `data/processed/freddie/` and skips them on
re-run — interrupting and restarting is safe by design.

## 6. Run the app locally

```bash
cd app/ui && npm install && npm run build && cd ../..
uv run uvicorn app.api.main:app --port 7860    # serves API + SPA + MDD at localhost:7860
```

Or via Docker (mirrors the live Hugging Face Space exactly):

```bash
docker build -t ifrs9-ecl . && docker run -p 7860:7860 --env-file .env ifrs9-ecl
```

## Licensing note

The DCR and Freddie Mac datasets are licensed for individual research/education use —
that is why they are not redistributed here. Do not commit them to your fork; this repo's
`.gitignore` already excludes `data/raw/`, `data/SFLLD/`, `data/processed/`, and `.env`.
