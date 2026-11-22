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
    // 双栈监听：默认只绑 ::1 时，走 IPv4 的浏览器会连接被拒
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // echarts 独立 chunk 体积是刻意为之：它只在 Monitor 页被路由 lazy 加载，
    // 首屏不下载 —— 放宽默认 500KB 告警阈值，让 CI 构建输出干净
    chunkSizeWarningLimit: 1024,
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
