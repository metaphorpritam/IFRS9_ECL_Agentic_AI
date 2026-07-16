import { useMemo } from 'preact/hooks';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { colors, chartText, gridLine, inkMuted, surface, baselineColor } from '../palette.js';
import { fmtMillions } from '../format.js';

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Weighted allowance under the adopted basis vs policy-alternative weight
 * sets. One measure across named sets -> emphasis encoding (accent = the
 * basis actually reported; muted gray = illustrative alternatives), not
 * categorical identity — there is only one series here (FINAL_SPEC §8.4,
 * "otherwise plain --accent with the status dot carried by the adjacent
 * table"). */
function buildOption(weightSets, reducedMotion) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const base = baselineColor();
  const surf = surface();
  const cats = weightSets.map((w) => w.label);
  const vals = weightSets.map((w) => w.weighted_allowance / 1e6);
  return {
    textStyle: text,
    backgroundColor: 'transparent',
    grid: { left: 60, right: 20, top: 20, bottom: 60, containLabel: true },
    tooltip: {
      trigger: 'item',
      backgroundColor: surf,
      borderColor: base,
      borderWidth: 1,
      textStyle: { color: text.color },
      formatter: (p) => {
        const w = weightSets[p.dataIndex];
        return `<b>${w.label}</b><br/>${fmtMillions(w.weighted_allowance / 1e6)} (${(w.coverage * 100).toFixed(2)}% coverage)<br/>Δ vs adopted: ${w.delta_vs_adopted_pct.toFixed(1)}%`;
      },
    },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { color: muted, interval: 0, rotate: 12, fontSize: 12, fontFamily: text.fontFamily },
      axisLine: { lineStyle: { color: base } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Weighted allowance ($m)',
      nameTextStyle: { color: muted, fontFamily: text.fontFamily },
      axisLabel: { color: muted, fontFamily: text.fontFamily },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: grid, type: 'solid' } },
    },
    series: [
      {
        type: 'bar',
        barMaxWidth: 24,
        data: vals.map((v, i) => ({
          value: v,
          itemStyle: {
            color: weightSets[i].id === 'adopted' ? c.accent : c.gray,
            borderRadius: [4, 4, 0, 0],
          },
        })),
        label: {
          show: true,
          position: 'top',
          color: text.color,
          fontSize: 12,
          fontFamily: text.fontFamily,
          formatter: (p) => fmtMillions(p.value),
        },
      },
    ],
    animationDuration: reducedMotion ? 0 : 300,
  };
}

export default function WeightsBarChart({ weightSets }) {
  const themeV = useThemeVersion();
  const option = useMemo(
    () => (weightSets?.length ? buildOption(weightSets, prefersReducedMotion()) : null),
    [weightSets, themeV],
  );
  const ref = useECharts(option);
  const live = colors();
  return (
    <>
      <div ref={ref} class="chart" />
      <div class="chart-legend-row">
        <span class="legend-item">
          <span class="legend-dot" style={{ background: live.accent }} />
          Adopted basis (reported)
        </span>
        <span class="legend-item">
          <span class="legend-dot" style={{ background: live.gray }} />
          Policy alternative
        </span>
      </div>
    </>
  );
}
