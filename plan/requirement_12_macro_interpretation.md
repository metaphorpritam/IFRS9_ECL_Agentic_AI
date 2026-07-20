# Requirement 12 — Macro/FRED interpretation must be first-class (notes AND app)

User mandate: the interpretation of models and coefficients must be clear **for the
FRED/macro data as well** — and highlighted in the App.

## Notes side (binds ch03 §macro, ch06 scenarios/satellite, ch11-12 Freddie)

Every macro variable, in every model where it appears, gets the full card:
- **Source**: exact series (FRED ID where applicable — e.g. UNRATE, {POSTAL}UR,
  {POSTAL}STHPI, DFAST variable names), geography, frequency, SA/NSA.
- **Transformation + window**: level vs delta vs log-growth, the lag and WHY that lag
  (timing convention; publication-lag realism per the ALFRED chapter).
- **Units and scale**: what "one unit" means (pp of unemployment, quarterly log-growth,
  etc.) — the classic misreading (0.01 vs 1pp) called out as a gotcha.
- **Coefficient reading**: sign, hazard-ratio form exp(beta·delta) with a WORKED numeric
  example computed in python (e.g. "+1pp state UER ⇒ hazard × exp(0.667×1) ≈ 1.95 —
  a 95% proportional increase in the monthly default hazard"). No hand-typed results.
- **Economic channel**: the one-paragraph causal story (labour-income channel, collateral/
  negative-equity channel, refinancing-incentive channel), consistent with the wiki.
- **Cross-model comparison** where the same concept appears twice (DCR national vs SFLLD
  state-level; satellite's hpi/gdp terms and the no-UER coherent-shock consequence).

## App side (implemented as its own ship — additive, contract-first)

- Extend /api/model/variable_dictionary + /api/model/coefficients + /api/freddie/hazard
  payloads with per-variable interpretation fields: {unit_meaning, transformation, lag,
  fred_series (nullable), economic_channel, hazard_ratio_per_unit, worked_example}.
  All content grounded in outputs/variable_dictionary.md + hazard reports; hazard-ratio
  arithmetic computed mechanically from the coefficient (never invented).
- UI: coefficients tables gain a hazard-ratio column and an expandable per-row
  interpretation panel; FRED-source badges on macro rows; the Model tab and the
  Real Data tab both get an "How to read these coefficients" intro panel; satellite/
  scenario panels state the coherent-shock convention in one line with the explain icon
  adjacent.
- Contract doc + tests extended field-by-field; verbatim-number law holds (worked
  examples computed client-side from the served coefficient, or server-side in python).
