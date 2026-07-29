// src/api/index.js
// 统一 API 调用层
// 集中管理所有后端接口请求，统一基于 utils/request.js 的 safeFetch（含超时控制 + JWT 鉴权 + 错误兜底）。
// 例外：fetchWeeklyAiReport 返回二进制流、uploadDoc 涉及 FormData 文件上传，二者单独使用 fetch 处理（详见各函数注释）。

import { safeFetch, getAuthHeaders, authFetch } from '../utils/request'

// ===================== 仪表盘 =====================

/**
 * 获取首页能效全景监控仪表盘数据
 * GET /api/dashboard
 * @returns {Promise<Object>} 后端返回的仪表盘数据（kpi/pie/bar/line）
 */
export function fetchDashboard() {
  return safeFetch('/api/dashboard')
}

// ===================== 设备监控 =====================

/**
 * 按条件查询设备监测数据
 * GET /api/devices
 * @param {Object} params 查询参数对象（如 building/device_type/status/size/start_date/end_date）
 * @returns {Promise<Object>} 后端返回的设备列表数据
 */
export function fetchDevices(params = {}) {
  // 过滤掉 undefined/null 值，避免 URLSearchParams 将其序列化为字符串 "undefined"
  const filtered = {}
  Object.keys(params).forEach((key) => {
    const val = params[key]
    if (val !== undefined && val !== null && val !== '') filtered[key] = val
  })
  const qs = new URLSearchParams(filtered).toString()
  const path = qs ? `/api/devices?${qs}` : '/api/devices'
  return safeFetch(path)
}

// ===================== 能耗分析 =====================

/**
 * 获取全天候系统能效比 (COP) 趋势数据
 * GET /api/cop_trend
 * @returns {Promise<Object>} 后端返回的 { times, values }
 */
export function fetchCopTrend() {
  return safeFetch('/api/cop_trend')
}

/**
 * 获取能耗分布数据（饼图等）
 * GET /api/energy_distribution
 * @returns {Promise<Object>} 后端返回的能耗分布数据
 */
export function fetchEnergyDistribution() {
  return safeFetch('/api/energy_distribution')
}

/**
 * 获取未来能耗 AI 预测数据
 * GET /api/energy/forecast
 * @param {number} hours 预测时长（小时），常用 12/24/48
 * @returns {Promise<Object>} 后端返回的历史 + 预测 + 置信区间数据
 */
export function fetchEnergyForecast(hours = 24) {
  return safeFetch(`/api/energy/forecast?hours_to_predict=${encodeURIComponent(hours)}`)
}

/**
 * 获取 AI 预测性维护 (RUL) 数据
 * GET /api/equipment/predictive_maintenance
 * @returns {Promise<Object>} 后端返回的设备健康度、振动、预测衰减等数据
 */
export function fetchPredictiveMaintenance() {
  return safeFetch('/api/equipment/predictive_maintenance')
}

// ===================== 空间孪生 =====================

/**
 * 获取空间孪生校园级数据（建筑列表、状态、能耗等）
 * GET /api/spatial-twin/campus-data
 * @returns {Promise<Object>} 后端返回的 campus_name/data/last_update 等
 */
export function fetchSpatialCampusData() {
  return safeFetch('/api/spatial-twin/campus-data')
}

/**
 * 获取全校园仿真数据
 * GET /api/spatial-twin/full-campus-sim
 * @returns {Promise<Object>} 后端返回的全校园仿真数据
 */
export function fetchFullCampusSim() {
  return safeFetch('/api/spatial-twin/full-campus-sim')
}

/**
 * 获取指定建筑的 3D 详细数据
 * GET /api/buildings/{id}/3d-data
 * @param {string|number} id 建筑 ID
 * @returns {Promise<Object>} 后端返回的建筑 3D 渲染数据
 */
export function fetchBuilding3DData(id) {
  return safeFetch(`/api/buildings/${encodeURIComponent(id)}/3d-data`)
}

// ===================== AI 报告 =====================

/**
 * 生成并下载 AI 能效诊断周报（Word 文件）
 * GET /api/report/weekly_ai
 * @returns {Promise<Blob>} 返回 Word 文档二进制流，调用方需自行触发下载
 *
 * 注：此接口返回二进制流（.docx），不能用 safeFetch（其内部会 res.json() 导致解析失败）。
 *    这里直接使用 fetch + getAuthHeaders 保留鉴权能力，与原 DeviceMonitor.vue 行为一致。
 */
export async function fetchWeeklyAiReport() {
  const res = await authFetch('/api/report/weekly_ai')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.blob()
}

// ===================== 数据导出（CSV/Excel）=====================

/**
 * 导出能耗记录为 CSV / XLSX
 * GET /api/export/energy_records
 * @param {Object} params { start_date, end_date, building_id, device_id, format, limit }
 * @returns {Promise<Blob>} 返回二进制流（csv 或 xlsx），调用方需自行触发下载
 *
 * 注：此接口返回二进制流，不能用 safeFetch（其内部会 res.json() 导致解析失败）。
 *    异常时后端返回 JSON，这里通过 Content-Type 判断后分别处理。
 */
export async function exportEnergyRecords(params = {}) {
  const filtered = {}
  Object.keys(params).forEach((key) => {
    const val = params[key]
    if (val !== undefined && val !== null && val !== '') filtered[key] = val
  })
  const qs = new URLSearchParams(filtered).toString()
  const path = `/api/export/energy_records?${qs}`

  const res = await fetch(path, { headers: getAuthHeaders() })
  // 异常时后端返回 application/json
  const contentType = res.headers.get('Content-Type') || ''
  if (!res.ok || contentType.includes('application/json')) {
    let message = `HTTP ${res.status}`
    try {
      const errBody = await res.json()
      message = errBody.message || message
    } catch (_) {
      /* ignore */
    }
    throw new Error(message)
  }
  return res.blob()
}

// ===================== 设备工单 =====================

/**
 * 查询工单列表（支持 status/device_id 分页查询）
 * GET /api/workorders
 * @param {Object} params { status?, device_id?, page?, page_size? }
 * @returns {Promise<Object>} { status, data, total, page, page_size }
 */
export function fetchWorkOrders(params = {}) {
  const filtered = {}
  Object.keys(params).forEach((key) => {
    const val = params[key]
    if (val !== undefined && val !== null && val !== '') filtered[key] = val
  })
  const qs = new URLSearchParams(filtered).toString()
  const path = qs ? `/api/workorders?${qs}` : '/api/workorders'
  return safeFetch(path)
}

/**
 * 查询单个工单详情
 * GET /api/workorders/{order_id}
 * @param {string} orderId 工单ID
 * @returns {Promise<Object>} { status, data }
 */
export function fetchWorkOrderDetail(orderId) {
  return safeFetch(`/api/workorders/${encodeURIComponent(orderId)}`)
}

/**
 * 创建新工单（手动报修）
 * POST /api/workorders
 * @param {Object} payload { device_id, diagnosis_title, rag_advice?, maintenance_action?, repair_cost?, user_feedback? }
 * @returns {Promise<Object>} { status, message, data }
 */
export function createWorkOrder(payload) {
  return safeFetch('/api/workorders', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/**
 * 更新工单状态（状态流转）
 * PUT /api/workorders/{order_id}/status
 * @param {string} orderId 工单ID
 * @param {Object} payload { new_status, maintenance_action?, user_feedback?, repair_cost? }
 * @returns {Promise<Object>} { status, message, data }
 */
export function updateWorkOrderStatus(orderId, payload) {
  return safeFetch(`/api/workorders/${encodeURIComponent(orderId)}/status`, {
    method: 'PUT',
    body: JSON.stringify(payload)
  })
}

// ===================== 管理后台 =====================

/**
 * 获取管理后台仪表盘数据（真实 KPI）
 * GET /api/admin/dashboard
 * @returns {Promise<Object>} 后端返回的管理后台统计数据
 */
export function fetchAdminDashboard() {
  return safeFetch('/api/admin/dashboard')
}

/**
 * 查询审计日志
 * GET /api/admin/audit_logs
 * @param {Object} params { limit?: number, risk_level?: 'all'|'low'|'high' }
 * @returns {Promise<Object>} { status, data: [...], total }
 */
export function fetchAuditLogs(params = {}) {
  const qs = new URLSearchParams({
    limit: params.limit || 50,
    risk_level: params.risk_level || 'all'
  }).toString()
  return safeFetch(`/api/admin/audit_logs?${qs}`)
}

/**
 * 知识库文档列表
 * GET /api/admin/kb/list
 * @returns {Promise<Object>} { status, data: [...], total }
 */
export function fetchKnowledgeList() {
  return safeFetch('/api/admin/kb/list')
}

/**
 * 录入知识条目
 * POST /api/admin/kb/upload
 * @param {Object} item { title, content, tags }
 * @returns {Promise<Object>} { status, message, data }
 */
export function uploadKnowledgeItem(item) {
  return safeFetch('/api/admin/kb/upload', {
    method: 'POST',
    body: JSON.stringify(item)
  })
}

/**
 * 删除知识条目
 * DELETE /api/admin/kb/{doc_index}
 * @param {number} docIndex 知识条目索引
 * @returns {Promise<Object>} { status, message, data }
 */
export function deleteKnowledgeItem(docIndex) {
  return safeFetch(`/api/admin/kb/${docIndex}`, {
    method: 'DELETE'
  })
}

// ===================== 文件上传 =====================

/**
 * 上传文档至知识库（FormData 文件上传）
 * POST /api/upload_doc
 * @param {File} file 待上传的文件对象
 * @param {string} [user] 上传人标识（可选）
 * @returns {Promise<Object>} 后端返回的 JSON 结果
 *
 * 注：文件上传使用 FormData，必须由浏览器自动设置 multipart/form-data 边界，
 *    因此不能用 safeFetch（其默认 Content-Type: application/json 会破坏上传）。
 *    这里直接使用 fetch + getAuthHeaders 保留鉴权能力，与原 AiAgent.vue 行为一致。
 */
export async function uploadDoc(file, user) {
  const formData = new FormData()
  formData.append('file', file)
  if (user) formData.append('user', user)

  const res = await fetch('/api/upload_doc', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: formData
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

// ===================== AI 对话（SSE 流式）=====================

/**
 * AI 对话流式接口（SSE）
 * POST /api/chat/stream
 * 统一封装 SSE 解析逻辑，调用方只关心回调，无需重复实现 reader/decoder/data: 切分。
 *
 * @param {Object} payload 请求体（prompt / currentPage / image_base64 / agent_mode / history 等）
 * @param {Object} callbacks 回调集合
 * @param {(reply: string) => void} [callbacks.onThinking] 每收到一条 thinking 消息触发
 * @param {(reply: string, fullText: string) => void} [callbacks.onMessage] 每收到一条 success/error 消息触发
 * @param {() => void} [callbacks.onDone] 流结束时触发
 * @param {(err: Error) => void} [callbacks.onError] 任何异常时触发
 * @returns {Promise<void>}
 */
export async function chatStream(payload, { onThinking, onMessage, onDone, onError } = {}) {
  try {
    const res = await authFetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })

    if (!res.body) {
      throw new Error('响应体为空，浏览器不支持流式读取')
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let fullAiText = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value)
      // 解决粘包：按行拆分 data: {...}
      const lines = chunk.split('\n').filter((line) => line.trim() !== '')

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.substring(6))
          if (data.status === 'thinking') {
            onThinking && onThinking(data.reply)
          } else if (data.status === 'success' || data.status === 'error') {
            fullAiText += data.reply
            onMessage && onMessage(data.reply, fullAiText)
          }
          if (data.done) {
            onDone && onDone()
          }
        } catch (e) {
          console.error('解析流式数据失败:', e, line)
        }
      }
    }
    // 流自然结束时也触发一次 onDone（兼容后端未发 done 的场景）
    onDone && onDone()
  } catch (err) {
    console.error('chatStream 异常:', err)
    onError && onError(err)
  }
}

// ===================== 登录 =====================

/**
 * 管理员登录
 * POST /api/login
 * @param {string} username 用户名
 * @param {string} password 密码
 * @returns {Promise<Object>} 后端返回的 { status, token, ... }
 */
export async function login(username, password) {
  return safeFetch('/api/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  })
}

// ===================== 功能5：异常检测与根因分析 =====================

/**
 * 异常检测（Isolation Forest + SHAP 根因归因）
 * GET /api/anomaly/detect
 * @param {Object} params { hours?: number, building_type?: string }
 * @returns {Promise<Object>} 异常事件列表（含根因链）
 */
export function fetchAnomalyDetect(params = {}) {
  const qs = new URLSearchParams({
    hours: params.hours || 168,
    building_type: params.building_type || 'ALL'
  }).toString()
  return safeFetch(`/api/anomaly/detect?${qs}`)
}

/**
 * 最近异常事件（轻量版）
 * GET /api/anomaly/recent
 */
export function fetchAnomalyRecent(hours = 24, limit = 20) {
  return safeFetch(`/api/anomaly/recent?hours=${hours}&limit=${limit}`)
}

/**
 * 单设备根因分析
 * GET /api/anomaly/root_cause/{device_id}
 */
export function fetchRootCause(deviceId, hours = 48) {
  return safeFetch(`/api/anomaly/root_cause/${encodeURIComponent(deviceId)}?hours=${hours}`)
}

// ===================== 功能1：碳排放追踪 =====================

export function fetchCarbonOverview(days = 30) {
  return safeFetch(`/api/carbon/overview?days=${days}`)
}

export function fetchCarbonPathway(targetYear = 2030) {
  return safeFetch(`/api/carbon/pathway?target_year=${targetYear}`)
}

// ===================== 功能2：虚拟电厂 =====================

export function fetchVppStatus() {
  return safeFetch('/api/vpp/status')
}

export function fetchVppDispatch(storageCapacityKwh = 500, storagePowerKw = 100) {
  return safeFetch(`/api/vpp/dispatch?storage_capacity_kwh=${storageCapacityKwh}&storage_power_kw=${storagePowerKw}`)
}

export function fetchVppEconomy(days = 30) {
  return safeFetch(`/api/vpp/economy?days=${days}`)
}

// ===================== 功能3：光储充微电网 =====================

export function fetchMicrogridOverview() {
  return safeFetch('/api/microgrid/overview')
}

export function fetchPvForecast() {
  return safeFetch('/api/microgrid/pv_forecast')
}

export function fetchMicrogridSchedule() {
  return safeFetch('/api/microgrid/schedule')
}

// ===================== 功能4：多智能体协作 =====================

export function fetchAgentsList() {
  return safeFetch('/api/agents/list')
}

/**
 * 执行多智能体工作流（SSE 流式）
 * @param {Object} payload { task, device_id?, context? }
 * @param {Object} callbacks { onAgentStart, onAgentComplete, onWorkflowComplete, onError }
 */
export async function executeAgentWorkflow(payload, { onAgentStart, onAgentComplete, onWorkflowComplete, onError } = {}) {
  try {
    const res = await fetch('/api/agents/workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body: JSON.stringify(payload)
    })
    if (!res.body) throw new Error('响应体为空')
    const reader = res.body.getReader()
    const decoder = new TextDecoder('utf-8')
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value)
      const lines = chunk.split('\n').filter(l => l.trim())
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const data = JSON.parse(line.substring(6))
          if (data.status === 'agent_start') onAgentStart && onAgentStart(data)
          else if (data.status === 'agent_complete') onAgentComplete && onAgentComplete(data)
          else if (data.status === 'workflow_complete') onWorkflowComplete && onWorkflowComplete(data)
        } catch (e) { console.error('解析失败:', e) }
      }
    }
  } catch (err) {
    console.error('agent workflow error:', err)
    onError && onError(err)
  }
}

// ===================== 功能6：知识图谱 =====================

export function fetchKnowledgeGraph(nodeType = '') {
  const qs = nodeType ? `?node_type=${nodeType}` : ''
  return safeFetch(`/api/knowledge/graph${qs}`)
}

export function extractEntities(text) {
  return safeFetch(`/api/knowledge/entities?text=${encodeURIComponent(text)}`)
}

// ===================== 功能7：3D 实时孪生 =====================

export function fetchTwinRealtime() {
  return safeFetch('/api/twin/realtime')
}

export function fetchTwinHeatmap(buildingId, hours = 24) {
  return safeFetch(`/api/twin/building/${encodeURIComponent(buildingId)}/heatmap?hours=${hours}`)
}

export function fetchTwinDevices3D() {
  return safeFetch('/api/twin/devices_3d')
}

/**
 * 获取校园→建筑→空间→设备层级树
 * GET /api/twin/hierarchy
 * @returns {Promise<Object>} 完整层级树（含实时统计数据）
 */
export function fetchTwinHierarchy() {
  return safeFetch('/api/twin/hierarchy')
}

// ===================== 功能8：AR 远程运维 =====================

export function fetchArDevice(deviceId) {
  return safeFetch(`/api/ar/device/${encodeURIComponent(deviceId)}`)
}

export function fetchArWorkOrders(deviceId, limit = 5) {
  return safeFetch(`/api/ar/work_orders/${encodeURIComponent(deviceId)}?limit=${limit}`)
}

export function fetchArManual(deviceId) {
  return safeFetch(`/api/ar/manual/${encodeURIComponent(deviceId)}`)
}

export function fetchArDevices() {
  return safeFetch('/api/ar/devices')
}

export function fetchArAnnotations(deviceId, limit = 20) {
  const qs = new URLSearchParams({ limit }).toString()
  const path = deviceId
    ? `/api/ar/annotations?device_id=${encodeURIComponent(deviceId)}&${qs}`
    : `/api/ar/annotations?${qs}`
  return safeFetch(path)
}

export function saveArAnnotation(payload) {
  return safeFetch('/api/ar/annotate', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// ===================== 功能9：可观测性 =====================

export function fetchObservabilityMetrics(windowSeconds = 300) {
  return safeFetch(`/api/observability/metrics?window_seconds=${windowSeconds}`)
}

export function fetchObservabilityHealth() {
  return safeFetch('/api/observability/health')
}

export function fetchObservabilityDashboard() {
  return safeFetch('/api/observability/dashboard')
}

// ===================== 功能10：边缘网关 =====================

export function fetchEdgeStatus() {
  return safeFetch('/api/edge/gateway/status')
}

export function fetchEdgeDevices() {
  return safeFetch('/api/edge/devices')
}

export function fetchEdgeSnapshot() {
  return safeFetch('/api/edge/snapshot')
}

export function injectEdgeAnomaly(payload) {
  return safeFetch('/api/edge/gateway/inject_anomaly', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// ===================== 进阶能力1：设备健康度 & RUL 预测 =====================

export function fetchRulOverview() {
  return safeFetch('/api/rul/overview')
}

export function fetchRulDeviceDetail(deviceId) {
  return safeFetch(`/api/rul/device/${encodeURIComponent(deviceId)}`)
}

export function fetchRulRanking(top = 10) {
  return safeFetch(`/api/rul/ranking?top=${top}`)
}

// ===================== 进阶能力2：能耗基准对标 =====================

export function fetchBenchmarkOverview() {
  return safeFetch('/api/benchmark/overview')
}

export function fetchBenchmarkBuildingDetail(buildingId) {
  return safeFetch(`/api/benchmark/building/${encodeURIComponent(buildingId)}`)
}

export function fetchBenchmarkStandards() {
  return safeFetch('/api/benchmark/standards')
}

// ===================== 进阶能力3：多能耦合优化 =====================

export function fetchMultiEnergyOverview() {
  return safeFetch('/api/multi_energy/overview')
}

export function fetchMultiEnergyOptimize() {
  return safeFetch('/api/multi_energy/optimize')
}

export function fetchMultiEnergyComparison() {
  return safeFetch('/api/multi_energy/comparison')
}

// ===================== 进阶能力4：智能告警中心 =====================

export function fetchAlertsCenter(params = {}) {
  const filtered = {}
  Object.keys(params).forEach((key) => {
    const val = params[key]
    if (val !== undefined && val !== null && val !== '') filtered[key] = val
  })
  const qs = new URLSearchParams(filtered).toString()
  const path = qs ? `/api/alerts/center?${qs}` : '/api/alerts/center'
  return safeFetch(path)
}

export function fetchAlertsStats() {
  return safeFetch('/api/alerts/stats')
}

export function acknowledgeAlert(alertId) {
  return safeFetch(`/api/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    method: 'POST'
  })
}

export function silenceAlert(alertId, durationMinutes = 60) {
  return safeFetch(`/api/alerts/${encodeURIComponent(alertId)}/silence?duration_minutes=${durationMinutes}`, {
    method: 'POST'
  })
}

export function fetchAlertChannels() {
  return safeFetch('/api/alerts/channels')
}

export function updateAlertChannels(payload) {
  return safeFetch('/api/alerts/channels', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function testAlertPush(payload = {}) {
  return safeFetch('/api/alerts/test_push', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// ===================== 进阶能力5：能源审计报告 =====================

export function fetchAuditBuildings() {
  return safeFetch('/api/audit/buildings')
}

export function fetchAuditReport(buildingId) {
  return safeFetch(`/api/audit/report?building_id=${encodeURIComponent(buildingId)}`)
}

/**
 * 导出审计报告为 Word 文档
 * POST /api/audit/export （返回二进制流）
 */
export async function exportAuditReport(buildingId) {
  const res = await authFetch(`/api/audit/export?building_id=${encodeURIComponent(buildingId)}`, {
    method: 'POST'
  })
  const contentType = res.headers.get('Content-Type') || ''
  if (!res.ok || contentType.includes('application/json')) {
    let message = `HTTP ${res.status}`
    try {
      const errBody = await res.json()
      message = errBody.message || message
    } catch (_) { /* ignore */ }
    throw new Error(message)
  }
  return res.blob()
}

// ===================== 进阶能力6：工单全生命周期增强 =====================

export function fetchWorkOrdersPro(params = {}) {
  const filtered = {}
  Object.keys(params).forEach((key) => {
    const val = params[key]
    if (val !== undefined && val !== null && val !== '') filtered[key] = val
  })
  const qs = new URLSearchParams(filtered).toString()
  const path = qs ? `/api/workorders/pro/list?${qs}` : '/api/workorders/pro/list'
  return safeFetch(path)
}

export function fetchWorkOrderProDetail(orderId) {
  return safeFetch(`/api/workorders/pro/${encodeURIComponent(orderId)}`)
}

export function dispatchWorkOrder(orderId) {
  return safeFetch(`/api/workorders/pro/dispatch?order_id=${encodeURIComponent(orderId)}`, {
    method: 'POST'
  })
}

export function fetchSlaStats() {
  return safeFetch('/api/workorders/pro/sla_stats')
}

export function fetchPartsInventory() {
  return safeFetch('/api/workorders/pro/parts')
}

// ===================== 进阶能力7：ESG 报告 =====================

export function fetchEsgOverview() {
  return safeFetch('/api/esg/overview')
}

export function fetchEsgReport() {
  return safeFetch('/api/esg/report')
}

export function fetchEsgTrend() {
  return safeFetch('/api/esg/trend')
}

export function fetchEsgBuildingCarbon(days = 30) {
  return safeFetch(`/api/esg/building-carbon?days=${days}`)
}

export function fetchEsgBenchmark(days = 30) {
  return safeFetch(`/api/esg/benchmark?days=${days}`)
}

export function fetchEsgRecommendations(days = 30) {
  return safeFetch(`/api/esg/recommendations?days=${days}`)
}

// ===================== 进阶能力8：节能改造 ROI 测算 =====================

export function fetchRoiScenarios() {
  return safeFetch('/api/roi/scenarios')
}

export function calculateRoi(payload) {
  return safeFetch('/api/roi/calculate', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function compareRoiScenarios(buildingId, scenarioIds) {
  return safeFetch('/api/roi/compare', {
    method: 'POST',
    body: JSON.stringify({ building_id: buildingId, scenario_ids: scenarioIds })
  })
}

export function analyzeRoiSensitivity(scenarioId, buildingId) {
  return safeFetch('/api/roi/sensitivity', {
    method: 'POST',
    body: JSON.stringify({ scenario_id: scenarioId, building_id: buildingId })
  })
}

export function fetchRoiRiskAssessment(scenarioId) {
  return safeFetch(`/api/roi/risk-assessment?scenario_id=${scenarioId}`)
}

export function optimizeRoiPortfolio(buildingId, budgetLimit, scenarioIds = []) {
  return safeFetch('/api/roi/portfolio', {
    method: 'POST',
    body: JSON.stringify({ building_id: buildingId, budget_limit: budgetLimit, scenario_ids: scenarioIds })
  })
}

export function fetchRoiHistory() {
  return safeFetch('/api/roi/history')
}

export function saveRoiScenario(payload) {
  return safeFetch('/api/roi/save', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

// ===================== 进阶能力9：告警推送服务（Web Push / PWA）=====================

export function fetchVapidPublicKey() {
  return safeFetch('/api/push/vapid_public_key')
}

export function subscribePush(payload) {
  return safeFetch('/api/push/subscribe', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function fetchPushSubscriptions() {
  return safeFetch('/api/push/subscriptions')
}

export function unsubscribePush(endpoint) {
  return safeFetch('/api/push/unsubscribe', {
    method: 'POST',
    body: JSON.stringify({ endpoint })
  })
}

export function sendPushNotification(payload) {
  return safeFetch('/api/push/send', {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

export function fetchPushNotifications(limit = 20) {
  return safeFetch(`/api/push/notifications?limit=${limit}`)
}
