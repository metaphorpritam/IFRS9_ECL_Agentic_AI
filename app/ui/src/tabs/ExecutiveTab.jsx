import { useEffect, useState } from 'preact/hooks';
import { explainPanelQuestion, getSummary } from '../api.js';
import { fmtMillions, fmtPct, fmtPctScale, fmtRatio, runDate } from '../format.js';
import StatTile from '../components/StatTile.jsx';
import StageMixBar from '../components/StageMixBar.jsx';
import WaterfallChart from '../components/WaterfallChart.jsx';
import CreditCycleChart from '../components/CreditCycleChart.jsx';
import Panel from '../components/Panel.jsx';

// Template narrative — NOT an LLM call. Every number is read straight off
// /api/ecl/summary; this is consultant prose with blanks filled in, per the
// north-star spec ("template, not LLM").
function narrative(s) {
  const pct = (w) => (w * 100).toFixed(0);
  const s1 = s.stage_mix.stage1;
  const s2 = s.stage_mix.stage2;
  const s3 = s.stage_mix.stage3;
  const jensenDir = s.jensen_ratio > 1 ? 'above' : 'below';
  const jensenVerb = s.jensen_ratio > 1 ? 'adding to' : 'trimming';
  return (
    `As of ${s.as_of.period} (t=${s.as_of.t}), the book comprises ${s.n_loans.toLocaleString()} ` +
    `loans totalling ${fmtMillions(s.balance / 1e6)} of exposure. Under the adopted ` +
    `${pct(s.weights.up)}/${pct(s.weights.base)}/${pct(s.weights.down)} up/base/down scenario ` +
    `weighting, the reported scenario-weighted allowance is ${fmtMillions(s.weighted_allowance / 1e6)} ` +
    `— a coverage ratio of ${fmtPct(s.coverage)}. The Jensen ratio of ${fmtRatio(s.jensen_ratio)} shows ` +
    `the scenario-weighted allowance running ${jensenDir} the allowance computed at the single ` +
    `weighted-average macro path (${fmtMillions(s.allowance_at_average_path / 1e6)}): scenario convexity ` +
    `is ${jensenVerb} the reported number, the quantitative signature IFRS 9 asks firms to capture rather ` +
    `than approximate with a single central path. By allowance, the book is dominated by Stage 1 ` +
    `(${fmtPctScale(s1.allowance_pct_of_total)} across ${s1.n_loans.toLocaleString()} performing loans); ` +
    `Stage 2 (significant increase in credit risk) carries ${fmtPctScale(s2.allowance_pct_of_total)} from ` +
    `just ${s2.n_loans} loans, and Stage 3 (credit-impaired) contributes ${fmtPctScale(s3.allowance_pct_of_total)} ` +
    `of allowance from ${s3.n_loans} defaulted loans — a calm-quarter book where the reported number is set ` +
    `almost entirely by 12-month ECL and therefore is exactly where scenario weights and macro shocks act ` +
    `(see Scenario Lab).`
  );
}

// Leading 9px status dot per FINAL_SPEC §5.3/§1.3 — up = good, down =
// critical, base = neutral; the scenario NAME is the label, dot secondary.
const SCENARIO_DOT = { up: 'scenario-dot-good', base: 'scenario-dot-muted', down: 'scenario-dot-crit' };

function ScenarioTable({ scenarios }) {
  return (
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th class="num">Weight (%)</th>
            <th class="num">Allowance ($m)</th>
            <th class="num">Coverage (%)</th>
            <th class="num">UER peak (pp)</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((sc) => (
            <tr key={sc.name}>
              <td class="cap">
                <span
                  class={`scenario-dot ${SCENARIO_DOT[sc.name] ?? 'scenario-dot-muted'}`}
                  aria-hidden="true"
                />
                {sc.name}
              </td>
              <td class="num">{fmtPct(sc.weight, 0)}</td>
              <td class="num">{fmtMillions(sc.allowance / 1e6)}</td>
              <td class="num">{fmtPct(sc.coverage)}</td>
              <td class="num">{sc.uer_peak_pp.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ExecutiveTab() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    getSummary()
      .then((s) => alive && (setSummary(s), setError(null)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div class="tab-body">
      <header class="tab-intro">
        <h1>Executive Overview</h1>
        <p>
          The consultant's headline read of the book as reported — every
          figure below is an engine number as of the {summary?.as_of?.period ?? 'current'}{' '}
          reporting date.
        </p>
      </header>

      {error && (
        <div class="empty-note">
          Engine API offline ({error}). Start the FastAPI service on :7860.
        </div>
      )}

      {summary && (
        <>
          <div class="tiles">
            <StatTile
              label="Scenario-weighted allowance"
              value={fmtMillions(summary.weighted_allowance / 1e6)}
              hint={`${summary.n_loans.toLocaleString()} loans, ${fmtMillions(summary.balance / 1e6)} balance`}
              buildExplainQuestion={() =>
                explainPanelQuestion({
                  panelId: 'kpi_weighted_allowance',
                  title: 'Scenario-weighted allowance',
                  recap: `Reported scenario-weighted allowance is ${fmtMillions(summary.weighted_allowance / 1e6)} across ${summary.n_loans.toLocaleString()} loans (${fmtMillions(summary.balance / 1e6)} balance), under the adopted ${(summary.weights.up * 100).toFixed(0)}/${(summary.weights.base * 100).toFixed(0)}/${(summary.weights.down * 100).toFixed(0)} up/base/down weighting.`,
                })
              }
            />
            <StatTile
              label="Coverage"
              value={fmtPct(summary.coverage)}
              hint="allowance / balance"
              buildExplainQuestion={() =>
                explainPanelQuestion({
                  panelId: 'kpi_coverage',
                  title: 'Coverage',
                  recap: `Coverage (allowance / balance) is ${fmtPct(summary.coverage)}.`,
                })
              }
            />
            <StatTile
              label="Jensen ratio"
              value={fmtRatio(summary.jensen_ratio)}
              hint="weighted ECL vs avg-path ECL"
              buildExplainQuestion={() =>
                explainPanelQuestion({
                  panelId: 'kpi_jensen_ratio',
                  title: 'Jensen ratio',
                  recap: `Jensen ratio is ${fmtRatio(summary.jensen_ratio)} — scenario-weighted allowance ${fmtMillions(summary.weighted_allowance / 1e6)} vs allowance at the averaged macro path ${fmtMillions(summary.allowance_at_average_path / 1e6)}.`,
                })
              }
            />
            <StatTile
              label="Reporting date"
              value={summary.as_of.period}
              hint={`t=${summary.as_of.t} of 60`}
              buildExplainQuestion={() =>
                explainPanelQuestion({
                  panelId: 'kpi_reporting_date',
                  title: 'Reporting date',
                  recap: `Reporting date is ${summary.as_of.period} (t=${summary.as_of.t} of 60).`,
                })
              }
            />
          </div>

          <Panel
            exhibit={1}
            title="Stage mix of allowance"
            subtitle="Part-to-whole share of the reported allowance by IFRS 9 stage (colour = risk state, not identity)."
            source={{ endpoint: 'GET /api/ecl/summary', runDate: runDate() }}
            buildExplainQuestion={() =>
              explainPanelQuestion({
                panelId: 'stage_mix',
                exhibitLabel: 'Exhibit 1',
                title: 'Stage mix of allowance',
                recap: `Stage 1 ${fmtPctScale(summary.stage_mix.stage1.allowance_pct_of_total)} of allowance (${summary.stage_mix.stage1.n_loans} loans), Stage 2 ${fmtPctScale(summary.stage_mix.stage2.allowance_pct_of_total)} (${summary.stage_mix.stage2.n_loans} loans), Stage 3 ${fmtPctScale(summary.stage_mix.stage3.allowance_pct_of_total)} (${summary.stage_mix.stage3.n_loans} loans).`,
              })
            }
          >
            <StageMixBar stageMix={summary.stage_mix} />
          </Panel>

          <Panel
            title="Consultant's read"
            dense={false}
            className="narrative-panel"
            buildExplainQuestion={() =>
              explainPanelQuestion({
                panelId: 'consultant_read',
                title: "Consultant's read",
                recap: narrative(summary),
              })
            }
          >
            <p class="narrative-text">{narrative(summary)}</p>
          </Panel>

          <Panel
            exhibit={2}
            title="Scenario table"
            subtitle={`Adopted weights: ${(summary.weights.up * 100).toFixed(0)}/${(summary.weights.base * 100).toFixed(0)}/${(summary.weights.down * 100).toFixed(0)} (up/base/down).`}
            source={{ endpoint: 'GET /api/ecl/summary', runDate: runDate() }}
            buildExplainQuestion={() =>
              explainPanelQuestion({
                panelId: 'scenario_table',
                exhibitLabel: 'Exhibit 2',
                title: 'Scenario table',
                recap: summary.scenarios
                  .map((sc) => `${sc.name} ${fmtPct(sc.weight, 0)} weight, allowance ${fmtMillions(sc.allowance / 1e6)}, coverage ${fmtPct(sc.coverage)}`)
                  .join('; '),
              })
            }
          >
            <ScenarioTable scenarios={summary.scenarios} />
            <p class="caveat coherent-shock-note">
              <b>Coherent-shock convention.</b> Each scenario's macro path
              moves UER/HPI/GDP together (DFAST-coherent shapes); the
              satellite feeding this table has no unemployment term
              (Z = f(hpi_growth_lag1, gdp_growth_lag2)) — see the Macro
              data glossary on The Model tab.
            </p>
          </Panel>
        </>
      )}

      {/* Default window = the latest single quarter (FINAL_SPEC §8.2) — long
          cumulative windows (e.g. t=20→t=40) are a Scenario Lab drill-down,
          never the executive default. */}
      <WaterfallChart t0={59} t1={60} action={null} exhibit={summary ? 3 : null} />
      <CreditCycleChart exhibit={summary ? 4 : null} />
    </div>
  );
}
