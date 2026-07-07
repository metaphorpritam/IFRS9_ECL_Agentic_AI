import { useState } from 'preact/hooks';
import { askAgent } from '../api.js';

function ToolCitation({ call }) {
  return (
    <code class="citation" title="Engine tool call backing this answer">
      {call.tool}({call.args ? JSON.stringify(call.args) : ''})
    </code>
  );
}

function AgentMessage({ msg }) {
  if (msg.refusal) {
    return (
      <div class="msg msg-refusal">
        <span class="refusal-tag">Outside validated scope</span>
        <p>{msg.answer}</p>
      </div>
    );
  }
  return (
    <div class="msg msg-agent">
      <p>{msg.answer}</p>
      {msg.tool_calls?.length > 0 && (
        <div class="citations">
          <span class="citations-label">via</span>
          {msg.tool_calls.map((c, i) => (
            <ToolCitation call={c} key={i} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Ask the copilot; answers cite the engine tool call. Refusals render amber. */
export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    const q = question.trim();
    if (!q || busy) return;
    setQuestion('');
    setMessages((m) => [...m, { role: 'user', text: q }]);
    setBusy(true);
    try {
      const res = await askAgent(q);
      setMessages((m) => [...m, { role: 'agent', ...res }]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        { role: 'error', text: `Request failed: ${err.message}` },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section class="panel">
      <h2>Ask the copilot</h2>
      <p class="panel-sub">
        Narrated answers with the engine tool call cited. Out-of-scope questions
        are refused by design.
      </p>
      <div class="chat-log">
        {messages.length === 0 && (
          <div class="empty-note">
            Try: “What is the reported allowance under the severe scenario?”
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
        {busy && <div class="empty-note">Copilot thinking…</div>}
      </div>
      <form class="chat-form" onSubmit={submit}>
        <input
          type="text"
          value={question}
          placeholder="Ask about ECL, staging, scenarios…"
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
