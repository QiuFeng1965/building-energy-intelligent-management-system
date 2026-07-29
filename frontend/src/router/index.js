// src/router/index.js
// 路由配置：替代原 App.vue 的 v-if 链，支持 URL 直达、前进后退、刷新保持页面
import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'

// 路由表：path ↔ 组件
const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('../views/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/',
    redirect: '/spatial-twin'
  },
  {
    path: '/spatial-twin',
    name: 'spatial-twin',
    component: () => import('../views/SpatialTwin.vue'),
    meta: { title: '全息建筑孪生', requiresAuth: true, menuIndex: '5' }
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/Dashboard.vue'),
    meta: { title: '能源态势总览', requiresAuth: true, menuIndex: '1' }
  },
  {
    path: '/energy',
    name: 'energy',
    component: () => import('../views/EnergyAnalysis.vue'),
    meta: { title: '能效诊断分析', requiresAuth: true, menuIndex: '2' }
  },
  {
    path: '/devices',
    name: 'devices',
    component: () => import('../views/DeviceMonitor.vue'),
    meta: { title: '能耗设备监测', requiresAuth: true, menuIndex: '3' }
  },
  {
    path: '/ai-agent',
    name: 'ai-agent',
    component: () => import('../views/AiAgent.vue'),
    meta: { title: 'AI 策略寻优', requiresAuth: true, menuIndex: '4' }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/AdminDashboard.vue'),
    meta: { title: '全局数据驾驶舱', requiresAuth: true, menuIndex: 'admin' }
  },
  {
    path: '/frontier',
    name: 'frontier',
    redirect: '/frontier/energy'
  },
  {
    path: '/frontier/energy',
    name: 'frontier-energy',
    component: () => import('../views/FrontierHub.vue'),
    props: { category: 'energy' },
    meta: { title: '能源智能分析', requiresAuth: true, menuIndex: '6-1' }
  },
  {
    path: '/frontier/ai',
    name: 'frontier-ai',
    component: () => import('../views/FrontierHub.vue'),
    props: { category: 'ai' },
    meta: { title: '智能体与知识', requiresAuth: true, menuIndex: '6-2' }
  },
  {
    path: '/frontier/ops',
    name: 'frontier-ops',
    component: () => import('../views/FrontierHub.vue'),
    props: { category: 'ops' },
    meta: { title: '数字孪生与运维', requiresAuth: true, menuIndex: '6-3' }
  },
  // ===== 进阶能力中心（9 大新功能）=====
  {
    path: '/advanced',
    name: 'advanced',
    redirect: '/advanced/diagnose'
  },
  {
    path: '/advanced/diagnose',
    name: 'advanced-diagnose',
    component: () => import('../views/AdvancedHub.vue'),
    props: { category: 'diagnose' },
    meta: { title: '能源诊断与优化', requiresAuth: true, menuIndex: '7-1' }
  },
  {
    path: '/advanced/ops',
    name: 'advanced-ops',
    component: () => import('../views/AdvancedHub.vue'),
    props: { category: 'ops' },
    meta: { title: '运营管理', requiresAuth: true, menuIndex: '7-2' }
  },
  {
    path: '/advanced/esg',
    name: 'advanced-esg',
    component: () => import('../views/AdvancedHub.vue'),
    props: { category: 'esg' },
    meta: { title: 'ESG 与投资决策', requiresAuth: true, menuIndex: '7-3' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫：JWT 鉴权 + 过期校验
/**
 * 解析 JWT payload，校验是否过期
 * @param {string} token JWT token
 * @returns {boolean} true=有效，false=过期或无效
 */
function isTokenValid(token) {
  if (!token) return false
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return false
    // 解码 payload（Base64Url，需补齐 padding）
    const payloadB64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = payloadB64 + '==='.slice((payloadB64.length + 3) % 4)
    const payload = JSON.parse(decodeURIComponent(escape(atob(padded))))
    // 校验 exp（Unix 时间戳，秒）
    if (payload.exp && Date.now() / 1000 > payload.exp) {
      return false
    }
    return true
  } catch (e) {
    return false
  }
}

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const valid = isTokenValid(token)

  if (to.meta.requiresAuth) {
    if (!token) {
      ElMessage.warning('请先登录')
      next({ name: 'login' })
    } else if (!valid) {
      // token 过期或无效，清除并跳转登录
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      ElMessage.warning('登录已过期，请重新登录')
      next({ name: 'login' })
    } else {
      next()
    }
  } else if (to.name === 'login' && valid) {
    // 已登录且 token 有效，访问登录页直接进主页
    next({ name: 'spatial-twin' })
  } else {
    next()
  }
})

// 路由后置：设置页面标题
router.afterEach((to) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - 擎翼数字中枢`
  }
})

export default router
