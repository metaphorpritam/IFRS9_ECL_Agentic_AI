import { useEffect, useRef, useState } from 'preact/hooks';
import { AGENT_STREAM_URL } from '../api.js';
import { fmtTime } from '../format.js';

const MAX_EVENTS = 200;

const TYPE_META = {
  router: { label: 'ROUTER', cls: 'badge-router' },
  tool_call: { label: 'TOOL CALL', cls: 'badge-tool' },
  tool_result: { label: 'RESULT', cls: 'badge-result' },
  narration: { label: 'NARRATION', cls: 'badge-narration' },
  error: { label: 'ERROR', cls: 'badge-error' },
};

function EventRow({ ev }) {
  const meta = TYPE_META[ev.type] ?? { label: (ev.type || 'EVENT').toUpperCase(), cls: 'badge-other' };
  return (
    <li class="trace-row">
      <span class="trace-time">{fmtTime(ev.at)}</span>
      <span class={`badge ${meta.cls}`}>{meta.label}</span>
      <span class="trace-body">
        {ev.tool && <code class="trace-tool">{ev.tool}</code>}
        {ev.args !== undefined && (
          <code class="trace-args">{JSON.stringify(ev.args)}</code>
        )}
        {ev.result !== undefined && (
          <code class="trace-args">{JSON.stringify(ev.result)}</code>
        )}
        {ev.text && <span>{ev.text}</span>}
      </span>
    </li>
  );
}

/** Live tool-call log streamed from the agent over SSE. */
export default function AgentTrace() {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState('connecting');
  const listRef = useRef(null);

  useEffect(() => {
    const es = new EventSource(AGENT_STREAM_URL);
    es.onopen = () => setStatus('live');
    es.onerror = () => setStatus('reconnecting'); // EventSource auto-retries
    es.onmessage = (e) => {
      let d;
      try {
        d = JSON.parse(e.data);
      } catch {
        d = { type: 'narration', text: e.data };
      }
      setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), { ...d, at: Date.now() }]);
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events]);

  return (
    <section class="panel">
      <div class="panel-head">
        <h2>Agent trace</h2>
        <span class={`conn conn-${status}`}>
          <span class="conn-dot" /> {status}
        </span>
      </div>
      <p class="panel-sub">
        Router decisions, typed tool calls, engine results, narration — the LLM
        never does arithmetic.
      </p>
      <ul class="trace-list" ref={listRef}>
        {events.length === 0 && (
          <li class="empty-note">Waiting for agent activity…</li>
        )}
        {events.map((ev, i) => (
          <EventRow ev={ev} key={i} />
        ))}
      </ul>
    </section>
  );
}
