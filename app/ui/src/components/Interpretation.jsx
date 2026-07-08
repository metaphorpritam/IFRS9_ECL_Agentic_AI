import { useEffect, useState } from 'preact/hooks';
import { interpretResult } from '../api.js';

/**
 * Auto-interpretation card: POST /api/agent/interpret with the tool result
 * that just ran, render the grounded interpretation beside the numbers.
 * Loading state while in flight; if the request itself fails (LLM/network
 * down), fall back to the tool's own `headline` — the interpretation panel
 * must never go blank or show a raw error to the client.
 */
export default function Interpretation({ tool, result }) {
  const [state, setState] = useState({ status: 'idle' });

  useEffect(() => {
    if (!tool || !result) {
      setState({ status: 'idle' });
      return;
    }
    let alive = true;
    setState({ status: 'loading' });
    interpretResult(tool, result)
      .then((d) => alive && setState({ status: 'done', ...d }))
      .catch(
        (err) =>
          alive &&
          setState({
            status: 'done',
            interpretation:
              result.headline ||
              'Engine run complete — no narration available right now.',
            grounded: false,
            mode: `client_error:${err.message}`,
          }),
      );
    return () => {
      alive = false;
    };
  }, [tool, result]);

  if (state.status === 'idle') return null;

  return (
    <div class="interpretation">
      <div class="interpretation-head">
        <span class="interpretation-label">Auto-interpretation</span>
        {state.status === 'done' && (
          <span class={`badge-ground ${state.grounded ? 'badge-ai' : 'badge-engine'}`}>
            {state.grounded ? 'AI interpretation' : 'Engine summary'}
          </span>
        )}
      </div>
      {state.status === 'loading' ? (
        <p class="interpretation-loading">
          <span class="spinner" /> interpreting the run…
        </p>
      ) : (
        <p class="interpretation-text">{state.interpretation}</p>
      )}
    </div>
  );
}
