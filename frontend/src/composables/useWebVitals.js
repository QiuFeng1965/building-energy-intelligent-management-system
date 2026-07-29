/**
 * Web Vitals 性能监控
 * 采集 LCP / FID / CLP / TTFB / INP 五大核心指标
 * 上报到 /api/observability/web-vitals 接口
 */

const REPORT_URL = '/api/observability/web-vitals'
const SAMPLE_RATE = 1.0 // 100% 采样（开发期），生产可调到 0.1

let reported = false

/** 上报指标 */
function report(metric) {
  try {
    if (Math.random() > SAMPLE_RATE) return
    const body = JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      delta: metric.delta,
      id: metric.id,
      url: window.location.href,
      ts: Date.now(),
    })
    if (navigator.sendBeacon) {
      navigator.sendBeacon(REPORT_URL, new Blob([body], { type: 'application/json' }))
    } else {
      fetch(REPORT_URL, { body, method: 'POST', keepalive: true, headers: { 'Content-Type': 'application/json' } })
    }
  } catch (e) {
    // 静默失败
  }
}

/** 计算 TTFB */
function measureTTFB() {
  try {
    const nav = performance.getEntriesByType('navigation')[0]
    if (nav && nav.responseStart > 0) {
      const value = nav.responseStart - nav.requestStart
      report({
        name: 'TTFB',
        value: Math.max(0, value),
        rating: value < 800 ? 'good' : value < 1800 ? 'needs-improvement' : 'poor',
        delta: value,
        id: 'ttfb-' + Date.now(),
      })
    }
  } catch (e) {}
}

/** 计算 LCP */
function measureLCP() {
  try {
    const po = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const last = entries[entries.length - 1]
      if (last) {
        const value = last.startTime
        report({
          name: 'LCP',
          value,
          rating: value < 2500 ? 'good' : value < 4000 ? 'needs-improvement' : 'poor',
          delta: value,
          id: 'lcp-' + Date.now(),
        })
      }
    })
    po.observe({ type: 'largest-contentful-paint', buffered: true })
  } catch (e) {}
}

/** 计算 CLS */
function measureCLS() {
  try {
    let clsValue = 0
    let clsEntries = []
    const po = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value
          clsEntries.push(entry)
        }
      }
    })
    po.observe({ type: 'layout-shift', buffered: true })
    // 页面隐藏时上报
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && !reported) {
        reported = true
        report({
          name: 'CLS',
          value: clsValue,
          rating: clsValue < 0.1 ? 'good' : clsValue < 0.25 ? 'needs-improvement' : 'poor',
          delta: clsValue,
          id: 'cls-' + Date.now(),
        })
      }
    }, { once: true })
  } catch (e) {}
}

/** 计算 INP（替代 FID） */
function measureINP() {
  try {
    let worst = 0
    const po = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const duration = entry.duration
        if (duration > worst) worst = duration
      }
    })
    po.observe({ type: 'event', buffered: true })
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden' && worst > 0) {
        report({
          name: 'INP',
          value: worst,
          rating: worst < 200 ? 'good' : worst < 500 ? 'needs-improvement' : 'poor',
          delta: worst,
          id: 'inp-' + Date.now(),
        })
      }
    }, { once: true })
  } catch (e) {}
}

/** 初始化所有指标采集 */
export function initWebVitals() {
  if (typeof window === 'undefined' || !window.performance) return
  // 等到页面加载完成后采集
  if (document.readyState === 'complete') {
    measureTTFB()
    measureLCP()
    measureCLS()
    measureINP()
  } else {
    window.addEventListener('load', () => {
      measureTTFB()
      measureLCP()
      measureCLS()
      measureINP()
    }, { once: true })
  }
}
