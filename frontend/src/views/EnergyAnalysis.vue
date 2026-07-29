<template>
  <div class="flex flex-col gap-6 pb-8 bg-slate-50/50 min-h-screen">
    
    <div class="bg-white p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-300 border border-slate-200/60 group">
      <div class="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
        <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2.5">
          <div class="p-1.5 bg-indigo-50 rounded-lg text-indigo-500">
            <el-icon><TrendCharts /></el-icon>
          </div>
          未来能耗 AI 预测 <span class="text-sm font-normal text-slate-400 ml-2">Prophet & 多模态气象融合</span>
        </h3>
        
        <div class="flex items-center gap-4">
          <el-radio-group v-model="predictHours" size="small" @change="renderForecastChart" class="shadow-sm">
            <el-radio-button :label="12">12 小时</el-radio-button>
            <el-radio-button :label="24">24 小时</el-radio-button>
            <el-radio-button :label="48">48 小时</el-radio-button>
          </el-radio-group>
          <el-tag type="warning" effect="light" class="border-orange-200 bg-orange-50 text-orange-600 rounded-lg hidden sm:flex">置信区间 80%</el-tag>
        </div>
      </div>
      <div ref="forecastChartRef" class="w-full h-[360px]"></div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      <div class="bg-white p-6 rounded-2xl shadow-sm hover:shadow-md transition-shadow duration-300 border border-slate-200/60 flex flex-col">
        <div class="flex items-center justify-between border-b border-slate-100 pb-4 mb-4">
          <h3 class="font-bold text-slate-800 text-lg flex items-center gap-2.5">
            <div class="w-1.5 h-5 bg-gradient-to-b from-blue-400 to-blue-600 rounded-full"></div>
            全天候系统能效比 (COP)
            <el-button link class="text-slate-400 hover:text-blue-500 transition-colors pt-1" @click="copModalVisible = true">
              <el-icon class="text-lg"><InfoFilled /></el-icon>
            </el-button>
          </h3>
          <el-tag type="info" size="small" effect="plain" round class="bg-slate-50">近24小时基准</el-tag>
        </div>
        <div ref="copChartRef" class="w-full flex-1 min-h-[280px]"></div>
      </div>

      <div class="bg-slate-900 p-6 rounded-2xl shadow-xl hover:shadow-2xl transition-all duration-300 border border-slate-700 text-white relative overflow-hidden flex flex-col justify-center">
        <div class="absolute -top-16 -right-16 w-48 h-48 bg-indigo-500/20 rounded-full blur-[50px] pointer-events-none"></div>
        <div class="absolute -bottom-10 -left-10 w-32 h-32 bg-emerald-500/10 rounded-full blur-[40px] pointer-events-none"></div>
        <div class="absolute bottom-0 left-0 w-full h-1 bg-gradient-to-r from-transparent via-indigo-500/80 to-transparent opacity-50"></div>
        
        <div class="flex justify-between items-center mb-6 relative z-10">
          <h3 class="font-bold text-lg flex items-center gap-2">
            <el-icon class="text-indigo-400 text-xl"><Cpu /></el-icon> AI 预测性维护 (RUL)
          </h3>
          <span class="px-2.5 py-1 bg-indigo-500/10 text-indigo-300 text-xs rounded-md border border-indigo-500/20 backdrop-blur-sm">
            Model: Health-Score V2
          </span>
        </div>

        <div v-if="rulLoading" class="flex-1 flex items-center justify-center relative z-10 min-h-[200px]">
          <el-icon class="is-loading text-4xl text-indigo-400"><Loading /></el-icon>
        </div>

        <div v-else class="grid grid-cols-5 gap-6 relative z-10 flex-1 items-center">
          <div class="col-span-2 flex flex-col items-center justify-center bg-slate-800/50 backdrop-blur-md rounded-2xl p-5 border border-slate-700/50 relative group">
            <div class="absolute inset-0 border-2 border-emerald-500/10 rounded-2xl group-hover:border-emerald-500/30 transition-colors duration-500"></div>
            <div class="text-slate-400 text-xs mb-3 uppercase tracking-wider">综合健康度</div>
            <div :class="['text-5xl font-black font-mono tracking-tighter drop-shadow-md', getHealthColor(rulData.health_score)]">
              {{ rulData.health_score }}<span class="text-lg opacity-50 ml-1 font-sans">分</span>
            </div>
            <div :class="['mt-4 text-xs px-3 py-1.5 rounded-full font-medium tracking-wide', getHealthBg(rulData.health_score)]">
              {{ rulData.status }}
            </div>
          </div>

          <div class="col-span-3 flex flex-col gap-3.5 justify-center">
            <div class="flex justify-between items-center text-sm p-2 rounded-lg hover:bg-slate-800/50 transition-colors">
              <span class="text-slate-400 flex items-center gap-2"><div class="w-1.5 h-1.5 rounded-full bg-slate-500"></div>目标设备</span>
              <span class="font-medium text-slate-100">{{ rulData.equipment_name }}</span>
            </div>
            <div class="flex justify-between items-center text-sm p-2 rounded-lg hover:bg-slate-800/50 transition-colors">
              <span class="text-slate-400 flex items-center gap-2"><div class="w-1.5 h-1.5 rounded-full bg-yellow-500/50"></div>当前振动</span>
              <span class="font-mono text-yellow-400">{{ rulData.vibration_mm_s }} <span class="text-xs text-yellow-500/70">mm/s</span></span>
            </div>
            <div class="flex justify-between items-center text-sm p-2 rounded-lg hover:bg-slate-800/50 transition-colors">
              <span class="text-slate-400 flex items-center gap-2"><div class="w-1.5 h-1.5 rounded-full bg-indigo-400/50"></div>预测衰减</span>
              <span class="font-mono text-indigo-300">{{ rulData.predicted_failure }}</span>
            </div>
            
            <div class="w-full h-px bg-gradient-to-r from-slate-700/0 via-slate-700 to-slate-700/0 my-1"></div>
            
            <div class="text-xs text-slate-300 leading-relaxed bg-slate-800/30 p-3 rounded-lg border border-slate-700/50">
              <strong class="text-indigo-300 mb-1 block">💡 AI 维保建议：</strong>
              {{ rulData.maintenance_action }}
            </div>
          </div>
        </div>
      </div>

    </div>

    <div class="p-6 rounded-2xl shadow-lg border border-slate-800 relative overflow-hidden group" style="background-image: radial-gradient(ellipse at top center, #1e293b 0%, #020617 100%);">
      <div class="flex items-center justify-between mb-4 relative z-10">
        <h3 class="font-bold text-emerald-400 text-lg flex items-center gap-2 tracking-wide drop-shadow-[0_0_8px_rgba(52,211,153,0.3)]">
          <el-icon class="animate-pulse"><DataLine /></el-icon> 核心机组实时负载心电图
        </h3>
        <div class="flex items-center gap-2 bg-slate-900/50 px-3 py-1.5 rounded-full border border-slate-700/50">
          <span class="relative flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span class="text-xs text-emerald-500 font-mono tracking-wider">LIVE / 500ms</span>
        </div>
      </div>
      <div ref="ecgChartRef" class="w-full h-72 relative z-10 transition-opacity duration-300 group-hover:opacity-100 opacity-90"></div>
    </div>
    
    <el-dialog v-model="weatherModalVisible" title="🌤️ 气象多模态参数" width="420px" class="!rounded-2xl" align-center>
      <div class="flex flex-col gap-5 pt-2">
        <div class="flex justify-between items-center bg-slate-50 p-4 rounded-xl border border-slate-100 shadow-inner">
          <div class="flex flex-col">
            <span class="text-slate-400 text-xs mb-1 uppercase tracking-wider">气象采集节点 (智能定位)</span>
            <span class="font-bold text-slate-700">{{ locationName }}</span>
          </div>
          <div class="p-2 bg-blue-100/50 rounded-full">
            <el-icon class="text-2xl text-blue-500"><Location /></el-icon>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4">
          <div class="bg-gradient-to-br from-orange-50 to-orange-100/50 p-5 rounded-xl border border-orange-100 flex flex-col items-center justify-center relative overflow-hidden">
            <div class="absolute -right-4 -bottom-4 text-5xl opacity-10">🌡️</div>
            <span class="text-orange-500/80 text-xs mb-1 font-medium">切片时刻气温</span>
            <span class="text-3xl font-black text-orange-600">{{ weatherData.temp }} <span class="text-base font-medium">°C</span></span>
          </div>
          <div class="bg-gradient-to-br from-indigo-50 to-indigo-100/50 p-5 rounded-xl border border-indigo-100 flex flex-col items-center justify-center text-center relative overflow-hidden">
            <div class="absolute -right-4 -bottom-4 text-5xl opacity-10">⏱️</div>
            <span class="text-indigo-400/80 text-xs mb-1 font-medium">时间序列节点</span>
            <span class="text-base font-bold text-indigo-600 mt-1 font-mono">{{ weatherData.time }}</span>
          </div>
        </div>
        
        <div class="bg-slate-50 p-3 rounded-lg border border-slate-100 flex items-start gap-2">
          <el-icon class="text-slate-400 mt-0.5"><InfoFilled /></el-icon> 
          <p class="text-xs text-slate-500 leading-relaxed">
            该温度数据已作为外生变量 (Regressor) 同步输入至后端 Prophet 预测大模型参与计算。
          </p>
        </div>
      </div>
    </el-dialog>

  </div>
  <el-dialog v-model="copModalVisible" title="📊 核心指标：系统能效比 (COP)" width="480px" class="!rounded-2xl" align-center>
      <div class="flex flex-col gap-4 pt-2">
        <div class="bg-blue-50/50 p-4 rounded-xl border border-blue-100 flex items-start gap-3">
          <el-icon class="text-blue-500 text-xl mt-0.5"><Opportunity /></el-icon>
          <div>
            <h4 class="font-bold text-blue-700 mb-1">什么是 COP？(Coefficient of Performance)</h4>
            <p class="text-sm text-blue-600/80 leading-relaxed">
              它是衡量空调冷水机组**“花多少电，干多少活”**的核心指标。数值越高，表示系统越节能、转换效率越高。
            </p>
          </div>
        </div>
        
        <div class="flex flex-col items-center justify-center p-5 bg-slate-50 rounded-xl border border-slate-200 shadow-inner">
          <span class="text-slate-400 text-xs mb-2 tracking-widest uppercase">底层计算逻辑</span>
          <div class="text-lg font-mono font-bold text-slate-700 bg-white px-5 py-2.5 rounded-lg shadow-sm border border-slate-200">
             COP = 系统总制冷量 (kW) / 主机耗电功率 (kW)
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="p-3 bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col relative overflow-hidden group">
            <div class="absolute -right-2 -bottom-2 text-4xl opacity-5 group-hover:opacity-10 transition-opacity">❄️</div>
            <span class="text-xs text-slate-400 mb-1">分子：制冷量采集</span>
            <span class="text-sm font-semibold text-slate-700">供回水温差 × 管道流量</span>
            <span class="text-[11px] text-emerald-500 mt-1.5 flex items-center gap-1"><div class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></div>边缘网关 PLC 轮询</span>
          </div>
          <div class="p-3 bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col relative overflow-hidden group">
            <div class="absolute -right-2 -bottom-2 text-4xl opacity-5 group-hover:opacity-10 transition-opacity">⚡</div>
            <span class="text-xs text-slate-400 mb-1">分母：耗电量采集</span>
            <span class="text-sm font-semibold text-slate-700">主机电源智能电表参数</span>
            <span class="text-[11px] text-blue-500 mt-1.5 flex items-center gap-1"><div class="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse"></div>Modbus RTU 透传</span>
          </div>
        </div>
        
        <div class="mt-1">
           <p class="text-xs text-slate-400 mb-2 font-medium">💡 行业基准健康度参考：</p>
           <div class="flex items-center gap-2 text-xs font-medium">
             <span class="w-1/3 text-center py-2 rounded-lg bg-red-50 text-red-500 border border-red-100">COP < 3.5<br/><span class="text-[10px] font-normal">性能衰减 建议维保</span></span>
             <span class="w-1/3 text-center py-2 rounded-lg bg-yellow-50 text-yellow-600 border border-yellow-100">3.5 - 4.5<br/><span class="text-[10px] font-normal">运行平稳 标准状态</span></span>
             <span class="w-1/3 text-center py-2 rounded-lg bg-emerald-50 text-emerald-600 border border-emerald-100">COP > 4.5<br/><span class="text-[10px] font-normal">高效运行 节能区</span></span>
           </div>
        </div>
      </div>
    </el-dialog>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onActivated, onDeactivated, nextTick, shallowRef } from 'vue'
import * as echarts from 'echarts'
import { DataLine, TrendCharts, Cpu, Loading, Location, InfoFilled, Opportunity } from '@element-plus/icons-vue'
import axios from 'axios'
import { fetchCopTrend, fetchEnergyForecast, fetchPredictiveMaintenance } from '../api/index.js'

// ================= 1. DOM 与数据引用 =================
const copChartRef = ref(null)
const ecgChartRef = ref(null)
const forecastChartRef = ref(null)

const copChart = shallowRef(null)
const ecgChart = shallowRef(null)
const forecastChart = shallowRef(null)
let ws = null

// 🌟 新增：绑定时间切换器的变量，默认 24 小时
const predictHours = ref(24)

const data = []
for (let i = 0; i < 50; i++) {
  const time = new Date().getTime() - (50 - i) * 1000
  data.push({ name: time.toString(), value: [time, 0] })
}

const rulLoading = ref(true)
const rulData = ref({})

const weatherModalVisible = ref(false)
const weatherData = ref({ time: '', temp: '' })
// 🌟 新增：动态定位存储变量，初始显示定位中
const locationName = ref('定位中...')
// 🌟 新增：控制 COP 弹窗
const copModalVisible = ref(false)
// ================= 2. 获取设备 RUL 数据 =================
const fetchRulData = async () => {
  rulLoading.value = true
  try {
    const res = await fetchPredictiveMaintenance()
    if (res.status === 'success') {
      rulData.value = res.data
    }
  } catch (error) {
    console.error("获取 RUL 数据失败", error)
    rulData.value = {
      equipment_name: "1# 离心冷水机组",
      vibration_mm_s: 4.2,
      health_score: 82.4,
      status: "健康运行",
      predicted_failure: "约 64 天",
      maintenance_action: "当前轴承温度略高，建议两周内安排例行润滑。"
    }
  } finally {
    rulLoading.value = false
  }
}

const getHealthColor = (score) => {
  if (score > 80) return 'text-emerald-400'
  if (score > 50) return 'text-yellow-400'
  return 'text-red-500'
}
const getHealthBg = (score) => {
  if (score > 80) return 'bg-emerald-400/20 text-emerald-300 border border-emerald-400/20'
  if (score > 50) return 'bg-yellow-400/20 text-yellow-300 border border-yellow-400/20'
  return 'bg-red-500/20 text-red-300 border border-red-500/20'
}

// ================= 3. 图表渲染逻辑 =================
const loadCopData = async () => {
  try {
    const result = await fetchCopTrend()
    renderCopChart(result.times, result.values)
  } catch (error) {
    const mockTimes = Array.from({ length: 24 }, (_, i) => {
      const d = new Date()
      d.setHours(d.getHours() - (23 - i))
      return `${d.getHours()}:00`
    })
    const mockValues = Array.from({ length: 24 }, () => (Math.random() * 2 + 3.5).toFixed(2))
    renderCopChart(mockTimes, mockValues)
  }
}

const renderCopChart = (xData, yData) => {
  if (!copChartRef.value) return
  if (!copChart.value) copChart.value = echarts.init(copChartRef.value)

  copChart.value.setOption({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e2e8f0', textStyle: { color: '#1e293b' }, extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);' },
    grid: { left: '2%', right: '4%', bottom: '2%', top: '10%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: xData, axisLine: { lineStyle: { color: '#cbd5e1' } }, axisLabel: { color: '#64748b' } },
    yAxis: { type: 'value', min: 2, max: 6, splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }, axisLabel: { color: '#64748b' } },
    series: [{
      name: '系统综合 COP', type: 'line', smooth: true, data: yData, symbolSize: 0, showSymbol: false,
      itemStyle: { color: '#3b82f6' },
      lineStyle: { width: 3, shadowColor: 'rgba(59,130,246,0.2)', shadowBlur: 8, shadowOffsetY: 4 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59,130,246,0.3)' },
          { offset: 1, color: 'rgba(59,130,246,0.01)' }
        ])
      }
    }]
  })
}

const initEcgChart = () => {
  const ecgDom = document.getElementById('ecg-chart') || ecgChartRef.value
  if (ecgDom) {
    ecgChart.value = echarts.init(ecgDom)
    ecgChart.value.setOption({
      grid: { left: '3%', right: '3%', bottom: '10%', top: '10%', containLabel: true },
      xAxis: { type: 'time', splitLine: { show: false }, axisLabel: { color: '#475569' } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#1e293b', type: 'dashed' } }, axisLabel: { color: '#475569' } },
      series: [{ type: 'line', showSymbol: false, data: data, itemStyle: { color: '#10b981' }, lineStyle: { color: '#10b981', width: 2, shadowColor: 'rgba(16, 185, 129, 0.5)', shadowBlur: 10 } }]
    })
  }
}

const renderForecastChart = async () => {
  // 🌟 修复：将 forecastChart 实例保存到 ref，避免内存泄漏（onUnmounted 时可正确 dispose）
  if (!forecastChart.value) {
    forecastChart.value = echarts.init(forecastChartRef.value)
  }
  const chart = forecastChart.value
  chart.clear()
  chart.showLoading({ color: '#8b5cf6', maskColor: 'rgba(255, 255, 255, 0.8)' })

  try {
    // 🌟 原有请求代码
    const res = await fetchEnergyForecast(predictHours.value)
    
    // 🌟 新增：解析后端返回的动态定位信息
    if (res.meta && res.meta.location) {
      locationName.value = res.meta.location
    } else {
      locationName.value = '福建省福州市闽侯县'
    }

    // 🌟 原有的错误拦截
    if (res.status === 'error' || !res.data) {
      console.error("❌ 后端算法接口报错:", res.message)
      locationName.value = '定位失败' // 发生错误时的兜底显示
      chart.hideLoading()
      return 
    }

    const { history, forecast } = res.data
    // 🌟 边界保护：history 或 forecast 为空/非数组时给出兜底，避免后续 toFixed 崩溃
    const safeHistory = Array.isArray(history) ? history : []
    const safeForecast = Array.isArray(forecast) ? forecast : []

    if (safeHistory.length === 0 && safeForecast.length === 0) {
      console.warn("⚠️ 后端返回空数据：history 和 forecast 均为空")
      chart.hideLoading()
      return
    }

    const xAxisData = [], historyValues = [], forecastValues = [], lowerBounds = [], upperBounds = [], tempValues = []

    // 🌟 安全访问数值：null/undefined/NaN 统一返回 '-'，避免 toFixed 崩溃
    const safeNum = (v, digits = 2) => {
      const n = Number(v)
      return (v === null || v === undefined || Number.isNaN(n)) ? '-' : n.toFixed(digits)
    }

    // 取与预测等长的近期历史（若历史不足则全部取用）
    const recentHistory = safeForecast.length > 0
      ? safeHistory.slice(-safeForecast.length)
      : safeHistory

    recentHistory.forEach(item => {
      xAxisData.push(item.ds ? item.ds.substring(5, 16) : '-')
      historyValues.push(safeNum(item.y, 2))
      forecastValues.push('-')
      lowerBounds.push('-')
      upperBounds.push('-')
      tempValues.push(safeNum(item.temperature, 1))
    })

    // 🌟 仅当存在历史末点时，将其作为预测起点衔接，避免 lastHistory 未定义
    if (recentHistory.length > 0) {
      const lastHistory = recentHistory[recentHistory.length - 1]
      forecastValues[forecastValues.length - 1] = safeNum(lastHistory.y, 2)
    }

    safeForecast.forEach(item => {
      xAxisData.push(item.ds ? item.ds.substring(5, 16) : '-')
      historyValues.push('-')
      forecastValues.push(safeNum(item.yhat, 2))
      lowerBounds.push(safeNum(item.yhat_lower, 2))
      // 置信带宽度 = upper - lower；若任一缺失则置 '-'
      const lo = Number(item.yhat_lower), hi = Number(item.yhat_upper)
      upperBounds.push((Number.isNaN(lo) || Number.isNaN(hi)) ? '-' : (hi - lo).toFixed(2))
      tempValues.push(safeNum(item.temperature, 1))
    })

    const option = {
      tooltip: { 
        trigger: 'axis', 
        axisPointer: { type: 'cross', crossStyle: { color: '#94a3b8' } },
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        borderColor: '#e2e8f0',
        textStyle: { color: '#1e293b' },
        extraCssText: 'box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border-radius: 8px;'
      },
      legend: { data: ['历史真实能耗', 'AI 预测能耗', '室外气象温度'], top: 0, icon: 'circle' },
      grid: { left: '3%', right: '3%', bottom: '12%', top: '15%', containLabel: true }, 
      xAxis: { 
        type: 'category', 
        boundaryGap: false, 
        data: xAxisData,
        axisLabel: {
          rotate: 40,
          interval: predictHours.value === 48 ? 5 : 3, // 🌟 优化：如果选择48小时，间隔加大一点防止拥挤
          hideOverlap: true,
          color: '#64748b',
          fontSize: 11
        },
        axisLine: { lineStyle: { color: '#cbd5e1' } }
      },
      yAxis: [
        { 
          type: 'value', 
          name: '能耗 (kWh)', 
          position: 'left',
          nameTextStyle: { color: '#8b5cf6', padding: [0, 0, 0, -20] },
          axisLine: { show: true, lineStyle: { color: '#e2e8f0' } }, 
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } },
          axisLabel: { color: '#64748b' }
        },
        { 
          type: 'value', 
          name: '气温 (°C)', 
          position: 'right',
          nameTextStyle: { color: '#f59e0b', padding: [0, -20, 0, 0] },
          axisLine: { show: true, lineStyle: { color: '#e2e8f0' } }, 
          splitLine: { show: false },
          axisLabel: { color: '#64748b' }
        }
      ],
      series: [
        { 
          name: '历史真实能耗', type: 'line', smooth: true, symbol: 'none', 
          itemStyle: { color: '#3b82f6' }, 
          lineStyle: { width: 3 },
          data: historyValues,
          tooltip: { valueFormatter: value => value === '-' ? '-' : value + ' kWh' }
        },
        {
          name: 'AI 预测能耗', type: 'line', smooth: true, symbol: 'none',
          lineStyle: { type: 'dashed', color: '#8b5cf6', width: 3 },
          itemStyle: { color: '#8b5cf6' }, data: forecastValues,
          tooltip: { valueFormatter: value => value === '-' ? '-' : value + ' kWh' },
          markPoint: {
            symbol: 'pin', symbolSize: 45,
            data: [
              { type: 'max', name: '明日预测峰值', itemStyle: { color: '#ef4444' } },
              { type: 'min', name: '深夜谷值', itemStyle: { color: '#10b981' } } 
            ]
          },
          markLine: {
            silent: true, symbol: 'none',
            data: [{ yAxis: 260, label: { formatter: '🚨 削峰填谷红线', position: 'insideEndTop', color: '#ef4444' }, lineStyle: { color: '#ef4444', type: 'dashed', width: 2 } }]
          }
        },
        { name: 'LOWER', type: 'line', stack: 'confidence-band', symbol: 'none', lineStyle: { opacity: 0 }, data: lowerBounds },
        {
          name: 'UPPER', type: 'line', stack: 'confidence-band', symbol: 'none', lineStyle: { opacity: 0 },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [{ offset: 0, color: 'rgba(139, 92, 246, 0.3)' }, { offset: 1, color: 'rgba(139, 92, 246, 0.05)' }]) },
          data: upperBounds
        },
        { 
          name: '室外气象温度', 
          type: 'line', 
          yAxisIndex: 1, 
          smooth: true, 
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { type: 'dotted', color: '#f59e0b', width: 2 }, 
          itemStyle: { color: '#f59e0b', borderWidth: 2, borderColor: '#fff' },
          data: tempValues,
          tooltip: { valueFormatter: value => value + ' °C' }
        }
      ]
    }
    
    chart.hideLoading()
    chart.setOption(option)

    chart.off('click')
    chart.on('click', (params) => {
      if (params.seriesName === '室外气象温度') {
        weatherData.value = {
          time: params.name,
          temp: params.value
        }
        weatherModalVisible.value = true
      }
    })

  } catch (error) {
    console.error("请求发生网络错误:", error)
    chart.hideLoading()
  } 
}

const handleResize = () => {
  if (copChart.value) copChart.value.resize()
  if (ecgChart.value) ecgChart.value.resize()
  if (forecastChart.value) forecastChart.value.resize()
}

// ================= 4. WebSocket 生命周期 =================
const connectWebSocket = () => {
  if (ws && ws.readyState === WebSocket.OPEN) return 
  ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/realtime_energy?token=${encodeURIComponent(localStorage.getItem('token') || '')}`)
  ws.onopen = () => console.log('🔗 WebSocket 实时大动脉已连接！')
  ws.onmessage = (event) => {
    try {
      const realData = JSON.parse(event.data)
      const nextTime = new Date().getTime()
      data.shift()
      data.push({ name: nextTime, value: [nextTime, realData.total_power] })
      if (ecgChart.value) ecgChart.value.setOption({ series: [{ data: data }] })
    } catch (e) { console.error('解析失败', e) }
  }
}
const closeWebSocket = () => { if (ws) { ws.onclose = null; ws.close(); ws = null } }

// ================= 5. Vue 生命周期 =================
onMounted(() => {
  renderForecastChart()
  loadCopData()
  fetchRulData() 
  initEcgChart()
  window.addEventListener('resize', handleResize)
})
onActivated(() => { connectWebSocket(); nextTick(() => handleResize()) })
onDeactivated(() => closeWebSocket())
onUnmounted(() => {
  closeWebSocket()
  window.removeEventListener('resize', handleResize)
  if (copChart.value) copChart.value.dispose()
  if (ecgChart.value) ecgChart.value.dispose()
  if (forecastChart.value) forecastChart.value.dispose()
})
</script>