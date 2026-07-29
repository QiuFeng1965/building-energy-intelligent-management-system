<template>
  <div class="space-y-3">
    <!-- KPI 卡片骨架 -->
    <div v-if="type === 'kpi'" class="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <div v-for="i in 4" :key="i" class="bg-white dark:bg-slate-800 rounded-xl p-4 border border-slate-100 dark:border-slate-700 shadow-sm">
        <div class="skeleton h-3 w-20 mb-3"></div>
        <div class="skeleton h-7 w-24 mb-2"></div>
        <div class="skeleton h-2 w-16"></div>
      </div>
    </div>
    <!-- 表格骨架 -->
    <div v-else-if="type === 'table'" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4">
      <div v-for="i in rows" :key="i" class="flex items-center gap-4 py-3 border-b border-slate-50 dark:border-slate-700 last:border-0">
        <div class="skeleton h-4 flex-1"></div>
        <div class="skeleton h-4 w-24"></div>
        <div class="skeleton h-4 w-20"></div>
        <div class="skeleton h-4 w-16"></div>
      </div>
    </div>
    <!-- 图表骨架 -->
    <div v-else-if="type === 'chart'" class="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4">
      <div class="skeleton h-5 w-32 mb-4"></div>
      <div class="flex items-end gap-2 h-64">
        <div v-for="i in 12" :key="i" class="skeleton flex-1" :style="{ height: (30 + Math.random() * 60) + '%' }"></div>
      </div>
    </div>
    <!-- 通用卡片骨架 -->
    <div v-else class="bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700 p-4 space-y-3">
      <div class="skeleton h-5 w-1/3"></div>
      <div class="skeleton h-3 w-full"></div>
      <div class="skeleton h-3 w-2/3"></div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  type: { type: String, default: 'card' }, // kpi | table | chart | card
  rows: { type: Number, default: 6 },
})
</script>
