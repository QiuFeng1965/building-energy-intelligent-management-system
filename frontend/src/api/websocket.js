// src/api/websocket.js
// WebSocket 实时数据流封装
// 订阅 /ws/realtime_energy，自动重连 + 指数退避 + 心跳 + 消息分发

// 根据当前页面协议自动选择 ws/wss，端口跟随页面端口
const WS_BASE = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}${window.location.port ? ':' + window.location.port : ''}`
const WS_PATH = '/ws/realtime_energy'

// 指数退避配置（防惊群效应）
const BASE_DELAY = 1000      // 初始延迟 1s
const MAX_DELAY = 30000      // 最大延迟 30s
const MAX_RETRIES = 10       // 最大重连次数（从 5 提升到 10）
const HEARTBEAT_INTERVAL = 25000  // 心跳间隔 25s
const HEARTBEAT_TIMEOUT = 10000   // 心跳超时 10s

let ws = null
let retryCount = 0
let listeners = { snapshot: [], alarm: [] }
let manualClose = false
let heartbeatTimer = null
let heartbeatTimeoutTimer = null
let reconnectTimer = null

/**
 * 计算指数退避延迟（含 jitter 防惊群）
 * @param {number} retry 当前重试次数
 * @returns {number} 延迟毫秒数
 */
function getBackoffDelay(retry) {
  const exp = Math.min(BASE_DELAY * 2 ** retry, MAX_DELAY)
  return exp + Math.random() * 1000  // jitter：0~1s 随机抖动
}

/**
 * 启动心跳检测
 */
function startHeartbeat() {
  stopHeartbeat()
  heartbeatTimer = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
      // 心跳超时检测：10s 内未收到 pong 则认为连接已死
      heartbeatTimeoutTimer = setTimeout(() => {
        console.warn('⚠️ WebSocket 心跳超时，主动断开触发重连')
        if (ws) ws.close()
      }, HEARTBEAT_TIMEOUT)
    }
  }, HEARTBEAT_INTERVAL)
}

/**
 * 停止心跳检测
 */
function stopHeartbeat() {
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null }
  if (heartbeatTimeoutTimer) { clearTimeout(heartbeatTimeoutTimer); heartbeatTimeoutTimer = null }
}

/**
 * 连接 WebSocket
 */
function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return
  }

  manualClose = false
  // WebSocket 鉴权：从 localStorage 读取 token，通过 query 参数传递
  const token = localStorage.getItem('token')
  const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : ''
  ws = new WebSocket(`${WS_BASE}${WS_PATH}${tokenQuery}`)

  ws.onopen = () => {
    console.log('🟢 WebSocket 实时连接已建立')
    retryCount = 0
    startHeartbeat()
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      // 心跳响应：清除超时定时器
      if (data.type === 'pong') {
        if (heartbeatTimeoutTimer) { clearTimeout(heartbeatTimeoutTimer); heartbeatTimeoutTimer = null }
        return
      }
      if (data.type === 'snapshot') {
        listeners.snapshot.forEach((cb) => cb(data))
      } else if (data.type === 'alarm') {
        listeners.alarm.forEach((cb) => cb(data))
      }
    } catch (e) {
      console.warn('WebSocket 消息解析失败:', e)
    }
  }

  ws.onerror = (err) => {
    console.error('WebSocket 异常:', err)
  }

  ws.onclose = () => {
    console.log('🔴 WebSocket 连接已断开')
    stopHeartbeat()
    if (!manualClose && retryCount < MAX_RETRIES) {
      retryCount++
      const delay = getBackoffDelay(retryCount)
      console.log(`尝试第 ${retryCount}/${MAX_RETRIES} 次重连，延迟 ${Math.round(delay / 1000)}s...`)
      reconnectTimer = setTimeout(connect, delay)
    }
  }
}

/**
 * 订阅实时数据快照（每 3 秒推送一次）
 * @param {(data: Object) => void} callback 回调函数
 * @returns {() => void} 取消订阅函数
 */
export function onSnapshot(callback) {
  listeners.snapshot.push(callback)
  if (!ws || ws.readyState === WebSocket.CLOSED) connect()
  return () => {
    listeners.snapshot = listeners.snapshot.filter((cb) => cb !== callback)
  }
}

/**
 * 订阅告警事件（异常设备检测到时立即推送）
 * @param {(alarm: Object) => void} callback 回调函数
 * @returns {() => void} 取消订阅函数
 */
export function onAlarm(callback) {
  listeners.alarm.push(callback)
  if (!ws || ws.readyState === WebSocket.CLOSED) connect()
  return () => {
    listeners.alarm = listeners.alarm.filter((cb) => cb !== callback)
  }
}

/**
 * 主动关闭连接（页面卸载时调用）
 */
export function disconnect() {
  manualClose = true
  // 清理所有定时器
  stopHeartbeat()
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  // 清理 WebSocket 事件回调（防止 onclose 触发重连）
  if (ws) {
    ws.onclose = null
    ws.onerror = null
    ws.onmessage = null
    ws.onopen = null
    ws.close()
    ws = null
  }
  // 关键：重置重试计数，避免下次 connect 立即放弃
  retryCount = 0
  listeners = { snapshot: [], alarm: [] }
}

/**
 * 获取连接状态
 * @returns {string} 'connected' | 'connecting' | 'disconnected'
 */
export function getConnectionStatus() {
  if (!ws) return 'disconnected'
  switch (ws.readyState) {
    case WebSocket.OPEN:
      return 'connected'
    case WebSocket.CONNECTING:
      return 'connecting'
    default:
      return 'disconnected'
  }
}
