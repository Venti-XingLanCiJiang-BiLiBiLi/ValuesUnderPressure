import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

/**
 * Vite 配置
 * ============================================================================
 * - `base`: 用相对路径 './'，让 index.html 里的资源引用能自适应任意部署路径
 *           （B 站 Toy / GitHub Pages 子路径均可）。
 * - 纯前端应用：引擎与题库全部本地打包，无任何后端 API。
 * ============================================================================
 */
export default defineConfig(() => ({
  // 部署到子路径（如 https://<user>.github.io/<repo>/ 或 Toy 环境）时用 './'（相对路径）
  // 部署到根路径时用 '/'
  base: './',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: '127.0.0.1',
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
        },
      },
    },
  },
}))
