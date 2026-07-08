import { defineConfig } from 'vite';
import preact from '@preact/preset-vite';

export default defineConfig({
  plugins: [preact()],
  server: {
    // 9P / WSL2 drvfs mount: inotify is unreliable, poll instead.
    watch: { usePolling: true },
    proxy: {
      // FastAPI engine service (HF Spaces convention: port 7860).
      '/api': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
      // Exhibit PNGs (/static/exhibits/*) are served by the same FastAPI
      // app — proxy them too so images render in `npm run dev`.
      '/static': {
        target: 'http://localhost:7860',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        // Cache the big chart lib separately from app code.
        manualChunks: { echarts: ['echarts/core', 'echarts/charts', 'echarts/components', 'echarts/renderers'] },
      },
    },
  },
});
