import { Fragment } from 'preact';
import { useEffect, useMemo, useState } from 'preact/hooks';
import {
  explainPanelQuestion,
  getModelCoefficients,
  getVariableDictionary,
  getMacroGlossary,
  getLgd,
  getExhibitsList,
} from '../api.js';
import { runDate } from '../format.js';
import SearchableTable from '../components/SearchableTable.jsx';
import ExhibitImage from '../components/ExhibitImage.jsx';
import Panel from '../components/Panel.jsx';
import HowToReadCoefficients from '../components/HowToReadCoefficients.jsx';
import ModelAtAGlance from '../components/ModelAtAGlance.jsx';
import EadEirMethod, { buildEadEirExplainQuestion } from '../components/EadEirMethod.jsx';
import {
  ExpandToggle,
  InterpretationRow,
  useExpandableRows,
} from '../components/CoefficientInterpretation.jsx';

const FAMILY_LABEL = {
  baseline: 'Baseline (seasoning)',
  borrower: 'Borrower quality',
  collateral: 'Collateral / equity',
  macro: 'Macro-economic',
  incentive: 'Incentive / behavioural',
};

const COEF_COLS = 6; // toggle + variable + HR + per-unit HR + CI + p

function CoefficientsTable({ model, modelKey }) {
  const { isOpen, toggle } = useExpandableRows();
  if (!model) return null;
  const families = [];
  const seen = new Set();
  for (const c of model.coefficients) {
    if (!seen.has(c.family)) {
      seen.add(c.family);
      families.push(c.family);
    }
  }
  return (
    <div class="table-scroll">
      <table class="data-table coef-table">
        <thead>
          <tr>
            <th />
            <th>Variable</th>
            <th class="num">Hazard ratio</th>
            <th class="num" data-tip="0.01-vs-1pp-corrected, see the intro panel">Per-unit HR</th>
            <th class="num">95% CI</th>
            <th class="num">p</th>
          </tr>
        </thead>
        <tbody>
          {families.map((fam) => (
            <Fragment key={fam}>
              <tr class="family-row">
                <td colSpan={COEF_COLS}>{FAMILY_LABEL[fam] ?? fam}</td>
              </tr>
              {model.coefficients
                .filter((c) => c.family === fam)
                .map((c) => {
                  const key = `${modelKey}:${c.variable}`;
                  const open = isOpen(key);
                  return (
                    <Fragment key={key}>
                      <tr class={`coef-row${open ? ' row-open' : ''}`} onClick={() => toggle(key)}>
                        <td>
                          <ExpandToggle open={open} onToggle={() => toggle(key)} label={c.variable} />
                        </td>
                        <td>
                          {c.variable}
                          {c.fred_series && <span class="fred-badge fred-badge-inline">FRED</span>}
                        </td>
                        <td class={`num ${c.hazard_ratio > 1 ? 'hr-up' : 'hr-down'}`}>
                          {c.hazard_ratio.toFixed(4)}
                        </td>
                        <td class="num">
                          {c.hazard_ratio_per_unit != null ? c.hazard_ratio_per_unit.toFixed(4) : '—'}
                        </td>
                        <td class="num">[{c.ci[0].toFixed(3)}, {c.ci[1].toFixed(3)}]</td>
                        <td class="num">{c.p_display}</td>
                      </tr>
                      {open && <InterpretationRow row={c} colSpan={COEF_COLS} />}
                    </Fragment>
                  );
                })}
              <tr class="story-row">
                <td colSpan={COEF_COLS}>
                  {model.coefficients.find((c) => c.family === fam)?.story}
                </td>
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FitStats({ fitStats }) {
  if (!fitStats) return null;
  const rows = [
    { id: 'default', label: 'Default hazard', ...fitStats.default },
    { id: 'prepay', label: 'Prepayment hazard', ...fitStats.prepay },
  ];
  return (
    <>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Model</th>
              <th class="num">n fit</th>
              <th class="num">Events</th>
              <th class="num">Train AUC</th>
              <th class="num">OOT AUC</th>
              <th class="num">McFadden R²</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.label}</td>
                <td class="num">{r.n_fit.toLocaleString()}</td>
                <td class="num">{r.events.toLocaleString()}</td>
                <td class="num">{r.train_auc.toFixed(4)}</td>
                <td class="num">{r.oot_auc.toFixed(4)}</td>
                <td class="num">{r.mcfadden_r2.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div class="caveat-block">
        <p class="caveat">
          <b>Honest caveat — OOT is the stress window.</b> Out-of-time
          (t=41–60, 2010Q2–2015Q1) is the GFC stress aftermath, not a random
          holdout: the AUC drop from train to OOT above is expected and does
          not by itself indicate overfitting.
        </p>
        <p class="caveat">
          <b>Net UER effect.</b> {fitStats.net_uer_effect_note}
        </p>
        <p class="caveat">
          <b>Double trigger (LTV × UER).</b> {fitStats.double_trigger_note}
        </p>
        {fitStats.seasoning_peak && (
          <p class="caveat">
            <b>Seasoning peak.</b> Fitted hazard peaks at quarter{' '}
            {fitStats.seasoning_peak.fitted_q} vs an empirical peak at{' '}
            {fitStats.seasoning_peak.empirical_q} (plausible window{' '}
            {fitStats.seasoning_peak.plausible_window_q.join('–')}).
          </p>
        )}
      </div>
    </>
  );
}

function VariableDictionary({ dict }) {
  if (!dict) return null;
  const columns = [
    { key: 'variable', label: 'Variable' },
    { key: 'source_transformation', label: 'Source / transformation' },
    { key: 'lag_window', label: 'Lag / window' },
    { key: 'economic_rationale', label: 'Economic rationale' },
    { key: 'expected_sign', label: 'Expected sign' },
    { key: 'fitted_verified', label: 'Fitted / verified' },
    { key: 'consumed_by', label: 'Consumed by' },
    {
      key: 'fred_series', label: 'FRED',
      render: (r) => (r.fred_series ? <span class="fred-badge">{r.fred_series}</span> : '—'),
    },
  ];
  return (
    <>
      <p class="panel-sub preamble">{dict.preamble}</p>
      <SearchableTable
        columns={columns}
        rows={dict.rows}
        placeholder="Search variables (e.g. ltv, uer, fico)…"
      />
      <p class="panel-sub preamble">{dict.notes}</p>
    </>
  );
}

function MacroGlossary({ glossary }) {
  if (!glossary) return null;
  const columns = [
    { key: 'label', label: 'Series' },
    {
      key: 'fred_series', label: 'FRED ID',
      render: (r) => (r.fred_series ? <code>{r.fred_series}</code> : '—'),
    },
    { key: 'geography', label: 'Geography' },
    { key: 'frequency', label: 'Frequency' },
    { key: 'transformation', label: 'Transformation' },
    { key: 'lag', label: 'Lag' },
    { key: 'lag_rationale', label: 'Why this lag' },
    {
      key: 'which_models', label: 'Used by',
      render: (r) => r.which_models.join('; '),
    },
  ];
  return (
    <details class="stage-guide macro-glossary">
      <summary>Macro data glossary ({glossary.series.length} series)</summary>
      <SearchableTable
        columns={columns}
        rows={glossary.series}
        placeholder="Search macro series (e.g. UNRATE, STHPI, coherent)…"
      />
    </details>
  );
}

function LgdSection({ lgd, exhibits }) {
  if (!lgd) return null;
  const calRows = Object.entries(lgd.oot_calibration).map(([key, v]) => ({
    metric: key.replace(/_/g, ' '),
    train: v.train,
    oot: v.oot,
  }));
  const coefCols = [
    { key: 'variable', label: 'Variable' },
    { key: 'coef', label: 'Coef', align: 'right', render: (r) => r.coef.toFixed(4) },
    { key: 'se', label: 'SE', align: 'right', render: (r) => (r.se ?? r.se_hc1)?.toFixed(4) },
    { key: 'z', label: 'z', align: 'right', render: (r) => r.z.toFixed(3) },
    { key: 'p', label: 'p', align: 'right', render: (r) => r.p.toFixed(4) },
  ];
  return (
    <>
      <div class="tiles">
        <div class="tile">
          <div class="tile-label">Cure rate</div>
          <div class="tile-value">{(lgd.cure_rate * 100).toFixed(1)}%</div>
        </div>
        <div class="tile">
          <div class="tile-label">Cure AUC (train / OOT)</div>
          <div class="tile-value">
            {lgd.cure_auc.train.toFixed(3)} / {lgd.cure_auc.oot.toFixed(3)}
          </div>
        </div>
        <div class="tile">
          <div class="tile-label">Excess-loss loading</div>
          <div class="tile-value">{(lgd.excess_loss_loading * 100).toFixed(2)}%</div>
        </div>
      </div>

      <h3>OOT calibration</h3>
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr><th>Metric</th><th class="num">Train</th><th class="num">OOT</th></tr>
          </thead>
          <tbody>
            {calRows.map((r) => (
              <tr key={r.metric}>
                <td class="cap">{r.metric}</td>
                <td class="num">{r.train.toFixed(4)}</td>
                <td class="num">{r.oot.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div class="two-col">
        <div>
          <h3>Cure-stage coefficients (logit)</h3>
          <SearchableTable columns={coefCols} rows={lgd.cure_stage_coefficients} placeholder="Search…" />
        </div>
        <div>
          <h3>Severity-stage coefficients (OLS, HC1)</h3>
          <SearchableTable
            columns={coefCols.map((c) => (c.key === 'se' ? { ...c, label: 'SE (HC1)' } : c))}
            rows={lgd.severity_stage_coefficients}
            placeholder="Search…"
          />
        </div>
      </div>

      <h3>LGD exhibits</h3>
      <div class="exhibit-grid">
        {exhibits
          .filter((e) => e.id.startsWith('lgd_'))
          .map((e) => (
            <ExhibitImage key={e.id} {...e} />
          ))}
      </div>
    </>
  );
}

export default function ModelTab() {
  const [coeffs, setCoeffs] = useState(null);
  const [dict, setDict] = useState(null);
  const [macroGlossary, setMacroGlossary] = useState(null);
  const [lgd, setLgd] = useState(null);
  const [exhibits, setExhibits] = useState([]);
  const [selected, setSelected] = useState('default');
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([
      getModelCoefficients(),
      getVariableDictionary(),
      getMacroGlossary(),
      getLgd(),
      getExhibitsList(),
    ])
      .then(([c, d, mg, l, ex]) => {
        if (!alive) return;
        setCoeffs(c);
        setDict(d);
        setMacroGlossary(mg);
        setLgd(l);
        setExhibits(ex.exhibits);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  const seasoningExhibits = useMemo(
    () => exhibits.filter((e) => e.id.startsWith('hazard_')),
    [exhibits],
  );

  const model = coeffs?.models?.[selected];

  return (
    <div class="tab-body">
      <header class="tab-intro">
        <h1>The Model</h1>
        <p>Coefficients, fit statistics, and the variable dictionary — with the honest caveats.</p>
      </header>

      {error && (
        <div class="empty-note">Engine API offline ({error}).</div>
      )}

      <ModelAtAGlance />

      <HowToReadCoefficients />

      <Panel
        id="panel-hazard"
        exhibit={1}
        title="Hazard-ratio coefficients"
        subtitle="Hazard ratio > 1 = risk-increasing; < 1 = risk-reducing (exp(coef) of a cloglog hazard). Each family's intuition story is below its rows."
        source={{ endpoint: 'GET /api/model/coefficients', runDate: runDate() }}
        actions={
          <div class="segmented">
            <button
              class={selected === 'default' ? 'active' : ''}
              onClick={() => setSelected('default')}
            >
              Default hazard
            </button>
            <button
              class={selected === 'prepay' ? 'active' : ''}
              onClick={() => setSelected('prepay')}
            >
              Prepayment hazard
            </button>
          </div>
        }
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'hazard_coefficients',
            params: { model: selected },
            exhibitLabel: 'Exhibit 1',
            title: 'Hazard-ratio coefficients',
            recap: model
              ? `${selected} hazard model: n=${model.n_fit.toLocaleString()}, ${model.coefficients.length} coefficients, McFadden R² ${model.mcfadden_r2.toFixed(4)}. Largest hazard ratio: ${model.coefficients.reduce((a, b) => (Math.abs(Math.log(b.hazard_ratio)) > Math.abs(Math.log(a.hazard_ratio)) ? b : a)).variable}.`
              : 'no data rendered yet',
          })
        }
      >
        <CoefficientsTable model={model} modelKey={selected} />
      </Panel>

      <Panel
        exhibit={2}
        title="Fit statistics"
        source={{ endpoint: 'GET /api/model/coefficients', runDate: runDate() }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'fit_stats',
            exhibitLabel: 'Exhibit 2',
            title: 'Fit statistics',
            recap: coeffs?.fit_stats
              ? `Default hazard: train AUC ${coeffs.fit_stats.default.train_auc.toFixed(4)}, OOT AUC ${coeffs.fit_stats.default.oot_auc.toFixed(4)}. Prepayment hazard: train AUC ${coeffs.fit_stats.prepay.train_auc.toFixed(4)}, OOT AUC ${coeffs.fit_stats.prepay.oot_auc.toFixed(4)}.`
              : 'no data rendered yet',
          })
        }
      >
        <FitStats fitStats={coeffs?.fit_stats} />
      </Panel>

      <Panel
        exhibit={3}
        title="Seasoning & term-structure exhibits"
        source={{ endpoint: 'GET /api/exhibits/list', runDate: runDate() }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'seasoning_exhibits',
            exhibitLabel: 'Exhibit 3',
            title: 'Seasoning & term-structure exhibits',
            recap: `${seasoningExhibits.length} seasoning/term-structure exhibits rendered: ${seasoningExhibits.map((e) => e.title).join(', ')}.`,
          })
        }
      >
        <div class="exhibit-grid">
          {seasoningExhibits.map((e) => (
            <ExhibitImage key={e.id} {...e} />
          ))}
        </div>
      </Panel>

      <Panel
        exhibit={4}
        title="Variable dictionary"
        source={{ endpoint: 'GET /api/model/variable_dictionary', runDate: runDate() }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'variable_dictionary',
            exhibitLabel: 'Exhibit 4',
            title: 'Variable dictionary',
            recap: dict ? `${dict.rows.length} model variables documented, spanning baseline, borrower, collateral, macro and incentive families.` : 'no data rendered yet',
          })
        }
      >
        <VariableDictionary dict={dict} />
      </Panel>

      <Panel
        exhibit={5}
        title="Macro data glossary"
        subtitle="Every FRED/macro series across the DCR (national) and SFLLD (state) panels and the satellite Z regression -- source, geography, transformation, and why each lag."
        source={{ endpoint: 'GET /api/model/macro_glossary', runDate: runDate() }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'macro_glossary',
            exhibitLabel: 'Exhibit 5',
            title: 'Macro data glossary',
            recap: macroGlossary
              ? `${macroGlossary.series.length} macro series documented across DCR, SFLLD and the satellite: ${macroGlossary.series.map((s) => s.label).join('; ')}.`
              : 'no data rendered yet',
          })
        }
      >
        <MacroGlossary glossary={macroGlossary} />
      </Panel>

      <Panel
        id="panel-lgd"
        exhibit={6}
        title="LGD — two-stage workout model"
        source={{ endpoint: 'GET /api/model/lgd', runDate: runDate() }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'lgd',
            exhibitLabel: 'Exhibit 6',
            title: 'LGD — two-stage workout model',
            recap: lgd
              ? `Cure rate ${(lgd.cure_rate * 100).toFixed(1)}%, cure AUC (train/OOT) ${lgd.cure_auc.train.toFixed(3)}/${lgd.cure_auc.oot.toFixed(3)}, excess-loss loading ${(lgd.excess_loss_loading * 100).toFixed(2)}%.`
              : 'no data rendered yet',
          })
        }
      >
        <LgdSection lgd={lgd} exhibits={exhibits} />
      </Panel>

      <Panel
        id="panel-ead-eir"
        title="EAD & EIR method"
        subtitle="The two ECL terms with no coefficients to show — exposure and discounting are conventions, so here they are, stated exactly as the engine documents them."
        buildExplainQuestion={buildEadEirExplainQuestion}
      >
        <EadEirMethod />
      </Panel>
    </div>
  );
}
