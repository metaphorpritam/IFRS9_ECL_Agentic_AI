import { useCallback, useEffect, useState } from 'preact/hooks';
import { getSummary } from './api.js';
import { fmtMillions, fmtPct, fmtRatio } from './format.js';
import ScenarioControls from './components/ScenarioControls.jsx';
import WaterfallChart from './components/WaterfallChart.jsx';
import CreditCycleChart from './components/CreditCycleChart.jsx';
import AgentTrace from './components/AgentTrace.jsx';
import ChatPanel from './components/ChatPanel.jsx';

function StatTile({ label, value, hint }) {
  return (
    <div class="tile">
      <div class="tile-label">{label}</div>
      <div class="tile-value">{value}</div>
      {hint && <div class="tile-hint">{hint}</div>}
    </div>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [apiDown, setApiDown] = useState(false);
  const [rev, setRev] = useState(0);
  const [action, setAction] = useState(null); // last tool run: {label, result}

  useEffect(() => {
    let alive = true;
    getSummary()
      .then((s) => alive && (setSummary(s), setApiDown(false)))
      .catch(() => alive && setApiDown(true));
    return () => {
      alive = false;
    };
  }, [rev]);

  // After any tool run: keep the tool's own result (the header and waterfall
  // reflect the ACTION), and bump rev for anything that refetches.
  const onRan = useCallback((a) => {
    setAction(a ?? null);
    setRev((r) => r + 1);
  }, []);

  // Header values: the last action's engine numbers win over the baseline
  // summary; every value is a tool/engine result either way.
  const r = action?.result;
  const allowanceM =
    r?.shocked_allowance != null ? r.shocked_allowance / 1e6
    : r?.weighted_allowance != null ? r.weighted_allowance / 1e6
    : summary?.allowance_m;
  const coverage = r?.coverage ?? summary?.coverage;
  const jensen = r?.jensen_ratio ?? summary?.jensen_ratio;
  const afterHint = action ? `after: ${action.label}` : 'probability-weighted';

  return (
    <div class="page">
      <header class="header">
        <div class="header-title">
          <h1>IFRS 9 ECL Copilot</h1>
          <p class="header-sub">
            Scenario-conditional expected credit loss — every number computed by
            the validated engine; the LLM only routes, parameterises and
            narrates.
          </p>
          {apiDown && (
            <p class="header-offline">
              Engine API offline — start the FastAPI service on :7860.
            </p>
          )}
        </div>
        <div class="tiles">
          <StatTile
            label="Reported allowance"
            value={fmtMillions(allowanceM)}
            hint={afterHint}
          />
          <StatTile
            label="Coverage"
            value={fmtPct(coverage)}
            hint="allowance / EAD"
          />
          <StatTile
            label="Jensen ratio"
            value={fmtRatio(jensen)}
            hint="weighted ECL vs avg path"
          />
        </div>
      </header>

      <main class="grid">
        <div class="col-controls">
          <ScenarioControls onRan={onRan} />
        </div>
        <div class="col-waterfall">
          <WaterfallChart rev={rev} action={action} />
        </div>
        <div class="col-cycle">
          <CreditCycleChart />
        </div>
        <div class="col-trace">
          <AgentTrace />
        </div>
        <div class="col-chat">
          <ChatPanel />
        </div>
      </main>
    </div>
  );
}
