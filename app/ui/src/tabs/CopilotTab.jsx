import { useState } from 'preact/hooks';
import ChatPanel from '../components/ChatPanel.jsx';
import AgentTrace from '../components/AgentTrace.jsx';
import { fmtTime } from '../format.js';

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
    <section class="panel">
      <h2>Session audit log</h2>
      <p class="panel-sub">
        Every question asked in this Copilot session, most recent first —
        click a row for the full trace. (No server-side history endpoint;
        this is this browser session's own runs.)
      </p>
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
    </section>
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
