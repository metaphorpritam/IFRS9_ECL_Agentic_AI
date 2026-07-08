import { useEffect, useState } from 'preact/hooks';
import { getStagingSensitivity, getWeightsTable } from '../api.js';
import { fmtMillions, fmtPct, fmtPctScale } from '../format.js';
import DecisionHeader from '../components/DecisionHeader.jsx';
import ExhibitImage from '../components/ExhibitImage.jsx';
import StageGuide from '../components/StageGuide.jsx';
import WeightsBarChart from '../components/WeightsBarChart.jsx';

function StagingSensitivityPanel({ data }) {
  if (!data) return null;
  return (
    <section class="panel">
      <h2>Stage-2 share vs SICR threshold</h2>
      <DecisionHeader>
        Where would you set the SICR (significant-increase-in-credit-risk) ratio
        threshold that triggers Stage 2? — the 2.0× adopted convention vs the
        alternatives shown.
      </DecisionHeader>
      <ExhibitImage png_url={data.image_url} caption={data.reading} />
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>t</th>
              <th>Period</th>
              {data.thresholds.map((th) => (
                <th key={th}>{th}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.t}>
                <td>{r.t}</td>
                <td>{r.period}</td>
                {data.thresholds.map((th) => (
                  <td key={th}>{fmtPctScale(r.stage2_share_pct[th])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="panel-sub">Add-on held at {data.add_on_pp}pp across every threshold shown.</p>
    </section>
  );
}

function WeightsTablePanel({ data }) {
  if (!data) return null;
  return (
    <section class="panel">
      <h2>Scenario-weight sensitivity</h2>
      <DecisionHeader>
        Management judgment: which probability weighting across up / base / down
        scenarios best reflects "reasonable and supportable" forward-looking
        information?
      </DecisionHeader>
      <WeightsBarChart weightSets={data.weight_sets} />
      <div class="table-scroll">
        <table class="data-table">
          <thead>
            <tr>
              <th>Weight set</th>
              <th>Up / Base / Down</th>
              <th>Weighted allowance</th>
              <th>Coverage</th>
              <th>Jensen ratio</th>
              <th>Δ vs adopted</th>
            </tr>
          </thead>
          <tbody>
            {data.weight_sets.map((w) => (
              <tr key={w.id} class={w.id === 'adopted' ? 'row-adopted' : ''}>
                <td>{w.label}</td>
                <td>
                  {fmtPct(w.weights.up, 0)} / {fmtPct(w.weights.base, 0)} /{' '}
                  {fmtPct(w.weights.down, 0)}
                </td>
                <td>{fmtMillions(w.weighted_allowance / 1e6)}</td>
                <td>{fmtPct(w.coverage)}</td>
                <td>{w.jensen_ratio.toFixed(4)}×</td>
                <td>{w.delta_vs_adopted_pct >= 0 ? '+' : ''}{w.delta_vs_adopted_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="panel-sub">
        Governance note: viewing this table calls the real reweight_scenarios
        tool for each of the three sets and appends to the audit trail —
        every reweighting the app has ever shown a user is logged, including
        from this convenience view.
      </p>
    </section>
  );
}

function StageGuidePanel() {
  return (
    <section class="panel">
      <h2>Stage → ECL horizon guide</h2>
      <DecisionHeader>
        How does a loan's stage translate into the ECL horizon — 12-month vs
        full lifetime — that the allowance is computed over?
      </DecisionHeader>
      <StageGuide />
    </section>
  );
}

function OverlayNotePanel() {
  return (
    <section class="panel">
      <h2>When judgment overrides the model — the overlay question</h2>
      <DecisionHeader>
        When does experienced credit judgment override the modelled number —
        and how is that override governed, quantified and eventually retired?
      </DecisionHeader>
      <p class="overlay-note">
        This engine reports a model-driven allowance: every figure on every
        tab traces to the frozen hazard/LGD/EAD/staging/ECL modules. Real
        portfolios routinely sit a modelled number next to a{' '}
        <b>post-model adjustment (overlay)</b> — the 2020 COVID-19 shock is
        the textbook case: default-rate models trained on pre-pandemic data
        could not see furlough schemes, payment holidays or the speed of the
        macro shock, so most large banks booked material management overlays
        on top of (not instead of) their IFRS 9 models that year, and
        supervisors (the ECB's 2024 thematic review, the PRA's Dear-CFO
        letters) still find roughly a quarter of performing-book coverage
        held as overlay at some institutions — with explicit warnings that
        overlays applied at the total-ECL level, bypassing PD and staging,
        are contrary to IFRS 9 principles and an earnings-management risk if
        left ungoverned.
      </p>
      <p class="overlay-note">
        A defensible overlay has four parts, and this app's design is meant
        to make each one legible rather than opaque: a named{' '}
        <b>trigger</b> (a model blind spot or genuinely novel risk — not "the
        model number looked wrong"), a <b>quantification basis</b> tied to
        evidence (a sensitivity run, a peer benchmark — never a plug),
        <b> allocation</b> to the stages and segments it actually affects (so
        staging and scenario logic still function underneath it), and{' '}
        <b>exit criteria</b> — the evidence that lets the overlay be retired
        or migrated into the model itself. The Scenario Lab's shock and
        reweight tools are the model-native way to explore "what would an
        overlay-sized stress look like" before reaching for a judgmental
        add-on.
      </p>
    </section>
  );
}

export default function PolicyTab() {
  const [staging, setStaging] = useState(null);
  const [weights, setWeights] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    Promise.all([getStagingSensitivity(), getWeightsTable()])
      .then(([s, w]) => alive && (setStaging(s), setWeights(w)))
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, []);

  return (
    <div class="tab-body">
      <header class="tab-intro">
        <h1>Policy</h1>
        <p>
          Every exhibit below is paired with the governance decision it
          informs — the dials a credit-risk committee actually turns.
        </p>
      </header>
      {error && <div class="empty-note">Engine API offline ({error}).</div>}
      <StagingSensitivityPanel data={staging} />
      <WeightsTablePanel data={weights} />
      <StageGuidePanel />
      <OverlayNotePanel />
    </div>
  );
}
