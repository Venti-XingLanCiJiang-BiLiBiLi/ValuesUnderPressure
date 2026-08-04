import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vite 配置
 * ============================================================================
 * - `base`: GitHub Pages 部署在子路径（如 /ValuesUnderPressure/），用相对路径 './'
 *           让 index.html 里的资源引用能自适应。
 * - dev server: /api 代理到本地 FastAPI (http://127.0.0.1:8000)
 * - 生产构建: 使用 import.meta.env.VITE_API_BASE_URL 决定 API 地址
 *             （默认 /api，部署时通过环境变量覆盖）
 * ============================================================================
 */
export default defineConfig(({ mode }) => ({
  // 部署到 https://<user>.github.io/<repo>/ 时用 './'（相对路径）
  // 部署到 https://<user>.github.io/ 时用 '/'
  base: mode === 'development' ? '/' : './',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      // 把 /api 代理到 FastAPI 后端
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 兼容老浏览器
    target: 'es2020',
    // 输出 gzip/brotli 压缩后的体积，便于评估优化效果
    reportCompressedSize: true,
    // 把所有第三方依赖拆成更小的 chunk（避免全塞进主包）
    rollupOptions: {
      output: {
        manualChunks: {
          // Vue 生态单独一份，方便长期缓存
          vue: ['vue', 'vue-router', 'pinia'],
          // axios 等其余第三方依赖单独一份
          vendor: ['axios'],
        },
      },
    },
  },
}))
