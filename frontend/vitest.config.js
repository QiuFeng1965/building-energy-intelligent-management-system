// Vitest 单元测试配置文件
// 通过 mergeConfig 复用 vite.config.js 中的 @vitejs/plugin-vue（含 Tres 自定义元素配置），
// 避免重复维护插件配置。文档：https://vitest.dev/config/
import { mergeConfig, defineConfig } from 'vitest/config'
import viteConfig from './vite.config.js'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // 测试环境：jsdom 提供 DOM / localStorage / window 等浏览器 API
      environment: 'jsdom',
      // 启用全局 API（describe / it / expect 等可不显式 import）
      globals: true,
      // 覆盖率配置（可选）：运行 vitest run --coverage 时生效
      // 使用 v8 provider 需额外安装：npm i -D @vitest/coverage-v8
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html']
      }
    }
  })
)
