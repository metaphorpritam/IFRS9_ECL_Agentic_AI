// Display formatting ONLY — no business arithmetic happens in the UI.
// Every number shown comes from the engine via the API.

export const fmtMillions = (v) =>
  v == null || Number.isNaN(Number(v)) ? '—' : `$${Number(v).toFixed(1)}m`;

export const fmtPct = (v, dp = 2) =>
  v == null || Number.isNaN(Number(v)) ? '—' : `${(Number(v) * 100).toFixed(dp)}%`;

export const fmtRatio = (v) =>
  v == null || Number.isNaN(Number(v)) ? '—' : `${Number(v).toFixed(3)}×`;

export const fmtSignedM = (v) =>
  v == null || Number.isNaN(Number(v))
    ? '—'
    : `${Number(v) >= 0 ? '+' : '−'}$${Math.abs(Number(v)).toFixed(1)}m`;

export const fmtTime = (ms) => {
  const d = new Date(ms);
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
};
