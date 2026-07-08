import { Fragment } from 'preact';
import { useEffect, useMemo, useState } from 'preact/hooks';
import {
  getModelCoefficients,
  getVariableDictionary,
  getLgd,
  getExhibitsList,
} from '../api.js';
import SearchableTable from '../components/SearchableTable.jsx';
import ExhibitImage from '../components/ExhibitImage.jsx';

const FAMILY_LABEL = {
  baseline: 'Baseline (seasoning)',
  borrower: 'Borrower quality',
  collateral: 'Collateral / equity',
  macro: 'Macro-economic',
  incentive: 'Incentive / behavioural',
};

function CoefficientsTable({ model }) {
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
            <th>Variable</th>
            <th>Hazard ratio</th>
            <th>95% CI</th>
            <th>p</th>
          </tr>
        </thead>
        <tbody>
          {families.map((fam) => (
            <Fragment key={fam}>
              <tr class="family-row">
                <td colSpan={4}>{FAMILY_LABEL[fam] ?? fam}</td>
              </tr>
              {model.coefficients
                .filter((c) => c.family === fam)
                .map((c) => (
                  <tr key={c.variable}>
                    <td>{c.variable}</td>
                    <td class={c.hazard_ratio > 1 ? 'hr-up' : 'hr-down'}>
                      {c.hazard_ratio.toFixed(4)}
                    </td>
                    <td>[{c.ci[0].toFixed(3)}, {c.ci[1].toFixed(3)}]</td>
                    <td>{c.p_display}</td>
                  </tr>
                ))}
              <tr class="story-row">
                <td colSpan={4}>
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
              <th>n fit</th>
              <th>Events</th>
              <th>Train AUC</th>
              <th>OOT AUC</th>
              <th>McFadden R²</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.label}</td>
                <td>{r.n_fit.toLocaleString()}</td>
                <td>{r.events.toLocaleString()}</td>
                <td>{r.train_auc.toFixed(4)}</td>
                <td>{r.oot_auc.toFixed(4)}</td>
                <td>{r.mcfadden_r2.toFixed(4)}</td>
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

function LgdSection({ lgd, exhibits }) {
  if (!lgd) return null;
  const calRows = Object.entries(lgd.oot_calibration).map(([key, v]) => ({
    metric: key.replace(/_/g, ' '),
    train: v.train,
    oot: v.oot,
  }));
  const coefCols = [
    { key: 'variable', label: 'Variable' },
    { key: 'coef', label: 'Coef', render: (r) => r.coef.toFixed(4) },
    { key: 'se', label: 'SE', render: (r) => (r.se ?? r.se_hc1)?.toFixed(4) },
    { key: 'z', label: 'z', render: (r) => r.z.toFixed(3) },
    { key: 'p', label: 'p', render: (r) => r.p.toFixed(4) },
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
            <tr><th>Metric</th><th>Train</th><th>OOT</th></tr>
          </thead>
          <tbody>
            {calRows.map((r) => (
              <tr key={r.metric}>
                <td class="cap">{r.metric}</td>
                <td>{r.train.toFixed(4)}</td>
                <td>{r.oot.toFixed(4)}</td>
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
  const [lgd, setLgd] = useState(null);
  const [exhibits, setExhibits] = useState([]);
  const [selected, setSelected] = useState('default');
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([getModelCoefficients(), getVariableDictionary(), getLgd(), getExhibitsList()])
      .then(([c, d, l, ex]) => {
        if (!alive) return;
        setCoeffs(c);
        setDict(d);
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

  return (
    <div class="tab-body">
      <header class="tab-intro">
        <h1>The Model</h1>
        <p>Coefficients, fit statistics, and the variable dictionary — with the honest caveats.</p>
      </header>

      {error && (
        <div class="empty-note">Engine API offline ({error}).</div>
      )}

      <section class="panel">
        <div class="panel-head">
          <h2>Hazard-ratio coefficients</h2>
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
        </div>
        <p class="panel-sub">
          Hazard ratio &gt; 1 = risk-increasing; &lt; 1 = risk-reducing (exp(coef) of a
          cloglog hazard). Each family's intuition story is below its rows.
        </p>
        <CoefficientsTable model={coeffs?.models?.[selected]} />
      </section>

      <section class="panel">
        <h2>Fit statistics</h2>
        <FitStats fitStats={coeffs?.fit_stats} />
      </section>

      <section class="panel">
        <h2>Seasoning &amp; term-structure exhibits</h2>
        <div class="exhibit-grid">
          {seasoningExhibits.map((e) => (
            <ExhibitImage key={e.id} {...e} />
          ))}
        </div>
      </section>

      <section class="panel">
        <h2>Variable dictionary</h2>
        <VariableDictionary dict={dict} />
      </section>

      <section class="panel">
        <h2>LGD — two-stage workout model</h2>
        <LgdSection lgd={lgd} exhibits={exhibits} />
      </section>
    </div>
  );
}
