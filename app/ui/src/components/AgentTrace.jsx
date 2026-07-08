import { useEffect, useRef, useState } from 'preact/hooks';
import { AGENT_STREAM_URL } from '../api.js';
import { fmtTime } from '../format.js';

const MAX_EVENTS = 200;

// Trace events are dicts {"node": router|<tool name>|narrator|refusal, ...}
// (docs/api_contract.md, GET /api/agent/stream) — NOT a `type` field. Any
// node that isn't router/narrator/refusal is a tool-execution node named
// after the tool itself (shock_macro, query_model_docs, analyze_data, ...);
// the offline fallback router also emits node "tool".
function eventMeta(ev) {
  if (ev.status === 'error') return { label: 'ERROR', cls: 'badge-error' };
  switch (ev.node) {
    case 'router':
      return { label: 'ROUTER', cls: 'badge-router' };
    case 'narrator':
      return { label: 'NARRATION', cls: 'badge-narration' };
    case 'refusal':
      return { label: 'REFUSAL', cls: 'badge-error' };
    case undefined:
      return { label: 'EVENT', cls: 'badge-other' };
    default:
      return { label: 'TOOL', cls: 'badge-tool' };
  }
}

// The most human line each event carries, across both the live LangGraph
// router's events (headline / detail / mode / message) and the offline
// keyword fallback router's (label / answer / detail).
const eventText = (ev) =>
  ev.headline ?? ev.answer ?? ev.message ?? ev.detail ?? ev.label ?? ev.mode ?? '';

function EventRow({ ev }) {
  const meta = eventMeta(ev);
  const isToolNode =
    ev.node && !['router', 'narrator', 'refusal', 'tool'].includes(ev.node);
  const toolName = ev.tool || ev.route || (isToolNode ? ev.node : null);
  return (
    <li class="trace-row">
      <span class="trace-time">{fmtTime(ev.at)}</span>
      <span class={`badge ${meta.cls}`}>{meta.label}</span>
      <span class="trace-body">
        {toolName && <code class="trace-tool">{toolName}</code>}
        {ev.args !== undefined && (
          <code class="trace-args">{JSON.stringify(ev.args)}</code>
        )}
        <span>{eventText(ev)}</span>
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
        d = { node: 'narrator', detail: e.data };
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
