import { useEffect, useRef } from 'preact/hooks';
import echarts from './echarts.js';

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
