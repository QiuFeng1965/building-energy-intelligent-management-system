<template>
  <div class="flex flex-col gap-4 h-full" id="pdf-report-container">

    <!-- ===== 筛选栏：分组布局，清晰整洁 ===== -->
    <div class="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
      <!-- 第一行：搜索 + 核心筛选 -->
      <div class="flex flex-wrap items-center gap-3 mb-3">
        <!-- 关键词搜索 -->
        <el-input
          v-model="filters.keyword"
          placeholder="搜索设备名称..."
          style="width: 220px"
          clearable
          @keyup.enter="fetchData"
          @clear="fetchData"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-divider direction="vertical" />

        <!-- 建筑筛选 -->
        <el-select v-model="filters.building" placeholder="全部场景" style="width: 140px" @change="fetchData">
          <el-option label="全部场景" value="ALL" />
          <el-option v-for="(val, key) in BUILDING_TYPES" :key="key" :label="val" :value="key" />
        </el-select>

        <!-- 设备类型筛选 -->
        <el-select v-model="filters.device_type" placeholder="全部设备" style="width: 150px" @change="fetchData">
          <el-option label="全部设备" value="ALL" />
          <el-option v-for="(val, key) in DEVICE_TYPES" :key="key" :label="val" :value="key" />
        </el-select>

        <!-- 状态筛选（紧凑下拉） -->
        <el-select v-model="filters.status" placeholder="全部状态" style="width: 130px" @change="fetchData">
          <el-option label="全部状态" value="ALL" />
          <el-option label="🟢 正常" value="NORMAL" />
          <el-option label="⚠️ 警告" value="WARNING" />
          <el-option label="🟡 异常" value="ABNORMAL" />
          <el-option label="🔴 严重" value="CRITICAL" />
        </el-select>

        <!-- 日期范围 -->
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="fetchData"
          clearable
        />

        <!-- 数据量 -->
        <el-select v-model="filters.size" style="width: 110px" @change="fetchData">
          <el-option label="50 条" :value="50" />
          <el-option label="100 条" :value="100" />
          <el-option label="500 条" :value="500" />
          <el-option label="1000 条" :value="1000" />
          <el-option label="全部" value="ALL" />
        </el-select>

        <!-- 操作按钮组 -->
        <div class="ml-auto flex items-center gap-2">
          <el-button @click="resetFilters" plain size="default">
            <el-icon class="mr-1"><RefreshLeft /></el-icon> 重置
          </el-button>
          <el-button type="success" plain @click="handleExport" :disabled="tableData.length === 0">
            <el-icon class="mr-1"><Download /></el-icon> 导出 CSV
          </el-button>
          <el-button type="success" color="#4f46e5" class="!rounded-xl shadow-md font-bold" @click="generateAIReport" :loading="isExporting">
            <el-icon class="mr-1"><Document /></el-icon> AI 聚合分析
          </el-button>
        </div>
      </div>

      <!-- 第二行：统计摘要 + 结果计数 -->
      <div class="flex flex-wrap items-center gap-4 pt-3 border-t border-slate-50">
        <span class="text-sm text-slate-500">
          共 <span class="font-bold text-slate-700">{{ totalCount }}</span> 条记录
        </span>
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1 text-sm">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span class="text-slate-600">正常</span>
            <span class="font-bold text-emerald-600">{{ summary.normal }}</span>
          </span>
          <span class="flex items-center gap-1 text-sm">
            <span class="w-2 h-2 rounded-full bg-amber-500"></span>
            <span class="text-slate-600">警告</span>
            <span class="font-bold text-amber-600">{{ summary.warning }}</span>
          </span>
          <span class="flex items-center gap-1 text-sm">
            <span class="w-2 h-2 rounded-full bg-yellow-500"></span>
            <span class="text-slate-600">异常</span>
            <span class="font-bold text-yellow-600">{{ summary.abnormal }}</span>
          </span>
          <span class="flex items-center gap-1 text-sm">
            <span class="w-2 h-2 rounded-full bg-rose-500"></span>
            <span class="text-slate-600">严重</span>
            <span class="font-bold text-rose-600">{{ summary.critical }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- ===== 数据表格 ===== -->
    <div class="bg-white rounded-2xl shadow-sm border border-slate-100 p-4 flex-1 overflow-hidden flex flex-col">
      <el-table
        :data="pagedData"
        stripe
        v-loading="loading"
        height="100%"
        size="default"
        header-cell-class-name="bg-slate-50 border-b-2 border-slate-200"
        :default-sort="{ prop: 'time', order: 'descending' }"
        @sort-change="handleSortChange"
        @row-click="openDeviceDetails"
        highlight-current-row
        style="cursor: pointer"
      >
        <!-- 监测时间 -->
        <el-table-column prop="time" min-width="160" fixed="left" sortable="custom">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-sm font-bold text-slate-700">监测时间</div>
            </div>
          </template>
          <template #default="scope">
            <span class="text-sm font-mono text-slate-600">{{ scope.row.time }}</span>
          </template>
        </el-table-column>

        <!-- 设备信息 -->
        <el-table-column min-width="280">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-indigo-500 font-bold mb-1">设备信息</div>
              <div class="text-sm font-bold text-slate-700">设备名称 / 编号</div>
            </div>
          </template>
          <template #default="scope">
            <div class="flex flex-col justify-center leading-tight gap-0.5">
              <span class="text-sm font-medium text-slate-800">{{ scope.row.device_name }}</span>
              <span class="text-xs font-mono text-slate-400">{{ scope.row.device_id }}</span>
            </div>
          </template>
        </el-table-column>

        <!-- 建筑信息 -->
        <el-table-column min-width="140">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-emerald-500 font-bold mb-1">所属场景</div>
              <div class="text-sm font-bold text-slate-700">建筑 / 类型</div>
            </div>
          </template>
          <template #default="scope">
            <div class="flex flex-col leading-tight gap-0.5">
              <span class="text-sm text-slate-700">{{ scope.row.building }}</span>
              <span class="text-xs text-slate-400">{{ scope.row.type }}</span>
            </div>
          </template>
        </el-table-column>

        <!-- 能耗数据 -->
        <el-table-column prop="value" min-width="120" sortable="custom">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-rose-500 font-bold mb-1">电力能耗</div>
              <div class="text-sm font-bold text-slate-700">kWh</div>
            </div>
          </template>
          <template #default="scope">
            <span class="font-mono font-bold text-slate-700">{{ scope.row.value }}</span>
          </template>
        </el-table-column>

        <!-- 水温指标 -->
        <el-table-column min-width="140">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-cyan-500 font-bold mb-1">水温指标</div>
              <div class="text-sm font-bold text-slate-700">出回水(℃) / COP</div>
            </div>
          </template>
          <template #default="scope">
            <div v-if="scope.row.supply_temp !== null" class="flex flex-col leading-tight gap-0.5 text-sm font-mono">
              <span class="text-slate-600">出: {{ scope.row.supply_temp }}℃</span>
              <span class="text-slate-600">回: {{ scope.row.return_temp }}℃</span>
              <span v-if="scope.row.cop !== null" class="text-cyan-600 font-bold">COP: {{ scope.row.cop }}</span>
            </div>
            <span v-else class="text-slate-300 text-sm">—</span>
          </template>
        </el-table-column>

        <!-- 碳排放 + 电费 -->
        <el-table-column min-width="120">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-amber-500 font-bold mb-1">碳排放 / 电费</div>
              <div class="text-sm font-bold text-slate-700">kg / ¥</div>
            </div>
          </template>
          <template #default="scope">
            <div class="flex flex-col leading-tight gap-0.5 text-sm font-mono">
              <span class="text-slate-600">{{ scope.row.carbon_emission ?? '—' }} kg</span>
              <span class="text-slate-500">¥{{ scope.row.electricity_cost ?? '—' }}</span>
            </div>
          </template>
        </el-table-column>

        <!-- 运行状态 -->
        <el-table-column prop="raw_status" min-width="100" sortable="custom">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-indigo-500 font-bold mb-1">运行状态</div>
              <div class="text-sm font-bold text-slate-700">状态监控</div>
            </div>
          </template>
          <template #default="scope">
            <el-tag :type="statusTagType(scope.row.raw_status)" effect="light" round size="small">
              {{ statusEmoji(scope.row.raw_status) }}
            </el-tag>
            <el-tooltip v-if="scope.row.fault_code" :content="`故障代码: ${scope.row.fault_code}`" placement="top">
              <el-icon class="ml-1 text-rose-400"><WarningFilled /></el-icon>
            </el-tooltip>
          </template>
        </el-table-column>

        <!-- 操作 -->
        <el-table-column min-width="100" fixed="right" align="center">
          <template #header>
            <div class="leading-tight py-1">
              <div class="text-xs text-purple-500 font-bold mb-1">运维</div>
              <div class="text-sm font-bold text-slate-700">操作</div>
            </div>
          </template>
          <template #default="scope">
            <el-button type="primary" size="small" plain @click.stop="openDeviceDetails(scope.row)">
              查看档案
            </el-button>
          </template>
        </el-table-column>

        <!-- 空状态 -->
        <template #empty>
          <div class="flex flex-col items-center py-12 text-slate-400">
            <el-icon size="48" class="mb-3"><DataAnalysis /></el-icon>
            <p class="text-sm">暂无符合条件的设备数据</p>
            <p class="text-xs mt-1">尝试调整筛选条件或重置筛选</p>
          </div>
        </template>
      </el-table>

      <!-- 分页 -->
      <div class="flex items-center justify-between pt-3 border-t border-slate-50 mt-2">
        <span class="text-xs text-slate-400">
          第 {{ (currentPage - 1) * pageSize + 1 }} - {{ Math.min(currentPage * pageSize, totalCount) }} 条 / 共 {{ totalCount }} 条
        </span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[20, 50, 100, 200]"
          :total="totalCount"
          layout="sizes, prev, pager, next, jumper"
          background
          small
        />
      </div>
    </div>

    <!-- ===== 设备详情弹窗 ===== -->
    <el-dialog
      v-model="dialogVisible"
      title="设备数字孪生档案"
      width="720px"
      destroy-on-close
      class="rounded-xl overflow-hidden"
    >
      <template #header>
        <div class="flex items-center gap-2 border-b border-slate-100 pb-3">
          <div class="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
            <el-icon class="text-indigo-600 text-xl"><Cpu /></el-icon>
          </div>
          <span class="font-bold text-lg text-slate-800">{{ currentDevice?.device_name || '设备档案' }}</span>
          <el-tag size="small" effect="dark" :type="statusTagType(currentDevice?.raw_status)" class="ml-auto">
            {{ statusEmoji(currentDevice?.raw_status) }}
          </el-tag>
        </div>
      </template>

      <div v-if="currentDevice" class="px-2">
        <el-descriptions border :column="2" size="large" class="custom-descriptions">
          <el-descriptions-item label="设备名称" label-align="right">
            <span class="font-bold text-slate-800">{{ currentDevice.device_name }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="设备编号" label-align="right">
            <span class="font-mono text-indigo-600 font-bold bg-indigo-50 px-2 py-1 rounded">{{ currentDevice.device_id }}</span>
          </el-descriptions-item>

          <el-descriptions-item label="所属场景" label-align="right">{{ currentDevice.building }}</el-descriptions-item>
          <el-descriptions-item label="建筑编号" label-align="right">
            <span class="font-mono text-slate-600">{{ currentDevice.building_id }}</span>
          </el-descriptions-item>

          <el-descriptions-item label="当前运行状态" label-align="right">
            <el-tag :type="statusTagType(currentDevice.raw_status)" effect="light" size="small">
              {{ statusEmoji(currentDevice.raw_status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="实时总能耗" label-align="right">
            <span class="font-bold text-rose-500 text-lg">{{ currentDevice.value }}</span> kWh
          </el-descriptions-item>

          <el-descriptions-item label="出水温度" label-align="right">
            <span class="font-mono">{{ currentDevice.supply_temp !== null ? currentDevice.supply_temp + ' ℃' : '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="回水温度" label-align="right">
            <span class="font-mono">{{ currentDevice.return_temp !== null ? currentDevice.return_temp + ' ℃' : '—' }}</span>
          </el-descriptions-item>

          <el-descriptions-item label="能效比 (COP)" label-align="right">
            <span class="font-bold text-cyan-600">{{ currentDevice.cop ?? '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="碳排放" label-align="right">
            <span class="font-mono">{{ currentDevice.carbon_emission ?? '—' }} kg</span>
          </el-descriptions-item>

          <el-descriptions-item label="电费" label-align="right">
            <span class="font-mono">¥{{ currentDevice.electricity_cost ?? '—' }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="故障代码" label-align="right">
            <span v-if="currentDevice.fault_code" class="font-mono text-rose-500 font-bold">{{ currentDevice.fault_code }}</span>
            <span v-else class="text-slate-400">无</span>
          </el-descriptions-item>

          <el-descriptions-item label="数据追踪时间" :span="2" label-align="right">
            <span class="font-mono text-slate-600">{{ currentDevice.time }}</span>
            <span class="text-xs text-slate-400 ml-2">(Digital Twin Engine V3.0)</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">关闭档案</el-button>
          <el-button type="primary" @click="dialogVisible = false">
            发送巡检指令
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { RefreshLeft, Cpu, Search, Download, Document, WarningFilled, DataAnalysis } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { fetchDevices, fetchWeeklyAiReport } from '../api/index.js'

// 字典定义
const BUILDING_TYPES = { TEACHING: "教学楼", LIBRARY: "图书馆", OFFICE: "行政办公楼", LABORATORY: "科研实验楼", CANTEEN: "食堂", DORMITORY: "学生宿舍", PLAZA: "公共广场", CONFERENCE: "会议交流中心" }
const DEVICE_TYPES = { HVAC: "暖通空调系统", PRECISION_AC: "精密空调", LIGHTING: "智能照明系统", SOCKET: "插座与办公用电", EV_CHARGER: "新能源充电桩", WATER_HEATER: "热泵热水系统", PUMP: "动力水泵", VENTILATION: "通风排风系统", REFRIGERATION: "冷冻冷藏系统" }

// 数据
const tableData = ref([])
const loading = ref(false)
const totalCount = ref(0)
const summary = reactive({ normal: 0, warning: 0, abnormal: 0, critical: 0 })

// 筛选条件
const filters = reactive({
  keyword: '',
  building: 'ALL',
  device_type: 'ALL',
  status: 'ALL',
  dateRange: null,
  size: 500
})

// 分页
const currentPage = ref(1)
const pageSize = ref(20)

// 排序
const sortConfig = reactive({ prop: 'time', order: 'descending' })

// 弹窗
const dialogVisible = ref(false)
const currentDevice = ref(null)

// 分页后的数据
const pagedData = computed(() => {
  let data = [...tableData.value]
  // 客户端排序
  if (sortConfig.prop) {
    const prop = sortConfig.prop
    const asc = sortConfig.order === 'ascending'
    data.sort((a, b) => {
      let valA = a[prop]
      let valB = b[prop]
      // 处理 null 值
      if (valA === null || valA === undefined) return asc ? -1 : 1
      if (valB === null || valB === undefined) return asc ? 1 : -1
      if (typeof valA === 'string') {
        return asc ? valA.localeCompare(valB) : valB.localeCompare(valA)
      }
      return asc ? valA - valB : valB - valA
    })
  }
  // 分页
  const start = (currentPage.value - 1) * pageSize.value
  return data.slice(start, start + pageSize.value)
})

// 状态标签类型
const statusTagType = (status) => {
  const map = { NORMAL: 'success', WARNING: 'warning', ABNORMAL: 'warning', CRITICAL: 'danger', ALARM: 'danger' }
  return map[status] || 'info'
}

// 状态 emoji
const statusEmoji = (status) => {
  const map = { NORMAL: '🟢 正常', WARNING: '⚠️ 警告', ABNORMAL: '🟡 异常', CRITICAL: '🔴 严重', ALARM: '🔴 告警' }
  return map[status] || status || '未知'
}

// 排序变更
const handleSortChange = ({ prop, order }) => {
  sortConfig.prop = prop
  sortConfig.order = order
  currentPage.value = 1
}

// 打开详情弹窗
const openDeviceDetails = (row) => {
  currentDevice.value = row
  dialogVisible.value = true
}

// 拉取数据
const fetchData = async () => {
  loading.value = true
  currentPage.value = 1
  try {
    const params = {
      building: filters.building,
      device_type: filters.device_type,
      status: filters.status,
      size: filters.size
    }

    if (filters.keyword && filters.keyword.trim()) {
      params.keyword = filters.keyword.trim()
    }

    if (filters.dateRange && filters.dateRange.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }

    const result = await fetchDevices(params)

    if (result.status === 'success') {
      tableData.value = result.data || []
      totalCount.value = result.total || 0
      const s = result.summary || {}
      summary.normal = s.normal || 0
      summary.warning = s.warning || 0
      summary.abnormal = s.abnormal || 0
      summary.critical = s.critical || 0
    }
  } catch (err) {
    console.error('前端抓取数据失败:', err)
    ElMessage.error('数据加载失败，请检查网络连接')
  } finally {
    loading.value = false
  }
}

// 重置筛选
const resetFilters = () => {
  filters.keyword = ''
  filters.building = 'ALL'
  filters.device_type = 'ALL'
  filters.status = 'ALL'
  filters.dateRange = null
  filters.size = 500
  fetchData()
}

// CSV 导出
const handleExport = () => {
  if (tableData.value.length === 0) {
    ElMessage.warning('当前没有数据可导出')
    return
  }

  const headers = ['监控时间', '设备名称', '设备编号', '建筑', '设备类型', '能耗(kWh)', '出水温度(℃)', '回水温度(℃)', 'COP', '碳排放(kg)', '电费(¥)', '运行状态', '故障代码']
  const rows = tableData.value.map(row => [
    row.time,
    row.device_name,
    row.device_id,
    row.building,
    row.type,
    row.value,
    row.supply_temp ?? '',
    row.return_temp ?? '',
    row.cop ?? '',
    row.carbon_emission ?? '',
    row.electricity_cost ?? '',
    row.status,
    row.fault_code ?? ''
  ])

  let csvContent = '\uFEFF' + headers.join(',') + '\n'
  rows.forEach(row => {
    csvContent += row.map(cell => `"${cell}"`).join(',') + '\n'
  })

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.setAttribute('download', `设备监测数据导出_${new Date().getTime()}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  ElMessage.success(`已导出 ${tableData.value.length} 条数据`)
}

// AI 报告导出
const isExporting = ref(false)
const generateAIReport = async () => {
  isExporting.value = true
  ElMessage({ message: '🤖 AI 正在穿透数据库计算近7天数据并撰写报告，请稍候...', type: 'info', duration: 4000 })

  try {
    const blob = await fetchWeeklyAiReport()
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `AI能效诊断周报_${new Date().toISOString().split('T')[0]}.docx`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('🎉 AI 报告撰写完毕并已成功下载！')
  } catch (error) {
    console.error('报告生成失败:', error)
    ElMessage.error('生成失败，请检查后端服务是否正常运行')
  } finally {
    isExporting.value = false
  }
}

onMounted(() => fetchData())
</script>

<style scoped>
:deep(.el-table__body-wrapper::-webkit-scrollbar) { width: 6px; height: 6px; }
:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb) { background-color: #cbd5e1; border-radius: 4px; }
:deep(.el-table__cell) { padding: 10px 0; }

:deep(.custom-descriptions .el-descriptions__label) {
  width: 140px;
  background-color: #f8fafc !important;
  color: #64748b;
  font-weight: bold;
}
:deep(.custom-descriptions .el-descriptions__content) {
  background-color: #ffffff !important;
}
</style>
