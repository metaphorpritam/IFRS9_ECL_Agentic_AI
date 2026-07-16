import { useState } from 'preact/hooks';
import { askAgent, explainPanelQuestion } from '../api.js';
import { renderWithNums } from '../numText.jsx';
import { useExplain } from './ExplainButton.jsx';

// The live LangGraph router emits route "REFUSE" (agent/graph.py's REFUSE
// constant); the offline keyword fallback router emits "refusal" (see
// app/api/main.py). Both mean the same thing to the UI — match either,
// case-insensitively, rather than assume one contract spelling.
export const isRefusalRoute = (route) => /^refus(e|al)$/i.test(route || '');

/** Shared agent-message bubble — used by ChatPanel's own log AND by
 * MiniChatDock's expanded log, so the two chat surfaces render identically. */
export function AgentMessage({ msg }) {
  const isRefusal = isRefusalRoute(msg.route);
  if (isRefusal) {
    return (
      <div class="msg msg-refusal">
        <span class="refusal-tag">Outside validated scope</span>
        <p>{msg.answer}</p>
      </div>
    );
  }
  return (
    <div class="msg msg-agent">
      <p>{renderWithNums(msg.answer)}</p>
      {msg.route && (
        <div class="citations">
          <span class="citations-label">via</span>
          <code class="citation">⚙ {msg.route}</code>
        </div>
      )}
    </div>
  );
}

/**
 * Ask-the-copilot chat. Two skins from the same component:
 *  - mode="dock": compact, used inside the collapsed mini-chat dock.
 *  - mode="full": Copilot tab, with suggestion chips.
 * `contextLabel` (e.g. the current tab name) is prefixed into the question
 * sent to the agent so the router has situational context; it is NOT
 * invented data, just a routing hint, and is shown to the user before send.
 */
export default function ChatPanel({ mode = 'full', contextLabel, suggestions, onResult }) {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);

  // Every panel heading carries the AI-explain affordance — including this
  // one (operator request #3); here it recaps the session's own state
  // rather than an exhibit payload.
  const { button: explainBtn, strip: explainStrip } = useExplain({
    label: 'Ask the copilot',
    buildQuestion:
      mode === 'full'
        ? () =>
            explainPanelQuestion({
              panelId: 'copilot_chat',
              title: 'Ask the copilot',
              recap: messages.length
                ? `${messages.filter((m) => m.role === 'user').length} question(s) asked this session; last route: ${
                    messages.filter((m) => m.role === 'agent').at(-1)?.route ?? 'none yet'
                  }.`
                : 'no questions asked yet this session — the five validated routes are the four numeric engine tools plus the cited documentation retriever.',
            })
        : undefined,
  });

  const send = async (q) => {
    const trimmed = q.trim();
    if (!trimmed || busy) return;
    setQuestion('');
    setMessages((m) => [...m, { role: 'user', text: trimmed }]);
    setBusy(true);
    try {
      const wire = contextLabel ? `[${contextLabel}] ${trimmed}` : trimmed;
      const res = await askAgent(wire);
      setMessages((m) => [...m, { role: 'agent', ...res }]);
      onResult?.({ question: trimmed, ...res, at: Date.now() });
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'error', text: `Request failed: ${err.message}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    send(question);
  };

  const defaultChips =
    suggestions || [
      'What is the reported allowance under the downside scenario?',
      'Write pandas to find the 10 largest-balance Stage 3 loans',
      'What does the double-trigger LTV x UER coefficient mean?',
    ];

  return (
    <section class={`panel chat-panel chat-panel-${mode}`}>
      {mode === 'full' && (
        <>
          <div class="panel-head">
            <h2>Ask the copilot</h2>
            {explainBtn}
          </div>
          <p class="panel-sub">
            Narrated, data-grounded answers — every number traces to an engine
            tool call; out-of-scope questions are refused by design.
          </p>
          {explainStrip}
        </>
      )}
      <div class="chat-log">
        {messages.length === 0 && (
          <div class="empty-note">
            {mode === 'full' ? (
              <div class="chip-row">
                {defaultChips.map((c) => (
                  <button type="button" class="chip" key={c} onClick={() => send(c)}>
                    {c}
                  </button>
                ))}
              </div>
            ) : (
              <>Ask about {contextLabel ? contextLabel.toLowerCase() : 'this book'}…</>
            )}
          </div>
        )}
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
        {busy && (
          <div class="explain-status">
            <span class="status-dot status-dot-warn pulse" /> THINKING
          </div>
        )}
      </div>
      <form class="chat-form" onSubmit={submit}>
        <input
          type="text"
          value={question}
          placeholder={
            contextLabel ? `Ask about ${contextLabel}…` : 'Ask about ECL, staging, scenarios…'
          }
          onInput={(e) => setQuestion(e.currentTarget.value)}
          disabled={busy}
        />
        <button class="btn" type="submit" disabled={busy || !question.trim()}>
          Ask
        </button>
      </form>
    </section>
  );
}
