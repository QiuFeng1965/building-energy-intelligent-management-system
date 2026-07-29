<template>
  <div v-if="error" class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 rounded-2xl bg-rose-50 dark:bg-rose-900/20 flex items-center justify-center mb-4">
      <el-icon class="text-3xl text-rose-500"><WarningFilled /></el-icon>
    </div>
    <h3 class="text-lg font-bold text-slate-800 dark:text-slate-100 mb-2">页面渲染异常</h3>
    <p class="text-sm text-slate-500 dark:text-slate-400 mb-4 max-w-md">
      抱歉，该模块发生了未知错误。请尝试刷新页面，或联系管理员反馈以下错误信息。
    </p>
    <details class="text-xs text-left bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg p-3 max-w-md w-full mb-4">
      <summary class="cursor-pointer text-slate-600 dark:text-slate-300 font-medium">错误详情</summary>
      <pre class="mt-2 text-rose-500 whitespace-pre-wrap break-all">{{ error.message }}\n{{ error.stack }}</pre>
    </details>
    <div class="flex gap-2">
      <el-button size="small" @click="reset">重试加载</el-button>
      <el-button size="small" type="primary" @click="reload">刷新页面</el-button>
    </div>
  </div>
  <slot v-else />
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { WarningFilled } from '@element-plus/icons-vue'

const error = ref(null)

onErrorCaptured((err) => {
  error.value = err
  // 上报错误到后端（如启用可观测性模块）
  try {
    if (window.navigator?.sendBeacon) {
      const blob = new Blob([JSON.stringify({
        type: 'frontend_error',
        message: err.message,
        stack: err.stack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
      })], { type: 'application/json' })
      window.navigator.sendBeacon('/api/observability/frontend-error', blob)
    }
  } catch (e) {
    // 静默失败，不影响用户
  }
  // 阻止错误继续向上冒泡
  return false
})

function reset() {
  error.value = null
}
function reload() {
  window.location.reload()
}
</script>
