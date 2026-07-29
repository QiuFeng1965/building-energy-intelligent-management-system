<template>
  <div class="flex flex-col gap-6">
    
    <div class="flex items-center justify-between bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
      <div class="flex items-center gap-2">
        <div class="w-2 h-6 bg-indigo-600 rounded-full"></div>
        <h2 class="text-xl font-bold text-slate-800 tracking-tight">能效全景监控中心</h2>
        <!-- WebSocket 实时连接状态指示灯 -->
        <span class="flex items-center gap-1 ml-2 px-2 py-0.5 rounded-full text-xs font-medium"
              :class="wsConnected ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'">
          <span class="w-1.5 h-1.5 rounded-full"
                :class="wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'"></span>
          {{ wsConnected ? '实时' : '离线' }}
        </span>
      </div>
      <div class="flex items-center gap-2 bg-indigo-50 px-4 py-2 rounded-xl border border-indigo-100">
        <span class="text-indigo-500 font-bold text-sm">🕒 系统时间:</span>
        <span class="text-indigo-600 font-mono font-bold tracking-wider">{{ currentTime }}</span>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div v-for="(item, index) in kpiList" :key="index" class="bg-white p-6 rounded-2xl shadow-sm border border-slate-100 relative overflow-hidden group hover:shadow-md transition-all">
        <div class="absolute -right-6 -top-6 opacity-5 group-hover:scale-110 transition-transform duration-500">
          <el-icon class="text-9xl"><component :is="item.icon" /></el-icon>
        </div>
        <div class="flex items-center justify-between mb-4 relative z-10">
          <div :class="`p-3 rounded-xl bg-${item.color}-50 text-${item.color}-600`">
            <el-icon class="text-2xl"><component :is="item.icon" /></el-icon>
          </div>
          <span :class="`text-xs font-medium px-2.5 py-1 rounded-full bg-${item.color}-50 text-${item.color}-600 border border-${item.color}-100`">
            {{ item.trend }}
          </span>
        </div>
        <div class="text-3xl font-black text-slate-800 mb-1 tracking-tight relative z-10">
          {{ item.value }}<span class="text-sm ml-1 font-medium text-slate-400">{{ item.unit }}</span>
        </div>
        <div class="text-sm font-medium text-slate-500 relative z-10">{{ item.label }}</div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
            <div class="w-1.5 h-4 bg-indigo-500 rounded-full"></div>24小时能耗负荷曲线
          </h3>
          <el-tag size="small" type="success" effect="plain" round class="animate-pulse">实时同步中</el-tag>
        </div>
        <div id="chart-line" class="h-72 w-full"></div>
      </div>

      <div class="lg:col-span-1 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
        <div class="flex items-center mb-4">
          <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
            <div class="w-1.5 h-4 bg-emerald-500 rounded-full"></div>各系统能耗占比
          </h3>
        </div>
        <div id="chart-pie" class="h-72 w-full"></div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow">
        <div class="flex items-center mb-4">
          <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
            <div class="w-1.5 h-4 bg-amber-500 rounded-full"></div>近7日能耗趋势对比
          </h3>
        </div>
        <div id="chart-bar" class="h-72 w-full"></div>
      </div>

      <div class="lg:col-span-1 bg-white p-6 rounded-2xl shadow-sm border border-slate-100 hover:shadow-md transition-shadow flex flex-col">
        <div class="flex items-center justify-between mb-4">
          <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2">
            <div class="w-1.5 h-4 bg-rose-500 rounded-full"></div>底层设备健康状态
          </h3>
          <span class="text-xs text-slate-400">实时巡检</span>
        </div>
        <div id="chart-health" class="flex-1 w-full min-h-[288px]"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage, ElNotification } from 'element-plus'
import { onSnapshot, onAlarm, disconnect } from '../api/websocket.js'

const props = defineProps({
  data: {
    type: Object,
    required: true,
    default: () => ({ kpi: {}, pie: [], bar: { x: [], y: [] }, line: { x: [], y: [] } })
  }
})

// --- WebSocket 实时数据 ---
const wsConnected = ref(false)
const realtimeAlarms = ref(0) // WebSocket 推送的实时告警数
let unsubSnapshot = null
let unsubAlarm = null

// --- 🌟 实时时钟核心逻辑 ---
const currentTime = ref('')
let clockTimer = null

const updateClock = () => {
  const now = new Date()
  const y = now.getFullYear()
  const m = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  const ss = String(now.getSeconds()).padStart(2, '0')
  currentTime.value = `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

// --- 🌟 动态时间轴：让 X 轴随“现在”滚动 ---
// 获取最近 24 小时的时间点（从 23 小时前到此时此刻）
const getRealtimeHours = (count = 24) => {
  const hours = []
  const now = new Date()
  for (let i = count - 1; i >= 0; i--) {
    const target = new Date(now.getTime() - i * 60 * 60 * 1000)
    hours.push(`${String(target.getHours()).padStart(2, '0')}:00`)
  }
  return hours
}

// 获取最近 7 天的日期（含今天）
// 获取最近 7 天的日期（排除今天，从昨天开始算）
const getRealtimeDays = (count = 7) => {
  const days = []
  const now = new Date()
  // 🌟 修改：基准时间设为昨天
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000) 
  for (let i = count - 1; i >= 0; i--) {
    const target = new Date(yesterday.getTime() - i * 24 * 60 * 60 * 1000)
    days.push(`${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`)
  }
  return days
}

const kpiList = computed(() => {
  const kpiData = props.data?.kpi || {}
  // 异常告警数优先使用 WebSocket 实时推送值，无 WebSocket 数据时回退到接口值
  const alarmCount = realtimeAlarms.value > 0 ? realtimeAlarms.value : (kpiData.alarms || 0)
  return [
    { label: '今日总耗电', value: kpiData.total_elec || '0', unit: 'kWh', icon: 'Lightning', color: 'indigo', trend: '稳定' },
    { label: '折算碳排放', value: kpiData.carbon || '0', unit: 'kg', icon: 'Location', color: 'emerald', trend: '达标' },
    { label: '综合能效比', value: kpiData.cop || '0', unit: 'COP', icon: 'PieChart', color: 'amber', trend: '优' },
    { label: '异常告警数', value: alarmCount, unit: '个', icon: 'Warning', color: 'rose', trend: alarmCount > 0 ? '紧急' : '正常' }
  ]
})

let lineChart = null
let pieChart = null
let barChart = null
let healthChart = null

const handleResize = () => {
  const charts = [lineChart, pieChart, barChart, healthChart]
  charts.forEach(chart => chart?.resize())
}

const initAllCharts = () => {
  // --- 折线图：滑动 24 小时窗口 ---
  const lineDom = document.getElementById('chart-line')
  if (lineDom && props.data.line?.y) {
    lineChart = echarts.getInstanceByDom(lineDom) || echarts.init(lineDom)
    lineChart.setOption({
      tooltip: { trigger: 'axis', backgroundColor: 'rgba(255, 255, 255, 0.9)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { 
        type: 'category', 
        boundaryGap: false, 
        data: getRealtimeHours(props.data.line.y.length), // 🌟 实时计算小时轴
        axisLine: { lineStyle: { color: '#cbd5e1' } }, 
        axisLabel: { color: '#64748b' } 
      },
      yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
      series: [{ 
        name: '能耗值',
        data: props.data.line.y, 
        type: 'line', 
        smooth: true,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(99, 102, 241, 0.3)' },
            { offset: 1, color: 'rgba(99, 102, 241, 0.05)' }
          ])
        },
        itemStyle: { color: '#6366f1' },
        lineStyle: { width: 3 }
      }]
    })
  }

  // 2. 饼图
  const pieDom = document.getElementById('chart-pie')
  if (pieDom) {
    pieChart = echarts.getInstanceByDom(pieDom) || echarts.init(pieDom)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: '0%', icon: 'circle' },
      series: [{ 
        type: 'pie', 
        radius: ['35%', '55%'], 
        center: ['50%', '40%'],
        data: props.data.pie, 
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        color: ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'] 
      }]
    }, true)
  }

  // --- 柱状图：滑动 7 天窗口 ---
  const barDom = document.getElementById('chart-bar')
  if (barDom && props.data.bar?.y) {
    barChart = echarts.getInstanceByDom(barDom) || echarts.init(barDom)
    barChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { 
        type: 'category', 
        data: props.data.bar.x, // 🌟 实时计算日期轴
        axisLine: { lineStyle: { color: '#cbd5e1' } }, 
        axisLabel: { color: '#64748b' } 
      },
      yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
      series: [{ 
        data: props.data.bar.y, 
        type: 'bar', 
        barWidth: '40%',
        itemStyle: { 
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#10b981' },
            { offset: 1, color: '#34d399' }
          ]),
          borderRadius: [4, 4, 0, 0] 
        } 
      }]
    })
  }

  // --- 健康状态环形图 (保持 AI 联动) ---
  const healthDom = document.getElementById('chart-health')
  if (healthDom) {
    healthChart = echarts.getInstanceByDom(healthDom) || echarts.init(healthDom)
    const alarmsCount = parseInt(props.data.kpi.alarms) || 0
    const normalCount = 680 - alarmsCount

    healthChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: '0%', icon: 'circle' },
      series: [{
        name: '设备状态',
        type: 'pie',
        radius: ['55%', '80%'],
        center: ['50%', '45%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: {
          show: true,
          position: 'center',
          formatter: () => alarmsCount > 0 ? `{val|${alarmsCount}}\n{text|告警中}` : `{valOk|0}\n{text|全正常}`,
          rich: {
            val: { fontSize: 32, fontWeight: 'bold', color: '#ef4444' },
            valOk: { fontSize: 32, fontWeight: 'bold', color: '#10b981' },
            text: { fontSize: 14, color: '#64748b' }
          }
        },
        data: [
          { value: normalCount, name: '🟢 正常运行', itemStyle: { color: '#10b981' } },
          { value: alarmsCount, name: '🔴 异常告警', itemStyle: { color: '#ef4444' } }
        ]
      }]
    })

    healthChart.off('click')
    healthChart.on('click', (params) => {
      let promptText = params.name.includes('异常告警') 
        ? `分析今天设备异常设备故障原因`
        : `帮我分析下 ${params.value} 台正常设备的能耗趋势。`
      
      window.dispatchEvent(new CustomEvent('trigger-global-ai', { detail: promptText }))
      ElMessage({ message: '已呼叫 AIgent 进行分析...', type: 'success', plain: true })
    })
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  setTimeout(initAllCharts, 200)

  // 订阅 WebSocket 实时数据
  unsubSnapshot = onSnapshot((data) => {
    wsConnected.value = true
    // 更新实时告警数
    if (data.active_alarms !== undefined) {
      realtimeAlarms.value = data.active_alarms
    }
    // 实时更新折线图最后一个数据点（当前小时能耗）
    if (lineChart && data.total_power !== undefined) {
      const option = lineChart.getOption()
      if (option.series && option.series[0] && option.series[0].data) {
        const seriesData = option.series[0].data
        // 更新最后一个点为实时值
        seriesData[seriesData.length - 1] = data.total_power
        lineChart.setOption({ series: [{ data: seriesData }] })
      }
    }
  })

  // 订阅告警事件
  unsubAlarm = onAlarm((alarm) => {
    // 弹出告警通知
    ElNotification({
      title: '🚨 实时告警',
      message: `设备「${alarm.device_name}」状态异常：${alarm.run_status}`,
      type: 'warning',
      duration: 8000,
      position: 'top-right'
    })
    // 更新告警计数
    realtimeAlarms.value++
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (clockTimer) clearInterval(clockTimer)
  // 取消 WebSocket 订阅
  if (unsubSnapshot) unsubSnapshot()
  if (unsubAlarm) unsubAlarm()
  const charts = [lineChart, pieChart, barChart, healthChart]
  charts.forEach(chart => chart?.dispose())
})

// 监听数据变化，重新渲染图表（时间轴会随之更新）
watch(() => props.data, () => {
  nextTick(initAllCharts)
}, { deep: true })
</script>