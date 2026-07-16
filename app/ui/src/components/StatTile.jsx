import { useExplain } from './ExplainButton.jsx';

/** Headline stat tile (FINAL_SPEC §5.1): value + label + optional hint/delta
 * + the AI-explain icon top-right; the answer strip renders at the BOTTOM of
 * the tile, under a hairline divider (§5.1/§7.4). Tone tinting is retired —
 * tone lives in the delta pill, never the tile chrome; `value` always
 * renders in `--ink`. */
export default function StatTile({ label, value, hint, delta, buildExplainQuestion }) {
  const { button: explainBtn, strip: explainStrip } = useExplain({
    label,
    buildQuestion: buildExplainQuestion,
  });
  return (
    <div class="tile">
      <div class="tile-head">
        <div class="tile-label">{label}</div>
        {explainBtn}
      </div>
      <div class="tile-value">{value}</div>
      {hint && <div class="tile-hint">{hint}</div>}
      {delta && (
        <div class={`tile-delta ${delta.good ? 'tile-delta-good' : 'tile-delta-bad'}`}>
          <span aria-hidden="true">{delta.up ? '▲' : '▼'}</span> {delta.text}
        </div>
      )}
      {explainStrip}
    </div>
  );
}
