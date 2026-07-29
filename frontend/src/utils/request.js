// 前端统一请求工具：超时控制 + JWT 鉴权 + 错误兜底
const DEFAULT_TIMEOUT = 15000

/**
 * 创建可取消的 fetch 请求
 */
export function createAbortableFetch(options = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT)
  return {
    controller,
    clear: () => clearTimeout(timer),
    signal: controller.signal
  }
}

/**
 * 获取鉴权请求头
 */
export function getAuthHeaders() {
  const token = localStorage.getItem('token')
  return token ? { 'Authorization': `Bearer ${token}` } : {}
}

/**
 * 统一安全 fetch：自动超时 + 鉴权 + 错误兜底
 */
export async function safeFetch(path, { timeout, ...opts } = {}) {
  const { controller, clear, signal } = createAbortableFetch({ timeout })
  try {
    const headers = {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(opts.headers || {})
    }
    const res = await fetch(path, { ...opts, headers, signal })
    if (res.status === 401) {
      handleUnauthorized()
      return { status: 'error', code: 'UNAUTHORIZED', message: '登录已过期，请重新登录' }
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return await res.json()
  } catch (e) {
    if (e.name === 'AbortError') {
      console.warn(`[请求超时] ${path}`)
      return { status: 'error', code: 'TIMEOUT', message: '请求超时，请稍后重试' }
    }
    console.error(`[请求失败] ${path}:`, e)
    return { status: 'error', code: 'NETWORK', message: '网络异常，请检查后端服务' }
  } finally {
    clear()
  }
}

/**
 * 处理 401 未授权：清除 token 并跳转登录页
 */
function handleUnauthorized() {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  window.dispatchEvent(new CustomEvent('auth:expired'))
  if (!window.location.pathname.includes('/login')) {
    const redirect = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.href = `/login?redirect=${redirect}`
  }
}

/**
 * 带 401 处理的原始 fetch（用于二进制流 / FormData / SSE 等不能用 safeFetch 的场景）
 * 自动添加鉴权头，检测 401 并跳转登录，返回原始 Response 对象。
 */
export async function authFetch(path, opts = {}) {
  const headers = {
    ...getAuthHeaders(),
    ...(opts.headers || {})
  }
  const res = await fetch(path, { ...opts, headers })
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error('登录已过期，请重新登录')
  }
  return res
}
