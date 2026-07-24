import Panel from './Panel.jsx';
import { explainPanelQuestion } from '../api.js';

/**
 * Dossier-v2 propagation: the "How grounding works" panel for the Copilot
 * tab side column — the four-step guard chain, the status legend the rest
 * of the UI uses, and the honest limitation, stated once. Copy grounded in
 * wiki/pages/agent-layer.md and agent/graph.py (no live numbers).
 */
const STEPS = [
  {
    name: 'Route',
    text:
      'A temperature-0 router LLM (Gemma, DeepSeek fallback) classifies the question into ' +
      'one of four validated Tier-1 numeric tools, the sandboxed pandas analyst ' +
      '(analyze_data), the cited documentation retriever (query_model_docs), a REASONED ' +
      'interpretation, or a refusal. Tool arguments are pydantic-validated with ' +
      'extra="forbid" — unexpected fields are rejected, not ignored.',
  },
  {
    name: 'Compute',
    text:
      'Only the deterministic engine computes numbers. The LLM never does arithmetic — ' +
      'every figure in an answer originates in a tool result the engine produced.',
  },
  {
    name: 'Narrate',
    text:
      'A narrator LLM writes the prose around the tool payload it was handed — nothing ' +
      'else — and must cite the tool it is narrating.',
  },
  {
    name: 'Verify',
    text:
      'Post-generation guards check that every digit AND every spelled-out number ' +
      '("tens of millions" included — a live bypass found in adversarial review, now ' +
      'blocked in all three guards with pinned regression tests) appears verbatim in the ' +
      'tool payload, plus a citation check. One failed narration is regenerated once; a ' +
      'second failure falls back to a deterministic template built from the payload itself.',
  },
];

const LEGEND = [
  {
    dot: 'status-dot-good',
    label: 'GROUNDED',
    text: 'engine-computed; every figure verbatim from a tool payload, with citation.',
  },
  {
    dot: 'status-dot-accent',
    label: 'REASONED',
    text: 'interpretation grounded in the model documentation — explicitly labelled "not engine output", and still number-guarded.',
  },
  {
    dot: 'status-dot-warn',
    label: 'THINKING',
    text: 'request in flight.',
  },
  {
    dot: 'status-dot-muted',
    label: 'OUT OF SCOPE',
    text: 'refused by design — the router found no validated path.',
  },
];

export default function HowGroundingWorks() {
  return (
    <Panel
      title="How grounding works"
      subtitle="Why the header can promise 'every figure cites its source' — the four-step chain every question passes through."
      buildExplainQuestion={() =>
        explainPanelQuestion({
          panelId: 'how_grounding_works',
          title: 'How grounding works',
          recap:
            'Route (temp-0 router into tools / docs / REASONED / refusal) → Compute (only the engine produces numbers) → Narrate (prose around the tool payload) → Verify (verbatim digit + spelled-number + citation guards, one regenerate, then deterministic fallback).',
        })
      }
    >
      <ol class="ground-steps">
        {STEPS.map((s) => (
          <li key={s.name}>
            <b>{s.name}.</b> {s.text}
          </li>
        ))}
      </ol>
      <div class="ground-legend">
        {LEGEND.map((l) => (
          <p class="ground-legend-row" key={l.label}>
            <span class={`status-dot ${l.dot}`} /> <b>{l.label}</b> — {l.text}
          </p>
        ))}
      </div>
      <p class="caveat">
        <b>Honest limitation.</b> The guards prove every number came from the engine; they
        cannot prove the prose attributes each number to the right concept. That residual
        attribution risk is documented in the model docs rather than hidden here.
      </p>
    </Panel>
  );
}
