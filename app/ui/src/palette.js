// Validated data-viz palette (see dataviz skill / references/palette.md).
// Categorical hues are assigned in FIXED order — never cycled. Both light and
// dark steps are given; charts read the live CSS custom properties (see
// styles.css :root / prefers-color-scheme) so they repaint with the OS theme
// without a second palette. This module exposes the same values as plain JS
// for ECharts option builders (which cannot read CSS vars directly).
//
// FINAL_SPEC.md §0.1 / §1.2 — the categorical slot ORDER below is the fix:
// the previous order (blue, aqua, yellow, green, violet, red, magenta,
// orange) failed the validator's normal-vision floor (worst adjacent pair
// #eb6834<->#e87ba4 dE 12.9 < 15). This order is judge-verified to pass in
// both modes. Never reorder without rerunning the validator.

const isDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-color-scheme: dark)').matches;

// Categorical — fixed slot order (identity, never rank): blue, green,
// magenta, yellow, aqua, orange, violet, red.
const CATEGORICAL_LIGHT = [
  '#2a78d6', // 1 blue
  '#008300', // 2 green
  '#e87ba4', // 3 magenta
  '#eda100', // 4 yellow
  '#1baf7a', // 5 aqua
  '#eb6834', // 6 orange
  '#4a3aa7', // 7 violet
  '#e34948', // 8 red
];
const CATEGORICAL_DARK = [
  '#3987e5', '#008300', '#d55181', '#c98500',
  '#199e70', '#d95926', '#9085e9', '#e66767',
];

export const categorical = () => (isDark() ? CATEGORICAL_DARK : CATEGORICAL_LIGHT);

// Status — reserved, never reused for series identity.
export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
};

// Readable text variants of the status hues (never use the raw fill as
// text — §1.1 contrast notes).
export const STATUS_TEXT = {
  good: (dark) => (dark ? '#0ca30c' : '#006300'),
  critical: (dark) => (dark ? '#e66767' : '#d03b3b'),
};

// Diverging pair (polarity: increase vs decrease) — waterfall only.
export const DIVERGING = {
  increase: { light: '#2a78d6', dark: '#3987e5' },
  decrease: { light: '#e34948', dark: '#e66767' },
};

export function tokens() {
  const dark = isDark();
  return {
    // panel/page surfaces (§1.1)
    page: dark ? '#0d0d0d' : '#f9f9f7',
    panel: dark ? '#1a1a19' : '#fcfcfb',
    panel2: dark ? '#232322' : '#ffffff',
    surface: dark ? '#1a1a19' : '#fcfcfb', // back-compat alias for `panel`
    border: dark ? 'rgba(255,255,255,0.10)' : 'rgba(11,11,11,0.10)',
    borderStrong: dark ? 'rgba(255,255,255,0.16)' : 'rgba(11,11,11,0.16)',
    ink: dark ? '#ffffff' : '#0b0b0b',
    inkMuted: dark ? '#c3c2b7' : '#52514e', // ink-2
    ink2: dark ? '#c3c2b7' : '#52514e',
    ink3: '#898781',
    axisMuted: '#898781', // back-compat alias for `ink3`
    gridLine: dark ? '#2c2c2a' : '#e1e0d9',
    baseline: dark ? '#383835' : '#c3c2b7',
    accent: dark ? '#3987e5' : '#2a78d6',
    accentSolid: dark ? '#3987e5' : '#1c5cab',
    accentOnSolid: dark ? '#0b0b0b' : '#ffffff',
    accentText: dark ? '#3987e5' : '#1c5cab',
    accentWash: dark ? 'rgba(57,135,229,0.10)' : 'rgba(42,120,214,0.08)',
    increase: dark ? '#3987e5' : '#2a78d6',
    decrease: dark ? '#e66767' : '#e34948',
    levelFill: dark ? '#c3c2b7' : '#52514e',
    good: dark ? '#0ca30c' : '#006300', // "good" TEXT (readable) per §1.1
    goodDot: '#0ca30c',
    critical: dark ? '#e66767' : '#d03b3b', // "critical" TEXT (readable)
    criticalDot: '#d03b3b',
  };
}

// Back-compat aliases used across chart option builders.
export const COLORS = {
  accent: '#2a78d6',
  warn: DIVERGING.decrease.light,
  good: STATUS.good,
  purple: '#4a3aa7',
  orange: '#eb6834',
  blue2: '#2a78d6',
  gray: '#898781',
};

// Live-theme series colors — call inside option builders (like the token
// accessors below) so the dark categorical steps apply in dark mode.
// STATUS hues stay fixed by design (reserved semantics, mid-tone in both
// themes); identity hues switch with the scheme. `increase`/`decrease` are
// the waterfall's diverging polarity pair (§1.2/§1.3) — NOT a good/bad read.
export function colors() {
  const c = categorical();
  const t = tokens();
  return {
    accent: c[0], // blue slot 1
    warn: t.decrease,
    good: STATUS.good,
    purple: c[6], // violet slot 7
    orange: c[5], // orange slot 6
    blue2: c[0],
    gray: t.ink3,
    increase: t.increase,
    decrease: t.decrease,
    levelFill: t.levelFill,
  };
}

export const CHART_TEXT_BASE = {
  fontFamily:
    "-apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, system-ui, sans-serif",
  fontSize: 12,
};

// Live-theme accessors — call inside option builders (not at module load) so
// dark/light values are read fresh each render.
export function chartText() {
  return { ...CHART_TEXT_BASE, color: tokens().ink };
}
export function gridLine() {
  return tokens().gridLine;
}
export function inkMuted() {
  return tokens().inkMuted;
}
export function surface() {
  return tokens().panel;
}
export function baselineColor() {
  return tokens().baseline;
}

// Legacy named exports some components still import directly.
export const SURFACE = '#fcfcfb';
export const INK = '#0b0b0b';
export const INK_MUTED = '#52514e';
export const GRID_LINE = '#e1e0d9';
export const CHART_TEXT = { ...CHART_TEXT_BASE, color: INK };
