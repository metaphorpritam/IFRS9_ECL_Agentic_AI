import { useEffect, useState } from 'preact/hooks';
import { askAgent } from '../api.js';
import { AgentMessage, isRefusalRoute } from './ChatPanel.jsx';

const SPARK_PATH = 'M8,0 L10,6 L16,8 L10,10 L8,16 L6,10 L0,8 L6,6 Z';

function useNarrowViewport() {
  const [narrow, setNarrow] = useState(
    typeof window !== 'undefined' ? window.innerWidth < 620 : false,
  );
  useEffect(() => {
    if (typeof window === 'undefined') return undefined;
    const onResize = () => setNarrow(window.innerWidth < 620);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return narrow;
}

/**
 * MiniChatDock (FINAL_SPEC §5.5): a fixed bottom-right pill bar, present on
 * tabs 1-4 (Copilot has its own full-page chat). Collapsed by default —
 * the agent is front-and-centre, never a drawer to discover. The status
 * dot + word are the REAL agent state (graft 2): GROUNDED after a cited
 * answer, THINKING in flight, OUT OF SCOPE after a refusal.
 */
export default function MiniChatDock({ tabLabel }) {
  const [expanded, setExpanded] = useState(false);
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [status, setStatus] = useState('idle'); // idle | thinking | grounded | refused
  const narrow = useNarrowViewport();
  const [narrowOpen, setNarrowOpen] = useState(false);

  const send = async (q) => {
    const trimmed = q.trim();
    if (!trimmed || status === 'thinking') return;
    setQuestion('');
    setMessages((m) => [...m, { role: 'user', text: trimmed }]);
    setStatus('thinking');
    setExpanded(true);
    try {
      const wire = `[${tabLabel}] ${trimmed}`;
      const res = await askAgent(wire);
      setMessages((m) => [...m, { role: 'agent', ...res }]);
      setStatus(isRefusalRoute(res.route) ? 'refused' : 'grounded');
    } catch (err) {
      setMessages((m) => [...m, { role: 'error', text: `Request failed: ${err.message}` }]);
      setStatus('refused');
    }
  };

  const submit = (e) => {
    e.preventDefault();
    send(question);
  };

  const statusMeta = {
    idle: { cls: 'status-dot-muted', word: 'ASK COPILOT' },
    thinking: { cls: 'status-dot-warn pulse', word: 'THINKING' },
    grounded: { cls: 'status-dot-good', word: 'GROUNDED' },
    refused: { cls: 'status-dot-muted', word: 'OUT OF SCOPE' },
  }[status];

  if (narrow && !narrowOpen) {
    return (
      <div class="mini-dock">
        <button
          type="button"
          class="mini-dock-send"
          aria-label="Open Copilot chat"
          onClick={() => setNarrowOpen(true)}
        >
          <svg viewBox="0 0 16 16" width="16" height="16" fill="currentColor" aria-hidden="true">
            <path d={SPARK_PATH} />
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div class="mini-dock">
      {expanded && messages.length > 0 && (
        <div class="mini-dock-panel">
          <div class="mini-dock-head">
            <span>Copilot — {tabLabel}</span>
            <button
              class="mini-dock-close"
              type="button"
              aria-label="Collapse chat"
              onClick={() => setExpanded(false)}
            >
              ×
            </button>
          </div>
          <div class="chat-panel chat-panel-dock">
            <div class="chat-log">
              {messages.map((msg, i) =>
                msg.role === 'user' ? (
                  <div class="msg msg-user" key={i}>
                    <p>{msg.text}</p>
                  </div>
                ) : msg.role === 'error' ? (
                  <div class="msg msg-error" key={i}>
                    <p>{msg.text}</p>
                  </div>
                ) : (
                  <AgentMessage msg={msg} key={i} />
                ),
              )}
            </div>
          </div>
        </div>
      )}
      <form class="mini-dock-bar" onSubmit={submit}>
        <span class="mini-dock-status">
          <span class={`status-dot ${statusMeta.cls}`} /> {statusMeta.word}
        </span>
        <input
          type="text"
          value={question}
          placeholder={`Ask about ${tabLabel}…`}
          onInput={(e) => setQuestion(e.currentTarget.value)}
          onFocus={() => messages.length > 0 && setExpanded(true)}
        />
        <button
          type="submit"
          class="mini-dock-send"
          disabled={!question.trim() || status === 'thinking'}
          aria-label="Send"
        >
          <svg viewBox="0 0 16 16" width="14" height="14" fill="currentColor" aria-hidden="true">
            <path d="M1 8 L15 1 L10 8 L15 15 Z" />
          </svg>
        </button>
      </form>
    </div>
  );
}
