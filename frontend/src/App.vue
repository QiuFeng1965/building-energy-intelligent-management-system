<template>
  <!-- 登录页：由路由控制，未登录时 router 守卫会自动跳转到 /login -->
  <router-view v-if="!isLoggedIn" />

  <div v-else class="flex h-screen w-full bg-slate-50 relative">

    <!-- 移动端侧边栏遮罩 -->
    <div v-show="sidebarOpen" class="fixed inset-0 bg-slate-900/50 z-20 md:hidden" @click="sidebarOpen = false"></div>

    <aside :class="[
      'bg-white border-r border-slate-200 flex flex-col z-30 shrink-0 transition-transform duration-300',
      'fixed md:relative inset-y-0 left-0 w-64',
      sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
    ]">
      <div class="h-16 flex items-center justify-between px-6 border-b font-bold text-lg text-indigo-600">
        <span>擎翼数字中枢</span>
        <!-- 移动端关闭按钮 -->
        <el-icon class="md:hidden cursor-pointer text-slate-400" @click="sidebarOpen = false"><Close /></el-icon>
      </div>
      <el-menu :default-active="currentMenuIndex" @select="handleMenuSelect" class="border-none p-3">

        <el-menu-item-group title="空间孪生管理">
          <el-menu-item index="5">
            <el-icon><OfficeBuilding /></el-icon>
            <span>全息建筑孪生</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group title="能源与能效体系">
          <el-menu-item index="1">
            <el-icon><DataBoard /></el-icon>
            <span>能源态势总览</span>
          </el-menu-item>
          <el-menu-item index="2">
            <el-icon><DataLine /></el-icon>
            <span>能效诊断分析</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group title="运维保障体系">
          <el-menu-item index="3">
            <el-icon><Cpu /></el-icon>
            <span>能耗设备监测</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group title="AI 智慧决策">
          <el-menu-item index="4">
            <el-icon><MagicStick /></el-icon>
            <span>AI 策略寻优</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group title="前沿创新实验室">
          <el-menu-item index="6-1">
            <el-icon><DataLine /></el-icon>
            <span>能源智能分析</span>
          </el-menu-item>
          <el-menu-item index="6-2">
            <el-icon><MagicStick /></el-icon>
            <span>智能体与知识</span>
          </el-menu-item>
          <el-menu-item index="6-3">
            <el-icon><Cpu /></el-icon>
            <span>数字孪生与运维</span>
          </el-menu-item>
        </el-menu-item-group>

        <el-menu-item-group title="进阶能力中心">
          <el-menu-item index="7-1">
            <el-icon><DataLine /></el-icon>
            <span>能源诊断与优化</span>
          </el-menu-item>
          <el-menu-item index="7-2">
            <el-icon><Bell /></el-icon>
            <span>运营管理</span>
          </el-menu-item>
          <el-menu-item index="7-3">
            <el-icon><Promotion /></el-icon>
            <span>ESG 与投资决策</span>
          </el-menu-item>
        </el-menu-item-group>

      </el-menu>
    </aside>

    <div class="flex-1 flex flex-col overflow-hidden relative">

      <header class="h-16 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between px-4 md:px-8 shrink-0">
        <div class="flex items-center gap-3">
          <!-- 移动端汉堡菜单 -->
          <el-icon class="md:hidden text-xl text-slate-600 dark:text-slate-300 cursor-pointer hover:text-indigo-600" @click="sidebarOpen = true"><Expand /></el-icon>
          <h2 class="font-semibold text-slate-800 dark:text-slate-100 flex items-center gap-2">
            <span class="hidden sm:inline">{{ pageTitle }}</span>
            <el-tag v-if="currentMenuIndex === 'admin'" type="danger" size="small" effect="dark" round class="ml-2 shadow-sm">Super Admin</el-tag>
          </h2>
        </div>

        <div class="flex items-center gap-3 md:gap-5">
          <!-- 全局搜索按钮（Ctrl+K） -->
          <el-tooltip content="按 Ctrl+K 唤起命令面板" placement="bottom">
            <button
              @click="cmdPaletteVisible = true"
              class="hidden sm:flex items-center gap-2 px-3 py-1.5 text-sm text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg transition-colors border border-transparent hover:border-slate-300 dark:hover:border-slate-500"
            >
              <el-icon><Search /></el-icon>
              <span class="text-xs">快速搜索</span>
              <kbd class="px-1.5 py-0.5 text-[10px] font-bold bg-white dark:bg-slate-800 rounded border border-slate-200 dark:border-slate-600">Ctrl K</kbd>
            </button>
          </el-tooltip>
          <el-icon class="sm:hidden text-xl text-slate-500 dark:text-slate-300 cursor-pointer hover:text-indigo-500" @click="cmdPaletteVisible = true"><Search /></el-icon>

          <!-- 主题切换按钮 -->
          <el-tooltip :content="isDark ? '切换到亮色模式' : '切换到暗色模式'" placement="bottom">
            <el-icon class="text-xl text-slate-500 dark:text-slate-300 cursor-pointer hover:text-indigo-500 transition-colors" @click="toggleTheme">
              <Sunny v-if="isDark" />
              <Moon v-else />
            </el-icon>
          </el-tooltip>

          <el-badge is-dot class="item mt-1.5">
            <el-icon class="text-xl text-slate-500 dark:text-slate-300 cursor-pointer hover:text-indigo-500 transition-colors"><Bell /></el-icon>
          </el-badge>

          <el-dropdown trigger="click" @command="handleCommand">
            <div class="flex items-center gap-2.5 cursor-pointer hover:bg-slate-100 py-1.5 px-3 rounded-full transition-all border border-transparent hover:border-slate-200">
              <el-avatar :size="32" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" class="border border-slate-200 shadow-sm" />
              <div class="flex flex-col">
                <span class="text-sm font-bold text-slate-700 leading-tight">Admin</span>
                <span class="text-[10px] text-emerald-500 font-bold tracking-wider leading-tight">SUPER PRO</span>
              </div>
              <el-icon class="text-slate-400 text-xs ml-1"><CaretBottom /></el-icon>
            </div>

            <template #dropdown>
              <el-dropdown-menu class="w-64 p-2 !rounded-xl !border-slate-100 !shadow-xl">
                <div class="px-3 py-3 mb-2 border-b border-slate-100 flex items-center gap-3 bg-slate-50 rounded-lg">
                   <el-avatar :size="40" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" class="border-2 border-white shadow-sm" />
                   <div>
                     <div class="font-bold text-slate-800 text-sm">系统最高管理员</div>
                     <div class="text-xs text-slate-400 mt-0.5">admin@nova.tech</div>
                   </div>
                </div>

                <el-dropdown-item command="profile" class="!rounded-lg hover:!bg-slate-50 !mb-1">
                  <el-icon><User /></el-icon> 个人偏好与设置
                </el-dropdown-item>
                <el-dropdown-item command="api" class="!rounded-lg hover:!bg-slate-50 !mb-1">
                  <el-icon><Key /></el-icon> 开发者 API 密钥
                </el-dropdown-item>
                <el-dropdown-item command="billing" class="!rounded-lg hover:!bg-slate-50 !mb-1">
                  <el-icon><CreditCard /></el-icon> 订阅与用量分析
                </el-dropdown-item>

                <el-dropdown-item divided command="admin" class="!text-indigo-600 !font-bold bg-indigo-50/50 hover:!bg-indigo-100 !rounded-lg mt-2 py-2">
                  <el-icon><Monitor /></el-icon> 核心数据驾驶舱 (管理空间)
                </el-dropdown-item>

                <el-dropdown-item divided command="logout" class="!text-rose-500 hover:!bg-rose-50 !rounded-lg mt-2">
                  <el-icon><SwitchButton /></el-icon> 安全退出
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>



      </header>

      <main class="flex-1 overflow-auto p-4 md:p-6 bg-slate-50 dark:bg-slate-900 relative">
        <ErrorBoundary>
          <router-view v-slot="{ Component }">
            <transition name="route-fade" mode="out-in">
              <keep-alive>
                <component :is="Component" :data="dashboardData" />
              </keep-alive>
            </transition>
          </router-view>
        </ErrorBoundary>
      </main>

      <div class="fixed bottom-6 right-6 z-50">
        <div
          @click="toggleGlobalChat"
          class="w-14 h-14 bg-indigo-600 rounded-full shadow-lg flex items-center justify-center cursor-pointer hover:bg-indigo-700 hover:scale-105 transition-all text-white relative group"
        >
          <el-icon class="text-2xl"><Service /></el-icon>
          <div class="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full border-2 border-white animate-pulse"></div>
        </div>

        <transition name="el-zoom-in-bottom">
          <div v-show="globalChatVisible" class="absolute bottom-16 right-0 w-80 md:w-96 bg-white rounded-2xl shadow-2xl border border-slate-100 flex flex-col overflow-hidden" style="height: 500px;">
            
            <div class="h-14 bg-indigo-600 px-4 flex items-center justify-between text-white shrink-0">
              <div class="flex items-center gap-2">
                <el-icon class="text-xl"><MagicStick /></el-icon>
                <span class="font-medium">全局 AI 助手</span>
              </div>
              <el-icon @click="toggleGlobalChat" class="cursor-pointer hover:opacity-80"><Close /></el-icon>
            </div>
            
            <div id="global-chat-scroll" class="flex-1 overflow-auto p-4 bg-slate-50 flex flex-col gap-4">
              <div v-for="(msg, index) in globalChatMessages" :key="index" class="flex" :class="msg.role === 'user' ? 'justify-end' : 'justify-start'">
                <div v-if="msg.role === 'ai'" class="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center shrink-0 mr-2 text-indigo-600">
                  <el-icon><Cpu /></el-icon>
                </div>
                
                <div :class="msg.role === 'user' ? 'bg-indigo-600 text-white rounded-l-xl rounded-tr-xl' : 'bg-white text-slate-700 rounded-r-xl rounded-tl-xl border border-slate-100 shadow-sm'" class="px-4 py-2.5 max-w-[85%] text-sm leading-relaxed">
                  <div v-if="msg.loading" class="flex items-center gap-1 h-5">
                    <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"></span>
                    <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></span>
                    <span class="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.4s"></span>
                  </div>
                  <div v-else v-html="sanitizeHtml(msg.content)"></div>
                </div>
              </div>
            </div>

            <div class="p-3 bg-white border-t shrink-0">
              <el-input v-model="inputText" placeholder="询问任何数据或发出指令..." @keyup.enter="handleGlobalSend">
                <template #append>
                  <el-button @click="handleGlobalSend" type="primary" class="!bg-indigo-600 !text-white !border-none hover:!bg-indigo-700">
                    <el-icon><Position /></el-icon>
                  </el-button>
                </template>
              </el-input>
            </div>
          </div>
        </transition>
      </div>

    </div>

    <!-- 全局命令面板（Ctrl+K） -->
    <CommandPalette
      :visible="cmdPaletteVisible"
      @close="cmdPaletteVisible = false"
      @toggle-theme="toggleTheme"
      @refresh="refreshCurrentPage"
    />
  </div>
</template>

<script setup>

import { ref, nextTick, onMounted, onUnmounted, computed, watch } from 'vue'
import DOMPurify from 'dompurify'
// 业务组件已由 vue-router 懒加载，此处不再静态 import，避免首屏 bundle 膨胀
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Sunny, Moon } from '@element-plus/icons-vue'
import { safeFetch, getAuthHeaders } from './utils/request'
import { fetchDashboard, chatStream } from './api/index.js'
import { useRouter, useRoute } from 'vue-router'
// 新增：全局升级组件
import CommandPalette from './components/CommandPalette.vue'
import ErrorBoundary from './components/ErrorBoundary.vue'
import { useTheme } from './composables/useTheme'
import { initWebVitals } from './composables/useWebVitals'

// 主题系统（亮 / 暗 / 跟随系统）
const { currentTheme, isDark, setTheme, toggleTheme } = useTheme()

// 命令面板可见状态
const cmdPaletteVisible = ref(false)

// 触发当前页面数据刷新（通过广播事件让视图组件自行重载）
const refreshCurrentPage = () => {
  window.dispatchEvent(new CustomEvent('app:refresh-current'))
}

// DOMPurify 清洗 HTML，防止 XSS
const sanitizeHtml = (html) => {
  if (!html) return ''
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

// ================= 🌟 登录系统核心控制 =================
// 基于路由判断登录态：route.name === 'login' 时显示登录页，其余显示主布局
const isLoggedIn = computed(() => route.name !== 'login')

// 移动端侧边栏控制
const sidebarOpen = ref(false)

// 新增：防抖锁，防止用户在 AI 响应期间狂点按钮
const isGlobalChatting = ref(false)

// 路由实例
const router = useRouter()
const route = useRoute()

// 当前菜单 index（从路由 meta 推导）
const currentMenuIndex = computed(() => route.meta.menuIndex || '5')
// 当前页标题
const pageTitle = computed(() => route.meta.title || '擎翼数字中枢')

// ================== 👇 补充的 3 段核心代码 👇 ==================

// 1. 🌟 必须定义这个变量，不然模板里的 :data="dashboardData" 会报错
// 在 App.vue 里，初始化数据时直接把骨架搭好
const dashboardData = ref({
  kpi: {},
  pie: [],
  bar: { x: [], y: [] },
  line: { x: [], y: [] }
})

// 2. 🌟 拉取数据的函数（走 vite proxy + token 鉴权）
const fetchDashboardData = async () => {
  try {
    dashboardData.value = await fetchDashboard()
  } catch (error) {
    if (import.meta.env.DEV) console.error("获取大屏数据失败:", error)
  }
}

// 3. 🌟 登录成功后存储 token（兼容旧 emit 方式，新逻辑由 Login.vue 直接 router.push）
const handleLoginSuccess = (data) => {
  if (data?.token) {
    localStorage.setItem('token', data.token)
    localStorage.setItem('username', data.username || 'admin')
  }
  fetchDashboardData()
  // 登录成功后跳转到主页
  router.push('/spatial-twin')
}
// ======================================================

// ================= 菜单与路由映射 =================
// 菜单 index ↔ 路由 path 的映射表
const MENU_TO_ROUTE = {
  '1': '/dashboard',
  '2': '/energy',
  '3': '/devices',
  '4': '/ai-agent',
  '5': '/spatial-twin',
  '6-1': '/frontier/energy',
  '6-2': '/frontier/ai',
  '6-3': '/frontier/ops',
  '7-1': '/advanced/diagnose',
  '7-2': '/advanced/ops',
  '7-3': '/advanced/esg',
  'admin': '/admin'
}

// 菜单点击：切换路由（替代原 activeMenu 赋值）
const handleMenuSelect = (index) => {
  const path = MENU_TO_ROUTE[index]
  if (path && path !== route.path) {
    router.push(path)
  }
  // 移动端点击菜单后自动收起侧边栏
  sidebarOpen.value = false
}

// 🌟 处理下拉菜单点击事件
const handleCommand = (command) => {
  if (command === 'admin') {
    router.push('/admin')
  } else if (command === 'logout') {
    ElMessageBox.confirm('您确定要退出数字中枢系统吗？', '安全登出', {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning',
      center: true
    }).then(() => {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      router.push('/login')
      ElMessage.success('已安全退出系统')
    }).catch(() => {})
  } else {
    // 预留功能点击时的弹窗提示
    ElMessage.info({ message: `🚀 [${command}] 模块正在升级中，敬请期待...`, grouping: true })
  }
}

// --- 全局 AI 悬浮窗相关状态 ---
const globalChatVisible = ref(false)
const globalChatMessages = ref([
  { role: 'ai', content: '您好，我是擎翼数字中枢的全局 AI 助手。请问有什么可以帮您？' }
])
const inputText = ref('')

// 切换全局聊天窗口
const toggleGlobalChat = () => {
  globalChatVisible.value = !globalChatVisible.value
}

// 自动滚动到底部
const scrollGlobalToBottom = () => {
  nextTick(() => {
    const container = document.getElementById('global-chat-scroll')
    if (container) container.scrollTop = container.scrollHeight
  })
}

// 发送全局消息给大模型
// 发送全局消息给大模型
// 发送全局消息给大模型
const handleGlobalSend = async () => {
  // 1. 拦截器：如果输入为空，或者【正在对话中】，直接返回
  if (!inputText.value.trim() || isGlobalChatting.value) return
  
  const text = inputText.value
  globalChatMessages.value.push({ role: 'user', content: text })
  inputText.value = ''
  scrollGlobalToBottom()

  const aiIdx = globalChatMessages.value.length
  globalChatMessages.value.push({ role: 'ai', content: '', loading: true })
  scrollGlobalToBottom()

  // 2. 锁定状态
  isGlobalChatting.value = true 

  try {
    let currentPage = '未知页面'
    if (currentMenuIndex.value === '1') currentPage = '综合态势大屏'
    if (currentMenuIndex.value === '2') currentPage = '深度能效洞察'
    if (currentMenuIndex.value === '3') currentPage = '底层数据穿透'
    if (currentMenuIndex.value === '4') currentPage = 'AIgent智慧调度'

    // ✅ 统一走 api 层封装的 SSE 调用
    await chatStream(
      { prompt: text, currentPage },
      {
        onThinking: (reply) => {
          globalChatMessages.value[aiIdx].content = `<span style="color: #94a3b8; font-size: 12px; font-style: italic;">${reply}</span>`
          scrollGlobalToBottom()
        },
        onMessage: (_reply, fullText) => {
          // 剔除 Echarts 代码，防止悬浮窗出现乱码
          globalChatMessages.value[aiIdx].content = fullText.replace(/```echarts[\s\S]*?```/g, '<br><span style="color:#8b5cf6;font-size:12px;font-weight:bold;">[📊 详细数据图表请前往 "AI 策略寻优" 页面查看]</span>')
          scrollGlobalToBottom()
        },
        onDone: () => {
          globalChatMessages.value[aiIdx].loading = false
          scrollGlobalToBottom()
        },
        onError: () => {
          globalChatMessages.value[aiIdx].loading = false
          globalChatMessages.value[aiIdx].content = "⚠️ 连接 AI 引擎失败，请检查后端服务是否启动。"
          scrollGlobalToBottom()
        }
      }
    )

  } catch (error) {
    globalChatMessages.value[aiIdx].loading = false
    globalChatMessages.value[aiIdx].content = "⚠️ 连接 AI 引擎失败，请检查后端服务是否启动。"
    scrollGlobalToBottom()
  } finally {
    // 3. 释放锁定
    isGlobalChatting.value = false
  }
}
// 监听 token 过期事件（由 request.js 在 401 时派发）
const handleAuthExpired = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  router.push('/login')
}

// 👇 ========= 请把这段接收指令的函数，放在 onMounted 的上方 ========= 👇

// 🌟 接收全局 AI 呼叫的事件回调
// 🌟 接收全局 AI 呼叫的事件回调
const handleTriggerAI = (event) => {
  const autoPrompt = event.detail
  if (!autoPrompt) return

  // 1. 如果你的 AI 聊天面板默认是收起的，这里可以加一行代码把它展开
  // isGlobalChatVisible.value = true (如果没这个变量可以忽略这行)
  // 1. 自动展开 AI 悬浮面板
  globalChatVisible.value = true
  // 2. 将图表传过来的文本赋给你的输入框变量，并触发你的发送函数！
  if (!isGlobalChatting.value) {
     inputText.value = autoPrompt     // 👈 换成你真实的变量名 inputText
     handleGlobalSend()               // 👈 换成你真实的发送函数 handleGlobalSend
  }
}
// 👆 ============================================================== 👆

// ===== 全局快捷键：Ctrl+K 唤起命令面板 =====
const handleGlobalKeydown = (e) => {
  // Ctrl+K / Cmd+K：唤起命令面板
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (isLoggedIn.value) {
      cmdPaletteVisible.value = !cmdPaletteVisible.value
    }
  }
  // Shift+D：切换主题
  if (e.shiftKey && e.key.toLowerCase() === 'd' && !e.ctrlKey && !e.metaKey && !e.altKey) {
    // 仅当焦点不在输入框时触发
    const tag = document.activeElement?.tagName?.toLowerCase()
    if (tag !== 'input' && tag !== 'textarea' && !document.activeElement?.isContentEditable) {
      e.preventDefault()
      toggleTheme()
    }
  }
}

// 初始化数据
onMounted(() => {
  // 👇 ========= 在 onMounted 里面加这一行：竖起耳朵监听 ========= 👇
  window.addEventListener('trigger-global-ai', handleTriggerAI)
  // 监听 token 过期事件
  window.addEventListener('auth:expired', handleAuthExpired)
  // 全局快捷键
  window.addEventListener('keydown', handleGlobalKeydown)
  // 初始化 Web Vitals 性能采集
  initWebVitals()
  // 🌟 修复：刷新页面后从 localStorage 恢复登录态时，主动拉取一次大屏数据
  // 否则跳过登录页直接进入主界面时，dashboardData 会一直停留在空骨架，表现为"数据丢失"
  if (isLoggedIn.value) {
    fetchDashboardData()
  }
})
// 👇 ========= 新增一个 onUnmounted 生命周期：防止内存泄漏 ========= 👇
onUnmounted(() => {
  window.removeEventListener('trigger-global-ai', handleTriggerAI)
  window.removeEventListener('auth:expired', handleAuthExpired)
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<style scoped>
/* 深度修改输入框的圆角和样式，显得更精致 */
:deep(.el-input__wrapper) {
  border-radius: 9999px !important;
  box-shadow: 0 0 0 1px #e2e8f0 inset !important;
}
:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #3b82f6 inset !important;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
/* 在 App.vue 的 <style> 中添加 */
:deep(.el-menu-item-group__title) {
  padding: 16px 0 8px 16px !important;
  font-size: 11px !important;
  font-weight: 800 !important;
  color: #64748b !important; /* 灰度标题，体现专业感 */
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

:deep(.el-menu-item) {
  border-radius: 8px;
  margin-bottom: 4px;
}

:deep(.el-menu-item.is-active) {
  background-color: #eef2ff !important; /* 选中状态显示淡淡的靛青色 */
  font-weight: bold;
}
</style>