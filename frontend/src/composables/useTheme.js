/**
 * 主题管理系统
 * 支持亮色 / 暗色 / 跟随系统三种模式，状态持久化到 localStorage
 */
import { ref, watch, onMounted, onUnmounted } from 'vue'

const THEME_STORAGE_KEY = 'nova-theme-preference'
const VALID_THEMES = ['light', 'dark', 'auto']

const currentTheme = ref('auto')
const systemPrefersDark = ref(false)
const isDark = ref(false)

/** 应用主题到 <html> 元素 */
function applyTheme(theme) {
  const root = document.documentElement
  const shouldBeDark = theme === 'dark' || (theme === 'auto' && systemPrefersDark.value)
  if (shouldBeDark) {
    root.classList.add('dark')
  } else {
    root.classList.remove('dark')
  }
  isDark.value = shouldBeDark
  // 同步 meta theme-color
  const metaThemeColor = document.querySelector('meta[name="theme-color"]')
  if (metaThemeColor) {
    metaThemeColor.setAttribute('content', shouldBeDark ? '#0f172a' : '#4f46e5')
  }
}

/** 从 localStorage 读取偏好 */
function loadPreference() {
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved && VALID_THEMES.includes(saved)) {
      currentTheme.value = saved
    }
  } catch (e) {
    // 隐私模式下 localStorage 可能不可用，使用默认值
  }
}

/** 持久化偏好 */
function savePreference(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch (e) {
    // ignore
  }
}

/** 监听系统主题变化（仅 auto 模式生效） */
let mediaQuery = null
function setupMediaListener() {
  if (typeof window === 'undefined' || !window.matchMedia) return
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemPrefersDark.value = mediaQuery.matches
  const handler = (e) => {
    systemPrefersDark.value = e.matches
    if (currentTheme.value === 'auto') {
      applyTheme('auto')
    }
  }
  // 现代浏览器使用 addEventListener，旧版使用 addListener
  if (mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', handler)
  } else if (mediaQuery.addListener) {
    mediaQuery.addListener(handler)
  }
  return handler
}

let mediaHandler = null

/** 切换主题 */
function setTheme(theme) {
  if (!VALID_THEMES.includes(theme)) return
  currentTheme.value = theme
  savePreference(theme)
  applyTheme(theme)
}

/** 在 light / dark 之间切换（auto 视为当前系统态） */
function toggleTheme() {
  const next = isDark.value ? 'light' : 'dark'
  setTheme(next)
}

export function useTheme() {
  onMounted(() => {
    loadPreference()
    mediaHandler = setupMediaListener()
    applyTheme(currentTheme.value)
  })

  onUnmounted(() => {
    if (mediaQuery && mediaHandler) {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', mediaHandler)
      } else if (mediaQuery.removeListener) {
        mediaQuery.removeListener(mediaHandler)
      }
    }
  })

  return {
    currentTheme,
    isDark,
    setTheme,
    toggleTheme,
  }
}
