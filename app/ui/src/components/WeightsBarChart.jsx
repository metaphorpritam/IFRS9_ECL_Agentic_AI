import { useMemo } from 'preact/hooks';
import { useECharts, useThemeVersion } from '../charts/useECharts.js';
import { colors, chartText, gridLine, inkMuted } from '../palette.js';
import { fmtMillions } from '../format.js';

/** Weighted allowance under the adopted basis vs policy-alternative weight
 * sets. One measure across named sets -> emphasis encoding (accent = the
 * basis actually reported; muted gray = illustrative alternatives), not
 * categorical identity — there is only one series here. */
function buildOption(weightSets) {
  const c = colors();
  const text = chartText();
  const grid = gridLine();
  const muted = inkMuted();
  const cats = weightSets.map((w) => w.label);
  const vals = weightSets.map((w) => w.weighted_allowance / 1e6);
  return {
    textStyle: text,
    grid: { left: 60, right: 20, top: 20, bottom: 60 },
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const w = weightSets[p.dataIndex];
        return `<b>${w.label}</b><br/>${fmtMillions(w.weighted_allowance / 1e6)} (${(w.coverage * 100).toFixed(2)}% coverage)<br/>Δ vs adopted: ${w.delta_vs_adopted_pct.toFixed(1)}%`;
      },
    },
    xAxis: {
      type: 'category',
      data: cats,
      axisLabel: { color: muted, interval: 0, rotate: 12, fontSize: 11 },
      axisLine: { lineStyle: { color: grid } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      name: 'Weighted allowance ($m)',
      nameTextStyle: { color: muted },
      axisLabel: { color: muted },
      splitLine: { lineStyle: { color: grid, type: 'dashed' } },
    },
    series: [
      {
        type: 'bar',
        barWidth: '46%',
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
          fontSize: 11,
          formatter: (p) => fmtMillions(p.value),
        },
      },
    ],
  };
}

export default function WeightsBarChart({ weightSets }) {
  const themeV = useThemeVersion();
  const option = useMemo(
    () => (weightSets?.length ? buildOption(weightSets) : null),
    [weightSets, themeV],
  );
  const ref = useECharts(option);
  const live = colors();
  return (
    <>
      <div ref={ref} class="chart" />
      <div class="stage-mix-legend">
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
