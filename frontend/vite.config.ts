import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    tsconfigPaths()
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vite 8 底层是 Rolldown：manualChunks 只支持函数形式；
        // echarts 单独分包（约 1MB），页面级拆分靠路由 lazy
        manualChunks(id: string) {
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
            return 'echarts';
          }
          if (id.includes('node_modules/react') || id.includes('node_modules/react-router') || id.includes('node_modules/scheduler')) {
            return 'vendor';
          }
          return undefined;
        },
      },
    },
  },
})
