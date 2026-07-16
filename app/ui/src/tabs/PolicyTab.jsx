import { useEffect, useState } from 'preact/hooks';
import { explainPanelQuestion, getStagingSensitivity, getWeightsTable } from '../api.js';
import { fmtMillions, fmtPct, fmtPctScale, runDate } from '../format.js';
import DecisionHeader from '../components/DecisionHeader.jsx';
import ExhibitImage from '../components/ExhibitImage.jsx';
import StageGuide from '../components/StageGuide.jsx';
import WeightsBarChart from '../components/WeightsBarChart.jsx';
import Panel from '../components/Panel.jsx';

function StagingSensitivityPanel({ data }) {
  if (!data) return null;
  return (
    <Panel
      exhibit={1}
      title="Stage-2 share vs SICR threshold"
      source={{ endpoint: 'GET /api/policy/staging_sensitivity', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'staging_sensitivity',
          exhibitLabel: 'Exhibit 1',
          title: 'Stage-2 share vs SICR threshold',
          recap: `Thresholds shown: ${data.thresholds.join(', ')}; add-on held at ${data.add_on_pp}pp across every threshold. ${data.reading}`,
        })
      }
    >
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
                <th class="num" key={th}>Stage 2 share ({th}) (%)</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.t}>
                <td>{r.t}</td>
                <td>{r.period}</td>
                {data.thresholds.map((th) => (
                  <td class="num" key={th}>{fmtPctScale(r.stage2_share_pct[th])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="panel-sub">Add-on held at {data.add_on_pp}pp across every threshold shown.</p>
    </Panel>
  );
}

function WeightsTablePanel({ data }) {
  if (!data) return null;
  const adopted = data.weight_sets.find((w) => w.id === 'adopted');
  return (
    <Panel
      exhibit={2}
      title="Scenario-weight sensitivity"
      source={{ endpoint: 'GET /api/policy/weights_table', runDate: runDate() }}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'weights_table',
          exhibitLabel: 'Exhibit 2',
          title: 'Scenario-weight sensitivity',
          recap: data.weight_sets
            .map((w) => `${w.label} (${fmtPct(w.weights.up, 0)}/${fmtPct(w.weights.base, 0)}/${fmtPct(w.weights.down, 0)}): allowance ${fmtMillions(w.weighted_allowance / 1e6)}, ${w.delta_vs_adopted_pct >= 0 ? '+' : ''}${w.delta_vs_adopted_pct.toFixed(1)}% vs adopted`)
            .join('; '),
        })
      }
    >
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
              <th>Up / Base / Down (%)</th>
              <th class="num">Weighted allowance ($m)</th>
              <th class="num">Coverage (%)</th>
              <th class="num">Jensen ratio (x)</th>
              <th class="num">Δ vs adopted (%)</th>
            </tr>
          </thead>
          <tbody>
            {data.weight_sets.map((w) => (
              <tr key={w.id} class={w.id === 'adopted' ? 'row-adopted' : ''}>
                <td>
                  {w.label}
                  {w.id === 'adopted' && <span class="adopted-tag">ADOPTED</span>}
                </td>
                <td>
                  {fmtPct(w.weights.up, 0)} / {fmtPct(w.weights.base, 0)} /{' '}
                  {fmtPct(w.weights.down, 0)}
                </td>
                <td class="num">{fmtMillions(w.weighted_allowance / 1e6)}</td>
                <td class="num">{fmtPct(w.coverage)}</td>
                <td class="num">{w.jensen_ratio.toFixed(4)}×</td>
                <td class="num">
                  {w.id === 'adopted' ? (
                    '—'
                  ) : (
                    /* Δ-vs-adopted pill (§5.3): ▲/▼ inside the same text run —
                       one coherent string for screen readers. Up = allowance
                       above the adopted basis (a provisions cost increase). */
                    <span
                      class={`delta-pill ${w.delta_vs_adopted_pct >= 0 ? 'delta-pill-bad' : 'delta-pill-good'}`}
                    >
                      {w.delta_vs_adopted_pct >= 0 ? '▲' : '▼'}{' '}
                      {Math.abs(w.delta_vs_adopted_pct).toFixed(1)}% vs adopted
                    </span>
                  )}
                </td>
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
        {adopted ? ` Adopted basis: ${fmtMillions(adopted.weighted_allowance / 1e6)}.` : ''}
      </p>
    </Panel>
  );
}

function StageGuidePanel() {
  return (
    <Panel
      title="Stage → ECL horizon guide"
      dense={false}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'stage_guide',
          title: 'Stage → ECL horizon guide',
          recap:
            'Stage 1 (performing) = 12-month ECL; Stage 2 (SICR, lifetime PD > 2x origination + 0.5pp add-on) = lifetime ECL over the remaining contractual life; Stage 3 (impaired) = LGD x current exposure.',
        })
      }
    >
      <DecisionHeader>
        How does a loan's stage translate into the ECL horizon — 12-month vs
        full lifetime — that the allowance is computed over?
      </DecisionHeader>
      <StageGuide />
    </Panel>
  );
}

function OverlayNotePanel() {
  return (
    <Panel
      title="When judgment overrides the model — the overlay question"
      dense={false}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'overlay_note',
          title: 'When judgment overrides the model — the overlay question',
          recap:
            'This engine reports a model-driven allowance; a defensible management overlay needs a named trigger, an evidence-based quantification basis, allocation to the stages/segments it affects, and exit criteria.',
        })
      }
    >
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
    </Panel>
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
