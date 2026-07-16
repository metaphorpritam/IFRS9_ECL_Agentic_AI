import { useState } from 'preact/hooks';
import ChatPanel from '../components/ChatPanel.jsx';
import AgentTrace from '../components/AgentTrace.jsx';
import Panel from '../components/Panel.jsx';
import { fmtTime } from '../format.js';
import { explainPanelQuestion } from '../api.js';

const SUGGESTIONS = [
  'What is the reported allowance under the downside scenario?',
  'Write pandas to find the 10 largest-balance Stage 3 loans by exposure',
  'Why does the double-trigger LTV × UER coefficient come out negative?',
];

function AuditLogRow({ entry }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <li class="audit-row">
      <div class="audit-row-head" onClick={() => setExpanded((v) => !v)}>
        <span class="audit-time">{fmtTime(entry.at)}</span>
        <span class={`badge ${/^refus(e|al)$/i.test(entry.route || '') ? 'badge-error' : 'badge-tool'}`}>
          {entry.route}
        </span>
        <span class="audit-question">{entry.question}</span>
        <span class="audit-toggle">{expanded ? '▾' : '▸'}</span>
      </div>
      {expanded && (
        <div class="audit-row-body">
          <p class="audit-answer">{entry.answer}</p>
          {Array.isArray(entry.trace) && entry.trace.length > 0 && (
            <pre class="audit-trace">{JSON.stringify(entry.trace, null, 2)}</pre>
          )}
        </div>
      )}
    </li>
  );
}

/** Session-only audit log: this app has no GET history endpoint for past
 * /ask calls, so — per spec — this renders the session's own runs only,
 * built from each ChatPanel resolution via onResult. */
function AuditLog({ entries }) {
  return (
    <Panel
      title="Session audit log"
      subtitle="Every question asked in this Copilot session, most recent first — click a row for the full trace. (No server-side history endpoint; this is this browser session's own runs.)"
      dense={false}
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'session_audit_log',
          title: 'Session audit log',
          recap: entries.length
            ? `${entries.length} question(s) asked this session; most recent route: ${entries.at(-1).route}.`
            : 'no questions asked yet this session',
        })
      }
    >
      <ul class="audit-list">
        {entries.length === 0 && (
          <li class="empty-note">No questions asked yet this session.</li>
        )}
        {entries
          .slice()
          .reverse()
          .map((e, i) => (
            <AuditLogRow entry={e} key={i} />
          ))}
      </ul>
    </Panel>
  );
}

export default function CopilotTab() {
  const [log, setLog] = useState([]);

  return (
    <div class="tab-body copilot-tab">
      <header class="tab-intro">
        <h1>Copilot</h1>
        <p>
          Ask anything about the book. The router picks one of five
          validated paths — four numeric tools plus a documentation
          retriever — and the LLM narrates the result; it never computes a
          number itself. Out-of-scope questions are refused by design.
        </p>
      </header>

      <div class="copilot-grid">
        <div class="copilot-chat-col">
          <ChatPanel mode="full" suggestions={SUGGESTIONS} onResult={(e) => setLog((l) => [...l, e])} />
        </div>
        <div class="copilot-side-col">
          <AgentTrace />
          <AuditLog entries={log} />
        </div>
      </div>
    </div>
  );
}
