import { useState } from 'preact/hooks';
import { askAgent } from '../api.js';
import { renderWithNums } from '../numText.jsx';

// FINAL_SPEC.md §7.1 — inline SVG path, currentColor, no icon font.
const SPARK_PATH = 'M8,0 L10,6 L16,8 L10,10 L8,16 L6,10 L0,8 L6,6 Z';

export function SparkIcon({ size = 16 }) {
  return (
    <svg viewBox="0 0 16 16" width={size} height={size} fill="currentColor" aria-hidden="true">
      <path d={SPARK_PATH} />
    </svg>
  );
}

// The live LangGraph router emits route "REFUSE"; the offline keyword
// fallback router emits "refusal" — match either (see ChatPanel.jsx).
const isRefusalRoute = (route) => /^refus(e|al)$/i.test(route || '');

/** The response-surface strip (FINAL_SPEC §7.4): THINKING / GROUNDED answer
 * + citation chip / OUT OF SCOPE refusal — shared by the panel/tile explain
 * affordance and the selection-explain popover. */
export function ExplainStrip({ state, floating = false }) {
  return (
    <div class={`explain-strip${floating ? ' explain-strip-floating' : ''}`}>
      <div class="explain-avatar">
        <SparkIcon />
      </div>
      <div class="explain-body">
        {state.status === 'loading' && (
          <p class="explain-status">
            <span class="status-dot status-dot-warn" /> THINKING
          </p>
        )}
        {state.status === 'network-error' && (
          <p class="explain-status">
            <span class="status-dot status-dot-muted" /> OUT OF SCOPE — request failed (
            {state.message})
          </p>
        )}
        {state.status === 'done' && isRefusalRoute(state.route) && (
          <>
            <p class="explain-status">
              <span class="status-dot status-dot-muted" /> OUT OF SCOPE
            </p>
            <p class="explain-text">{renderWithNums(state.answer)}</p>
          </>
        )}
        {state.status === 'done' && !isRefusalRoute(state.route) && (
          <>
            <p class="explain-status">
              <span class="status-dot status-dot-good" /> GROUNDED
            </p>
            <p class="explain-text">{renderWithNums(state.answer)}</p>
            {state.route && <code class="citation">⚙ {state.route}</code>}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * The AI-explain affordance (FINAL_SPEC §7) as a hook, so the two pieces can
 * live where the spec puts them: the 28px circular spark BUTTON in the
 * panel/tile heading, and the answer STRIP inline UNDER the panel/tile body
 * (§7.4 — never a modal, never squeezed into the header row). Click ->
 * POST /api/agent/ask via `buildQuestion()` (called fresh at click time so
 * the question always reflects the CURRENT payload) -> grounded answer,
 * refusal, or network error rendered in the strip.
 *
 * Returns `{ button, strip }` — both `null` when `buildQuestion` is absent.
 */
export function useExplain({ label, buildQuestion }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState({ status: 'idle' });

  if (!buildQuestion) return { button: null, strip: null };

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    setOpen(true);
    setState({ status: 'loading' });
    let question;
    try {
      question = buildQuestion();
    } catch {
      question = `Explain this exhibit: ${label}. What should I take from this?`;
    }
    try {
      const res = await askAgent(question);
      setState({ status: 'done', question, ...res });
    } catch (err) {
      setState({ status: 'network-error', message: err.message });
    }
  };

  const button = (
    <button
      type="button"
      class={`explain-btn${open && state.status === 'loading' ? ' loading' : ''}`}
      aria-expanded={open}
      aria-label={`Ask Copilot to explain ${label}`}
      data-tip="Ask Copilot to explain this"
      onClick={toggle}
    >
      <SparkIcon />
    </button>
  );

  const strip = open ? <ExplainStrip state={state} /> : null;

  return { button, strip };
}
