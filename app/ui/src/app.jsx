import { useEffect, useState } from 'preact/hooks';
import ExecutiveTab from './tabs/ExecutiveTab.jsx';
import ModelTab from './tabs/ModelTab.jsx';
import ScenarioLabTab from './tabs/ScenarioLabTab.jsx';
import PolicyTab from './tabs/PolicyTab.jsx';
import FreddieTab from './tabs/FreddieTab.jsx';
import CopilotTab from './tabs/CopilotTab.jsx';
import MiniChatDock from './components/MiniChatDock.jsx';
import SelectionExplain from './components/SelectionExplain.jsx';
import { getSummary } from './api.js';
import { fmtMillions } from './format.js';

// Simple hash router — no router library, per the north-star build spec.
const TABS = [
  { id: 'executive', label: 'Executive Overview', Comp: ExecutiveTab },
  { id: 'model', label: 'The Model', Comp: ModelTab },
  { id: 'scenario', label: 'Scenario Lab', Comp: ScenarioLabTab },
  { id: 'policy', label: 'Policy', Comp: PolicyTab },
  { id: 'freddie', label: 'Real Data', Comp: FreddieTab },
  { id: 'copilot', label: 'Copilot', Comp: CopilotTab },
];

function tabFromHash() {
  const h = (location.hash || '').replace('#', '');
  return TABS.some((t) => t.id === h) ? h : 'executive';
}

export default function App() {
  const [tabId, setTabId] = useState(tabFromHash());
  const [meta, setMeta] = useState(null);

  useEffect(() => {
    const onHash = () => setTabId(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    let alive = true;
    getSummary()
      .then((s) => alive && setMeta(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  const go = (id) => {
    location.hash = id;
    setTabId(id);
  };

  const active = TABS.find((t) => t.id === tabId) ?? TABS[0];
  const Active = active.Comp;
  const activeIdx = TABS.indexOf(active);

  const onTabKeyDown = (e) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    e.preventDefault();
    const dir = e.key === 'ArrowRight' ? 1 : -1;
    const next = TABS[(activeIdx + dir + TABS.length) % TABS.length];
    go(next.id);
    e.currentTarget.parentElement?.querySelector(`[data-tab-id="${next.id}"]`)?.focus();
  };

  return (
    <div class="app-shell">
      <header class="app-header">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">
            9
          </span>
          <span class="brand-name">IFRS 9 ECL Copilot</span>
          <a
            class="mdd-link"
            href="/static/mdd/MDD.html"
            target="_blank"
            rel="noopener noreferrer"
          >
            MDD
          </a>
          <a
            class="mdd-link"
            href="https://metaphorpritam.github.io/IFRS9_ECL_Agentic_AI/"
            target="_blank"
            rel="noopener noreferrer"
            data-tip="The 13-chapter study compendium + CV dossier"
          >
            Notes
          </a>
        </div>
        <span class="grounded-badge">
          <span class="status-dot status-dot-good" />
          every figure cites its source
        </span>
        {meta && (
          <span class="header-meta">
            {meta.as_of.period} · {meta.n_loans.toLocaleString()} loans ·{' '}
            {fmtMillions(meta.balance / 1e6)} book
          </span>
        )}
      </header>

      <nav class="tab-nav" role="tablist" aria-label="Primary">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            data-tab-id={t.id}
            tabindex={t.id === tabId ? 0 : -1}
            aria-selected={t.id === tabId}
            class={`tab-btn ${t.id === tabId ? 'active' : ''}`}
            onClick={() => go(t.id)}
            onKeyDown={onTabKeyDown}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main class="app-main">
        <Active />
      </main>

      <SelectionExplain tabLabel={active.label} />

      {tabId !== 'copilot' && <MiniChatDock tabLabel={active.label} />}
    </div>
  );
}
