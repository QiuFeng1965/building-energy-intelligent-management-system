<template>
  <transition name="fade-scale">
    <div v-if="visible" class="fixed inset-0 z-[3000] flex justify-center pt-[12vh] px-4 cmdk-overlay" @click.self="close">
      <div class="w-full max-w-xl bg-white dark:bg-slate-800 rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 overflow-hidden animate-scale-in">
        <!-- 搜索框 -->
        <div class="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700">
          <el-icon class="text-slate-400 text-xl"><Search /></el-icon>
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            placeholder="搜索页面、功能或快捷操作..."
            class="flex-1 bg-transparent outline-none text-slate-800 dark:text-slate-100 text-base"
            @keydown.esc="close"
            @keydown.down.prevent="moveDown"
            @keydown.up.prevent="moveUp"
            @keydown.enter.prevent="selectActive"
          />
          <kbd class="px-2 py-0.5 text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-700 rounded border border-slate-200 dark:border-slate-600">ESC</kbd>
        </div>

        <!-- 结果列表 -->
        <div class="max-h-[60vh] overflow-y-auto p-2">
          <template v-if="filtered.length">
            <div v-for="(group, gi) in grouped" :key="group.label">
              <div v-if="group.items.length" class="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">{{ group.label }}</div>
              <button
                v-for="(item, ii) in group.items"
                :key="item.id"
                :ref="el => { if (el) itemEls[globalIndex(gi, ii)] = el }"
                @click="execute(item)"
                @mouseenter="activeIdx = globalIndex(gi, ii)"
                :class="[
                  'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                  activeIdx === globalIndex(gi, ii)
                    ? 'bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300'
                    : 'text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700/50'
                ]"
              >
                <el-icon class="text-lg shrink-0">
                  <component :is="item.icon || 'Document'" />
                </el-icon>
                <div class="flex-1 min-w-0">
                  <div class="font-medium text-sm truncate">{{ item.title }}</div>
                  <div v-if="item.subtitle" class="text-xs text-slate-400 truncate">{{ item.subtitle }}</div>
                </div>
                <kbd v-if="item.shortcut" class="px-1.5 py-0.5 text-[10px] font-bold text-slate-400 bg-slate-100 dark:bg-slate-700 rounded">{{ item.shortcut }}</kbd>
              </button>
            </div>
          </template>
          <div v-else class="px-3 py-8 text-center text-slate-400 dark:text-slate-500">
            <el-icon class="text-3xl mb-2"><Search /></el-icon>
            <div class="text-sm">未找到匹配 "{{ query }}" 的功能</div>
          </div>
        </div>

        <!-- 底部快捷键提示 -->
        <div class="px-4 py-2 border-t border-slate-100 dark:border-slate-700 flex items-center justify-between text-[11px] text-slate-400">
          <div class="flex items-center gap-3">
            <span><kbd class="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded">↑↓</kbd> 导航</span>
            <span><kbd class="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded">↵</kbd> 选择</span>
          </div>
          <span class="text-indigo-500">擎翼数字中枢 · {{ filtered.length }} 项可操作</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Search, Document, DataBoard, DataLine, Cpu, MagicStick, OfficeBuilding,
  Bell, Promotion, Monitor, Setting, Moon, Sunny, Refresh
} from '@element-plus/icons-vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'toggle-theme', 'refresh'])

const router = useRouter()
const route = useRoute()

const query = ref('')
const activeIdx = ref(0)
const inputRef = ref(null)
const itemEls = ref([])

// 命令清单：路由跳转 / 主题切换 / 全局动作
const commands = [
  // ===== 路由跳转 =====
  { id: 'nav-spatial', group: 'navigation', title: '全息建筑孪生', subtitle: '3D 校园与建筑可视化', icon: OfficeBuilding, action: () => router.push('/spatial-twin') },
  { id: 'nav-dashboard', group: 'navigation', title: '能源态势总览', subtitle: 'KPI 大屏与综合看板', icon: DataBoard, action: () => router.push('/dashboard') },
  { id: 'nav-energy', group: 'navigation', title: '能效诊断分析', subtitle: '能耗趋势与 AI 预测', icon: DataLine, action: () => router.push('/energy') },
  { id: 'nav-devices', group: 'navigation', title: '能耗设备监测', subtitle: '设备状态实时监控', icon: Cpu, action: () => router.push('/devices') },
  { id: 'nav-ai', group: 'navigation', title: 'AI 策略寻优', subtitle: '智能体对话与策略生成', icon: MagicStick, action: () => router.push('/ai-agent') },
  { id: 'nav-admin', group: 'navigation', title: '核心数据驾驶舱', subtitle: '管理后台与系统配置', icon: Monitor, action: () => router.push('/admin') },
  // 前沿
  { id: 'nav-frontier-energy', group: 'navigation', title: '前沿 · 能源智能分析', subtitle: '碳排放 / 虚拟电厂 / 微电网', icon: DataLine, action: () => router.push('/frontier/energy') },
  { id: 'nav-frontier-ai', group: 'navigation', title: '前沿 · 智能体与知识', subtitle: '多智能体 / 知识图谱', icon: MagicStick, action: () => router.push('/frontier/ai') },
  { id: 'nav-frontier-ops', group: 'navigation', title: '前沿 · 数字孪生与运维', subtitle: '3D 孪生 / AR / 边缘网关', icon: Cpu, action: () => router.push('/frontier/ops') },
  // 进阶
  { id: 'nav-advanced-diagnose', group: 'navigation', title: '进阶 · 能源诊断与优化', subtitle: 'RUL / 基准对标 / 多能耦合', icon: DataLine, action: () => router.push('/advanced/diagnose') },
  { id: 'nav-advanced-ops', group: 'navigation', title: '进阶 · 运营管理', subtitle: '告警中心 / 审计 / 工单', icon: Bell, action: () => router.push('/advanced/ops') },
  { id: 'nav-advanced-esg', group: 'navigation', title: '进阶 · ESG 与投资决策', subtitle: 'ESG / ROI / 推送', icon: Promotion, action: () => router.push('/advanced/esg') },

  // ===== 全局动作 =====
  { id: 'action-refresh', group: 'actions', title: '刷新全部数据', subtitle: '触发当前页面数据重载', icon: Refresh, shortcut: 'F5', action: () => { emit('refresh'); ElMessage.success('已触发数据刷新') } },
  { id: 'action-theme', group: 'actions', title: '切换主题（亮色 / 暗色）', subtitle: '一键切换视觉主题', icon: Moon, shortcut: '⇧D', action: () => emit('toggle-theme') },
  { id: 'action-logout', group: 'actions', title: '安全退出登录', subtitle: '清除 token 并跳转登录页', icon: Document, action: () => {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    router.push('/login')
    ElMessage.success('已安全退出')
  }},
]

// 计算属性：分组 + 过滤
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return commands
  return commands.filter(c =>
    c.title.toLowerCase().includes(q) ||
    (c.subtitle && c.subtitle.toLowerCase().includes(q))
  )
})

const grouped = computed(() => {
  const nav = filtered.value.filter(c => c.group === 'navigation')
  const act = filtered.value.filter(c => c.group === 'actions')
  return [
    { label: '页面导航', items: nav },
    { label: '快捷动作', items: act },
  ].filter(g => g.items.length)
})

function globalIndex(gi, ii) {
  let count = 0
  for (let i = 0; i < gi; i++) count += grouped.value[i].items.length
  return count + ii
}

function moveDown() {
  if (!filtered.value.length) return
  activeIdx.value = (activeIdx.value + 1) % filtered.value.length
  scrollToActive()
}
function moveUp() {
  if (!filtered.value.length) return
  activeIdx.value = (activeIdx.value - 1 + filtered.value.length) % filtered.value.length
  scrollToActive()
}
function selectActive() {
  if (filtered.value[activeIdx.value]) execute(filtered.value[activeIdx.value])
}
function scrollToActive() {
  nextTick(() => {
    const el = itemEls.value[activeIdx.value]
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
  })
}
function execute(item) {
  if (item.action) item.action()
  close()
}
function close() {
  query.value = ''
  activeIdx.value = 0
  emit('close')
}

// 监听可见状态：自动聚焦输入框
watch(() => props.visible, (v) => {
  if (v) {
    nextTick(() => {
      inputRef.value?.focus()
    })
  } else {
    query.value = ''
    activeIdx.value = 0
  }
})

// 重置 activeIdx 当搜索词变化
watch(query, () => { activeIdx.value = 0 })
</script>

<style scoped>
.fade-scale-enter-active, .fade-scale-leave-active {
  transition: opacity 0.2s ease;
}
.fade-scale-enter-from, .fade-scale-leave-to {
  opacity: 0;
}
</style>
