<template>
  <!-- 错误兜底组件：接口失败时展示友好提示 -->
  <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
    <div class="w-16 h-16 rounded-full bg-rose-50 flex items-center justify-center mb-4">
      <el-icon size="32" class="text-rose-400"><WarningFilled /></el-icon>
    </div>
    <p class="text-slate-600 font-medium mb-1">{{ message }}</p>
    <p class="text-slate-400 text-sm mb-4">{{ detail }}</p>
    <el-button v-if="showRetry" type="primary" plain size="small" @click="$emit('retry')">
      <el-icon class="mr-1"><Refresh /></el-icon> 重新加载
    </el-button>
  </div>
</template>

<script setup>
import { WarningFilled, Refresh } from '@element-plus/icons-vue'

defineProps({
  message: {
    type: String,
    default: '数据加载失败'
  },
  detail: {
    type: String,
    default: '请检查网络连接或稍后重试'
  },
  showRetry: {
    type: Boolean,
    default: true
  }
})

defineEmits(['retry'])
</script>
