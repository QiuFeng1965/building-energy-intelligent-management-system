import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          // 🔥 核心修复：告诉 Vue 放行所有 Tres 开头的 3D 引擎专属标签
          isCustomElement: (tag) => tag.startsWith('Tres') && tag !== 'TresCanvas',
        },
      },
    }),
  ],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vite 8 / rolldown 要求 manualChunks 为函数形式
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('vue') && !id.includes('element-plus')) return 'vendor-vue'
            if (id.includes('echarts')) return 'vendor-echarts'
            if (id.includes('three') || id.includes('@tresjs')) return 'vendor-three'
            if (id.includes('element-plus') || id.includes('@element-plus')) return 'vendor-element'
            // 拆分大型库避免单个 chunk 过大
            if (id.includes('html2pdf') || id.includes('jspdf') || id.includes('html2canvas')) return 'vendor-pdf'
            if (id.includes('dompurify')) return 'vendor-security'
            return 'vendor'
          }
        }
      }
    },
    // 上线前阈值：echarts/element-plus 全量导入 gzip 后约 300KB，可接受
    chunkSizeWarningLimit: 1500
  }
})
