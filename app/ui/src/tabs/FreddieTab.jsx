import { useEffect, useState } from 'preact/hooks';
import {
  explainPanelQuestion,
  getFreddieSummary,
  getFreddieHazard,
  getFreddieBacktest,
  getFreddieExhibits,
} from '../api.js';
import { fmtNum, fmtPct, fmtRatio, runDate } from '../format.js';
import StatTile from '../components/StatTile.jsx';
import ExhibitImage from '../components/ExhibitImage.jsx';
import Panel from '../components/Panel.jsx';

// Local formatter: this tab's rates arrive pre-computed on the 0-100 scale
// (the *_pct convention, see docs/api_contract.md §4) -- never re-multiply.
const fmtPctScale100 = (v, dp = 2) =>
  v == null || Number.isNaN(Number(v)) ? '—' : `${Number(v).toFixed(dp)}%`;

function exhibitById(exhibits, id) {
  return exhibits.find((e) => e.id === id) || null;
}

function HeroTiles({ summary }) {
  if (!summary) return null;
  const { panel, hazard, covid, backtest_headline: bh, lstm } = summary;
  return (
    <div class="tiles">
      <StatTile
        label="SFLLD panel scale"
        value={fmtNum(panel.n_loans)}
        hint={`${fmtNum(panel.n_loan_months)} loan-months, ${panel.n_vintages} vintages`}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_panel_scale',
            title: 'SFLLD panel scale',
            recap: `${fmtNum(panel.n_loans)} loans, ${fmtNum(panel.n_loan_months)} loan-months across ${panel.n_vintages} vintages (2005-2010, 2014-2016, 2018-2025 -- 2011-2013/2017 are a documented coverage gap, never downloaded). Overall D90 rate ${fmtPctScale100(panel.overall_d90_rate_pct)}, overall prepay rate ${fmtPctScale100(panel.overall_prepay_rate_pct)}.`,
          })
        }
      />
      <StatTile
        label="Hazard OOT AUC: SFLLD vs DCR"
        value={`${hazard.oot_auc.toFixed(4)} / ${hazard.dcr_oot_auc.toFixed(4)}`}
        hint={`train ${hazard.train_auc.toFixed(4)} / ${hazard.dcr_train_auc.toFixed(4)}`}
        delta={{
          up: hazard.oot_auc > hazard.dcr_oot_auc,
          good: hazard.oot_auc > hazard.dcr_oot_auc,
          text: `${hazard.oot_auc > hazard.dcr_oot_auc ? '+' : ''}${(hazard.oot_auc - hazard.dcr_oot_auc).toFixed(4)} OOT AUC vs DCR`,
        }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_hazard_auc',
            title: 'Hazard OOT AUC: SFLLD vs DCR',
            recap: `Real-data (SFLLD) champion hazard: train AUC ${hazard.train_auc.toFixed(4)}, OOT AUC ${hazard.oot_auc.toFixed(4)}. DCR synthetic-panel champion: train AUC ${hazard.dcr_train_auc.toFixed(4)}, OOT AUC ${hazard.dcr_oot_auc.toFixed(4)}. McFadden pseudo-R2 (SFLLD fit sample) ${hazard.mcfadden_r2.toFixed(4)}.`,
          })
        }
      />
      <StatTile
        label="COVID regime treatment"
        value={covid.verdict.toUpperCase()}
        hint={`window ${covid.window} -- review overturn`}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_covid_verdict',
            title: 'COVID regime treatment',
            recap: `Recommended treatment: ${covid.verdict} (window ${covid.window}). OOT2 AUC -- naive ${covid.naive_oot2_auc.toFixed(4)}, additive ${covid.additive_oot2_auc.toFixed(4)}, exclude ${covid.exclude_oot2_auc.toFixed(4)}. ${covid.recommendation}`,
          })
        }
      />
      <StatTile
        label="Backtest: worst miss ratio"
        value={fmtRatio(bh.worst_miss_ratio_frozen)}
        hint={`${bh.worst_asof} -- frozen-macro projection, GFC`}
        delta={{ up: true, good: false, text: 'underpredicted the GFC' }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_backtest_miss',
            title: 'Backtest: worst miss ratio',
            recap: `At ${bh.worst_asof}, a model refit through that date with macro frozen underpredicts realized 36-month D90 by ${fmtRatio(bh.worst_miss_ratio_frozen)} (hindsight-macro miss ratio ${fmtRatio(bh.worst_miss_ratio_actual)}). Saturation case: ${bh.saturation_asof}, hindsight miss ratio ${fmtRatio(bh.saturation_miss_ratio_actual)} (macro ~20 SDs outside training support).`,
          })
        }
      />
      <StatTile
        label="LSTM challenger OOT AUC"
        value={lstm.oot_lstm_auc.toFixed(4)}
        hint={`vs champion ${lstm.oot_champion_auc.toFixed(4)}`}
        delta={{
          up: true, good: true,
          text: `+${(lstm.oot_lstm_auc - lstm.oot_champion_auc).toFixed(4)} vs champion`,
        }}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_lstm',
            title: 'LSTM challenger OOT AUC',
            recap: `LSTM path-dependence challenger OOT AUC ${lstm.oot_lstm_auc.toFixed(4)} vs champion ${lstm.oot_champion_auc.toFixed(4)}. Split by prior delinquency: prior-spell loans ${lstm.prior_dlq_champion_auc.toFixed(4)} -> ${lstm.prior_dlq_lstm_auc.toFixed(4)}; clean-history loans ${lstm.clean_champion_auc.toFixed(4)} -> ${lstm.clean_lstm_auc.toFixed(4)} (near-zero lift). Challenger-never-champion: discrimination-only scorecard, not integrated into the reported allowance.`,
          })
        }
      />
      <StatTile
        label="LGD excess-loss loading: SFLLD vs DCR"
        value={`${(summary.lgd.excess_loading_sflld * 100).toFixed(2)}% / ${(summary.lgd.excess_loading_dcr * 100).toFixed(2)}%`}
        hint={`mean realized LGD (train) ${(summary.lgd.mean_realized_lgd_train * 100).toFixed(1)}%`}
        buildExplainQuestion={() =>
          explainPanelQuestion({
            panelId: 'freddie_hero_lgd',
            title: 'LGD excess-loss loading: SFLLD vs DCR',
            recap: `SFLLD's realized-loss LGD refit: excess-loss loading ${(summary.lgd.excess_loading_sflld * 100).toFixed(2)}% vs the DCR champion's ${(summary.lgd.excess_loading_dcr * 100).toFixed(2)}%. Mean realized LGD (train) ${(summary.lgd.mean_realized_lgd_train * 100).toFixed(1)}%; cure-stage AUC train/OOT ${summary.lgd.cure_auc_train.toFixed(4)}/${summary.lgd.cure_auc_oot.toFixed(4)} (OOT is COVID-cure-dominated, not a like-for-like regime test).`,
          })
        }
      />
    </div>
  );
}

function VintageCurvesPanel({ exhibits }) {
  const ex = exhibitById(exhibits, 'freddie_vintage_curves');
  if (!ex) return null;
  return (
    <Panel
      exhibit={1}
      title="Vintage curves — the pre-crisis-vintage hump"
      source={{ endpoint: 'GET /api/freddie/exhibits', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_vintage_curves',
          exhibitLabel: 'Exhibit 1',
          title: ex.title,
          recap: ex.caption,
        })
      }
    >
      <ExhibitImage {...ex} tall />
    </Panel>
  );
}

function CovidAnomalyPanel({ exhibits }) {
  const rollRate = exhibitById(exhibits, 'freddie_roll_rate_matrices');
  const calendar = exhibitById(exhibits, 'freddie_calendar_time_series');
  if (!rollRate) return null;
  return (
    <Panel
      exhibit={2}
      title="The COVID roll-rate anomaly"
      subtitle="A naive D90-entry read makes COVID look like the worse credit event; the roll-rate breakdown shows the opposite."
      source={{ endpoint: 'GET /api/freddie/exhibits', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_covid_anomaly',
          exhibitLabel: 'Exhibit 2',
          title: 'The COVID roll-rate anomaly',
          recap: `${rollRate.caption} ${calendar ? calendar.caption : ''}`,
        })
      }
    >
      <div class="exhibit-grid">
        <ExhibitImage {...rollRate} />
        {calendar && <ExhibitImage {...calendar} />}
      </div>
      <p class="panel-sub">
        Net read: COVID's delinquency-status ladder (60→90+ roll, D90-entry rate) looks
        worse than the GFC by a naive count, but 90+→liquidation collapses over 10× in
        the same window — a forbearance-accounting artifact, not genuine credit
        deterioration.
      </p>
    </Panel>
  );
}

function BacktestPanel({ backtest }) {
  if (!backtest) return null;
  const rows = backtest.rows;
  const gfc = rows.find((r) => r.asof === '2007-12');
  return (
    <Panel
      exhibit={3}
      title="The backtest honesty panel — model risk, historicised"
      subtitle="Champion hazard refit-in-time at 5 pseudo-reporting dates, projected 36 months, scored against what actually happened."
      source={{ endpoint: 'GET /api/freddie/backtest', runDate: runDate() }}
      className="freddie-centerpiece"
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_backtest_honesty',
          exhibitLabel: 'Exhibit 3',
          title: 'The backtest honesty panel',
          recap: `${backtest.central_honesty_note} 2019-12 hindsight miss ratio ${rows.find((r) => r.asof === '2019-12')?.miss_ratio_actual.toFixed(3)}× (macro ~20 SDs outside training support).`,
        })
      }
    >
      {gfc && (
        <div class="callout callout-crit">
          <span class="callout-figure">{fmtRatio(gfc.miss_ratio_frozen)}</span>
          <span class="callout-text">
            underprediction of the 2007-12 GFC: a model refit through that date with
            macro frozen at then-current levels predicted {fmtPct(gfc.predicted_cum_d90_frozen, 3)}{' '}
            36-month D90 against a realized {fmtPct(gfc.realized_cum_d90, 3)}.
          </span>
        </div>
      )}
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Reporting date</th>
              <th class="num">Fit n / events</th>
              <th class="num">Active loans</th>
              <th class="num">Realized D90 (36mo)</th>
              <th class="num">Predicted (frozen)</th>
              <th class="num">Miss (frozen)</th>
              <th class="num">Predicted (hindsight)</th>
              <th class="num">Miss (hindsight)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.asof} class={r.asof === '2007-12' ? 'row-adopted' : ''}>
                <td>{r.asof}</td>
                <td class="num">{fmtNum(r.fit_n)} / {fmtNum(r.fit_events)}</td>
                <td class="num">{fmtNum(r.n_active_loans)}</td>
                <td class="num">{fmtPct(r.realized_cum_d90, 3)}</td>
                <td class="num">{fmtPct(r.predicted_cum_d90_frozen, 3)}</td>
                <td class="num">{fmtRatio(r.miss_ratio_frozen)}</td>
                <td class="num">{fmtPct(r.predicted_cum_d90_actual, 3)}</td>
                <td class="num">{fmtRatio(r.miss_ratio_actual)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="caveat">{backtest.central_honesty_note}</p>
      <p class="overlay-note">
        <b>Why this argues for scenario overlays.</b> The "frozen" column is exactly the
        naive point-in-time extrapolation IFRS 9 para 5.5.17 exists to prevent: a hazard
        scored with macro held at today's value, carried forward unchanged for 36
        months. At 2007-12 that produces a {fmtRatio(gfc?.miss_ratio_frozen ?? 0)} underprediction of
        the GFC — the model was never wrong about its own coefficients, it simply never
        saw the crisis coming because nothing in a frozen macro path could show it one.
        The "hindsight" column is the ceiling a perfect scenario overlay could reach
        (still a {fmtRatio(gfc?.miss_ratio_actual ?? 0)} miss in 2007-12 — spec/parameter risk no overlay
        closes) and, at 2019-12, the mirror failure: fed the real April-2020 unemployment
        print, the linear hazard saturates to a miss ratio of{' '}
        {fmtRatio(rows.find((r) => r.asof === '2019-12')?.miss_ratio_actual ?? 0)}, extrapolating
        ~20 standard deviations outside its training support. A forward-looking,
        probability-weighted scenario overlay — never a single frozen path — is what
        closes the gap this exhibit measures.
      </p>
    </Panel>
  );
}

function SeverityCyclePanel({ exhibits }) {
  const ex = exhibitById(exhibits, 'freddie_severity_cycle');
  if (!ex) return null;
  return (
    <Panel
      exhibit={4}
      title="Realized severity — a lagging, not coincident, indicator"
      source={{ endpoint: 'GET /api/freddie/exhibits', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_severity_cycle',
          exhibitLabel: 'Exhibit 4',
          title: ex.title,
          recap: ex.caption,
        })
      }
    >
      <ExhibitImage {...ex} tall />
    </Panel>
  );
}

function HazardVsDcrPanel({ hazard, exhibits }) {
  if (!hazard) return null;
  const seasoning = exhibitById(exhibits, 'freddie_seasoning_curve');
  const stateUer = exhibitById(exhibits, 'freddie_state_uer_effect');
  const calByYear = exhibitById(exhibits, 'freddie_hazard_calibration_by_year');
  const covidCal = exhibitById(exhibits, 'freddie_covid_calibration_comparison');
  return (
    <Panel
      exhibit={5}
      title="Champion hazard vs the DCR priors, and the COVID regime verdict"
      subtitle="Sign comparison against engine/hazard.py's expected directions, plus the reviewed COVID/forbearance regime treatment."
      source={{ endpoint: 'GET /api/freddie/hazard', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_hazard_vs_dcr',
          exhibitLabel: 'Exhibit 5',
          title: 'Champion hazard vs the DCR priors',
          recap: `Recommended COVID treatment: ${hazard.covid.verdict} (window ${hazard.covid.window}). ${hazard.covid.recommendation}`,
        })
      }
    >
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Variable</th>
              <th>DCR variable</th>
              <th>DCR expected sign</th>
            </tr>
          </thead>
          <tbody>
            {hazard.dcr_sign_comparison.map((r) => (
              <tr key={r.variable}>
                <td><code>{r.variable}</code></td>
                <td>{r.dcr_variable ? <code>{r.dcr_variable}</code> : '—'}</td>
                <td>{r.dcr_expected_sign}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="caveat">
        <b>COVID / forbearance regime — reviewed verdict: {hazard.covid.verdict}.</b>{' '}
        {hazard.covid.recommendation}
      </p>
      <div class="exhibit-grid">
        {calByYear && <ExhibitImage {...calByYear} />}
        {seasoning && <ExhibitImage {...seasoning} />}
        {stateUer && <ExhibitImage {...stateUer} />}
        {covidCal && <ExhibitImage {...covidCal} />}
      </div>
    </Panel>
  );
}

function StateHeterogeneityPanel({ exhibits }) {
  const ex = exhibitById(exhibits, 'freddie_state_heterogeneity');
  if (!ex) return null;
  return (
    <Panel
      exhibit={6}
      title="State heterogeneity — the collateral channel, in real geography"
      source={{ endpoint: 'GET /api/freddie/exhibits', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_state_heterogeneity',
          exhibitLabel: 'Exhibit 6',
          title: ex.title,
          recap: ex.caption,
        })
      }
    >
      <ExhibitImage {...ex} tall />
    </Panel>
  );
}

function LstmLiftPanel({ summary, exhibits }) {
  if (!summary) return null;
  const lstm = summary.lstm;
  const calibration = exhibitById(exhibits, 'freddie_lstm_calibration');
  const liftSplit = exhibitById(exhibits, 'freddie_lstm_lift_split');
  const rows = [
    { group: 'Overall OOT', champion: lstm.oot_champion_auc, model: lstm.oot_lstm_auc },
    { group: 'Clean history', champion: lstm.clean_champion_auc, model: lstm.clean_lstm_auc },
    { group: 'Prior delinquency spell', champion: lstm.prior_dlq_champion_auc, model: lstm.prior_dlq_lstm_auc },
  ];
  return (
    <Panel
      exhibit={7}
      title="LSTM path-dependence challenger — lift decomposition"
      subtitle="Challenger-never-champion: a discrimination-only scorecard testing whether trailing delinquency-path memory adds signal the current-state-only champion cannot see."
      source={{ endpoint: 'GET /api/freddie/summary', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'freddie_lstm_lift',
          exhibitLabel: 'Exhibit 7',
          title: 'LSTM path-dependence challenger',
          recap: rows.map((r) => `${r.group}: champion ${r.champion.toFixed(4)} -> LSTM ${r.model.toFixed(4)} (Δ ${(r.model - r.champion >= 0 ? '+' : '')}${(r.model - r.champion).toFixed(4)})`).join('; '),
        })
      }
    >
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Group</th>
              <th class="num">Champion AUC</th>
              <th class="num">LSTM AUC</th>
              <th class="num">Δ (LSTM − champion)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const delta = r.model - r.champion;
              return (
                <tr key={r.group}>
                  <td>{r.group}</td>
                  <td class="num">{r.champion.toFixed(4)}</td>
                  <td class="num">{r.model.toFixed(4)}</td>
                  <td class={`num ${delta >= 0 ? 'hr-down' : 'hr-up'}`}>
                    {delta >= 0 ? '+' : ''}{delta.toFixed(4)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p class="caveat">
        The lift concentrates almost entirely on loans with a prior delinquency spell
        (Δ {(lstm.prior_dlq_lstm_auc - lstm.prior_dlq_champion_auc).toFixed(4)}) vs
        essentially zero on clean-history loans (Δ{' '}
        {(lstm.clean_lstm_auc - lstm.clean_champion_auc).toFixed(4)}) — direct evidence
        for the path-dependence hypothesis. A forbearance-era delinquency-ladder
        distortion may inflate part of the 2020-21 window's contribution — flagged, not
        resolved, in the calibration chart's shaded window.
      </p>
      <div class="exhibit-grid">
        {liftSplit && <ExhibitImage {...liftSplit} />}
        {calibration && <ExhibitImage {...calibration} />}
      </div>
    </Panel>
  );
}

export default function FreddieTab() {
  const [summary, setSummary] = useState(null);
  const [hazard, setHazard] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [exhibits, setExhibits] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([
      getFreddieSummary(),
      getFreddieHazard(),
      getFreddieBacktest(),
      getFreddieExhibits(),
    ])
      .then(([s, h, b, ex]) => {
        if (!alive) return;
        setSummary(s);
        setHazard(h);
        setBacktest(b);
        setExhibits(ex.exhibits);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div class="tab-body">
      <header class="tab-intro">
        <h1>Real Data</h1>
        <p>
          The DCR engine above runs on a synthetic panel. This tab surfaces a second,
          real pipeline built on the actual Freddie Mac Single-Family Loan-Level Dataset
          (SFLLD) — a fresh champion hazard/LGD refit, an ALFRED-vintage backtest, and an
          LSTM path-dependence challenger — read-only, for comparison against the
          reported engine.
        </p>
      </header>

      {error && <div class="empty-note">Engine API offline ({error}).</div>}

      <HeroTiles summary={summary} />
      <VintageCurvesPanel exhibits={exhibits} />
      <CovidAnomalyPanel exhibits={exhibits} />
      <BacktestPanel backtest={backtest} />
      <SeverityCyclePanel exhibits={exhibits} />
      <HazardVsDcrPanel hazard={hazard} exhibits={exhibits} />
      <StateHeterogeneityPanel exhibits={exhibits} />
      <LstmLiftPanel summary={summary} exhibits={exhibits} />
    </div>
  );
}
