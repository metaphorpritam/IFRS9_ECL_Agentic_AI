import { useEffect, useState } from 'preact/hooks';
import { getSummary } from '../api.js';
import { fmtMillions, fmtPct, fmtPctScale, fmtRatio } from '../format.js';
import StatTile from '../components/StatTile.jsx';
import StageMixBar from '../components/StageMixBar.jsx';
import WaterfallChart from '../components/WaterfallChart.jsx';
import CreditCycleChart from '../components/CreditCycleChart.jsx';

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

function ScenarioTable({ scenarios }) {
  return (
    <div class="table-scroll">
      <table class="data-table">
        <thead>
          <tr>
            <th>Scenario</th>
            <th>Weight</th>
            <th>Allowance</th>
            <th>Coverage</th>
            <th>UER peak</th>
          </tr>
        </thead>
        <tbody>
          {scenarios.map((sc) => (
            <tr key={sc.name}>
              <td class="cap">{sc.name}</td>
              <td>{fmtPct(sc.weight, 0)}</td>
              <td>{fmtMillions(sc.allowance / 1e6)}</td>
              <td>{fmtPct(sc.coverage)}</td>
              <td>{sc.uer_peak_pp.toFixed(1)}pp</td>
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
            />
            <StatTile
              label="Coverage"
              value={fmtPct(summary.coverage)}
              hint="allowance / balance"
            />
            <StatTile
              label="Jensen ratio"
              value={fmtRatio(summary.jensen_ratio)}
              hint="weighted ECL vs avg-path ECL"
            />
            <StatTile
              label="Reporting date"
              value={summary.as_of.period}
              hint={`t=${summary.as_of.t} of 60`}
            />
          </div>

          <section class="panel">
            <h2>Stage mix of allowance</h2>
            <p class="panel-sub">
              Part-to-whole share of the reported allowance by IFRS 9 stage (colour = risk
              state, not identity).
            </p>
            <StageMixBar stageMix={summary.stage_mix} />
          </section>

          <section class="panel narrative-panel">
            <h2>Consultant's read</h2>
            <p class="narrative-text">{narrative(summary)}</p>
          </section>

          <section class="panel">
            <h2>Scenario table</h2>
            <p class="panel-sub">Adopted weights: {(summary.weights.up * 100).toFixed(0)}/{(summary.weights.base * 100).toFixed(0)}/{(summary.weights.down * 100).toFixed(0)} (up/base/down).</p>
            <ScenarioTable scenarios={summary.scenarios} />
          </section>
        </>
      )}

      <WaterfallChart t0={20} t1={40} action={null} />
      <CreditCycleChart />
    </div>
  );
}
