/** Headline stat tile: value + label + optional hint/delta. */
export default function StatTile({ label, value, hint, tone }) {
  return (
    <div class={`tile ${tone ? `tile-${tone}` : ''}`}>
      <div class="tile-label">{label}</div>
      <div class="tile-value">{value}</div>
      {hint && <div class="tile-hint">{hint}</div>}
    </div>
  );
}
