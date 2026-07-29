// ESLint 9 扁平配置文件（Flat Config）
// 文档：https://eslint.org/docs/latest/use/configure/configuration-files
//
// 说明：
// - ESLint 9 默认采用扁平配置（eslint.config.js），不再使用 .eslintrc.* 与 .eslintignore。
// - 命令行不再支持 --ext 参数，被 lint 的文件类型由各配置对象的 files 字段决定，
//   因此 lint 脚本使用 `eslint src --fix` 即可同时校验 .vue 与 .js 文件。
// - .vue 文件的解析由 eslint-plugin-vue 内部配置的 vue-eslint-parser 负责。

import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import eslintConfigPrettier from 'eslint-config-prettier'

export default [
  // 1) eslint:recommended 推荐规则
  js.configs.recommended,

  // 2) plugin:vue/vue3-recommended 的扁平版本
  //    内部已为 *.vue 文件自动配置 vue-eslint-parser 解析器
  ...pluginVue.configs['flat/vue3-recommended'],

  // 3) 面向 JS / Vue 文件的全局规则
  {
    files: ['**/*.{js,mjs,cjs,vue}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        // 浏览器环境全局变量，避免 no-undef 误报
        window: 'readonly',
        document: 'readonly',
        localStorage: 'readonly',
        sessionStorage: 'readonly',
        console: 'readonly',
        fetch: 'readonly',
        setTimeout: 'readonly',
        clearTimeout: 'readonly',
        setInterval: 'readonly',
        clearInterval: 'readonly',
        requestAnimationFrame: 'readonly',
        cancelAnimationFrame: 'readonly',
        AbortController: 'readonly',
        URL: 'readonly',
        URLSearchParams: 'readonly',
        Blob: 'readonly',
        FileReader: 'readonly',
        FormData: 'readonly',
        navigator: 'readonly',
        location: 'readonly',
        history: 'readonly',
        HTMLElement: 'readonly',
        Element: 'readonly',
        Event: 'readonly',
        CustomEvent: 'readonly',
        WebSocket: 'readonly',
        ResizeObserver: 'readonly',
        IntersectionObserver: 'readonly',
        performance: 'readonly',
        btoa: 'readonly',
        atob: 'readonly',
        alert: 'readonly',
        confirm: 'readonly',
        prompt: 'readonly'
      }
    },
    rules: {
      // 未使用的变量仅警告，不阻断开发
      'no-unused-vars': 'warn',
      // 允许单词组件名（项目存在 Login.vue 等单名单组件）
      'vue/multi-word-component-names': 'off'
    }
  },

  // 4) 关闭所有与 Prettier 冲突的格式化规则（必须放在最后，确保覆盖前面的规则）
  eslintConfigPrettier,

  // 5) 全局忽略项（flat config 内置 ignores 字段，等价于旧版 .eslintignore）
  {
    ignores: ['node_modules/**', 'dist/**', '*.config.js']
  }
]
