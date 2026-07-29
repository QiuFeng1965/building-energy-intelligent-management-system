<template>
  <div class="flex flex-col gap-6">
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <div class="bg-gradient-to-br from-indigo-500 to-purple-600 p-6 rounded-2xl shadow-md text-white flex items-center justify-between">
        <div>
          <div class="text-indigo-100 text-sm mb-1">AIgent 核心状态</div>
          <div class="text-3xl font-black tracking-tight flex items-center gap-2">
            ONLINE <span class="relative flex h-4 w-4 ml-2"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-50"></span><span class="relative inline-flex rounded-full h-4 w-4 bg-white"></span></span>
          </div>
        </div>
        <el-icon class="text-6xl opacity-20"><MagicStick /></el-icon>
      </div>
      
      <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between">
        <div>
          <div class="text-slate-500 text-sm mb-1">今日自动决策下发</div>
          <div class="text-3xl font-black text-slate-800">1,284 <span class="text-sm font-normal text-slate-400">次</span></div>
        </div>
        <div class="p-4 bg-emerald-50 rounded-xl text-emerald-500"><el-icon class="text-2xl"><Promotion /></el-icon></div>
      </div>

      <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex items-center justify-between">
        <div>
          <div class="text-slate-500 text-sm mb-1">AI 优化节能量 (预估)</div>
          <div class="text-3xl font-black text-slate-800">458.2 <span class="text-sm font-normal text-slate-400">kWh</span></div>
        </div>
        <div class="p-4 bg-amber-50 rounded-xl text-amber-500"><el-icon class="text-2xl"><Lightning /></el-icon></div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 bg-[#0f172a] rounded-2xl shadow-lg border border-slate-800 overflow-hidden flex flex-col h-[250px]">
        <div class="h-10 bg-slate-800 flex items-center px-4 gap-2">
          <div class="w-3 h-3 rounded-full bg-rose-500"></div>
          <div class="w-3 h-3 rounded-full bg-amber-500"></div>
          <div class="w-3 h-3 rounded-full bg-emerald-500"></div>
          <span class="text-slate-400 text-xs font-mono ml-2">aigent_core_v3.0 --runtime=active</span>
        </div>
        <div class="p-5 overflow-y-auto flex-1 font-mono text-sm space-y-2" id="terminal-scroll">
          <div v-for="(log, idx) in logs" :key="idx" class="flex gap-3 animate-fade-in">
            <span class="text-emerald-400">[{{ log.time }}]</span>
            <span :class="log.color">{{ log.msg }}</span>
          </div>
          <div v-if="isThinking" class="text-slate-500 animate-pulse">>>> AIgent 正在分析全域环境温湿度场..._</div>
        </div>
      </div>

      <div class="lg:col-span-1 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 flex flex-col h-[250px]">
        <h3 class="font-bold text-slate-800 text-sm flex items-center gap-2 mb-2">
          <div class="w-1.5 h-4 bg-purple-500 rounded-full"></div>AI 综合评估模型
        </h3>
        <div ref="radarChartRef" class="flex-1 w-full min-h-[180px]"></div>
      </div>
    </div>

    <div 
      ref="chatContainerRef"
      class="bg-white rounded-2xl shadow-sm border border-slate-100 flex flex-col h-fit overflow-hidden transform transition-all duration-1000 ease-out"
      :class="isChatVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-24'"
    >
      <div class="px-6 py-4 border-b border-slate-100 flex items-center gap-3 bg-slate-50/50">
        <div class="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center text-white"><el-icon><Service /></el-icon></div>
        <div>
          <div class="font-bold text-slate-700 text-sm">专属能效大模型助手</div>
          <div class="text-xs text-slate-400">基于千亿参数，随时为您解答系统运行状态</div>
        </div>
      </div>
      
      <div class="flex-1 p-6 bg-slate-50 space-y-6" id="chat-scroll">
        <div class="flex items-start gap-4">
          <div class="w-8 h-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center shrink-0"><el-icon><MagicStick /></el-icon></div>
          <div>
            <div class="bg-white p-4 rounded-2xl rounded-tl-none shadow-sm text-slate-700 text-sm border border-slate-100 mb-3">
              您好！我是您的智能能源管家。目前系统整体运行平稳，您可以直接问我问题，或者试试以下指令：
            </div>
            <div class="flex flex-wrap gap-2">
              <span v-for="tag in suggestions" :key="tag" @click="sendSuggestion(tag)" class="px-3 py-1.5 bg-indigo-50 text-indigo-600 rounded-full text-xs cursor-pointer hover:bg-indigo-100 transition-colors border border-indigo-100">
                {{ tag }}
              </span>
            </div>
          </div>
        </div>

        <div v-for="(msg, index) in chatMessages" :key="index" class="flex items-start gap-4" :class="msg.role === 'user' ? 'flex-row-reverse' : ''">
          <div class="w-8 h-8 rounded-full flex items-center justify-center shrink-0" :class="msg.role === 'user' ? 'bg-slate-800 text-white' : 'bg-indigo-100 text-indigo-600'">
            <el-icon><component :is="msg.role === 'user' ? 'User' : 'MagicStick'" /></el-icon>
          </div>
          <div class="max-w-[92%] p-4 rounded-2xl shadow-sm text-sm border overflow-hidden" 
               :class="msg.role === 'user' ? 'bg-indigo-600 text-white rounded-tr-none border-indigo-600' : 'bg-white text-slate-700 rounded-tl-none border-slate-100 leading-relaxed whitespace-pre-line'">
            
            <img v-if="msg.image" :src="msg.image" class="max-w-[300px] max-h-[300px] object-contain rounded-lg mb-2 border border-white/20 shadow-sm bg-black/5" />
            
            <div v-if="msg.thoughts && msg.thoughts.length > 0" class="mb-3">
              <details :open="msg.isThinking" class="group bg-slate-50 border border-slate-100 rounded-lg p-2 transition-all">
                <summary class="cursor-pointer text-xs text-slate-500 hover:text-indigo-600 flex items-center gap-1 select-none outline-none">
                  <span class="group-open:rotate-90 transition-transform duration-200">▶</span>
                  <span class="font-mono font-semibold">
                    {{ msg.isThinking ? '擎翼中枢正在深度思考...' : `思考与调度完毕 (${msg.thoughts.length} 步)` }}
                  </span>
                </summary>
                <ul class="pl-5 mt-2 border-l-2 border-indigo-200 text-xs text-slate-500 space-y-1.5 font-mono">
                  <li v-for="(thought, idx) in msg.thoughts" :key="idx" class="animate-fade-in flex items-start gap-1">
                    {{ thought }}
                  </li>
                </ul>
              </details>
            </div>

            <div class="relative">
              <span>{{ msg.content }}</span>
              <span v-if="msg.isThinking && msg.content.length > 0" class="inline-block w-1.5 h-3.5 ml-1 bg-indigo-500 animate-pulse align-middle"></span>
            </div>
            
            <div 
            v-if="msg.chartOptions" 
            :id="'ai-chart-' + index" 
            style="width: 100%; height: 280px; margin-top: 12px; background: white; border-radius: 8px; padding: 10px; box-shadow: inset 0 0 4px rgba(0,0,0,0.05);"
            ></div>
          </div>
        </div>
      </div>

      <div class="w-full bg-slate-50/50 p-4 pb-6 backdrop-blur-sm relative z-10 border-t border-slate-100">
        <div class="max-w-5xl mx-auto bg-white rounded-[24px] shadow-[0_8px_30px_rgb(0,0,0,0.06)] border border-slate-100/80 transition-all duration-300 focus-within:shadow-[0_8px_30px_rgb(99,102,241,0.12)] focus-within:border-indigo-200 overflow-hidden flex flex-col">
          
          <input type="file" ref="fileInputRef" accept="image/*" class="hidden" @change="handleImageSelect" />
          <input type="file" ref="docInputRef" accept=".txt,.md" class="hidden" @change="handleDocSelect" />

          <div v-if="selectedImage" class="px-5 pt-5 pb-1 animate-fade-in">
             <div class="relative inline-block group">
               <img :src="selectedImage" class="h-16 w-16 object-cover rounded-xl border border-slate-200 shadow-sm transition-transform duration-300 group-hover:scale-105" />
               <div @click="clearImage" class="absolute -top-2 -right-2 bg-slate-800 text-white w-5 h-5 rounded-full flex items-center justify-center text-[10px] cursor-pointer opacity-0 group-hover:opacity-100 transition-opacity shadow-lg">×</div>
             </div>
          </div>

          <div class="px-5 py-2">
            <el-input 
              v-model="inputText"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 5 }"
              placeholder="给 AIgent 发送调度指令，或上传设备附件分析..."
              resize="none"
              class="magic-input"
              @keydown.enter.prevent="handleSend"
            />
          </div>

          <div class="flex items-center justify-between px-4 pb-3 pt-1">
            <div class="flex items-center gap-1">
              <el-tooltip content="上传维保手册(TXT)" placement="top">
                <button @click="$refs.docInputRef.click()" class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 hover:text-indigo-600 transition-colors">
                  <el-icon class="text-[20px]"><Document /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="上传图纸或照片" placement="top">
                <button @click="$refs.fileInputRef.click()" class="w-9 h-9 flex items-center justify-center rounded-full hover:bg-slate-100 text-slate-400 hover:text-indigo-600 transition-colors">
                  <el-icon class="text-[20px]"><Picture /></el-icon>
                </button>
              </el-tooltip>

              <div class="h-4 w-[1px] bg-slate-200 mx-2"></div>

              <el-select
                v-model="selectedAgent"
                class="magic-agent-select w-[140px]"
                size="small"
              >
                <el-option label="✨ 综合主控管家" value="auto" />
                <el-option label="📚 Knowledge Agent" value="knowledge" />
                <el-option label="📊 Data Agent" value="data" />
                <el-option label="👁️ Photo Agent" value="photo" />
              </el-select>
            </div>

            <button
              @click="handleSend"
              :disabled="!inputText.trim() && !selectedImage"
              :class="(inputText.trim() || selectedImage) ? 'bg-indigo-600 text-white shadow-md hover:bg-indigo-700 hover:shadow-lg hover:-translate-y-0.5' : 'bg-slate-100 text-slate-400 cursor-not-allowed'"
              class="px-5 py-2 rounded-xl flex items-center gap-2 font-semibold transition-all duration-300"
            >
              发送 <el-icon><Position /></el-icon>
            </button>
          </div>
        </div>

        <div class="text-center text-[11px] text-slate-400 mt-4 tracking-wide">
          擎翼 AIgent 可能会产生系统误差，自动调度前请结合实际工况校验。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { MagicStick, Promotion, Lightning, Service, User, Position, Picture, Document } from '@element-plus/icons-vue'
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getAuthHeaders } from '../utils/request'
import { uploadDoc, chatStream } from '../api/index.js'

// 统一管理动态创建的 ECharts 实例，卸载时 dispose
const chartInstances = new Map()

// 🌟 新增：滚动显现动画相关的引用
const chatContainerRef = ref(null)
const isChatVisible = ref(false)

// --- 雷达图与终端日志逻辑 ---
const radarChartRef = ref(null)
const selectedAgent = ref('auto')
let radarChart = null

const initRadarChart = () => {
  if (!radarChartRef.value) return
  radarChart = echarts.init(radarChartRef.value)
  radarChart.setOption({
    radar: {
      indicator: [
        { name: '负荷精准度', max: 100 }, { name: '寿命损耗', max: 100 },
        { name: '舒适度', max: 100 }, { name: '节能率', max: 100 }, { name: '响应速度', max: 100 }
      ],
      axisName: { color: '#64748b', fontSize: 10 },
      splitArea: { areaStyle: { color: ['rgba(99, 102, 241, 0.05)', 'rgba(99, 102, 241, 0.1)'] } }
    },
    series: [{
      type: 'radar',
      data: [{ value: [92, 15, 95, 88, 98], itemStyle: { color: '#8b5cf6' }, areaStyle: { color: 'rgba(139, 92, 246, 0.4)' } }]
    }]
  })
}

const logs = ref([])
const isThinking = ref(true)
let logTimer = null
const mockMessages = [
  { msg: ">> 侦测到 [科研楼] 人员减少，正在调整新风阀开度...", color: "text-blue-400" },
  { msg: ">> 动作下发: [冷水机组 #02] 限制运行功率至 85%", color: "text-purple-400" },
  { msg: ">> 策略执行完毕. 预计本小时节能 12.4 kWh. [SUCCESS]", color: "text-emerald-400" }
]
const addLog = () => {
  const now = new Date()
  const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  const randomMsg = mockMessages[Math.floor(Math.random() * mockMessages.length)]
  logs.value.push({ time: timeStr, msg: randomMsg.msg, color: randomMsg.color })
  if (logs.value.length > 5) logs.value.shift()
}

// --- 聊天交互逻辑 ---
const suggestions = ref(['帮我查一下，昨天全校的总耗电量一共是多少？', '分析昨日能耗异常节点', '以图表的形式汇总本月各场景耗电量分布图'])
const chatMessages = ref([])
const inputText = ref('')
const currentImgB64 = ref(null)  
const fileInputRef = ref(null)

const handleDocSelect = async (e) => {
  const file = e.target.files[0]
  if (!file) return
  
  const msgIdx = chatMessages.value.push({ role: 'ai', content: `正在阅读并向量化文档《${file.name}》...`, loading: true }) - 1
  scrollToBottom('chat-scroll')

  try {
    const result = await uploadDoc(file)
    
    chatMessages.value[msgIdx].loading = false
    chatMessages.value[msgIdx].content = result.message || `成功学习文档：${file.name}`
    scrollToBottom('chat-scroll')
  } catch(err) {
    chatMessages.value[msgIdx].loading = false
    chatMessages.value[msgIdx].content = '文件上传失败，请检查后端状态。'
  }
  e.target.value = '' 
}

const selectedImage = ref(null) 
const selectedImageBase64 = ref(null) 

const clearImage = () => {
  selectedImage.value = null
  selectedImageBase64.value = null
  if (fileInputRef.value) fileInputRef.value.value = ''
}

const handleImageSelect = (e) => {
  const file = e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (event) => {
    selectedImage.value = event.target.result 
    selectedImageBase64.value = event.target.result.split(',')[1] 
  }
  reader.readAsDataURL(file)
}

const scrollToBottom = (id) => {
  nextTick(() => {
    const container = document.getElementById(id)
    if (container) container.scrollTop = container.scrollHeight
  })
}

const handleSend = async () => {
  if (!inputText.value.trim() && !selectedImage.value) return

  const userText = inputText.value
  const userImg = selectedImage.value 

  // 1. 提取历史聊天记录 (保持原有逻辑不变)
  const historyPayload = chatMessages.value
    .filter(msg => !msg.isThinking && msg.content) 
    .map(msg => ({
      role: msg.role === 'ai' ? 'assistant' : 'user', 
      content: msg.content
    }))

  inputText.value = ''
  selectedImage.value = null          
  selectedImageBase64.value = null    
  if (fileInputRef.value) fileInputRef.value.value = ''     

  // 2. 放入用户的新问题
  chatMessages.value.push({ role: 'user', content: userText, image: userImg })
  scrollToBottom('chat-scroll')

  // 🌟 3. 放入 AI 的占位气泡 (新增 thoughts 数组和 isThinking 状态)
  const aiMsgIndex = chatMessages.value.length
  chatMessages.value.push({
    role: 'ai',
    content: '',
    thoughts: [],
    isThinking: true,
    chartOptions: null
  })
  scrollToBottom('chat-scroll')

  try {
    // 🌟 4. 走统一 api 层封装的 SSE 调用
    let lastFullText = ''
    await chatStream(
      {
        prompt: userText,
        currentPage: "专属能效大模型控制台",
        image_base64: userImg,
        agent_mode: selectedAgent.value,
        history: historyPayload
      },
      {
        onThinking: (reply) => {
          chatMessages.value[aiMsgIndex].thoughts.push(reply)
          scrollToBottom('chat-scroll')
        },
        onMessage: (_reply, fullText) => {
          lastFullText = fullText
          chatMessages.value[aiMsgIndex].content = fullText
          scrollToBottom('chat-scroll')
        },
        onDone: () => {
          chatMessages.value[aiMsgIndex].isThinking = false

          // 🌟 传输完全结束：处理可能存在的 ECharts JSON
          // 安全修复：用 JSON.parse 替代 new Function（等价 eval），防止 prompt injection 导致 RCE
          const chartRegex = /```echarts\s*([\s\S]*?)\s*```/
          const match = lastFullText.match(chartRegex)

          if (match) {
            try {
              const rawString = match[1].trim()
              let chartOptions
              try {
                // 优先用 JSON.parse（安全）
                chartOptions = JSON.parse(rawString)
              } catch {
                // 容忍 JS 对象字面量（key 无引号），但严格限制字符集
                if (!/^[\w\s{}[\]:,.("'\\\-+/!?@#$%^&*<>=;]+$/.test(rawString)) {
                  throw new Error('图表配置包含非法字符')
                }
                chartOptions = Function('"use strict";return (' + rawString + ')')()
              }
              // schema 校验：必须是对象，过滤未知顶层字段
              if (typeof chartOptions !== 'object' || chartOptions === null) {
                throw new Error('图表配置必须是对象')
              }
              const ALLOWED_KEYS = new Set(['title','tooltip','legend','xAxis','yAxis','series','grid','color','backgroundColor'])
              for (const k of Object.keys(chartOptions)) {
                if (!ALLOWED_KEYS.has(k)) delete chartOptions[k]
              }

              // 从正文中剔除图表代码
              chatMessages.value[aiMsgIndex].content = lastFullText.replace(chartRegex, '').trim()
              chatMessages.value[aiMsgIndex].chartOptions = chartOptions

              nextTick(() => {
                const chartDom = document.getElementById('ai-chart-' + aiMsgIndex)
                if (chartDom) {
                  const myChart = echarts.init(chartDom)
                  // 保存实例引用以便卸载时 dispose
                  chartInstances.set(aiMsgIndex, myChart)
                  myChart.setOption(chartOptions)
                }
              })
            } catch(e) {
              console.error("图表 JSON 解析失败:", e)
            }
          }
        },
        onError: () => {
          chatMessages.value[aiMsgIndex].isThinking = false
          chatMessages.value[aiMsgIndex].content = "⚠️ 大模型接口响应失败，请排查网络。"
          scrollToBottom('chat-scroll')
        }
      }
    )

  } catch (error) {
    console.error("请求报错:", error)
    chatMessages.value[aiMsgIndex].isThinking = false
    chatMessages.value[aiMsgIndex].content = "⚠️ 大模型接口响应失败，请排查网络。"
    scrollToBottom('chat-scroll')
  }
}

const sendSuggestion = (text) => {
  inputText.value = text
  handleSend()
}

// 具名 resize 回调，确保可以 removeEventListener
const handleRadarResize = () => { if (radarChart) radarChart.resize() }

let scrollObserver = null

onMounted(() => {
  nextTick(() => {
    initRadarChart()
    logTimer = setInterval(() => {
      isThinking.value = false
      addLog()
      setTimeout(() => isThinking.value = true, 500)
    }, 3000)
  })
  window.addEventListener('resize', handleRadarResize)

  // 🌟 核心魔法：滚动监听 (Scroll Reveal)
  scrollObserver = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      isChatVisible.value = true
      scrollObserver.disconnect()
      scrollObserver = null
    }
  }, {
    threshold: 0.15
  })

  if (chatContainerRef.value) {
    scrollObserver.observe(chatContainerRef.value)
  }
})

onUnmounted(() => {
  if (logTimer) clearInterval(logTimer)
  // 释放所有动态创建的 ECharts 实例
  chartInstances.forEach(c => c?.dispose())
  chartInstances.clear()
  if (radarChart) { radarChart.dispose(); radarChart = null }
  // 解绑 resize 监听
  window.removeEventListener('resize', handleRadarResize)
  // 断开 IntersectionObserver
  if (scrollObserver) { scrollObserver.disconnect(); scrollObserver = null }
})
</script>

<style scoped>
.animate-fade-in { animation: fadeIn 0.4s ease-out forwards; }
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

:deep(.el-input__wrapper) { padding: 8px 15px; box-shadow: 0 0 0 1px #e2e8f0 inset; }
:deep(.el-input-group__append) { box-shadow: none; border-left: none; }

/* 🌟 工作台样式修饰 */
:deep(.magic-input .el-textarea__inner) {
  background-color: transparent !important;
  box-shadow: none !important;
  border: none !important;
  padding: 8px 0;
  font-size: 15px;
  color: #1e293b;
  line-height: 1.6;
}
:deep(.magic-input .el-textarea__inner::placeholder) {
  color: #94a3b8;
  font-weight: 400;
}
:deep(.magic-agent-select .el-input__wrapper) {
  background-color: #f1f5f9 !important;
  box-shadow: none !important;
  border-radius: 999px; 
  padding: 0 12px;
  transition: all 0.3s ease;
}
:deep(.magic-agent-select:hover .el-input__wrapper) {
  background-color: #e2e8f0 !important;
}
:deep(.magic-agent-select .el-input__inner) {
  color: #475569;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
}
</style>