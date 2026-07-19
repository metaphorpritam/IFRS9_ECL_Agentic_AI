import { useState } from 'preact/hooks';

/**
 * Requirement 12 -- per-row coefficient interpretation, shared by the Model
 * tab's DCR coefficients table and the Real Data tab's SFLLD coefficients
 * table. `row` is any coefficient object carrying the interpretation fields
 * documented in docs/api_contract.md: unit_meaning, transformation, lag,
 * fred_series (nullable), economic_channel, hazard_ratio_per_unit,
 * worked_example. Nothing here computes a number -- every figure rendered
 * came pre-computed from the API (the governing rule, extended to the UI).
 */

/** Small toggle button for a table row's first cell -- caret + label. */
export function ExpandToggle({ open, onToggle, label }) {
  return (
    <button
      type="button"
      class="row-expand-btn"
      aria-expanded={open}
      aria-label={`${open ? 'Hide' : 'Show'} interpretation for ${label}`}
      onClick={(e) => {
        // The button sits inside a row that ALSO toggles on click (bigger
        // hit target); stop here so a button click never double-fires.
        e.stopPropagation();
        onToggle();
      }}
    >
      <span class="row-expand-caret">{open ? '▾' : '▸'}</span>
    </button>
  );
}

/** The expanded interpretation content -- one <tr><td colSpan> per table. */
export function InterpretationRow({ row, colSpan }) {
  if (!row) return null;
  return (
    <tr class="interp-row">
      <td colSpan={colSpan}>
        <div class="interp-body">
          <div class="interp-tags">
            {row.fred_series && <span class="fred-badge">FRED · {row.fred_series}</span>}
            {row.lag && <span class="lag-badge">lag {row.lag}</span>}
          </div>
          {row.unit_meaning && (
            <p class="interp-line"><b>Unit.</b> {row.unit_meaning}</p>
          )}
          {row.transformation && (
            <p class="interp-line"><b>Transformation.</b> {row.transformation}</p>
          )}
          {row.economic_channel && (
            <p class="interp-line"><b>Economic channel.</b> {row.economic_channel}</p>
          )}
          {row.worked_example && (
            <p class="interp-line interp-worked">
              <b>Worked example.</b> {row.worked_example}
            </p>
          )}
        </div>
      </td>
    </tr>
  );
}

/** Hook: a Set of expanded row-keys + a toggle callback, so each table
 * manages its own independent expand state. */
export function useExpandableRows() {
  const [open, setOpen] = useState(() => new Set());
  const toggle = (key) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  return { isOpen: (key) => open.has(key), toggle };
}
