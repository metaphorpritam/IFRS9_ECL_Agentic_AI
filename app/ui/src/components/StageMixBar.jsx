import { fmtPctScale } from '../format.js';

// Stage colors are STATUS semantics (risk state), not arbitrary categorical
// identity: Stage 1 performing = good, Stage 2 SICR = warning, Stage 3
// impaired = critical. Reserved status hues, never reused for series.
const STAGE_META = [
  { key: 'stage1', label: 'Stage 1 — performing', cls: 'stage-good' },
  { key: 'stage2', label: 'Stage 2 — SICR', cls: 'stage-warn' },
  { key: 'stage3', label: 'Stage 3 — impaired', cls: 'stage-crit' },
];

/** Part-to-whole stage mix of allowance, as a single stacked bar with a
 * legend + direct labels (segments < 6% skip their inline label to avoid
 * collision; the legend still names them). */
export default function StageMixBar({ stageMix }) {
  if (!stageMix) return null;
  return (
    <div class="stage-mix">
      <div class="stage-mix-bar" role="img" aria-label="Stage mix of allowance">
        {STAGE_META.map((s) => {
          const seg = stageMix[s.key];
          const pct = seg?.allowance_pct_of_total ?? 0;
          if (pct <= 0) return null;
          return (
            <div
              key={s.key}
              class={`stage-seg ${s.cls}`}
              style={{ width: `${pct}%` }}
              title={`${s.label}: ${fmtPctScale(pct)} of allowance, ${seg.n_loans} loans`}
            >
              {pct >= 6 && <span>{fmtPctScale(pct, 0)}</span>}
            </div>
          );
        })}
      </div>
      <div class="stage-mix-legend">
        {STAGE_META.map((s) => {
          const seg = stageMix[s.key];
          return (
            <span class="legend-item" key={s.key}>
              <span class={`legend-dot ${s.cls}`} />
              {s.label} · {fmtPctScale(seg?.allowance_pct_of_total ?? 0)} ·{' '}
              {seg?.n_loans ?? 0} loans
            </span>
          );
        })}
      </div>
    </div>
  );
}
