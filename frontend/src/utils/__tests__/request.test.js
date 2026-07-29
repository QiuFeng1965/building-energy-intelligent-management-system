// request.js 单元测试示例
// 说明：request.js 基于 window.fetch 实现（非 axios），不存在 baseURL 配置，
// 因此本测试针对其真实导出 createAbortableFetch / getAuthHeaders / safeFetch 编写。
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { createAbortableFetch, getAuthHeaders, safeFetch } from '../request.js'

describe('createAbortableFetch', () => {
  it('应返回包含 controller、clear、signal 的可取消对象', () => {
    const result = createAbortableFetch()
    expect(result.controller).toBeInstanceOf(AbortController)
    expect(typeof result.clear).toBe('function')
    expect(result.signal).toBe(result.controller.signal)
    result.clear() // 清理定时器，避免句柄泄漏
  })

  it('clear() 可重复调用且不抛错', () => {
    const { clear } = createAbortableFetch()
    expect(() => {
      clear()
      clear()
    }).not.toThrow()
  })
})

describe('getAuthHeaders', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('localStorage 存在 token 时返回 Bearer 鉴权头', () => {
    localStorage.setItem('token', 'test-token-123')
    expect(getAuthHeaders()).toEqual({ Authorization: 'Bearer test-token-123' })
  })

  it('localStorage 无 token 时返回空对象', () => {
    expect(getAuthHeaders()).toEqual({})
  })
})

describe('safeFetch', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('请求成功时返回解析后的 JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', data: [1, 2, 3] })
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await safeFetch('/api/test')
    expect(fetchMock).toHaveBeenCalled()
    expect(result).toEqual({ status: 'ok', data: [1, 2, 3] })
  })

  it('自动附加 Content-Type 与鉴权头', async () => {
    localStorage.setItem('token', 'abc')
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    await safeFetch('/api/test', { method: 'POST' })
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.headers['Authorization']).toBe('Bearer abc')
  })

  it('HTTP 非 2xx 时返回网络错误结果', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) })
    )

    const result = await safeFetch('/api/fail')
    expect(result.status).toBe('error')
    expect(result.code).toBe('NETWORK')
    errorSpy.mockRestore()
  })
})
