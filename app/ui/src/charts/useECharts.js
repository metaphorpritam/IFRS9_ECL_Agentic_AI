import { useEffect, useRef, useState } from 'preact/hooks';
import echarts from './echarts.js';

/**
 * Bumps whenever the OS light/dark scheme flips. Include the returned value
 * in an option builder's useMemo deps so the option is rebuilt with the
 * live palette accessors (palette.js chartText()/gridLine()/colors()/...)
 * and the chart repaints for the new theme — the CSS custom properties in
 * styles.css handle the page, but ECharts needs an explicit setOption.
 */
export function useThemeVersion() {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const bump = () => setV((x) => x + 1);
    mq.addEventListener?.('change', bump);
    return () => mq.removeEventListener?.('change', bump);
  }, []);
  return v;
}

/** Mount an ECharts instance on a div ref; re-apply option when it changes. */
export function useECharts(option) {
  const nodeRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    const chart = echarts.init(nodeRef.current);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (option && chartRef.current) {
      chartRef.current.setOption(option, true);
    }
  }, [option]);

  return nodeRef;
}
