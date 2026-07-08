// Validated data-viz palette (see dataviz skill / references/palette.md).
// Categorical hues are assigned in FIXED order — never cycled. Both light and
// dark steps are given; charts read the live CSS custom properties (see
// styles.css :root / prefers-color-scheme) so they repaint with the OS theme
// without a second palette. This module exposes the same values as plain JS
// for ECharts option builders (which cannot read CSS vars directly).

const isDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-color-scheme: dark)').matches;

// Categorical — fixed slot order (identity, never rank).
const CATEGORICAL_LIGHT = [
  '#2a78d6', // 1 blue
  '#1baf7a', // 2 aqua
  '#eda100', // 3 yellow
  '#008300', // 4 green
  '#4a3aa7', // 5 violet
  '#e34948', // 6 red
  '#e87ba4', // 7 magenta
  '#eb6834', // 8 orange
];
const CATEGORICAL_DARK = [
  '#3987e5', '#199e70', '#c98500', '#008300',
  '#9085e9', '#e66767', '#d55181', '#d95926',
];

export const categorical = () => (isDark() ? CATEGORICAL_DARK : CATEGORICAL_LIGHT);

// Status — reserved, never reused for series identity.
export const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
};

// Diverging pair (polarity: increase vs decrease).
export const DIVERGING = { warm: '#e34948', cool: '#2a78d6' };

export function tokens() {
  const dark = isDark();
  return {
    surface: dark ? '#1a1a19' : '#fcfcfb',
    page: dark ? '#0d0d0d' : '#f9f9f7',
    ink: dark ? '#ffffff' : '#0b0b0b',
    inkMuted: dark ? '#c3c2b7' : '#52514e',
    axisMuted: '#898781',
    gridLine: dark ? '#2c2c2a' : '#e1e0d9',
    baseline: dark ? '#383835' : '#c3c2b7',
    good: dark ? '#0ca30c' : '#006300',
  };
}

// Back-compat aliases used across chart option builders.
export const COLORS = {
  accent: '#2a78d6',
  warn: DIVERGING.warm,
  good: STATUS.good,
  purple: '#4a3aa7',
  orange: '#eb6834',
  blue2: '#2a78d6',
  gray: '#898781',
};

// Live-theme series colors — call inside option builders (like the token
// accessors below) so the dark categorical steps apply in dark mode.
// STATUS/DIVERGING hues stay fixed by design (reserved semantics, mid-tone
// in both themes); identity hues switch with the scheme.
export function colors() {
  const c = categorical();
  return {
    accent: c[0], // blue slot 1
    warn: DIVERGING.warm,
    good: STATUS.good,
    purple: c[4],
    orange: c[7],
    blue2: c[0],
    gray: '#898781',
  };
}

export const CHART_TEXT_BASE = {
  fontFamily:
    "system-ui, -apple-system, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
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
  return tokens().surface;
}

// Legacy named exports some components still import directly.
export const SURFACE = '#fcfcfb';
export const INK = '#0b0b0b';
export const INK_MUTED = '#52514e';
export const GRID_LINE = '#e1e0d9';
export const CHART_TEXT = { ...CHART_TEXT_BASE, color: INK };
