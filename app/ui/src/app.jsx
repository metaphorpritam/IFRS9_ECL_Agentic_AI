import { useEffect, useState } from 'preact/hooks';
import ExecutiveTab from './tabs/ExecutiveTab.jsx';
import ModelTab from './tabs/ModelTab.jsx';
import ScenarioLabTab from './tabs/ScenarioLabTab.jsx';
import PolicyTab from './tabs/PolicyTab.jsx';
import CopilotTab from './tabs/CopilotTab.jsx';
import MiniChatDock from './components/MiniChatDock.jsx';

// Simple hash router — no router library, per the north-star build spec.
const TABS = [
  { id: 'executive', label: 'Executive Overview', Comp: ExecutiveTab },
  { id: 'model', label: 'The Model', Comp: ModelTab },
  { id: 'scenario', label: 'Scenario Lab', Comp: ScenarioLabTab },
  { id: 'policy', label: 'Policy', Comp: PolicyTab },
  { id: 'copilot', label: 'Copilot', Comp: CopilotTab },
];

function tabFromHash() {
  const h = (location.hash || '').replace('#', '');
  return TABS.some((t) => t.id === h) ? h : 'executive';
}

export default function App() {
  const [tabId, setTabId] = useState(tabFromHash());

  useEffect(() => {
    const onHash = () => setTabId(tabFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const go = (id) => {
    location.hash = id;
    setTabId(id);
  };

  const active = TABS.find((t) => t.id === tabId) ?? TABS[0];
  const Active = active.Comp;

  return (
    <div class="app-shell">
      <header class="app-header">
        <div class="brand">
          <span class="brand-mark">IFRS 9</span>
          <span class="brand-name">ECL Copilot</span>
        </div>
        <nav class="tab-nav" role="tablist" aria-label="Primary">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={t.id === tabId}
              class={`tab-btn ${t.id === tabId ? 'active' : ''}`}
              onClick={() => go(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main class="app-main">
        <Active />
      </main>

      {tabId !== 'copilot' && <MiniChatDock tabLabel={active.label} />}
    </div>
  );
}
